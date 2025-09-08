from flask import Blueprint, request, jsonify
from app.services.webhook_service import process_stripe_event

webhooks_bp = Blueprint("webhooks", __name__)


@webhooks_bp.post("/webhooks/stripe")
def stripe_webhook():
    try:
        status, resp = process_stripe_event(
            payload=request.data,
            sig_header=request.headers.get("Stripe-Signature"),
        )
        return jsonify(resp), status
    except Exception as e:
        # Never leak stack traces to Stripe; just log in server console.
        print(f"[webhook error] {e}")
        return jsonify({"error": "bad payload"}), 400
