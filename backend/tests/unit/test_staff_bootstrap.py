"""Dev-only staff logins for an empty database (services/staff_bootstrap.py)."""
import pytest

from auth import verify_password
from services.staff_bootstrap import bootstrap_staff, parse_staff

PASSWORD = "a-long-dev-password"
SPEC = "CEO@airyatra.co.in:super_admin, hr@airyatra.co.in:hr"


def test_parse_staff_reads_email_role_pairs():
    assert parse_staff(SPEC) == [("ceo@airyatra.co.in", ["super_admin"]), ("hr@airyatra.co.in", ["hr"])]


def test_parse_staff_reads_several_roles():
    assert parse_staff("ceo@airyatra.co.in:super_admin+admin") == [("ceo@airyatra.co.in", ["super_admin", "admin"])]


@pytest.mark.parametrize("spec", ["ceo@airyatra.co.in", "ceo@airyatra.co.in:customer", "nobody:admin",
                                  "ceo@airyatra.co.in:admin+customer", "ceo@airyatra.co.in:"])
def test_parse_staff_rejects_bad_entries(spec):
    with pytest.raises(ValueError):
        parse_staff(spec)


async def test_creates_missing_accounts_that_can_sign_in(mock_db):
    created = await bootstrap_staff(mock_db, SPEC, PASSWORD, "dev")

    assert created == ["ceo@airyatra.co.in", "hr@airyatra.co.in"]
    user = await mock_db.users.find_one({"email": "ceo@airyatra.co.in"})
    assert user["roles"] == ["super_admin"] and user["is_active"] is True
    assert verify_password(PASSWORD, user["password_hash"])


async def test_never_changes_an_existing_user(mock_db):
    await mock_db.users.insert_one({"id": "u1", "email": "hr@airyatra.co.in", "password_hash": "keep", "roles": ["hr"]})

    created = await bootstrap_staff(mock_db, SPEC, PASSWORD, "dev")

    assert created == ["ceo@airyatra.co.in"]
    existing = await mock_db.users.find_one({"email": "hr@airyatra.co.in"})
    assert existing["password_hash"] == "keep"
    assert await mock_db.users.count_documents({}) == 2


async def test_creates_an_operator_with_several_roles_in_order(mock_db):
    await bootstrap_staff(mock_db, "op@airyatra.co.in:operator, ceo@airyatra.co.in:super_admin+admin", PASSWORD, "dev")

    assert (await mock_db.users.find_one({"email": "op@airyatra.co.in"}))["roles"] == ["operator"]
    ceo = await mock_db.users.find_one({"email": "ceo@airyatra.co.in"})
    assert ceo["roles"] == ["super_admin", "admin"] and ceo["role"] == "super_admin"


async def test_updates_roles_of_its_own_accounts_only(mock_db):
    await bootstrap_staff(mock_db, "ceo@airyatra.co.in:super_admin", PASSWORD, "dev")
    await mock_db.users.insert_one({"id": "u1", "email": "hr@airyatra.co.in", "password_hash": "keep", "roles": ["customer"]})

    created = await bootstrap_staff(mock_db, "ceo@airyatra.co.in:super_admin+admin, hr@airyatra.co.in:hr", PASSWORD, "dev")

    assert created == []
    assert (await mock_db.users.find_one({"email": "ceo@airyatra.co.in"}))["roles"] == ["super_admin", "admin"]
    assert (await mock_db.users.find_one({"email": "hr@airyatra.co.in"}))["roles"] == ["customer"]


async def test_second_run_creates_nothing(mock_db):
    await bootstrap_staff(mock_db, SPEC, PASSWORD, "dev")
    assert await bootstrap_staff(mock_db, SPEC, PASSWORD, "dev") == []


@pytest.mark.parametrize("password", ["", "set-me", "short"])
async def test_does_nothing_without_a_real_password(mock_db, password):
    assert await bootstrap_staff(mock_db, SPEC, password, "dev") == []
    assert await mock_db.users.count_documents({}) == 0


@pytest.mark.parametrize("app_env", ["prod", "production", "staging"])
async def test_does_nothing_in_production(mock_db, app_env):
    assert await bootstrap_staff(mock_db, SPEC, PASSWORD, app_env) == []
    assert await mock_db.users.count_documents({}) == 0
