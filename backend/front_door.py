"""Real client IP behind Azure Front Door.

Behind Front Door every request reaches the API from a Front Door address, so per-IP rate limits,
login lockout and audit logs would all see the same few IPs. Front Door sends the caller's address in
``X-Azure-ClientIP`` and its own profile id in ``X-Azure-FDID``. This middleware replaces the ASGI
client address with ``X-Azure-ClientIP`` only when ``X-Azure-FDID`` equals our profile id
(``FRONT_DOOR_ID``), so nobody can spoof their IP by sending the header themselves. Everything that
reads ``request.client.host`` (slowapi, lockout, audit) then sees the real caller.
"""
from __future__ import annotations

import hmac
import ipaddress
from typing import Optional


def _header(scope, name: bytes) -> Optional[str]:
    for key, value in scope.get("headers") or []:
        if key.lower() == name:
            return value.decode("latin-1").strip()
    return None


def _valid_ip(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        return None


class FrontDoorClientIPMiddleware:
    def __init__(self, app, front_door_id: str):
        self.app = app
        self.front_door_id = (front_door_id or "").strip().lower()

    async def __call__(self, scope, receive, send):
        if self.front_door_id and scope.get("type") in ("http", "websocket"):
            fdid = (_header(scope, b"x-azure-fdid") or "").lower()
            if fdid and hmac.compare_digest(fdid, self.front_door_id):
                client_ip = _valid_ip(_header(scope, b"x-azure-clientip"))
                if client_ip:
                    port = scope["client"][1] if scope.get("client") else 0
                    scope = dict(scope, client=(client_ip, port))
        await self.app(scope, receive, send)
