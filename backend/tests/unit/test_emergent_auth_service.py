import httpx
import pytest

from services.emergent_auth_service import (
    EmergentAuthDisabledError,
    EmergentAuthError,
    EmergentSessionVerifier,
)

URL = "https://emergent.example/session-data"


def make_verifier(handler, enabled=True):
    return EmergentSessionVerifier(URL, enabled=enabled, transport=httpx.MockTransport(handler))


async def test_returns_profile_from_emergent_using_session_header():
    seen = {}

    def handler(request):
        seen["header"] = request.headers.get("X-Session-ID")
        return httpx.Response(200, json={"id": "g-1", "email": "Asha@Example.com", "name": "Asha", "session_token": "st"})

    profile = await make_verifier(handler).verify("sess-123")

    assert seen["header"] == "sess-123"
    assert profile == {"id": "g-1", "email": "Asha@Example.com", "name": "Asha", "picture": "", "session_token": "st"}


@pytest.mark.parametrize("session_id", [None, "", "x" * 513, 12345])
async def test_rejects_missing_or_malformed_session_id_without_calling_emergent(session_id):
    def handler(request):  # pragma: no cover - must not be called
        raise AssertionError("Emergent must not be called")

    with pytest.raises(EmergentAuthError):
        await make_verifier(handler).verify(session_id)


async def test_non_200_is_rejected():
    verifier = make_verifier(lambda r: httpx.Response(401, json={"detail": "expired"}))
    with pytest.raises(EmergentAuthError):
        await verifier.verify("sess")


@pytest.mark.parametrize("body", [{"name": "no email"}, {"email": "not-an-email"}, ["list"]])
async def test_profile_without_valid_email_is_rejected(body):
    verifier = make_verifier(lambda r: httpx.Response(200, json=body))
    with pytest.raises(EmergentAuthError):
        await verifier.verify("sess")


async def test_malformed_json_is_rejected():
    verifier = make_verifier(lambda r: httpx.Response(200, content=b"<html>"))
    with pytest.raises(EmergentAuthError):
        await verifier.verify("sess")


async def test_network_error_is_rejected():
    def handler(request):
        raise httpx.ConnectError("down", request=request)

    with pytest.raises(EmergentAuthError):
        await make_verifier(handler).verify("sess")


async def test_disabled_verifier_refuses_everything():
    verifier = make_verifier(lambda r: httpx.Response(200, json={"email": "a@b.co"}), enabled=False)
    assert verifier.enabled is False
    with pytest.raises(EmergentAuthDisabledError):
        await verifier.verify("sess")
