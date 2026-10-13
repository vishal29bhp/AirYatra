#!/usr/bin/env python3
"""Read-only check that uploaded files were copied intact and KYC files still decrypt.

Today uploads live on local disk under ``/app/uploads`` and ``/app/secure_uploads``. Before cutover
they are copied to Blob storage (see docs/migration/CUTOVER_RUNBOOK.md). Download the copy to a
scratch folder, then compare it with the original::

    FILE_ENCRYPTION_KEY=... python3 tools/migration/verify_files.py \
        --source /app/secure_uploads --target ./blob-copy/secure-uploads --decrypt-check

Every file must exist on both sides with the same SHA-256. With ``--decrypt-check`` each ``.enc``
file on the target is decrypted in memory with the key from ``FILE_ENCRYPTION_KEY``, which proves
the key in Key Vault is the one the files were written with. File contents are never printed or saved.

Exit code 0 means every check passed, 1 means at least one problem.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence

BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_hashes(root: Path) -> Dict[str, str]:
    """Relative POSIX path to SHA-256 for every regular file under ``root``."""
    return {p.relative_to(root).as_posix(): sha256_of(p) for p in sorted(root.rglob("*")) if p.is_file()}


@dataclass
class FileVerificationReport:
    source: str
    target: str
    files_checked: int = 0
    missing_on_target: List[str] = field(default_factory=list)
    only_on_target: List[str] = field(default_factory=list)
    content_differs: List[str] = field(default_factory=list)
    decrypted: Optional[int] = None
    decrypt_failures: List[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not (self.missing_on_target or self.only_on_target or self.content_differs or self.decrypt_failures)

    def to_dict(self) -> dict:
        return {**asdict(self), "passed": self.passed}


class FileCopyVerifier:
    """Compares two folder trees and optionally decrypt-tests encrypted files. Never writes."""

    def __init__(self, source: Path, target: Path, decrypt: Optional[Callable[[bytes], bytes]] = None):
        self.source, self.target, self.decrypt = Path(source), Path(target), decrypt

    def run(self) -> FileVerificationReport:
        report = FileVerificationReport(source=str(self.source), target=str(self.target))
        source_files, target_files = file_hashes(self.source), file_hashes(self.target)
        report.files_checked = len(source_files)
        report.missing_on_target = sorted(set(source_files) - set(target_files))
        report.only_on_target = sorted(set(target_files) - set(source_files))
        report.content_differs = sorted(
            name for name in set(source_files) & set(target_files) if source_files[name] != target_files[name]
        )
        if self.decrypt is not None:
            report.decrypted = 0
            for name in sorted(n for n in target_files if n.endswith(".enc")):
                try:
                    self.decrypt((self.target / name).read_bytes())
                    report.decrypted += 1
                except Exception:  # any failure means the key or the file is wrong
                    report.decrypt_failures.append(name)
        return report


def _kyc_decryptor() -> Callable[[bytes], bytes]:
    if not os.environ.get("FILE_ENCRYPTION_KEY"):
        raise SystemExit("FILE_ENCRYPTION_KEY is not set")
    sys.path.insert(0, str(BACKEND_DIR))
    from security_middleware import FileEncryption

    return FileEncryption().decrypt_file


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--decrypt-check", action="store_true", help="decrypt every .enc file on the target")
    parser.add_argument("--json", help="write the JSON report here")
    args = parser.parse_args(argv)
    for folder in (args.source, args.target):
        if not folder.is_dir():
            parser.error(f"{folder} is not a folder")

    report = FileCopyVerifier(args.source, args.target, _kyc_decryptor() if args.decrypt_check else None).run()
    data = report.to_dict()
    if args.json:
        Path(args.json).write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in data.items()}, indent=2))
    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
