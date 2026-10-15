"""Dev-only: create staff logins in a database that does not have them yet.

The Azure dev database starts empty, so nobody can sign in until real data is copied over.
When BOOTSTRAP_STAFF lists "email:role" pairs ("email:role+role" for several roles) and
BOOTSTRAP_STAFF_PASSWORD (from Key Vault) is set, each missing email gets an account with that
password. Accounts this bootstrap created earlier get their roles brought in line with the list;
every other user is never changed. Nothing runs in production environments.
"""
import logging
from datetime import datetime, timezone
from typing import List, Tuple
from uuid import uuid4

from auth import get_password_hash
from config import PRODUCTION_ENVS

logger = logging.getLogger(__name__)

MIN_PASSWORD_LENGTH = 12
PLACEHOLDER = "set-me"
STAFF_ROLES = {"super_admin", "admin", "finance", "hr", "sales", "support", "operations", "marketing",
               "operator", "pilot"}
CREATED_BY = "staff_bootstrap"


def parse_staff(spec: str) -> List[Tuple[str, List[str]]]:
    """'a@x.in:super_admin+admin, b@x.in:hr' -> [('a@x.in', ['super_admin', 'admin']), ('b@x.in', ['hr'])].

    Rejects unknown roles. The first role decides which dashboard opens after login.
    """
    staff = []
    for item in filter(None, (part.strip() for part in spec.split(","))):
        email, sep, role_list = item.rpartition(":")
        email = email.strip().lower()
        roles = [r.strip() for r in role_list.split("+") if r.strip()]
        if not sep or "@" not in email or not roles or any(r not in STAFF_ROLES for r in roles):
            raise ValueError(f"BOOTSTRAP_STAFF entry must be email:role[+role] with known roles, got {item!r}")
        staff.append((email, roles))
    return staff


async def bootstrap_staff(db, spec: str, password: str, app_env: str) -> List[str]:
    """Create the listed accounts that do not exist yet. Returns the emails created."""
    if not spec.strip():
        return []
    if app_env in PRODUCTION_ENVS:
        logger.warning("BOOTSTRAP_STAFF is ignored in %s", app_env)
        return []
    if password == PLACEHOLDER or len(password) < MIN_PASSWORD_LENGTH:
        logger.warning("BOOTSTRAP_STAFF is set but BOOTSTRAP_STAFF_PASSWORD is not (12+ characters); no accounts created")
        return []

    created = []
    password_hash = get_password_hash(password)
    for email, roles in parse_staff(spec):
        existing = await db.users.find_one({"email": email}, {"_id": 0, "id": 1, "roles": 1, "created_by": 1})
        if existing:
            if existing.get("created_by") == CREATED_BY and existing.get("roles") != roles:
                await db.users.update_one({"id": existing["id"]}, {"$set": {
                    "role": roles[0], "roles": roles, "updated_at": datetime.now(timezone.utc).isoformat()}})
                logger.info("Updated roles of bootstrap login %s", email)
            continue
        now = datetime.now(timezone.utc).isoformat()
        await db.users.insert_one({
            "id": str(uuid4()),
            "email": email,
            "password_hash": password_hash,
            "full_name": email.split("@")[0].capitalize(),
            "phone": "",
            "role": roles[0],
            "roles": roles,
            "is_verified": True,
            "is_active": True,
            "created_by": CREATED_BY,
            "created_at": now,
            "updated_at": now,
        })
        created.append(email)
    if created:
        logger.info("Created %d staff login(s) from BOOTSTRAP_STAFF", len(created))
    return created
