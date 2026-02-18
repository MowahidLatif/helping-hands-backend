from datetime import timedelta

from app.models.user import (
    get_user_by_email,
    get_user_by_id,
    create_user,
    update_password as model_update_password,
    anonymize_user as model_anonymize_user,
    get_user_totp_secret,
    set_totp_secret as model_set_totp_secret,
    set_totp_enabled as model_set_totp_enabled,
    clear_totp as model_clear_totp,
)
import re
import bcrypt
import pyotp
import qrcode
import io
import base64
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

    # Support both old and new field names
    first_name = (data.get("first_name") or "").strip()
    last_name = (data.get("last_name") or "").strip()
    name = (data.get("name") or "").strip()
    if not name and (first_name or last_name):
        name = f"{first_name} {last_name}".strip()
    name = name or None

    # Support both org_name and organization_name
    org_name = (
        data.get("org_name") or data.get("organization_name") or ""
    ).strip() or None
    org_subdomain = (data.get("org_subdomain") or "").strip() or None

    if not EMAIL_RE.match(email):
        return {"error": "Invalid email format"}
    if len(password) < 8:
        return {"error": "Password must be at least 8 characters"}
    if get_user_by_email(email):
        return {"error": "Email already registered"}

    user = create_user(email=email, password_hash=_hash_password(password), name=name)
    if not org_name:
        org_name = email.split("@", 1)[0] + "'s Org"
    org = create_organization(org_name, subdomain=org_subdomain)
    add_user_to_org(org_id=org["id"], user_id=user["id"], role="owner")

    tokens = _make_tokens(user["id"], {"org_id": org["id"], "role": "owner"})
    return {
        "id": user["id"],
        "email": user["email"],
        "name": user.get("name"),
        "org_id": org["id"],
        **tokens,
    }


def login_user(data: dict) -> dict:
    email = _normalize_email(data.get("email", ""))
    password = data.get("password") or ""

    user = get_user_by_email(email)
    if not user or not _verify_password(password, user["password_hash"]):
        return {"error": "Invalid credentials"}

    totp_enabled = user.get("totp_enabled", False)
    user_id = str(user["id"])
    if totp_enabled:
        temp_token = create_access_token(
            identity=user_id,
            additional_claims={"pre_2fa": True},
            expires_delta=timedelta(minutes=5),
        )
        return {"requires_2fa": True, "temp_token": temp_token}

    org_role = get_primary_org_role(user_id)
    claims = {}
    if org_role:
        claims = {"org_id": org_role[0], "role": org_role[1]}

    tokens = _make_tokens(user_id, claims)
    return {
        "id": user_id,
        "email": user["email"],
        "name": user.get("name"),
        **tokens,
    }


def change_password(user_id: str, current_password: str, new_password: str) -> dict:
    """
    Verify current password, then set new password (hashed).
    Returns {"success": True} or {"error": "..."}.
    """
    if not new_password or len(new_password) < 8:
        return {"error": "Password must be at least 8 characters"}
    user = get_user_by_id(user_id)
    if not user:
        return {"error": "User not found"}
    if not _verify_password(current_password, user["password_hash"]):
        return {"error": "Current password is incorrect"}
    model_update_password(user_id, _hash_password(new_password))
    return {"success": True}


def _unusable_password_hash() -> str:
    """Return a bcrypt hash that will never match any login (for anonymized users)."""
    return bcrypt.hashpw(b"anonymized", bcrypt.gensalt()).decode("utf-8")


def delete_account(user_id: str, password: str, totp_code: str | None = None) -> dict:
    """
    Verify password (and TOTP if enabled), then anonymize user. No hard delete.
    Returns {"success": True} or {"error": "..."}.
    """
    user = get_user_by_id(user_id)
    if not user:
        return {"error": "User not found"}
    if not _verify_password(password, user["password_hash"]):
        return {"error": "Password is incorrect"}
    if user.get("totp_enabled"):
        if not totp_code or len(totp_code) != 6:
            return {"error": "2FA code required"}
        secret = get_user_totp_secret(user_id)
        if not secret or not pyotp.TOTP(secret).verify(totp_code, valid_window=1):
            return {"error": "Invalid 2FA code"}
    model_anonymize_user(user_id, _unusable_password_hash())
    return {"success": True}


def setup_2fa(user_id: str) -> dict:
    """Generate TOTP secret, store it (totp_enabled=false), return secret, uri, qr_data_url."""
    user = get_user_by_id(user_id)
    if not user:
        return {"error": "User not found"}
    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret)
    provisioning_uri = totp.provisioning_uri(
        name=user.get("email") or str(user_id),
        issuer_name="Donations",
    )
    model_set_totp_secret(user_id, secret)
    qr = qrcode.QRCode(box_size=3, border=2)
    qr.add_data(provisioning_uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    qr_data_url = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    return {
        "secret": secret,
        "provisioning_uri": provisioning_uri,
        "qr_data_url": qr_data_url,
    }


def verify_2fa(user_id: str, code: str) -> dict:
    """Verify TOTP code and enable 2FA."""
    if not code or len(code) != 6:
        return {"error": "Invalid code"}
    secret = get_user_totp_secret(user_id)
    if not secret:
        return {"error": "2FA not set up"}
    if not pyotp.TOTP(secret).verify(code, valid_window=1):
        return {"error": "Invalid code"}
    model_set_totp_enabled(user_id)
    return {"success": True}


def disable_2fa(user_id: str, password: str, code: str) -> dict:
    """Verify password and TOTP code, then disable 2FA."""
    user = get_user_by_id(user_id)
    if not user:
        return {"error": "User not found"}
    if not _verify_password(password, user["password_hash"]):
        return {"error": "Password is incorrect"}
    if not code or len(code) != 6:
        return {"error": "2FA code required"}
    secret = get_user_totp_secret(user_id)
    if not secret or not pyotp.TOTP(secret).verify(code, valid_window=1):
        return {"error": "Invalid 2FA code"}
    model_clear_totp(user_id)
    return {"success": True}


def confirm_2fa_login(temp_token: str, code: str) -> dict:
    """
    Exchange temp_token (pre_2fa JWT) + TOTP code for real access and refresh tokens.
    Caller must decode temp_token and pass user_id; we verify TOTP and issue tokens.
    """
    if not code or len(code) != 6:
        return {"error": "Invalid code"}
    # Decode temp_token to get user_id (pre_2fa JWT from login when 2FA enabled)
    from flask_jwt_extended import decode_token

    try:
        decoded = decode_token(temp_token)
        if not decoded.get("pre_2fa") or not decoded.get("sub"):
            return {"error": "Invalid token"}
        user_id = str(decoded["sub"])
    except Exception:
        return {"error": "Invalid or expired token"}
    secret = get_user_totp_secret(user_id)
    if not secret or not pyotp.TOTP(secret).verify(code, valid_window=1):
        return {"error": "Invalid code"}
    org_role = get_primary_org_role(user_id)
    claims = {}
    if org_role:
        claims = {"org_id": org_role[0], "role": org_role[1]}
    tokens = _make_tokens(user_id, claims)
    user = get_user_by_id(user_id)
    return {
        "id": user["id"],
        "email": user["email"],
        "name": user.get("name"),
        **tokens,
    }
