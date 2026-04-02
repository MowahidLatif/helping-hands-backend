from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.services.platform_ai_payment import (
    create_ai_generation_payment_intent,
    require_payment_for_ai,
)

platform_bp = Blueprint("platform", __name__)


@platform_bp.post("/api/platform/ai-generation/checkout")
@jwt_required()
def ai_generation_checkout():
    if not require_payment_for_ai():
        return (
            jsonify(
                {
                    "error": "platform payment for AI generation is not enabled",
                    "hint": "Set REQUIRE_PLATFORM_PAYMENT_FOR_AI=1 and STRIPE_AI_GENERATION_AMOUNT_CENTS",
                }
            ),
            400,
        )
    user_id = get_jwt_identity()
    body = request.get_json(silent=True) or {}
    # Reserved for future: org_id validation
    _ = body.get("org_id")
    resp = create_ai_generation_payment_intent(user_id=str(user_id))
    if resp.get("error"):
        return jsonify(resp), 400
    return jsonify(resp), 200
