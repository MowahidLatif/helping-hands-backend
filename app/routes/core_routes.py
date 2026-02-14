import os
from flask import Blueprint, jsonify, request, send_from_directory
from app.utils.page_layout import BLOCK_TYPES, BLOCK_SCHEMA
from app.utils.db import get_db_connection
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

core = Blueprint("core", __name__)

_STATIC = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "static")


@core.get("/donate/<org_subdomain>/<camp_slug>")
def donate_page_no_subdomain(org_subdomain, camp_slug):
    """
    Donor page when using 127.0.0.1 (no subdomain). Use: /donate/demo/help-build-school
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM organizations WHERE subdomain=%s", (org_subdomain,))
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "org not found"}), 404
        cur.execute(
            "SELECT 1 FROM campaigns WHERE org_id=%s AND slug=%s",
            (row[0], camp_slug),
        )
        if not cur.fetchone():
            return jsonify({"error": "campaign not found"}), 404
    return send_from_directory(_STATIC, "donate_page.html")


@core.get("/api/public/<org_subdomain>/<camp_slug>")
def campaign_public_no_subdomain(org_subdomain, camp_slug):
    """
    Campaign JSON when using 127.0.0.1 (no subdomain). For donate page to fetch.
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM organizations WHERE subdomain=%s", (org_subdomain,))
        org_row = cur.fetchone()
        if not org_row:
            return jsonify({"error": "org not found"}), 404
        org_id = org_row[0]
        cur.execute(
            """
            SELECT id, title, slug,
                   COALESCE(goal, 0) AS goal,
                   COALESCE(total_raised, 0) AS total_raised,
                   giveaway_prize_cents,
                   page_layout
            FROM campaigns
            WHERE org_id=%s AND slug=%s
            """,
            (org_id, camp_slug),
        )
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "campaign not found"}), 404

    resp = {
        "id": str(row[0]),
        "title": row[1],
        "slug": row[2],
        "goal": float(row[3]),
        "total_raised": float(row[4]),
    }
    if row[5] is not None:
        resp["giveaway_prize_cents"] = row[5]
        resp["giveaway_prize"] = round(row[5] / 100.0, 2)
    if row[6] is not None:
        resp["page_layout"] = row[6]
    return jsonify(resp), 200


@core.get("/api/page-layout/schema")
def page_layout_schema():
    """Return block types and schema for page builder UI."""
    return jsonify({"block_types": sorted(BLOCK_TYPES), "schema": BLOCK_SCHEMA})


@core.get("/campaign-stub")
def campaign_stub():
    """Serve campaign stub UI for E2E testing."""
    return send_from_directory(_STATIC, "campaign_stub.html")


@core.get("/")
def root():
    return jsonify({"service": "donations-api", "ok": True})


@core.get("/api")
def api_index():
    return jsonify(
        {
            "endpoints": {
                "auth": ["/api/auth/login (POST)", "/api/auth/signup (POST)"],
                "users": ["/api/users ..."],
            }
        }
    )


@core.get("/api/me")
@jwt_required()
def me():
    claims = get_jwt()
    auth_header = request.headers.get("Authorization", "")
    return jsonify(
        {
            "user_id": get_jwt_identity(),
            "org_id": claims.get("org_id"),
            "role": claims.get("role"),
            "token_preview": (
                auth_header[:50] + "..." if len(auth_header) > 50 else auth_header
            ),
        }
    )
