"""Startup indexes go to the app's database (DB_NAME) and never change data or block writes."""
from db_optimization import INDEXES, create_indexes, needs_review, optimize_database


async def test_only_safe_indexes_are_created_and_data_is_untouched(mock_db):
    await mock_db.sessions.insert_one({"id": "s1", "user_id": "u1", "expires_at": "2020-01-01T00:00:00+00:00"})
    await mock_db.call_logs.insert_many([{"id": "c1"}, {"id": "c2"}])  # no call_sid on either

    created = await create_indexes(mock_db)

    safe = [(c, d["name"]) for c, defs in INDEXES.items() for d in defs if not needs_review(d)]
    assert created == len(safe)
    session_indexes = await mock_db.sessions.index_information()
    assert "user_idx" in session_indexes and "ttl_idx" not in session_indexes
    assert "call_sid_unique" not in await mock_db.call_logs.index_information()
    assert await mock_db.sessions.count_documents({}) == 1
    await mock_db.call_logs.insert_one({"id": "c3"})  # still accepted, as today


def test_review_rules():
    assert needs_review({"keys": [("expires_at", 1)], "expireAfterSeconds": 0, "name": "t"})
    assert needs_review({"keys": [("email", 1)], "unique": True, "name": "u"})
    assert needs_review({"keys": [("location", "2dsphere")], "name": "g"})
    assert needs_review({"keys": [("status", 1), ("created_at", -1)], "name": "c"}) == ""


async def test_optimize_uses_the_application_database(mock_db, monkeypatch):
    import database

    monkeypatch.setattr(database, "get_database", lambda: mock_db)
    result = await optimize_database()
    assert result["indexes_processed"] > 0
    assert "status_created_compound" in await mock_db.bookings.index_information()
