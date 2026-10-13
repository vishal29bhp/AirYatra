"""The API rate limit is one budget per client across all replicas when Redis is available."""
import types

import fakeredis
import pytest

import ultra_performance_middleware as upm
from services import redis_client


@pytest.fixture
def frozen_clock(monkeypatch):
    """No refill between calls, so the burst is exact."""
    monkeypatch.setattr(upm, "time", types.SimpleNamespace(time=lambda: 1_000_000.0))


class BrokenRedis:
    async def eval(self, *args):
        raise ConnectionError("redis down")


@pytest.fixture(autouse=True)
def reset():
    upm.rate_buckets.clear()
    yield
    redis_client.set_client_for_tests(None)
    upm.rate_buckets.clear()


async def test_redis_bucket_allows_the_burst_then_throttles(frozen_clock):
    redis_client.set_client_for_tests(fakeredis.FakeAsyncRedis(decode_responses=True))
    results = [await upm.check_rate_limit_shared("client-a") for _ in range(upm.RATE_LIMIT_BURST + 1)]
    assert all(allowed for allowed, _ in results[:upm.RATE_LIMIT_BURST])
    assert results[0][1] == upm.RATE_LIMIT_BURST - 1
    assert results[-1] == (False, 0)
    assert upm.rate_buckets == {}  # nothing kept in process memory


async def test_two_replicas_share_one_budget(frozen_clock):
    server = fakeredis.FakeServer()
    replica_a = fakeredis.FakeAsyncRedis(server=server, decode_responses=True)
    replica_b = fakeredis.FakeAsyncRedis(server=server, decode_responses=True)
    for i in range(upm.RATE_LIMIT_BURST):
        redis_client.set_client_for_tests(replica_a if i % 2 else replica_b)
        assert (await upm.check_rate_limit_shared("client-b"))[0]
    redis_client.set_client_for_tests(replica_a)
    assert (await upm.check_rate_limit_shared("client-b"))[0] is False


async def test_bucket_key_expires():
    fake = fakeredis.FakeAsyncRedis(decode_responses=True)
    redis_client.set_client_for_tests(fake)
    await upm.check_rate_limit_shared("client-c")
    assert 0 < await fake.ttl("ratelimit:client-c") <= 60


async def test_falls_back_to_memory_when_redis_fails(monkeypatch):
    monkeypatch.delenv("REDIS_HOST", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)
    redis_client.set_client_for_tests(BrokenRedis())
    allowed, remaining = await upm.check_rate_limit_shared("client-d")
    assert allowed and remaining == upm.RATE_LIMIT_BURST - 1
    assert "client-d" in upm.rate_buckets
    assert await redis_client.get_redis() is None  # dropped after the failure


async def test_no_redis_configured_uses_memory(monkeypatch):
    monkeypatch.delenv("REDIS_HOST", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)
    assert await redis_client.get_redis() is None
    assert (await upm.check_rate_limit_shared("client-e"))[0]
    assert "client-e" in upm.rate_buckets


def test_azure_redis_uses_entra_id_over_tls(monkeypatch):
    monkeypatch.setenv("REDIS_HOST", "airyatra.centralindia.redis.azure.net")
    monkeypatch.setenv("REDIS_PORT", "10000")
    monkeypatch.setenv("AZURE_CLIENT_ID", "00000000-0000-0000-0000-000000000001")
    client = redis_client._build_client()
    kwargs = client.connection_pool.connection_kwargs
    assert kwargs["host"] == "airyatra.centralindia.redis.azure.net" and kwargs["port"] == 10000
    assert client.connection_pool.connection_class.__name__ == "SSLConnection"
    assert kwargs.get("password") is None
    assert type(kwargs["credential_provider"]).__name__ == "EntraIdCredentialsProvider"
