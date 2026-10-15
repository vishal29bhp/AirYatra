"""Demo data for client walkthroughs: dev only, seeded once, linked to the demo logins, fully removable."""
from datetime import datetime, timezone

from services import demo_seed
from services.demo_seed import build_demo_data, remove_demo_data, seed_demo_data

NOW = datetime(2026, 10, 15, 10, 0, tzinfo=timezone.utc)


def test_every_area_gets_about_25_records_with_demo_ids():
    data = build_demo_data(NOW, "hash")

    for collection in ("operators", "aircraft", "pilots", "inquiries", "settlements", "landing_permissions",
                       "payment_transactions", "vendor_bills", "approval_requests"):
        assert len(data[collection]) == 25, collection
    assert len(data["bookings"]) == 75
    assert all(d["id"].startswith("demo-") for docs in data.values() for d in docs)


def test_demo_customer_has_25_trips_and_first_operator_has_fleet_and_open_inquiries():
    data = build_demo_data(NOW, "hash")
    customer = data["users"][0]
    operator = data["operators"][0]

    assert customer["email"] == "customer@airyatra.co.in" and customer["password_hash"] == "hash"
    assert sum(b["customer_id"] == customer["id"] for b in data["bookings"]) == 25
    assert sum(a["operator_id"] == operator["id"] for a in data["aircraft"]) == 6
    assert sum(i["status"] == "pending" for i in data["inquiries"]) == 8
    assert operator["status"] == "active" and operator["verification_status"] == "approved"
    # Other demo logins cannot sign in.
    assert all(u["password_hash"].startswith("!") for u in data["users"][1:])


async def test_seed_links_existing_logins_and_runs_once(mock_db):
    await mock_db.users.insert_one({"id": "real-op", "email": "operator@airyatra.co.in", "roles": ["operator"]})
    await mock_db.users.insert_one({"id": "real-cust", "email": "customer@airyatra.co.in", "roles": ["customer"]})

    counts = await seed_demo_data(mock_db, "dev", "hash", now=NOW)

    assert counts["bookings"] == 75
    assert await mock_db.bookings.count_documents({"customer_id": "real-cust"}) == 25
    assert (await mock_db.operators.find_one({"id": "demo-operator-01"}))["user_id"] == "real-op"
    assert await mock_db.users.count_documents({"email": "customer@airyatra.co.in"}) == 1
    assert await seed_demo_data(mock_db, "dev", "hash", now=NOW) == {}
    assert await mock_db.bookings.count_documents({}) == 75


async def test_seed_adds_to_an_operator_profile_that_already_exists(mock_db):
    await mock_db.users.insert_one({"id": "real-op", "email": "operator@airyatra.co.in", "roles": ["operator"]})
    await mock_db.operators.insert_one({"id": "real-operator", "user_id": "real-op", "company_name": "Mine"})

    await seed_demo_data(mock_db, "dev", "hash", now=NOW)

    assert await mock_db.aircraft.count_documents({"operator_id": "real-operator"}) == 6
    assert (await mock_db.operators.find_one({"id": "real-operator"}))["company_name"] == "Mine"
    assert await mock_db.operators.find_one({"id": "demo-operator-01"}) is None


async def test_never_seeds_in_production(mock_db):
    assert await seed_demo_data(mock_db, "prod", "hash", now=NOW) == {}
    assert await mock_db.bookings.count_documents({}) == 0


async def test_remove_takes_out_only_demo_records(mock_db):
    await mock_db.users.insert_one({"id": "real-cust", "email": "customer@airyatra.co.in", "roles": ["customer"]})
    await mock_db.bookings.insert_one({"id": "real-booking", "customer_id": "real-cust"})
    await seed_demo_data(mock_db, "dev", "hash", now=NOW)

    removed = await remove_demo_data(mock_db)

    assert removed["bookings"] == 75
    assert [b["id"] async for b in mock_db.bookings.find({}, {"_id": 0, "id": 1})] == ["real-booking"]
    assert await mock_db.users.find_one({"id": "real-cust"}) is not None
    for collection in demo_seed.COLLECTIONS:
        assert await mock_db[collection].count_documents({"id": {"$regex": "^demo-"}}) == 0


async def test_mode_off_does_nothing(mock_db):
    assert await demo_seed.run_from_env(mock_db, "dev", "off", "") == {}
    assert await mock_db.bookings.count_documents({}) == 0
