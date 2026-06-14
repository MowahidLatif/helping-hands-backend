import logging
from flask import Blueprint, request, jsonify
from app.services.webhook_service import process_stripe_event

webhooks_bp = Blueprint("webhooks", __name__)
logger = logging.getLogger(__name__)


@webhooks_bp.post("/webhooks/stripe")
def stripe_webhook():
    try:
        status, resp = process_stripe_event(
            payload=request.data,
            sig_header=request.headers.get("Stripe-Signature"),
        )
        return jsonify(resp), status
    except Exception as e:
        logger.error("stripe webhook error: %s", e)
        return jsonify({"error": "bad payload"}), 400


@webhooks_bp.post("/webhooks/sendgrid")
def sendgrid_webhook():
    from app.services.sendgrid_webhook_service import _verify_signature, process_sendgrid_events
    signature = request.headers.get("X-Twilio-Email-Event-Webhook-Signature")
    timestamp = request.headers.get("X-Twilio-Email-Event-Webhook-Timestamp")
    if not _verify_signature(request.data, signature, timestamp):
        return jsonify({"error": "invalid signature"}), 403
    try:
        events = request.get_json(force=True, silent=True) or []
        if not isinstance(events, list):
            events = [events]
        process_sendgrid_events(events)
        return jsonify({"ok": True}), 200
    except Exception as e:
        logger.error("sendgrid webhook error: %s", e)
        return jsonify({"error": "bad payload"}), 400
