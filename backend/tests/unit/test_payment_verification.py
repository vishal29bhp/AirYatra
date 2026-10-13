"""Regression tests for payment verification (Phase 0 audit: payments marked paid without a real payment)."""
import hashlib
import hmac

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from database import get_database
from middleware import get_current_user
from routes import payment_routes
from services.payment_service import PaymentService, payment_service

SECRET = "rzp_test_secret_value"
CUSTOMER = {"id": "cust-1", "email": "c@example.com", "roles": ["customer"]}


def sign(order_id: str, payment_id: str, secret: str = SECRET) -> str:
    return hmac.new(secret.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()


# ---------------- PaymentService.verify_payment ----------------

@pytest.fixture
def service_with_secret():
    service = PaymentService()
    service.key_secret = SECRET
    service.client = None
    return service


async def test_valid_signature_is_verified_without_sdk_client(service_with_secret):
    result = await service_with_secret.verify_payment("order_1", "pay_1", sign("order_1", "pay_1"))
    assert result["verified"] is True
    assert result["mock"] is False


async def test_invalid_signature_is_rejected(service_with_secret):
    result = await service_with_secret.verify_payment("order_1", "pay_1", sign("order_1", "pay_1", "wrong"))
    assert result["verified"] is False


async def test_missing_signature_is_rejected(service_with_secret):
    result = await service_with_secret.verify_payment("order_1", "pay_1", None)
    assert result["verified"] is False


async def test_unconfigured_gateway_is_a_failure_not_a_mock_success():
    service = PaymentService()
    service.key_secret = ""
    result = await service.verify_payment("order_1", "pay_1", "anything")
    assert result["verified"] is False
    assert result["success"] is False


async def test_mock_success_only_when_explicitly_allowed():
    service = PaymentService()
    service.key_secret = ""
    result = await service.verify_payment("order_1", "pay_1", "anything", allow_mock=True)
    assert result["verified"] is True
    assert result["mock"] is True


async def test_keys_configured_in_admin_settings_are_used(mock_db):
    await mock_db.api_keys_settings.insert_one(
        {"type": "api_keys", "razorpay_key_id": "short", "razorpay_key_secret": SECRET}
    )
    service = PaymentService()
    service.key_secret = ""
    result = await service.verify_payment("order_2", "pay_2", sign("order_2", "pay_2"), db=mock_db)
    assert result["verified"] is True


# ---------------- POST /api/payments/verify ----------------

@pytest.fixture
def client(mock_db, monkeypatch):
    monkeypatch.setattr(payment_service, "key_secret", SECRET)
    monkeypatch.setattr(payment_service, "client", None)
    monkeypatch.setattr(payment_service, "_db_settings_loaded", True)

    async def no_email(**kwargs):
        return None

    monkeypatch.setattr(payment_routes.notification_service, "send_booking_confirmation", no_email)
    app = FastAPI()
    app.include_router(payment_routes.router, prefix="/api")
    app.dependency_overrides[get_database] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: CUSTOMER
    return TestClient(app)


async def _seed(mock_db, customer_id="cust-1", mock=False):
    await mock_db.bookings.insert_one({"id": "bk-1", "customer_id": customer_id, "status": "pending_payment"})
    await mock_db.payment_orders.insert_one(
        {"id": "po-1", "order_id": "order_9", "booking_id": "bk-1", "customer_id": customer_id,
         "is_inquiry": False, "status": "created", "mock": mock}
    )


def _verify(client, signature, booking_id="bk-1", order_id="order_9"):
    return client.post("/api/payments/verify", json={
        "razorpay_order_id": order_id,
        "razorpay_payment_id": "pay_9",
        "razorpay_signature": signature,
        "booking_id": booking_id,
    })


async def test_valid_payment_marks_booking_paid(client, mock_db):
    await _seed(mock_db)
    response = _verify(client, sign("order_9", "pay_9"))
    assert response.status_code == 200
    assert response.json()["verified"] is True
    booking = await mock_db.bookings.find_one({"id": "bk-1"})
    assert booking["payment_status"] == "paid"


async def test_forged_signature_leaves_booking_unpaid(client, mock_db):
    await _seed(mock_db)
    response = _verify(client, "0" * 64)
    assert response.json()["verified"] is False
    booking = await mock_db.bookings.find_one({"id": "bk-1"})
    assert "payment_status" not in booking


async def test_cannot_verify_someone_elses_order(client, mock_db):
    await _seed(mock_db, customer_id="someone-else")
    response = _verify(client, sign("order_9", "pay_9"))
    assert response.status_code == 403


async def test_cannot_use_a_paid_order_to_mark_a_different_booking_paid(client, mock_db):
    await _seed(mock_db)
    await mock_db.bookings.insert_one({"id": "bk-expensive", "customer_id": "cust-1"})
    response = _verify(client, sign("order_9", "pay_9"), booking_id="bk-expensive")
    assert response.status_code == 400
    assert "payment_status" not in await mock_db.bookings.find_one({"id": "bk-expensive"})


async def test_unknown_order_is_404(client, mock_db):
    response = _verify(client, sign("nope", "pay_9"), order_id="nope")
    assert response.status_code == 404


async def test_mock_order_is_not_accepted_outside_local_dev(client, mock_db, monkeypatch):
    monkeypatch.setattr(payment_service, "key_secret", "")
    monkeypatch.setattr(payment_routes.settings, "payments_mock_enabled", False)
    await _seed(mock_db, mock=True)
    response = _verify(client, "anything")
    assert response.json()["verified"] is False
