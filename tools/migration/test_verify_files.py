"""Tests for the file copy and KYC decrypt verifier."""
import pytest
from cryptography.fernet import Fernet

from verify_files import FileCopyVerifier, main

KEY = Fernet.generate_key()


@pytest.fixture
def trees(tmp_path):
    source, target = tmp_path / "source", tmp_path / "target"
    encrypted = Fernet(KEY).encrypt(b"%PDF-1.7 pan card")
    for root in (source, target):
        (root / "kyc").mkdir(parents=True)
        (root / "kyc" / "pan.pdf.enc").write_bytes(encrypted)
        (root / "village_documents").mkdir()
        (root / "village_documents" / "noc.jpg").write_bytes(b"\xff\xd8 image")
    return source, target


def test_identical_trees_pass(trees):
    report = FileCopyVerifier(*trees, decrypt=Fernet(KEY).decrypt).run()
    assert report.passed and report.files_checked == 2 and report.decrypted == 1


def test_missing_extra_and_changed_files_fail(trees):
    source, target = trees
    (target / "village_documents" / "noc.jpg").write_bytes(b"\xff\xd8 resized")
    (target / "kyc" / "pan.pdf.enc").unlink()
    (target / "stray.txt").write_text("x")
    report = FileCopyVerifier(source, target).run()
    assert report.content_differs == ["village_documents/noc.jpg"]
    assert report.missing_on_target == ["kyc/pan.pdf.enc"]
    assert report.only_on_target == ["stray.txt"]
    assert not report.passed


def test_wrong_encryption_key_fails_decrypt_check(trees):
    report = FileCopyVerifier(*trees, decrypt=Fernet(Fernet.generate_key()).decrypt).run()
    assert report.decrypt_failures == ["kyc/pan.pdf.enc"]
    assert not report.passed


def test_cli_decrypts_with_the_backend_file_encryption(trees, monkeypatch, capsys):
    source, target = trees
    monkeypatch.setenv("FILE_ENCRYPTION_KEY", KEY.decode())
    assert main(["--source", str(source), "--target", str(target), "--decrypt-check"]) == 0
    out = capsys.readouterr().out
    assert '"decrypted": 1' in out and "pan card" not in out


def test_cli_requires_key_for_decrypt_check(trees, monkeypatch):
    monkeypatch.delenv("FILE_ENCRYPTION_KEY", raising=False)
    with pytest.raises(SystemExit, match="FILE_ENCRYPTION_KEY is not set"):
        main(["--source", str(trees[0]), "--target", str(trees[1]), "--decrypt-check"])
