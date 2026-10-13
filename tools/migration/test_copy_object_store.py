"""Tests for the Emergent object store to Blob copier, with in-memory stores."""
import asyncio

import mongomock
import pytest

from copy_object_store import ObjectStoreCopier, main, referenced_keys


class MemoryStore:
    def __init__(self, objects=None, broken=()):
        self.objects = dict(objects or {})
        self.broken = set(broken)
        self.puts = []

    async def get(self, key):
        if key in self.broken:
            raise ConnectionError("upstream 500")
        if key not in self.objects:
            raise FileNotFoundError(key)
        return self.objects[key]

    async def put(self, key, data, content_type=None):
        self.puts.append(key)
        self.objects[key] = (data, content_type)
        return key


def _run(copier, keys):
    return asyncio.run(copier.run(keys))


def test_referenced_keys_cover_all_object_fields():
    db = mongomock.MongoClient()["airyatra"]
    db.documents_vault.insert_many([
        {"storage_path": "airyatra/vault/u1/f1/a.pdf", "thumb_storage_path": "airyatra/vault/u1/f1/thumb_a.png"},
        {"storage_path": None, "storage_type": "mongodb_base64"},
    ])
    db.document_files.insert_one({"storage_path": "airyatra/vault/u1/x.pdf"})
    db.exchange_images.insert_many([{"storage_path": "airyatra/exchange/exi-1.jpg"},
                                    {"storage_path": "airyatra/exchange/exi-1.jpg"}])
    assert referenced_keys(db) == [
        "airyatra/exchange/exi-1.jpg", "airyatra/vault/u1/f1/a.pdf",
        "airyatra/vault/u1/f1/thumb_a.png", "airyatra/vault/u1/x.pdf",
    ]


def test_copies_under_the_same_key_and_verifies():
    source = MemoryStore({"k/a.pdf": (b"pdf", "application/pdf"), "k/b.jpg": (b"jpg", "image/jpeg")})
    target = MemoryStore()
    report = _run(ObjectStoreCopier(source, target), ["k/a.pdf", "k/b.jpg"])
    assert report.passed and report.copied == ["k/a.pdf", "k/b.jpg"]
    assert target.objects == source.objects


def test_rerun_skips_objects_already_copied():
    source = MemoryStore({"k/a.pdf": (b"pdf", "application/pdf")})
    target = MemoryStore({"k/a.pdf": (b"pdf", "application/pdf")})
    report = _run(ObjectStoreCopier(source, target), ["k/a.pdf"])
    assert report.already_present == ["k/a.pdf"] and target.puts == []


def test_different_target_content_is_overwritten_from_source():
    source = MemoryStore({"k/a.pdf": (b"new", "application/pdf")})
    target = MemoryStore({"k/a.pdf": (b"stale", "application/pdf")})
    report = _run(ObjectStoreCopier(source, target), ["k/a.pdf"])
    assert report.copied == ["k/a.pdf"] and target.objects["k/a.pdf"][0] == b"new"


def test_missing_and_failing_source_objects_fail_the_run():
    source = MemoryStore({"ok": (b"1", None)}, broken={"flaky"})
    report = _run(ObjectStoreCopier(source, MemoryStore()), ["ok", "gone", "flaky"])
    assert report.missing_in_source == ["gone"] and report.failed == ["flaky"]
    assert not report.passed


def test_write_that_does_not_read_back_identically_fails():
    class CorruptingStore(MemoryStore):
        async def put(self, key, data, content_type=None):
            return await super().put(key, data[:-1], content_type)

    report = _run(ObjectStoreCopier(MemoryStore({"k": (b"abc", None)}), CorruptingStore()), ["k"])
    assert report.failed == ["k"]


def test_dry_run_writes_nothing():
    target = MemoryStore()
    report = _run(ObjectStoreCopier(MemoryStore({"k": (b"abc", None)}), target, dry_run=True), ["k"])
    assert report.copied == ["k"] and target.puts == []


def test_cli_requires_environment(monkeypatch):
    for name in ("SOURCE_MONGO_URL", "AZURE_STORAGE_ACCOUNT_URL", "EMERGENT_LLM_KEY"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(SystemExit, match="SOURCE_MONGO_URL is not set"):
        main(["--db", "airyatra"])
