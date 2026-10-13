"""Shared Redis connection for state every API replica must agree on (rate limits, chat fan-out).

Configuration, first match wins:
  REDIS_HOST (+ REDIS_PORT, default 10000)  Azure Managed Redis over TLS, signed in with the app's
                                            managed identity (AZURE_CLIENT_ID) through Entra ID.
                                            Access keys are disabled on the Azure side.
  REDIS_URL                                 Any Redis URL, for local development.
  neither                                   No Redis; callers fall back to per-process state.

Redis is an accelerator here, never a hard dependency: when it is missing or down, get_redis()
returns None and callers keep working on their in-memory fallbacks.
"""
import logging
import os
import time
from typing import Optional

logger = logging.getLogger(__name__)

# Entra ID resource for Azure Cache for Redis / Azure Managed Redis tokens.
AZURE_REDIS_RESOURCE = "https://redis.azure.com/"
# After a failed connection attempt, wait this long before trying again.
RETRY_AFTER_SECONDS = 30.0

_client = None
_last_failure = 0.0


def redis_configured() -> bool:
    return bool(os.getenv("REDIS_HOST") or os.getenv("REDIS_URL"))


def _entra_credential_provider():
    from redis_entraid.cred_provider import (
        ManagedIdentityIdType,
        ManagedIdentityType,
        create_from_managed_identity,
    )

    client_id = os.getenv("AZURE_CLIENT_ID", "")
    if client_id:
        return create_from_managed_identity(
            identity_type=ManagedIdentityType.USER_ASSIGNED,
            resource=AZURE_REDIS_RESOURCE,
            id_type=ManagedIdentityIdType.CLIENT_ID,
            id_value=client_id,
        )
    return create_from_managed_identity(
        identity_type=ManagedIdentityType.SYSTEM_ASSIGNED,
        resource=AZURE_REDIS_RESOURCE,
    )


def _build_client():
    import redis.asyncio as redis

    common = {"decode_responses": True, "socket_connect_timeout": 2, "socket_timeout": 2,
              "health_check_interval": 30}
    host = os.getenv("REDIS_HOST")
    if host:
        return redis.Redis(
            host=host,
            port=int(os.getenv("REDIS_PORT", "10000")),
            ssl=True,
            credential_provider=_entra_credential_provider(),
            **common,
        )
    return redis.Redis.from_url(os.environ["REDIS_URL"], **common)


async def get_redis():
    """The process-wide Redis client, or None when Redis is not configured or not reachable."""
    global _client, _last_failure
    if _client is not None:
        return _client
    if not redis_configured() or time.monotonic() - _last_failure < RETRY_AFTER_SECONDS:
        return None
    try:
        client = _build_client()
        await client.ping()
    except Exception as exc:  # any failure means "run without Redis for now"
        _last_failure = time.monotonic()
        logger.warning("Redis unavailable, using in-process fallbacks: %s", exc)
        return None
    _client = client
    logger.info("Redis connected")
    return _client


def mark_unhealthy() -> None:
    """Drop the shared client after a command fails, so the next caller reconnects (after a pause)."""
    global _client, _last_failure
    _client = None
    _last_failure = time.monotonic()


def set_client_for_tests(client: Optional[object]) -> None:
    global _client, _last_failure
    _client = client
    _last_failure = 0.0


async def close_redis() -> None:
    global _client
    if _client is not None:
        try:
            await _client.aclose()
        except Exception:  # closing is best-effort at shutdown
            pass
        _client = None
