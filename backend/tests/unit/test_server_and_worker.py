"""App wiring: readiness probe, CORS allow-list, scheduler only where enabled, and the worker lifecycle."""
import asyncio
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient


class FakeDb:
    def __init__(self, healthy):
        self.healthy = healthy

    async def command(self, name):
        if not self.healthy:
            raise ConnectionError("no primary")
        return {"ok": 1}


@pytest.mark.parametrize("healthy,status", [(True, 200), (False, 503)])
def test_readiness_reflects_database(server, monkeypatch, healthy, status):
    monkeypatch.setattr(server, "get_database", lambda: FakeDb(healthy))
    response = TestClient(server.app).get("/health/ready")
    assert response.status_code == status


def test_liveness_unchanged(server):
    response = TestClient(server.app).get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_cors_rejects_unknown_origin(server):
    response = TestClient(server.app).options(
        "/health", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"})
    assert response.headers.get("access-control-allow-origin") != "https://evil.example"


def test_cors_allows_configured_origin(server):
    origin = server.settings.allowed_cors_origins[0]
    response = TestClient(server.app).options(
        "/health", headers={"Origin": origin, "Access-Control-Request-Method": "GET"})
    assert response.headers.get("access-control-allow-origin") == origin


@pytest.mark.parametrize("enabled", [True, False])
async def test_startup_starts_scheduler_only_when_enabled(server, monkeypatch, enabled):
    calls = []

    async def noop():
        return {}

    monkeypatch.setattr(server.settings, "scheduler_enabled", enabled)
    monkeypatch.setattr(server, "connect_to_mongo", noop)
    monkeypatch.setattr(server, "optimize_database", noop)
    monkeypatch.setattr(server, "init_security_middleware", lambda app, db: {})
    monkeypatch.setattr(server, "start_scheduler", lambda: calls.append("start"))
    monkeypatch.setattr("database.get_database", lambda: None)
    await server.startup_event()
    assert calls == (["start"] if enabled else [])


async def test_worker_runs_scheduler_until_stopped(monkeypatch):
    import worker

    events = []

    async def connect():
        events.append("connect")

    async def close():
        events.append("close")

    monkeypatch.setattr(worker, "connect_to_mongo", connect)
    monkeypatch.setattr(worker, "close_mongo_connection", close)
    monkeypatch.setattr(worker, "start_scheduler", lambda: events.append("start"))
    monkeypatch.setattr(worker, "stop_scheduler", lambda: events.append("stop"))

    instance = worker.SchedulerWorker()
    task = asyncio.create_task(instance.run())
    await asyncio.sleep(0.01)
    assert events == ["connect", "start"]
    instance.request_stop()
    await task
    assert events == ["connect", "start", "stop", "close"]
