"""Finance can see the settlement list for its payout queue; approving and paying stay with admin."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from middleware import get_current_user
from routes import admin_settlement_routes


def make_client(mock_db, monkeypatch, roles):
    monkeypatch.setattr(admin_settlement_routes, "get_database", lambda: mock_db)
    app = FastAPI()
    app.include_router(admin_settlement_routes.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: {"id": "u1", "roles": roles}
    return TestClient(app)


@pytest.mark.parametrize("roles, expected", [
    (["finance"], 200),
    (["admin"], 200),
    (["super_admin"], 200),
    (["customer"], 403),
    (["operator"], 403),
])
async def test_who_can_list_settlements(mock_db, monkeypatch, roles, expected):
    await mock_db.settlements.insert_one({"id": "s1", "operator_id": "o1", "status": "pending", "payout_amount": 900})

    response = make_client(mock_db, monkeypatch, roles).get("/api/admin/settlements/")

    assert response.status_code == expected
    if expected == 200:
        assert response.json()["settlements"][0]["payout_amount"] == 900


async def test_finance_cannot_approve_a_settlement(mock_db, monkeypatch):
    await mock_db.settlements.insert_one({"id": "s1", "operator_id": "o1", "status": "pending"})

    response = make_client(mock_db, monkeypatch, ["finance"]).post("/api/admin/settlements/s1/approve", json={})

    assert response.status_code == 403
