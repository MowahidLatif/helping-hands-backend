from flask import Blueprint, request

# from app.services.donation_service import (
#     create_donation, get_donations_for_campaign
# )
from flask import jsonify
from app.services.donation_service import start_checkout

donations_bp = Blueprint("donations", __name__)


@donations_bp.post("/api/donations/checkout")
def checkout():
    body = request.get_json(force=True, silent=True) or {}
    campaign_id = body.get("campaign_id")
    amount = body.get("amount")
    donor_email = (body.get("donor_email") or "").strip() or None
    if not campaign_id or amount is None:
        return jsonify({"error": "campaign_id and amount are required"}), 400
    try:
        amount = float(amount)
    except Exception:
        return jsonify({"error": "amount must be a number"}), 400

    resp = start_checkout(
        campaign_id=campaign_id, amount=amount, donor_email=donor_email
    )
    return jsonify(resp), (200 if "clientSecret" in resp else 400)
