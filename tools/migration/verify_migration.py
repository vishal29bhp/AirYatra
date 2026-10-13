#!/usr/bin/env python3
"""Read-only verification that a migrated MongoDB copy is identical to its source.

Phase 2 of the refurbishment moves the AirYatra database to Atlas with zero data change.
This tool proves it, collection by collection:

* the same collections exist on both sides (``system.*`` ignored);
* document counts match;
* a SHA-256 over every document's BSON bytes, read in ``_id`` order, matches (``--mode full``),
  or N randomly sampled documents are byte-identical (``--mode sample``);
* every source index exists on the target with the same keys and options.
  Extra target indexes are reported but allowed (additive changes are permitted).

It only reads. Connection strings come from the environment so passwords stay out of the
process list and shell history::

    export SOURCE_MONGO_URL='mongodb://...'  TARGET_MONGO_URL='mongodb+srv://...'
    python3 tools/migration/verify_migration.py --source-db airyatra --target-db airyatra \
        --mode full --json report.json --markdown report.md

Exit code 0 means every check passed, 1 means at least one mismatch, 2 means a usage error.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence

import bson

# Index options that describe behaviour. Server bookkeeping such as ``v`` and ``ns`` is ignored.
_INDEX_OPTIONS = (
    "unique", "sparse", "expireAfterSeconds", "partialFilterExpression", "collation",
    "weights", "default_language", "language_override", "textIndexVersion", "2dsphereIndexVersion",
    "hidden", "wildcardProjection",
)


def _raw_bytes(document: Any) -> bytes:
    """BSON bytes exactly as stored. Raw documents are used as is; plain dicts are encoded in key order."""
    raw = getattr(document, "raw", None)
    return bytes(raw) if raw is not None else bson.encode(document)


def _normalise_index(spec: Dict[str, Any]) -> Dict[str, Any]:
    key = spec.get("key", {})
    items = key.items() if hasattr(key, "items") else key
    normalised = {"key": [[name, direction] for name, direction in items]}
    for option in _INDEX_OPTIONS:
        if option in spec:
            normalised[option] = spec[option]
    return normalised


class DatabaseReader:
    """Read-only view of one database. Never issues a write."""

    def __init__(self, database: Any):
        self._db = database

    @property
    def name(self) -> str:
        return self._db.name

    def collection_names(self) -> List[str]:
        return sorted(n for n in self._db.list_collection_names() if not n.startswith("system."))

    def count(self, collection: str) -> int:
        return self._db[collection].count_documents({})

    def fingerprint(self, collection: str) -> str:
        digest = hashlib.sha256()
        for document in self._db[collection].find({}, sort=[("_id", 1)]):
            raw = _raw_bytes(document)
            digest.update(len(raw).to_bytes(8, "big"))
            digest.update(raw)
        return digest.hexdigest()

    def sample_ids(self, collection: str, size: int) -> List[Any]:
        pipeline = [{"$sample": {"size": size}}, {"$project": {"_id": 1}}]
        return [doc["_id"] for doc in self._db[collection].aggregate(pipeline)]

    def documents_by_id(self, collection: str, ids: Sequence[Any]) -> Dict[bytes, bytes]:
        """Map of encoded ``_id`` to raw document bytes."""
        found = {}
        for document in self._db[collection].find({"_id": {"$in": list(ids)}}):
            found[bson.encode({"_id": document["_id"]})] = _raw_bytes(document)
        return found

    def indexes(self, collection: str) -> Dict[str, Dict[str, Any]]:
        return {spec["name"]: _normalise_index(dict(spec)) for spec in self._db[collection].list_indexes()}


@dataclass
class CollectionResult:
    name: str
    source_count: Optional[int] = None
    target_count: Optional[int] = None
    content_check: str = "not run"
    missing_indexes: List[str] = field(default_factory=list)
    changed_indexes: List[str] = field(default_factory=list)
    extra_target_indexes: List[str] = field(default_factory=list)
    problems: List[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.problems


@dataclass
class VerificationReport:
    source_db: str
    target_db: str
    mode: str
    started_at: str
    collections: List[CollectionResult] = field(default_factory=list)
    problems: List[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.problems and all(c.passed for c in self.collections)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["passed"] = self.passed
        for entry, result in zip(data["collections"], self.collections):
            entry["passed"] = result.passed
        return data

    def to_markdown(self) -> str:
        failed = [c for c in self.collections if not c.passed]
        lines = [
            "# Migration verification report",
            "",
            f"- Result: **{'PASS' if self.passed else 'FAIL'}**",
            f"- Source DB: `{self.source_db}`, target DB: `{self.target_db}`, mode: `{self.mode}`",
            f"- Started: {self.started_at}",
            f"- Collections checked: {len(self.collections)}, failed: {len(failed)}",
            "",
        ]
        if self.problems:
            lines += ["## Database-level problems", ""] + [f"- {p}" for p in self.problems] + [""]
        lines += [
            "| Collection | Source docs | Target docs | Content | Indexes | Result |",
            "|---|---:|---:|---|---|---|",
        ]
        for c in self.collections:
            index_note = "match"
            if c.missing_indexes or c.changed_indexes:
                index_note = f"missing {len(c.missing_indexes)}, changed {len(c.changed_indexes)}"
            if c.extra_target_indexes:
                index_note += f", +{len(c.extra_target_indexes)} new"
            lines.append(
                f"| {c.name} | {c.source_count} | {c.target_count} | {c.content_check} | {index_note} | "
                f"{'PASS' if c.passed else 'FAIL'} |"
            )
        if failed:
            lines += ["", "## Failures", ""]
            for c in failed:
                lines += [f"- **{c.name}**: " + "; ".join(c.problems)]
        return "\n".join(lines) + "\n"


class MigrationVerifier:
    """Compares a source and a target database without writing to either."""

    MODES = ("full", "sample", "counts")

    def __init__(self, source: DatabaseReader, target: DatabaseReader, mode: str = "full",
                 sample_size: int = 1000, only: Optional[Iterable[str]] = None,
                 exclude: Optional[Iterable[str]] = None):
        if mode not in self.MODES:
            raise ValueError(f"mode must be one of {self.MODES}")
        self.source, self.target = source, target
        self.mode, self.sample_size = mode, sample_size
        self.only = set(only or [])
        self.exclude = set(exclude or [])

    def run(self) -> VerificationReport:
        report = VerificationReport(
            source_db=self.source.name, target_db=self.target.name, mode=self.mode,
            started_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
        source_names, target_names = set(self.source.collection_names()), set(self.target.collection_names())
        selected = (self.only or source_names | target_names) - self.exclude
        for name in sorted(selected):
            report.collections.append(self._check_collection(name, name in source_names, name in target_names))
        unknown = self.only - source_names - target_names
        if unknown:
            report.problems.append("requested collections not found: " + ", ".join(sorted(unknown)))
        return report

    def _check_collection(self, name: str, in_source: bool, in_target: bool) -> CollectionResult:
        result = CollectionResult(name=name)
        if not in_source or not in_target:
            result.problems.append("missing on target" if in_source else "exists only on target")
            return result
        result.source_count, result.target_count = self.source.count(name), self.target.count(name)
        if result.source_count != result.target_count:
            result.problems.append(f"count differs ({result.source_count} vs {result.target_count})")
        self._check_content(name, result)
        self._check_indexes(name, result)
        return result

    def _check_content(self, name: str, result: CollectionResult) -> None:
        if self.mode == "counts":
            result.content_check = "skipped"
        elif self.mode == "full":
            same = self.source.fingerprint(name) == self.target.fingerprint(name)
            result.content_check = "sha256 match" if same else "sha256 differs"
            if not same:
                result.problems.append("content hash differs")
        else:
            ids = self.source.sample_ids(name, self.sample_size)
            source_docs = self.source.documents_by_id(name, ids)
            target_docs = self.target.documents_by_id(name, ids)
            mismatched = sum(1 for key, raw in source_docs.items() if target_docs.get(key) != raw)
            result.content_check = f"{len(source_docs) - mismatched}/{len(source_docs)} sampled identical"
            if mismatched:
                result.problems.append(f"{mismatched} sampled documents differ or are missing")

    def _check_indexes(self, name: str, result: CollectionResult) -> None:
        source_ix, target_ix = self.source.indexes(name), self.target.indexes(name)
        result.missing_indexes = sorted(set(source_ix) - set(target_ix))
        result.changed_indexes = sorted(n for n in set(source_ix) & set(target_ix) if source_ix[n] != target_ix[n])
        result.extra_target_indexes = sorted(set(target_ix) - set(source_ix))
        if result.missing_indexes:
            result.problems.append("indexes missing on target: " + ", ".join(result.missing_indexes))
        if result.changed_indexes:
            result.problems.append("indexes differ: " + ", ".join(result.changed_indexes))


def _connect(env_var: str, db_name: str) -> DatabaseReader:
    from bson.raw_bson import RawBSONDocument
    from pymongo import MongoClient

    url = os.environ.get(env_var)
    if not url:
        raise SystemExit(f"{env_var} is not set")
    client = MongoClient(url, document_class=RawBSONDocument, readPreference="secondaryPreferred",
                         appname="airyatra-migration-verify")
    return DatabaseReader(client[db_name])


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--source-db", required=True)
    parser.add_argument("--target-db", required=True)
    parser.add_argument("--mode", choices=MigrationVerifier.MODES, default="full")
    parser.add_argument("--sample-size", type=int, default=1000)
    parser.add_argument("--collection", action="append", default=[], help="check only these (repeatable)")
    parser.add_argument("--exclude", action="append", default=[], help="skip these (repeatable)")
    parser.add_argument("--json", help="write the JSON report here")
    parser.add_argument("--markdown", help="write the Markdown report here")
    args = parser.parse_args(argv)

    verifier = MigrationVerifier(
        _connect("SOURCE_MONGO_URL", args.source_db), _connect("TARGET_MONGO_URL", args.target_db),
        mode=args.mode, sample_size=args.sample_size, only=args.collection, exclude=args.exclude,
    )
    report = verifier.run()
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(report.to_dict(), fh, indent=2, default=str)
    markdown = report.to_markdown()
    if args.markdown:
        with open(args.markdown, "w", encoding="utf-8") as fh:
            fh.write(markdown)
    print(markdown)
    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
