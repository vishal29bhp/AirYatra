"""Stripe Checkout behind the interface the payment routes already use.

The routes were written against ``emergentintegrations.payments.stripe.checkout``. This module keeps
the same calls (``create_checkout_session``, ``get_checkout_status``, ``handle_webhook``) and the same
response fields, and ``STRIPE_PROVIDER`` picks the implementation:

* ``emergent`` (default): Emergent's Stripe wrapper, exactly as today.
* ``stripe``: the official Stripe SDK with your own ``STRIPE_API_KEY``. Webhooks must carry a valid
  ``Stripe-Signature`` for ``STRIPE_WEBHOOK_SECRET``; without the secret every webhook is rejected.
"""
from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

PROVIDERS = ("emergent", "stripe")


class StripeWebhookError(ValueError):
    """Webhook rejected: missing secret, missing or invalid signature, or malformed payload."""


@dataclass
class CheckoutSessionRequest:
    amount: Optional[float] = None          # rupees, as the routes pass it today
    currency: str = "inr"
    success_url: str = ""
    cancel_url: str = ""
    metadata: Dict[str, str] = field(default_factory=dict)
    line_items: Optional[List[Dict[str, Any]]] = None
    mode: str = "payment"


@dataclass
class CheckoutSessionResponse:
    url: str
    session_id: str


@dataclass
class CheckoutStatusResponse:
    status: str
    payment_status: str
    amount_total: int
    currency: str
    metadata: Dict[str, str]


@dataclass
class WebhookResponse:
    event_type: str
    event_id: str
    session_id: Optional[str]
    payment_status: Optional[str]
    metadata: Dict[str, str]


def stripe_provider() -> str:
    provider = os.environ.get("STRIPE_PROVIDER", "emergent")
    if provider not in PROVIDERS:
        raise ValueError(f"STRIPE_PROVIDER must be one of {PROVIDERS}, got {provider!r}")
    return provider


def to_minor_units(amount: float) -> int:
    """Rupees (float) to paise (int), rounded to the nearest paisa."""
    return int(round(float(amount) * 100))


class StripeSdkCheckout:
    """Stripe Checkout with the official SDK. Blocking SDK calls run in a worker thread."""

    def __init__(self, api_key: str, webhook_url: str = "", webhook_secret: Optional[str] = None, sdk=None):
        if sdk is None:
            import stripe as sdk
        self.sdk, self.api_key, self.webhook_url = sdk, api_key, webhook_url
        self.webhook_secret = webhook_secret if webhook_secret is not None else os.environ.get("STRIPE_WEBHOOK_SECRET", "")

    def _session_params(self, request: CheckoutSessionRequest) -> Dict[str, Any]:
        line_items = request.line_items
        if not line_items:
            if request.amount is None:
                raise ValueError("amount or line_items is required")
            line_items = [{
                "price_data": {
                    "currency": request.currency,
                    "product_data": {"name": "AirYatra booking payment"},
                    "unit_amount": to_minor_units(request.amount),
                },
                "quantity": 1,
            }]
        return {
            "mode": request.mode,
            "line_items": line_items,
            "success_url": request.success_url,
            "cancel_url": request.cancel_url,
            "metadata": dict(request.metadata or {}),
            # The webhook needs the metadata too, so copy it onto the PaymentIntent as well.
            "payment_intent_data": {"metadata": dict(request.metadata or {})},
        }

    async def create_checkout_session(self, request: CheckoutSessionRequest) -> CheckoutSessionResponse:
        session = await asyncio.to_thread(
            self.sdk.checkout.Session.create, api_key=self.api_key, **self._session_params(request))
        return CheckoutSessionResponse(url=session["url"], session_id=session["id"])

    async def get_checkout_status(self, session_id: str) -> CheckoutStatusResponse:
        session = await asyncio.to_thread(self.sdk.checkout.Session.retrieve, session_id, api_key=self.api_key)
        return CheckoutStatusResponse(
            status=session["status"], payment_status=session["payment_status"],
            amount_total=session["amount_total"], currency=session["currency"],
            metadata=dict(session.get("metadata") or {}),
        )

    async def handle_webhook(self, payload: bytes, signature: Optional[str]) -> WebhookResponse:
        if not self.webhook_secret:
            raise StripeWebhookError("STRIPE_WEBHOOK_SECRET is not set")
        if not signature:
            raise StripeWebhookError("missing Stripe-Signature header")
        try:
            event = self.sdk.Webhook.construct_event(payload, signature, self.webhook_secret)
        except Exception as exc:  # SignatureVerificationError or a malformed payload
            raise StripeWebhookError("invalid webhook signature or payload") from exc
        obj = event["data"]["object"]
        is_session = obj.get("object") == "checkout.session"
        return WebhookResponse(
            event_type=event["type"], event_id=event["id"],
            session_id=obj.get("id") if is_session else None,
            payment_status=obj.get("payment_status") if is_session else None,
            metadata=dict(obj.get("metadata") or {}),
        )


class EmergentStripeCheckout:
    """Today's behaviour: Emergent's Stripe wrapper, with requests translated to its own types."""

    def __init__(self, api_key: str, webhook_url: str):
        from emergentintegrations.payments.stripe import checkout as sdk

        self._sdk = sdk
        self._client = sdk.StripeCheckout(api_key=api_key, webhook_url=webhook_url)

    async def create_checkout_session(self, request: CheckoutSessionRequest):
        sdk_request = self._sdk.CheckoutSessionRequest(
            amount=request.amount, currency=request.currency, success_url=request.success_url,
            cancel_url=request.cancel_url, metadata=request.metadata,
        )
        return await self._client.create_checkout_session(sdk_request)

    async def get_checkout_status(self, session_id: str):
        return await self._client.get_checkout_status(session_id)

    async def handle_webhook(self, payload: bytes, signature: Optional[str]):
        return await self._client.handle_webhook(payload, signature)


def StripeCheckout(api_key: str, webhook_url: str = ""):
    """Same call as the Emergent SDK constructor; returns the client for ``STRIPE_PROVIDER``."""
    if stripe_provider() == "stripe":
        return StripeSdkCheckout(api_key=api_key, webhook_url=webhook_url)
    return EmergentStripeCheckout(api_key=api_key, webhook_url=webhook_url)
