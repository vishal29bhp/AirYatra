"""Unit-test setup: isolated from any running server, database or third-party API.

Run from the repository root:  python -m pytest backend/tests/unit
"""
import os
import sys
import types
from unittest.mock import MagicMock
import tempfile
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]

# Settings are read at import time, so the environment must be set before any app module loads.
os.environ.setdefault("JWT_SECRET_KEY", "unit-test-secret-key-not-for-production")
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "airyatra_unit_test")
os.environ.setdefault("COOKIE_SECURE", "false")
# server.py creates upload folders on import; CI runners cannot write to the default /app.
os.environ.setdefault("UPLOAD_ROOT", tempfile.mkdtemp(prefix="airyatra-uploads-"))

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pytest  # noqa: E402
from mongomock_motor import AsyncMongoMockClient  # noqa: E402


@pytest.fixture
def mock_db():
    """A fresh in-memory Motor-compatible database per test."""
    return AsyncMongoMockClient()["airyatra_unit_test"]


def _stub_emergentintegrations():
    """server.py imports Stripe checkout from the Emergent SDK, which is not on public PyPI."""
    if "emergentintegrations" in sys.modules:
        return
    for name in ("emergentintegrations", "emergentintegrations.llm", "emergentintegrations.llm.chat",
                 "emergentintegrations.payments", "emergentintegrations.payments.stripe",
                 "emergentintegrations.payments.stripe.checkout"):
        module = types.ModuleType(name)
        module.__dict__.update({k: MagicMock(name=k) for k in (
            "LlmChat", "UserMessage", "TextDelta", "StreamDone", "StripeCheckout", "CheckoutSessionRequest")})
        sys.modules[name] = module


@pytest.fixture(scope="module")
def server():
    _stub_emergentintegrations()
    import server as server_module
    return server_module


# The Emergent SDK is never installed in CI; stub it for every test, whatever the order.
_stub_emergentintegrations()
