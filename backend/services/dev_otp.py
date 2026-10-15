"""Dev only: one fixed one-time code, so testers can sign in and register before SMTP and SMS exist.

DEV_FIXED_OTP (exactly six digits) is used in place of a random code only when APP_ENV is a local or
dev environment. Anywhere else, including an unset APP_ENV, it is ignored and codes stay random.
"""
import os
import re
from typing import Optional

from config import LOCAL_ENVS


def fixed_otp() -> Optional[str]:
    """The fixed code when it is allowed here, otherwise None."""
    code = os.getenv("DEV_FIXED_OTP", "").strip()
    app_env = os.getenv("APP_ENV", "").strip().lower()
    if app_env in LOCAL_ENVS and re.fullmatch(r"\d{6}", code):
        return code
    return None
