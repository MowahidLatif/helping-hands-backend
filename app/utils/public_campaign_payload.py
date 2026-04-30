"""Build the public campaign JSON dict shared by core and subdomain public routes."""

from typing import Any

from app.models.campaign import get_latest_winner_public


def build_public_campaign_dict(
    row: tuple[Any, ...], campaign_id_str: str
) -> dict[str, Any]:
    """
    row columns: id, title, slug, status, goal, total_raised, giveaway_prize_cents,
    page_layout, ai_site_recipe
    """
    resp: dict[str, Any] = {
        "id": str(row[0]),
        "title": row[1],
        "slug": row[2],
        "status": row[3],
        "goal": float(row[4]),
        "total_raised": float(row[5]),
    }
    if row[6] is not None:
        resp["giveaway_prize_cents"] = row[6]
        resp["giveaway_prize"] = round(row[6] / 100.0, 2)
    if row[7] is not None:
        resp["page_layout"] = row[7]
    if row[8] is not None:
        resp["ai_site_recipe"] = row[8]
    latest = get_latest_winner_public(campaign_id_str)
    if latest:
        resp["latest_winner"] = latest
    return resp
