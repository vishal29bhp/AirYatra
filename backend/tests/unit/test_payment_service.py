"""Unit tests for the Razorpay customer-payment service (services/payment_service.py).

Signature verification is covered in test_payment_verification.py; these tests cover key loading,
order creation, refunds and status. The Razorpay SDK client is always a MagicMock.
"""
import hashlib
import hmac
import sys
from unittest.mock import MagicMock, patch

import pytest

from services.payment_service import PaymentService

FAKE_KEY_ID = "rzp_test_FAKEKEY123"
FAKE_SECRET = "fake_secret_for_unit_tests"


@pytest.fixture
def service():
    svc = PaymentService()
    svc.key_id = ""
    svc.key_secret = ""
    svc.client = None
    return svc


@pytest.fixture
def live_service(service):
    service.key_id = FAKE_KEY_ID
    service.key_secret = FAKE_SECRET
    service.client = MagicMock(name="razorpay.Client")
    service._db_settings_loaded = True
    return service


# ==================== loading keys from admin settings ====================

async def test_db_keys_initialise_razorpay_client(service, mock_db):
    await mock_db.api_keys_settings.insert_one(
        {"type": "api_keys", "razorpay_key_id": FAKE_KEY_ID, "razorpay_key_secret": FAKE_SECRET})
    with patch("razorpay.Client") as client_cls:
        await service._load_api_keys_from_db(mock_db)
    client_cls.assert_called_once_with(auth=(FAKE_KEY_ID, FAKE_SECRET))
    assert service.client is client_cls.return_value
    assert (service.key_id, service.key_secret) == (FAKE_KEY_ID, FAKE_SECRET)
    assert service._db_settings_loaded is True


async def test_short_key_id_loads_secret_but_no_client(service, mock_db):
    await mock_db.api_keys_settings.insert_one(
        {"type": "api_keys", "razorpay_key_id": "short", "razorpay_key_secret": FAKE_SECRET})
    with patch("razorpay.Client") as client_cls:
        await service._load_api_keys_from_db(mock_db)
    client_cls.assert_not_called()
    assert service.client is None
    assert service.key_secret == FAKE_SECRET


async def test_missing_settings_document_leaves_env_keys(service, mock_db):
    service.key_secret = "from-env"
    await service._load_api_keys_from_db(mock_db)
    assert service.key_secret == "from-env"
    assert service._db_settings_loaded is False


async def test_loaded_client_is_not_reloaded(live_service):
    db = MagicMock()
    await live_service._load_api_keys_from_db(db)
    db.api_keys_settings.find_one.assert_not_called()


async def test_missing_razorpay_sdk_is_tolerated(service, mock_db, monkeypatch):
    await mock_db.api_keys_settings.insert_one(
        {"type": "api_keys", "razorpay_key_id": FAKE_KEY_ID, "razorpay_key_secret": FAKE_SECRET})
    monkeypatch.setitem(sys.modules, "razorpay", None)  # makes `import razorpay` raise ImportError
    await service._load_api_keys_from_db(mock_db)
    assert service.client is None
    assert service.key_secret == FAKE_SECRET


async def test_db_error_while_loading_keys_is_swallowed(service):
    db = MagicMock()
    db.api_keys_settings.find_one.side_effect = RuntimeError("db down")
    await service._load_api_keys_from_db(db)
    assert service.client is None


def test_reset_settings_cache(live_service):
    live_service.reset_settings_cache()
    assert live_service.client is None
    assert live_service._db_settings_loaded is False


# ==================== create_order ====================

async def test_create_order_sends_paise_and_booking_receipt(live_service):
    live_service.client.order.create.return_value = {"id": "order_ABC", "amount": 621270_00, "currency": "INR"}
    result = await live_service.create_order(621270_00, booking_id="bk-1", notes={"booking": "bk-1"})
    live_service.client.order.create.assert_called_once_with(data={
        "amount": 62127000, "currency": "INR", "receipt": "booking_bk-1", "notes": {"booking": "bk-1"}})
    assert result == {"success": True, "order_id": "order_ABC", "amount": 62127000, "currency": "INR",
                      "key_id": FAKE_KEY_ID, "mock": False}


async def test_create_order_without_booking_uses_generated_receipt(live_service):
    live_service.client.order.create.return_value = {"id": "order_X", "amount": 100, "currency": "INR"}
    await live_service.create_order(100)
    data = live_service.client.order.create.call_args.kwargs["data"]
    assert data["receipt"].startswith("order_")
    assert data["notes"] == {}


async def test_create_order_gateway_error_is_reported(live_service):
    live_service.client.order.create.side_effect = RuntimeError("BadRequestError: amount too small")
    result = await live_service.create_order(50, booking_id="bk-1")
    assert result == {"success": False, "error": "BadRequestError: amount too small"}


async def test_create_order_without_client_returns_flagged_mock_order(service, mock_db):
    result = await service.create_order(150000, booking_id="bk-1", db=mock_db)
    assert result["mock"] is True
    assert result["amount"] == 150000
    assert result["order_id"].startswith("order_")
    assert result["key_id"] == "rzp_test_mock"


# ==================== verify_payment with SDK client ====================

def _sign(order_id, payment_id):
    return hmac.new(FAKE_SECRET.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()


async def test_verified_payment_reports_amount_in_rupees(live_service):
    live_service.client.payment.fetch.return_value = {"amount": 250050, "method": "upi", "status": "captured"}
    result = await live_service.verify_payment("order_1", "pay_1", _sign("order_1", "pay_1"))
    live_service.client.payment.fetch.assert_called_once_with("pay_1")
    assert result["verified"] is True
    assert result["amount"] == 2500.50  # 2,50,050 paise
    assert (result["method"], result["status"]) == ("upi", "captured")


async def test_payment_fetch_failure_after_valid_signature_still_verifies(live_service):
    live_service.client.payment.fetch.side_effect = RuntimeError("timeout")
    result = await live_service.verify_payment("order_1", "pay_1", _sign("order_1", "pay_1"))
    assert result["verified"] is True
    assert result["amount"] == 0


async def test_invalid_signature_never_fetches_payment(live_service):
    result = await live_service.verify_payment("order_1", "pay_1", _sign("order_1", "pay_OTHER"))
    assert result["verified"] is False
    live_service.client.payment.fetch.assert_not_called()


# ==================== create_refund ====================

async def test_partial_refund_sends_amount_in_paise(live_service):
    live_service.client.payment.refund.return_value = {"id": "rfnd_1", "amount": 50000, "status": "processed"}
    result = await live_service.create_refund("pay_1", amount=50000, reason="Weather abort")
    live_service.client.payment.refund.assert_called_once_with(
        "pay_1", {"speed": "normal", "notes": {"reason": "Weather abort"}, "amount": 50000})
    assert result == {"success": True, "refund_id": "rfnd_1", "amount": 500.0, "status": "processed", "mock": False}


async def test_full_refund_omits_amount(live_service):
    live_service.client.payment.refund.return_value = {"id": "rfnd_2", "amount": 62127000, "status": "pending"}
    result = await live_service.create_refund("pay_1")
    sent = live_service.client.payment.refund.call_args.args[1]
    assert "amount" not in sent
    assert result["amount"] == 621270.0


async def test_refund_gateway_error_is_reported(live_service):
    live_service.client.payment.refund.side_effect = RuntimeError("already refunded")
    assert await live_service.create_refund("pay_1", 100) == {"success": False, "error": "already refunded"}


async def test_refund_without_client_is_flagged_mock(service, mock_db):
    result = await service.create_refund("pay_1", amount=12345, db=mock_db)
    assert result["mock"] is True
    assert result["amount"] == 123.45
    assert result["refund_id"].startswith("rfnd_")


async def test_full_mock_refund_reports_zero(service):
    assert (await service.create_refund("pay_1"))["amount"] == 0


# ==================== status / methods ====================

async def test_payment_status_when_configured(live_service, mock_db):
    assert await live_service.get_payment_status(db=mock_db) == {
        "razorpay_configured": True, "key_id_set": True, "mock_mode": False}


async def test_payment_status_when_unconfigured(service, mock_db):
    assert await service.get_payment_status(db=mock_db) == {
        "razorpay_configured": False, "key_id_set": False, "mock_mode": True}


async def test_payment_methods_list(service, mock_db):
    result = await service.get_payment_methods(db=mock_db)
    ids = [m["id"] for m in result["methods"]]
    assert ids == ["upi", "card", "netbanking", "wallet", "emi"]
    emi = result["methods"][-1]
    assert emi["min_amount"] == 300000
    assert result["mock_mode"] is True
