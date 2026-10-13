from pydantic import model_validator
from pydantic_settings import BaseSettings
from pathlib import Path
from typing import List
import os
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

PRODUCTION_ENVS = {"prod", "production", "staging"}
LOCAL_ENVS = {"dev", "development", "local", "test"}


def _require_env(name: str) -> str:
    """Fail fast if required environment variable is missing"""
    raise ValueError(f"SECURITY ERROR: {name} environment variable is required but not set!")


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_list(name: str) -> List[str]:
    return [item.strip() for item in os.getenv(name, "").split(",") if item.strip()]


_APP_ENV = os.getenv('APP_ENV', '').strip().lower()


class Settings(BaseSettings):
    # Deployment environment: dev | staging | prod. Unset is treated as neither local nor production.
    app_env: str = _APP_ENV
    mongo_url: str = os.getenv('MONGO_URL', 'mongodb://localhost:27017')
    db_name: str = os.getenv('DB_NAME', 'airyatra_db')
    # SECURITY: JWT_SECRET_KEY is required - fail fast if not set
    jwt_secret_key: str = os.getenv('JWT_SECRET_KEY') or _require_env('JWT_SECRET_KEY')
    jwt_algorithm: str = os.getenv('JWT_ALGORITHM', 'HS256')
    access_token_expire_minutes: int = int(os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES', 10080))
    aws_access_key_id: str = os.getenv('AWS_ACCESS_KEY_ID', '')
    aws_secret_access_key: str = os.getenv('AWS_SECRET_ACCESS_KEY', '')
    aws_region: str = os.getenv('AWS_REGION', 'ap-south-1')
    s3_bucket_name: str = os.getenv('S3_BUCKET_NAME', 'airyatra-documents')
    razorpay_key_id: str = os.getenv('RAZORPAY_KEY_ID', '')
    razorpay_key_secret: str = os.getenv('RAZORPAY_KEY_SECRET', '')
    sendgrid_api_key: str = os.getenv('SENDGRID_API_KEY', '')
    sender_email: str = os.getenv('SENDER_EMAIL', 'noreply@airyatra.com')
    emergent_llm_key: str = os.getenv('EMERGENT_LLM_KEY', '')

    # Browser origins allowed by CORS (env CORS_ORIGINS, comma-separated). Required in production; local runs default to the CRA dev server.
    allowed_cors_origins: List[str] = _env_list('CORS_ORIGINS') or (
        [] if _APP_ENV in PRODUCTION_ENVS else ['http://localhost:3000']
    )
    # The API process starts APScheduler only when true; on Azure the worker app sets it and the API does not.
    scheduler_enabled: bool = _env_bool('SCHEDULER_ENABLED', True)
    # Mock payments (no gateway keys) are only ever allowed for local development and tests.
    payments_mock_enabled: bool = _env_bool('PAYMENTS_MOCK_ENABLED', _APP_ENV in LOCAL_ENVS) and _APP_ENV not in PRODUCTION_ENVS
    # Emergent-managed Google sign-in. Identity is always confirmed server-side with Emergent.
    emergent_auth_enabled: bool = _env_bool('EMERGENT_AUTH_ENABLED', True)
    emergent_auth_session_url: str = os.getenv(
        'EMERGENT_AUTH_SESSION_URL',
        'https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data',
    )

    @model_validator(mode="after")
    def _never_mock_payments_in_production(self) -> "Settings":
        # pydantic-settings also reads PAYMENTS_MOCK_ENABLED from the environment directly,
        # so the production guard has to be enforced after loading, not only in the default.
        if self.is_production:
            self.payments_mock_enabled = False
        return self

    @property
    def is_production(self) -> bool:
        return self.app_env in PRODUCTION_ENVS


settings = Settings()
