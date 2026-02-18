"""
Contact form API: send submission via email to a fixed address; rate limit by submitter email.
"""

import os
import re
import html
from flask import Blueprint, request, jsonify
from app.utils.rate_limit import is_rate_limited
from app.utils.email_sender import send_email

contact_bp = Blueprint("contact", __name__)

EMAIL_RE = re.compile(r"^[^@]+@[^@]+\.[^@]+$")
CONTACT_WINDOW = 3600  # 1 hour in seconds


@contact_bp.post("/api/contact")
def submit_contact():
    """Accept contact form submission; validate, rate limit by email, send to CONTACT_TO_EMAIL."""
    data = request.get_json(force=True, silent=True) or {}
    first_name = (data.get("first_name") or "").strip()
    last_name = (data.get("last_name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    message = (data.get("message") or "").strip()

    if not first_name:
        return jsonify({"error": "first_name is required"}), 400
    if not last_name:
        return jsonify({"error": "last_name is required"}), 400
    if not email:
        return jsonify({"error": "email is required"}), 400
    if not EMAIL_RE.match(email):
        return jsonify({"error": "invalid email format"}), 400
    if not message:
        return jsonify({"error": "message is required"}), 400

    limit = int(os.getenv("CONTACT_RATE_LIMIT_PER_HOUR", "5"))
    if limit > 0:
        key = f"contact:{email}"
        if is_rate_limited(key, limit, window_seconds=CONTACT_WINDOW):
            return (
                jsonify(
                    {"error": "rate limit exceeded", "retry_after": CONTACT_WINDOW}
                ),
                429,
            )

    to_email = os.getenv("CONTACT_TO_EMAIL", "").strip()
    if not to_email:
        return jsonify({"error": "contact form not configured"}), 503

    full_name = f"{first_name} {last_name}"
    subject = f"Contact form: from {email}"
    body_text = f"From: {full_name} <{email}>\n\n{message}"
    body_html = f"<p><strong>From:</strong> {html.escape(full_name)} &lt;{html.escape(email)}&gt;</p><pre>{html.escape(message)}</pre>"

    provider, msg_or_err = send_email(
        to_email=to_email,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
    )
    if provider is None:
        return jsonify({"error": "Failed to send message"}), 500

    return jsonify({"message": "Message sent"}), 200
