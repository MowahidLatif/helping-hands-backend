from flask import Blueprint, jsonify
from app.utils.db import get_db_connection

public = Blueprint("public", __name__, subdomain="<org_subdomain>")


def _get_org_id_by_subdomain(cur, subdomain: str):
    cur.execute("SELECT id FROM organizations WHERE subdomain=%s", (subdomain,))
    row = cur.fetchone()
    return row[0] if row else None


@public.get("/")
def org_home(org_subdomain):
    """
    Public org landing (JSON for now).
    Returns the org subdomain and up to 20 recent campaigns (id/title/slug).
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        org_id = _get_org_id_by_subdomain(cur, org_subdomain)
        if not org_id:
            return jsonify({"error": "org not found"}), 404

        cur.execute(
            """
            SELECT id, title, slug
            FROM campaigns
            WHERE org_id=%s
            ORDER BY id DESC
            LIMIT 20
            """,
            (org_id,),
        )
        rows = cur.fetchall()

    return (
        jsonify(
            {
                "org_subdomain": org_subdomain,
                "campaigns": [{"id": r[0], "title": r[1], "slug": r[2]} for r in rows],
            }
        ),
        200,
    )


@public.get("/<camp_slug>")
def campaign_public(org_subdomain, camp_slug):
    """
    Public campaign page (JSON for now).
    Resolves org via subdomain and campaign via (org_id, slug).
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        org_id = _get_org_id_by_subdomain(cur, org_subdomain)
        if not org_id:
            return jsonify({"error": "org not found"}), 404

        cur.execute(
            """
            SELECT id, title, slug,
                   COALESCE(goal, 0) AS goal,
                   COALESCE(total_raised, 0) AS total_raised,
                   giveaway_prize_cents
            FROM campaigns
            WHERE org_id=%s AND slug=%s
            """,
            (org_id, camp_slug),
        )
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "campaign not found"}), 404

    resp = {
        "id": row[0],
        "title": row[1],
        "slug": row[2],
        "goal": float(row[3]),
        "total_raised": float(row[4]),
    }
    if row[5] is not None:
        resp["giveaway_prize_cents"] = row[5]
        resp["giveaway_prize"] = round(row[5] / 100.0, 2)
    return jsonify(resp), 200
