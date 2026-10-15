"""Dev-only fixed one-time code (services/dev_otp.py): on in dev when set, never anywhere else."""
import pytest

from routes import verification_routes
from services import otp_service
from services.dev_otp import fixed_otp


@pytest.mark.parametrize("app_env", ["dev", "development", "local", "test"])
def test_fixed_code_is_used_in_dev(monkeypatch, app_env):
    monkeypatch.setenv("APP_ENV", app_env)
    monkeypatch.setenv("DEV_FIXED_OTP", "123456")

    assert fixed_otp() == "123456"
    assert otp_service.generate_otp() == "123456"
    assert verification_routes.generate_otp() == "123456"


@pytest.mark.parametrize("app_env", ["prod", "production", "staging", ""])
def test_fixed_code_is_ignored_outside_dev(monkeypatch, app_env):
    monkeypatch.setenv("APP_ENV", app_env)
    monkeypatch.setenv("DEV_FIXED_OTP", "123456")

    assert fixed_otp() is None
    assert len({otp_service.generate_otp() for _ in range(20)}) > 1


@pytest.mark.parametrize("code", ["", "12345", "1234567", "abcdef", "set-me"])
def test_only_six_digits_count(monkeypatch, code):
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("DEV_FIXED_OTP", code)
    assert fixed_otp() is None


async def test_login_code_verifies_with_the_fixed_code(monkeypatch, mock_db):
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("DEV_FIXED_OTP", "123456")
    monkeypatch.setattr(otp_service, "get_database", lambda: mock_db)
    service = otp_service.OTPService()

    code, _ = await service.create_otp("u1", "ceo@airyatra.co.in")
    valid, _ = await service.verify_otp("u1", "123456")

    assert code == "123456" and valid is True
