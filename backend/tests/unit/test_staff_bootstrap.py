"""Dev-only staff logins for an empty database (services/staff_bootstrap.py)."""
import pytest

from auth import verify_password
from services.staff_bootstrap import bootstrap_staff, parse_staff

PASSWORD = "a-long-dev-password"
SPEC = "CEO@airyatra.co.in:super_admin, hr@airyatra.co.in:hr"


def test_parse_staff_reads_email_role_pairs():
    assert parse_staff(SPEC) == [("ceo@airyatra.co.in", "super_admin"), ("hr@airyatra.co.in", "hr")]


@pytest.mark.parametrize("spec", ["ceo@airyatra.co.in", "ceo@airyatra.co.in:customer", "nobody:admin"])
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
