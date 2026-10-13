"""Stripe adapter: official SDK path creates sessions in paise and only accepts signed webhooks."""
import json
import time

import pytest
import stripe

from services.stripe_checkout import (
    CheckoutSessionRequest, StripeSdkCheckout, StripeWebhookError, StripeCheckout, EmergentStripeCheckout,
    to_minor_units,
)

SECRET = "whsec_unit_test"


class FakeSession:
    created = None

    @classmethod
    def create(cls, api_key, **params):
        cls.created = {"api_key": api_key, **params}
        return {"id": "cs_test_1", "url": "https://checkout.stripe.test/cs_test_1"}

    @staticmethod
    def retrieve(session_id, api_key):
        return {"status": "complete", "payment_status": "paid", "amount_total": 1250050, "currency": "inr",
                "metadata": {"booking_id": "b1"}}


class FakeSdk:
    checkout = type("Checkout", (), {"Session": FakeSession})
    Webhook = stripe.Webhook  # real signature verification


def _client(secret=SECRET):
    return StripeSdkCheckout(api_key="sk_test_x", webhook_secret=secret, sdk=FakeSdk)


@pytest.mark.parametrize("rupees,paise", [(12500.5, 1250050), (0.1 + 0.2, 30), (1, 100), (99999.99, 9999999)])
def test_amounts_convert_to_paise_without_float_drift(rupees, paise):
    assert to_minor_units(rupees) == paise


async def test_create_session_from_amount_keeps_metadata():
    request = CheckoutSessionRequest(amount=12500.5, currency="inr", success_url="https://a/ok",
                                     cancel_url="https://a/cancel", metadata={"booking_id": "b1"})
    session = await _client().create_checkout_session(request)
    assert (session.session_id, session.url) == ("cs_test_1", "https://checkout.stripe.test/cs_test_1")
    created = FakeSession.created
    assert created["line_items"][0]["price_data"]["unit_amount"] == 1250050
    assert created["metadata"] == {"booking_id": "b1"}
    assert created["payment_intent_data"]["metadata"] == {"booking_id": "b1"}


async def test_status_maps_session_fields():
    status = await _client().get_checkout_status("cs_test_1")
    assert (status.status, status.payment_status, status.amount_total) == ("complete", "paid", 1250050)


def _signed(payload: dict, secret=SECRET):
    body = json.dumps(payload).encode()
    timestamp = int(time.time())
    signature = stripe.WebhookSignature._compute_signature(f"{timestamp}.{body.decode()}", secret)
    return body, f"t={timestamp},v1={signature}"


EVENT = {"id": "evt_1", "object": "event", "type": "checkout.session.completed",
         "data": {"object": {"id": "cs_test_1", "object": "checkout.session", "payment_status": "paid",
                             "metadata": {"booking_id": "b1"}}}}


async def test_signed_webhook_is_accepted():
    body, signature = _signed(EVENT)
    event = await _client().handle_webhook(body, signature)
    assert (event.event_type, event.session_id, event.payment_status) == ("checkout.session.completed", "cs_test_1", "paid")


@pytest.mark.parametrize("case", ["no_secret", "no_signature", "wrong_secret", "tampered"])
async def test_unsigned_or_forged_webhooks_are_rejected(case):
    body, signature = _signed(EVENT, secret="whsec_attacker" if case == "wrong_secret" else SECRET)
    if case == "tampered":
        body = body.replace(b'"paid"', b'"unpaid"')
    client = _client(secret="" if case == "no_secret" else SECRET)
    with pytest.raises(StripeWebhookError):
        await client.handle_webhook(body, None if case == "no_signature" else signature)


def test_provider_switch(monkeypatch):
    monkeypatch.setenv("STRIPE_PROVIDER", "stripe")
    assert isinstance(StripeCheckout(api_key="sk_test_x", webhook_url="https://a/api/webhook/stripe"), StripeSdkCheckout)
    monkeypatch.setenv("STRIPE_PROVIDER", "emergent")
    assert isinstance(StripeCheckout(api_key="sk_test_x", webhook_url="https://a"), EmergentStripeCheckout)
    monkeypatch.setenv("STRIPE_PROVIDER", "paypal")
    with pytest.raises(ValueError):
        StripeCheckout(api_key="sk_test_x")
