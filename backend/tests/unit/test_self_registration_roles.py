"""Self sign-up: customers and operators only; an operator waits for admin approval before inquiries."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import auth_routes
from security_middleware import limiter


@pytest.fixture
def client(mock_db, monkeypatch):
    monkeypatch.setattr(auth_routes, "get_database", lambda: mock_db)
    monkeypatch.setattr(limiter, "enabled", False)
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(auth_routes.router, prefix="/api")
    return TestClient(app)


def register(client, email, roles=None):
    body = {"email": email, "password": "Str0ng!Passw0rd", "full_name": "Test", "phone": "9999999999"}
    if roles is not None:
        body["roles"] = roles
    return client.post("/api/auth/register", json=body)


@pytest.mark.parametrize("roles, expected", [
    (None, ["customer"]),
    (["customer"], ["customer"]),
    (["operator"], ["operator"]),
    (["admin"], ["customer"]),
    (["super_admin", "operator"], ["operator"]),
    (["finance"], ["customer"]),
])
async def test_sign_up_gives_only_customer_or_operator(client, mock_db, roles, expected):
    response = register(client, f"u{len(roles or [])}{expected[0]}@example.com", roles)

    assert response.status_code == 200, response.text
    assert response.json()["user"]["roles"] == expected
    saved = await mock_db.users.find_one({"email": response.json()["user"]["email"]})
    assert saved["roles"] == expected


async def test_operator_sign_up_gets_no_customer_welcome_bonus(client, mock_db):
    response = register(client, "op@example.com", ["operator"])

    user_id = response.json()["user"]["id"]
    assert await mock_db.loyalty_profiles.find_one({"user_id": user_id}) is None
