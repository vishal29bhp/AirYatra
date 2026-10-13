"""Regression tests for the Razorpay webhook and the previously unauthenticated /api/razorpay routes."""
import hashlib
import hmac
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import razorpay_routes
from routes.razorpay_routes import is_valid_webhook_signature

SECRET = "whsec_unit_test"


def body_and_signature(event="payment.captured", secret=SECRET):
    body = json.dumps({"event": event, "payload": {"payment": {"entity": {"id": "pay_1", "order_id": "order_1"}}}}).encode()
    return body, hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_signature_helper():
    body, signature = body_and_signature()
    assert is_valid_webhook_signature(SECRET, body, signature) is True
    assert is_valid_webhook_signature(SECRET, body + b" ", signature) is False
    assert is_valid_webhook_signature(SECRET, body, "") is False
    assert is_valid_webhook_signature("", body, signature) is False


@pytest.fixture
def client(mock_db, monkeypatch):
    monkeypatch.setattr(razorpay_routes, "get_database", lambda: mock_db)
    monkeypatch.setattr(razorpay_routes, "RAZORPAY_WEBHOOK_SECRET", SECRET)
    app = FastAPI()
    app.include_router(razorpay_routes.router, prefix="/api")
    return TestClient(app)


async def test_webhook_without_signature_header_is_rejected_and_stores_nothing(client, mock_db):
    body, _ = body_and_signature()
    response = client.post("/api/razorpay/webhook", content=body)
    assert response.status_code == 400
    assert await mock_db.razorpay_webhooks.count_documents({}) == 0


async def test_webhook_with_forged_signature_is_rejected(client, mock_db):
    body, _ = body_and_signature()
    _, forged = body_and_signature(secret="attacker")
    response = client.post("/api/razorpay/webhook", content=body, headers={"X-Razorpay-Signature": forged})
    assert response.status_code == 400


def test_webhook_refused_when_secret_not_configured(client, monkeypatch):
    monkeypatch.setattr(razorpay_routes, "RAZORPAY_WEBHOOK_SECRET", "")
    body, signature = body_and_signature()
    response = client.post("/api/razorpay/webhook", content=body, headers={"X-Razorpay-Signature": signature})
    assert response.status_code == 503


def test_webhook_with_valid_signature_is_accepted(client):
    body, signature = body_and_signature()
    response = client.post("/api/razorpay/webhook", content=body, headers={"X-Razorpay-Signature": signature})
    assert response.status_code == 200, response.text


@pytest.mark.parametrize("method,path", [
    ("post", "/api/razorpay/create-order"),
    ("post", "/api/razorpay/verify-payment"),
    ("post", "/api/razorpay/refund"),
    ("get", "/api/razorpay/orders"),
    ("get", "/api/razorpay/stats"),
    ("get", "/api/razorpay/order/order_1"),
    ("get", "/api/razorpay/payment/pay_1"),
])
def test_payment_routes_require_login(client, method, path):
    response = getattr(client, method)(path, json={}) if method == "post" else client.get(path)
    assert response.status_code in (401, 403)
