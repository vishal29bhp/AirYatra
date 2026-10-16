"""super_admin passes admin checks, old single-"role" records still count, and login codes never leave the server."""
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

import middleware
from auth import create_access_token
from middleware import effective_roles, get_current_user, has_any_role
from routes import document_master_routes, verification_routes


@pytest.mark.parametrize("user, expected", [
    ({"roles": ["super_admin"]}, ["super_admin", "admin"]),
    ({"roles": ["super_admin", "admin"]}, ["super_admin", "admin"]),
    ({"role": "admin"}, ["admin"]),
    ({"roles": ["employee"], "role": "sales_manager"}, ["employee", "sales_manager"]),
    ({"roles": ["finance"]}, ["finance"]),
    ({}, []),
])
def test_effective_roles(user, expected):
    assert effective_roles(user) == expected


def test_has_any_role_reads_the_roles_list_not_only_the_old_field():
    assert has_any_role({"roles": ["sales_manager"]}, "admin", "sales_manager")
    assert has_any_role({"roles": ["super_admin"]}, "admin")
    assert not has_any_role({"roles": ["customer"]}, "admin", "super_admin")


def admin_only_client(mock_db, monkeypatch):
    monkeypatch.setattr(middleware, "get_database", lambda: mock_db)
    app = FastAPI()

    # The same inline check shape used across the staff screens: only "admin" is named.
    @app.get("/admin-only")
    async def admin_only(user: dict = Depends(document_master_routes.require_roles(["admin"]))):
        return {"roles": user["roles"]}

    return TestClient(app)


@pytest.mark.parametrize("stored, expected", [
    ({"roles": ["super_admin"]}, 200),
    ({"role": "admin"}, 200),
    ({"roles": ["finance"]}, 403),
])
async def test_admin_checks_through_the_real_sign_in(mock_db, monkeypatch, stored, expected):
    await mock_db.users.insert_one({"id": "u1", "email": "x@airyatra.co.in", **stored})
    token = create_access_token({"sub": "u1"})

    response = admin_only_client(mock_db, monkeypatch).get("/admin-only", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == expected
    # Nothing is written back: the stored record keeps its own roles.
    assert {k: v for k, v in (await mock_db.users.find_one({"id": "u1"}, {"_id": 0})).items() if k in stored} == stored


async def test_send_otp_does_not_return_the_code(mock_db):
    app = FastAPI()
    app.include_router(verification_routes.router, prefix="/api")
    app.dependency_overrides[verification_routes.get_database] = lambda: mock_db

    response = TestClient(app).post("/api/verification/send-otp", json={"email": "c@example.com", "purpose": "registration"})

    assert response.status_code == 200
    assert "debug_otp" not in response.json()
    stored = await mock_db.otp_records.find_one({"email": "c@example.com"})
    assert stored["otp"] not in response.text
