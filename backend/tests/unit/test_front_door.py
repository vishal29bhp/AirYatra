"""X-Azure-ClientIP is trusted only when X-Azure-FDID is our own Front Door profile."""
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from front_door import FrontDoorClientIPMiddleware
from security_middleware import get_client_ip

FDID = "8f2d6c3e-1b4a-4c5d-9e6f-0a1b2c3d4e5f"


def _client(front_door_id=FDID):
    app = FastAPI()

    @app.get("/ip")
    async def ip(request: Request):
        return {"client": request.client.host, "limiter_key": get_client_ip(request)}

    app.add_middleware(FrontDoorClientIPMiddleware, front_door_id=front_door_id)
    return TestClient(app)


def test_our_front_door_sets_the_real_client_ip():
    body = _client().get("/ip", headers={"X-Azure-FDID": FDID.upper(), "X-Azure-ClientIP": "49.36.12.7"}).json()
    assert body == {"client": "49.36.12.7", "limiter_key": "49.36.12.7"}


@pytest.mark.parametrize("headers", [
    {"X-Azure-ClientIP": "49.36.12.7"},                                         # no profile id: spoof attempt
    {"X-Azure-FDID": "00000000-0000-0000-0000-000000000000", "X-Azure-ClientIP": "49.36.12.7"},  # someone else's Front Door
    {"X-Azure-FDID": FDID, "X-Azure-ClientIP": "not-an-ip"},
    {"X-Azure-FDID": FDID},
])
def test_untrusted_or_invalid_headers_are_ignored(headers):
    assert _client().get("/ip", headers=headers).json()["client"] == "testclient"


def test_disabled_without_a_front_door_id():
    headers = {"X-Azure-FDID": FDID, "X-Azure-ClientIP": "49.36.12.7"}
    assert _client(front_door_id="").get("/ip", headers=headers).json()["client"] == "testclient"


def test_ipv6_client_is_accepted():
    headers = {"X-Azure-FDID": FDID, "X-Azure-ClientIP": "2401:4900:1c2a::7"}
    assert _client().get("/ip", headers=headers).json()["client"] == "2401:4900:1c2a::7"
