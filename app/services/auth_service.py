from app.models.user import get_user_by_email, create_user
import re
import bcrypt
from typing import Dict, Any
from flask_jwt_extended import create_access_token, create_refresh_token
from app.models.org import create_organization
from app.models.org_user import add_user_to_org, get_primary_org_role

EMAIL_RE = re.compile(r"^[^@]+@[^@]+\.[^@]+$")


def _normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        return False


def _make_tokens(
    user_id: str, extra_claims: Dict[str, Any] | None = None
) -> Dict[str, str]:
    claims = extra_claims or {}
    return {
        "access_token": create_access_token(identity=user_id, additional_claims=claims),
        "refresh_token": create_refresh_token(
            identity=user_id, additional_claims=claims
        ),
    }


def signup_user(data: dict) -> dict:
    email = _normalize_email(data.get("email", ""))
    password = data.get("password") or ""
    name = (data.get("name") or "").strip() or None
    org_name = (data.get("organization_name") or "").strip() or None

    if not EMAIL_RE.match(email):
        return {"error": "Invalid email format"}
    if len(password) < 8:
        return {"error": "Password must be at least 8 characters"}
    if get_user_by_email(email):
        return {"error": "Email already registered"}

    user = create_user(email=email, password_hash=_hash_password(password), name=name)
    if not org_name:
        org_name = email.split("@", 1)[0] + "'s Org"
    org = create_organization(org_name)
    add_user_to_org(org_id=org["id"], user_id=user["id"], role="owner")

    tokens = _make_tokens(user["id"], {"org_id": org["id"], "role": "owner"})
    return {"id": user["id"], "email": user["email"], "org_id": org["id"], **tokens}


def login_user(data: dict) -> dict:
    email = _normalize_email(data.get("email", ""))
    password = data.get("password") or ""

    user = get_user_by_email(email)
    if not user or not _verify_password(password, user["password_hash"]):
        return {"error": "Invalid credentials"}

    org_role = get_primary_org_role(user["id"])
    claims = {}
    if org_role:
        claims = {"org_id": org_role[0], "role": org_role[1]}

    tokens = _make_tokens(user["id"], claims)
    return {"id": user["id"], "email": user["email"], **tokens}
