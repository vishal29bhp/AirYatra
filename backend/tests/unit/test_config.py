"""Settings that protect production: CORS allow-list, mock payments, scheduler switch."""
import importlib
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[2]


def load_settings(monkeypatch, **env):
    for key in ("APP_ENV", "CORS_ORIGINS", "PAYMENTS_MOCK_ENABLED", "SCHEDULER_ENABLED", "EMERGENT_AUTH_ENABLED"):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    import config
    return importlib.reload(config).settings


@pytest.fixture(autouse=True)
def restore_config():
    yield
    import config
    importlib.reload(config)


def test_cors_origins_come_from_env_list(monkeypatch):
    settings = load_settings(monkeypatch, APP_ENV="prod", CORS_ORIGINS="https://airyatra.com, https://www.airyatra.com")
    assert settings.allowed_cors_origins == ["https://airyatra.com", "https://www.airyatra.com"]


def test_no_hosted_cors_default_in_production(monkeypatch):
    settings = load_settings(monkeypatch, APP_ENV="prod")
    assert settings.allowed_cors_origins == []
    assert settings.is_production is True


def test_local_default_is_only_the_dev_server(monkeypatch):
    settings = load_settings(monkeypatch, APP_ENV="dev")
    assert settings.allowed_cors_origins == ["http://localhost:3000"]
    assert not any("emergentagent" in origin for origin in settings.allowed_cors_origins)


@pytest.mark.parametrize("app_env,flag,expected", [
    ("dev", None, True),
    ("test", None, True),
    ("", None, False),
    ("prod", None, False),
    ("prod", "true", False),
    ("staging", "true", False),
    ("", "true", True),
    ("dev", "false", False),
])
def test_mock_payments_never_in_production(monkeypatch, app_env, flag, expected):
    env = {"APP_ENV": app_env}
    if flag is not None:
        env["PAYMENTS_MOCK_ENABLED"] = flag
    assert load_settings(monkeypatch, **env).payments_mock_enabled is expected


@pytest.mark.parametrize("flag,expected", [(None, True), ("false", False), ("true", True), ("0", False)])
def test_scheduler_switch(monkeypatch, flag, expected):
    env = {} if flag is None else {"SCHEDULER_ENABLED": flag}
    assert load_settings(monkeypatch, **env).scheduler_enabled is expected


def test_missing_jwt_secret_fails_fast():
    code = "import os; os.environ.pop('JWT_SECRET_KEY', None); import config"
    result = subprocess.run([sys.executable, "-c", code], cwd=BACKEND, capture_output=True, text=True,
                            env={"PATH": "", "APP_ENV": "test"})
    assert result.returncode != 0
    assert "JWT_SECRET_KEY" in result.stderr
