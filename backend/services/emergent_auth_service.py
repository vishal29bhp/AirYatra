"""Server-side verification of Emergent-managed Google sign-in.

The browser only ever hands us the Emergent ``session_id`` from the redirect. We ask Emergent who that
session belongs to; nothing the browser says about the user's identity is trusted.
"""
import logging
from typing import Any, Dict, Optional

import httpx

from config import settings

logger = logging.getLogger(__name__)


class EmergentAuthError(Exception):
    """The Emergent session could not be verified."""


class EmergentAuthDisabledError(EmergentAuthError):
    """Emergent sign-in is turned off for this deployment."""


class EmergentSessionVerifier:
    """Resolves an Emergent OAuth session id to the verified Google profile."""

    def __init__(
        self,
        session_url: str,
        enabled: bool = True,
        timeout_seconds: float = 10.0,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ) -> None:
        self._session_url = session_url
        self._enabled = enabled
        self._timeout = timeout_seconds
        self._transport = transport

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def verify(self, session_id: Optional[str]) -> Dict[str, Any]:
        if not self._enabled:
            raise EmergentAuthDisabledError("Emergent sign-in is disabled")
        if not session_id or not isinstance(session_id, str) or len(session_id) > 512:
            raise EmergentAuthError("Missing or invalid session id")

        try:
            async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
                response = await client.get(self._session_url, headers={"X-Session-ID": session_id})
        except httpx.HTTPError as exc:
            logger.warning("Emergent session lookup failed: %s", type(exc).__name__)
            raise EmergentAuthError("Could not reach the sign-in provider") from exc

        if response.status_code != 200:
            raise EmergentAuthError("Sign-in session is not valid")

        try:
            profile = response.json()
        except ValueError as exc:
            raise EmergentAuthError("Malformed sign-in response") from exc

        email = profile.get("email") if isinstance(profile, dict) else None
        if not isinstance(email, str) or "@" not in email:
            raise EmergentAuthError("Sign-in response has no e-mail")

        return {
            "id": profile.get("id"),
            "email": email.strip(),
            "name": profile.get("name") or "",
            "picture": profile.get("picture") or "",
            "session_token": profile.get("session_token"),
        }


emergent_session_verifier = EmergentSessionVerifier(
    session_url=settings.emergent_auth_session_url,
    enabled=settings.emergent_auth_enabled,
)
