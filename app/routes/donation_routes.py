from flask import jsonify, Blueprint, request
from app.services.donation_service import start_checkout
from app.models.donation import get_donation


def _mask_email(email: str | None) -> str | None:
    if not email:
        return None
    local, _, domain = email.partition("@")
    if not domain:
        return email
    if len(local) <= 2:
        masked = local[:1] + "***"
    else:
        masked = local[0] + "***" + local[-1]
    return masked + "@" + domain


donations_bp = Blueprint("donations", __name__)


@donations_bp.get("/api/donations/<donation_id>")
def get_one(donation_id):
    d = get_donation(donation_id)
    if not d:
        return jsonify({"error": "not found"}), 404
    return (
        jsonify(
            {
                "id": d["id"],
                "campaign_id": d["campaign_id"],
                "amount_cents": d["amount_cents"],
                "currency": d["currency"],
                "donor": _mask_email(d.get("donor_email")),
                "message": d.get("message"),
                "status": d["status"],
                "created_at": (
                    d.get("created_at").isoformat() if d.get("created_at") else None
                ),
            }
        ),
        200,
    )


@donations_bp.post("/api/donations/checkout")
def checkout():
    body = request.get_json(force=True, silent=True) or {}
    campaign_id = body.get("campaign_id")
    amount = body.get("amount")
    donor_email = (body.get("donor_email") or "").strip() or None
    message = (body.get("message") or "").strip() or None
    if not campaign_id or amount is None:
        return jsonify({"error": "campaign_id and amount are required"}), 400
    try:
        amount = float(amount)
    except Exception:
        return jsonify({"error": "amount must be a number"}), 400

    resp = start_checkout(
        campaign_id=campaign_id,
        amount=amount,
        donor_email=donor_email,
        message=message,
    )
    return jsonify(resp), (200 if "clientSecret" in resp else 400)
