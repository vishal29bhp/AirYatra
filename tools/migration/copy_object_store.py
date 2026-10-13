#!/usr/bin/env python3
"""Copy document-vault and exchange-image objects from the Emergent object store to Azure Blob.

Every object key referenced in MongoDB is copied under the **same key** into the ``documents``
container, so the ``storage_path`` values in the database stay unchanged. Each copy is read back and
compared by SHA-256. Re-running is safe: objects already in Blob with the same hash are skipped.

    export SOURCE_MONGO_URL='mongodb://...'                 # read-only; only storage paths are read
    export EMERGENT_LLM_KEY='...'                           # unlocks the Emergent object store
    export AZURE_STORAGE_ACCOUNT_URL='https://<account>.blob.core.windows.net/'
    az login                                                # or the migration host's managed identity
    python3 tools/migration/copy_object_store.py --db airyatra --json objects-report.json

Exit code 0 means every referenced object is in Blob and verified, 1 means at least one problem.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, List, Optional, Sequence, Set

BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"

# Collections and fields that hold Emergent object-store keys (see docs/migration/CUTOVER_RUNBOOK.md).
OBJECT_KEY_FIELDS = {
    "documents_vault": ("storage_path", "thumb_storage_path"),
    "document_files": ("storage_path",),
    "exchange_images": ("storage_path",),
}


def referenced_keys(database: Any) -> List[str]:
    """Every distinct non-empty object key referenced by the database, sorted."""
    keys: Set[str] = set()
    for collection, fields in OBJECT_KEY_FIELDS.items():
        projection = {name: 1 for name in fields}
        for document in database[collection].find({}, projection):
            keys.update(document[name] for name in fields if isinstance(document.get(name), str) and document[name])
    return sorted(keys)


@dataclass
class CopyReport:
    referenced: int = 0
    copied: List[str] = field(default_factory=list)
    already_present: List[str] = field(default_factory=list)
    missing_in_source: List[str] = field(default_factory=list)
    failed: List[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not (self.missing_in_source or self.failed)

    def summary(self) -> dict:
        data = {k: (len(v) if isinstance(v, list) else v) for k, v in asdict(self).items()}
        return {**data, "passed": self.passed}


class ObjectStoreCopier:
    """Copies keys from one FileStore to another and verifies each by SHA-256. Never deletes."""

    def __init__(self, source, target, concurrency: int = 8, dry_run: bool = False):
        self.source, self.target = source, target
        self.dry_run = dry_run
        self._limit = asyncio.Semaphore(concurrency)

    async def run(self, keys: Iterable[str]) -> CopyReport:
        keys = list(keys)
        report = CopyReport(referenced=len(keys))
        await asyncio.gather(*(self._copy_one(key, report) for key in keys))
        for name in ("copied", "already_present", "missing_in_source", "failed"):
            getattr(report, name).sort()
        return report

    async def _copy_one(self, key: str, report: CopyReport) -> None:
        async with self._limit:
            try:
                data, content_type = await self.source.get(key)
            except FileNotFoundError:
                report.missing_in_source.append(key)
                return
            except Exception:
                report.failed.append(key)
                return
            digest = hashlib.sha256(data).hexdigest()
            try:
                if await self._target_matches(key, digest):
                    report.already_present.append(key)
                    return
                if self.dry_run:
                    report.copied.append(key)
                    return
                await self.target.put(key, data, content_type)
                if await self._target_matches(key, digest):
                    report.copied.append(key)
                else:
                    report.failed.append(key)
            except Exception:
                report.failed.append(key)

    async def _target_matches(self, key: str, digest: str) -> bool:
        try:
            data, _ = await self.target.get(key)
        except FileNotFoundError:
            return False
        return hashlib.sha256(data).hexdigest() == digest


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"{name} is not set")
    return value


async def _main(args) -> int:
    from pymongo import MongoClient

    source_url, account_url = _require("SOURCE_MONGO_URL"), _require("AZURE_STORAGE_ACCOUNT_URL")
    _require("EMERGENT_LLM_KEY")
    sys.path.insert(0, str(BACKEND_DIR))
    from services.file_storage import BLOB_CONTAINERS, AzureBlobFileStore, EmergentObjectStore

    keys = referenced_keys(MongoClient(source_url, readPreference="secondaryPreferred")[args.db])
    target = AzureBlobFileStore(account_url, BLOB_CONTAINERS["objects"])
    report = await ObjectStoreCopier(EmergentObjectStore(), target, args.concurrency, args.dry_run).run(keys)
    if args.json:
        Path(args.json).write_text(json.dumps({**asdict(report), "passed": report.passed}, indent=2), encoding="utf-8")
    print(json.dumps(report.summary(), indent=2))
    return 0 if report.passed else 1


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--db", required=True, help="source database name (DB_NAME)")
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--dry-run", action="store_true", help="read and compare only, write nothing")
    parser.add_argument("--json", help="write the full report (every key) here")
    return asyncio.run(_main(parser.parse_args(argv)))


if __name__ == "__main__":
    sys.exit(main())
