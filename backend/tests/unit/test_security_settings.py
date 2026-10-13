"""Durable writes, KYC encryption key handling and no hard-coded secrets."""
import re
from pathlib import Path

import pytest

import database
from security_middleware import FileEncryption

REPO = Path(__file__).resolve().parents[3]


def test_mongo_writes_are_majority_and_journaled():
    assert database.MONGO_OPTIONS["w"] == "majority"
    assert database.MONGO_OPTIONS["journal"] is True


def test_file_encryption_key_required_in_production(monkeypatch):
    monkeypatch.delenv("FILE_ENCRYPTION_KEY", raising=False)
    monkeypatch.setenv("APP_ENV", "prod")
    with pytest.raises(ValueError, match="FILE_ENCRYPTION_KEY"):
        FileEncryption()


def test_existing_key_still_decrypts_files_written_with_it(monkeypatch):
    monkeypatch.setenv("FILE_ENCRYPTION_KEY", "an-existing-deployment-key")
    writer = FileEncryption()
    encrypted = writer.encrypt_file(b"%PDF-1.4 kyc")
    reader = FileEncryption()
    ciphertext = encrypted[0] if isinstance(encrypted, tuple) else encrypted
    assert reader.decrypt_file(ciphertext) == b"%PDF-1.4 kyc"


def test_local_runs_without_key_still_start(monkeypatch):
    monkeypatch.delenv("FILE_ENCRYPTION_KEY", raising=False)
    monkeypatch.setenv("APP_ENV", "dev")
    assert FileEncryption().master_key


SECRET_PATTERNS = [
    re.compile(r"sk-emergent-[A-Za-z0-9]{6,}"),
    re.compile(r"rzp_live_[A-Za-z0-9]{6,}"),
    re.compile(r"sk_live_[A-Za-z0-9]{6,}"),
]


def test_no_live_secrets_in_backend_source():
    offenders = []
    for path in (REPO / "backend").rglob("*.py"):
        if "tests" in path.parts:
            continue
        text = path.read_text(errors="ignore")
        offenders += [f"{path.relative_to(REPO)}" for pattern in SECRET_PATTERNS if pattern.search(text)]
    assert offenders == []


def test_credentials_file_is_not_tracked():
    import subprocess
    tracked = subprocess.run(["git", "ls-files", "memory/test_credentials.md"], cwd=REPO, capture_output=True, text=True)
    assert tracked.stdout.strip() == ""
