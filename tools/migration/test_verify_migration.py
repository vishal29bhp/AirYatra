"""Tests for the migration verifier, using in-memory mongomock databases (no server needed)."""
import json
from datetime import datetime

import mongomock
import pytest

from verify_migration import DatabaseReader, MigrationVerifier, main

BOOKING = {"_id": "b1", "id": "b1", "status": "confirmed", "estimated_price": 125000.0,
           "created_at": "2026-01-05T10:00:00+00:00", "passengers": [{"name": "A"}]}


def _pair():
    client = mongomock.MongoClient()
    source, target = client["source"], client["target"]
    for db in (source, target):
        db.bookings.insert_many([dict(BOOKING), {**BOOKING, "_id": "b2", "id": "b2"}])
        db.bookings.create_index("id", unique=True, name="id_1")
        db.users.insert_one({"_id": "u1", "email": "a@example.com"})
    return source, target


def _verify(source, target, **kwargs):
    return MigrationVerifier(DatabaseReader(source), DatabaseReader(target), **kwargs).run()


def _result(report, name):
    return next(c for c in report.collections if c.name == name)


def test_identical_copy_passes():
    report = _verify(*_pair())
    assert report.passed
    assert _result(report, "bookings").content_check == "sha256 match"


@pytest.mark.parametrize("change", [
    {"estimated_price": 125000},                      # float -> int (type change, same number)
    {"created_at": datetime(2026, 1, 5, 10, 0)},      # ISO string -> BSON date
    {"status": "Confirmed"},                          # value change
])
def test_any_type_or_value_change_fails_full_hash(change):
    source, target = _pair()
    target.bookings.update_one({"_id": "b1"}, {"$set": change})
    report = _verify(source, target)
    assert not report.passed
    assert "content hash differs" in _result(report, "bookings").problems


def test_field_order_change_is_detected():
    source, target = _pair()
    source.users.insert_one({"_id": "u2", "email": "b@example.com", "name": "B"})
    target.users.insert_one({"_id": "u2", "name": "B", "email": "b@example.com"})
    assert not _verify(source, target).passed


def test_missing_document_fails_on_count():
    source, target = _pair()
    target.bookings.delete_one({"_id": "b2"})
    problems = _result(_verify(source, target), "bookings").problems
    assert "count differs (2 vs 1)" in problems


def test_missing_and_extra_collections_fail():
    source, target = _pair()
    source.payments.insert_one({"_id": "p1"})
    target.scratch.insert_one({"_id": "x"})
    report = _verify(source, target)
    assert _result(report, "payments").problems == ["missing on target"]
    assert _result(report, "scratch").problems == ["exists only on target"]


def test_missing_or_changed_index_fails_but_new_index_is_allowed():
    source, target = _pair()
    target.users.create_index("email", name="email_1")
    assert _verify(source, target).passed
    assert _result(_verify(source, target), "users").extra_target_indexes == ["email_1"]

    target.bookings.drop_index("id_1")
    target.bookings.create_index("id", name="id_1")  # same name, no longer unique
    assert _result(_verify(source, target), "bookings").changed_indexes == ["id_1"]

    target.bookings.drop_index("id_1")
    assert _result(_verify(source, target), "bookings").missing_indexes == ["id_1"]


def test_sample_mode_finds_a_changed_document():
    source, target = _pair()
    target.bookings.update_one({"_id": "b2"}, {"$set": {"estimated_price": 1.0}})
    result = _result(_verify(source, target, mode="sample", sample_size=10), "bookings")
    assert result.content_check == "1/2 sampled identical"
    assert not result.passed


def test_counts_mode_skips_content():
    source, target = _pair()
    target.bookings.update_one({"_id": "b2"}, {"$set": {"status": "x"}})
    report = _verify(source, target, mode="counts")
    assert report.passed and _result(report, "bookings").content_check == "skipped"


def test_only_and_exclude_filter_collections():
    source, target = _pair()
    assert [c.name for c in _verify(source, target, only=["users"]).collections] == ["users"]
    assert [c.name for c in _verify(source, target, exclude=["users"]).collections] == ["bookings"]
    assert not _verify(source, target, only=["nope"]).passed


def test_verifier_never_writes():
    source, target = _pair()
    before = {db.name: {c: list(db[c].find()) for c in db.list_collection_names()} for db in (source, target)}
    for mode in MigrationVerifier.MODES:
        _verify(source, target, mode=mode)
    after = {db.name: {c: list(db[c].find()) for c in db.list_collection_names()} for db in (source, target)}
    assert before == after


def test_reports_render():
    source, target = _pair()
    target.bookings.delete_one({"_id": "b2"})
    report = _verify(source, target)
    markdown = report.to_markdown()
    assert "Result: **FAIL**" in markdown and "| bookings | 2 | 1 |" in markdown
    data = json.loads(json.dumps(report.to_dict(), default=str))
    assert data["passed"] is False and data["collections"][0]["passed"] is False


def test_invalid_mode_rejected():
    source, target = _pair()
    with pytest.raises(ValueError):
        MigrationVerifier(DatabaseReader(source), DatabaseReader(target), mode="fast")


def test_cli_requires_connection_strings_from_environment(monkeypatch):
    monkeypatch.delenv("SOURCE_MONGO_URL", raising=False)
    with pytest.raises(SystemExit, match="SOURCE_MONGO_URL is not set"):
        main(["--source-db", "a", "--target-db", "b"])


def test_raw_bson_documents_are_hashed_from_stored_bytes():
    """The CLI reads RawBSONDocument from a live server, so it hashes exactly what is stored."""
    import bson
    from bson.raw_bson import RawBSONDocument

    from verify_migration import _raw_bytes

    stored = bson.encode({"_id": "b1", "estimated_price": 125000.0})
    assert _raw_bytes(RawBSONDocument(stored)) == stored
    assert _raw_bytes({"_id": "b1", "estimated_price": 125000}) != stored
