from flask import Blueprint, request, jsonify
from psycopg2.errors import UniqueViolation

from app.models.waitlist import create_waitlist_entry
from app.utils.rate_limit import rate_limit_decorator

waitlist_bp = Blueprint("waitlist", __name__)


@waitlist_bp.post("/")
@rate_limit_decorator(limit_per_minute=30, key_prefix="waitlist")
def join_waitlist():
    data = request.get_json(silent=True) or {}

    first_name = (data.get("first_name") or "").strip()
    last_name = (data.get("last_name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    phone = (data.get("phone") or "").strip() or None

    if not first_name or not last_name or not email:
        return jsonify({"error": "first_name, last_name, and email are required."}), 400

    try:
        create_waitlist_entry(first_name, last_name, email, phone)
        return jsonify({"message": "You're on the list!"}), 201
    except UniqueViolation:
        return jsonify({"error": "This email is already on the waitlist."}), 409
