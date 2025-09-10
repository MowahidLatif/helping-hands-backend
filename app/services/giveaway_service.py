from __future__ import annotations
from typing import Dict, Any, Tuple, List, Optional

# import secrets
import hashlib
from datetime import datetime
from secrets import choice

# from app.models.campaign import get_campaign_by_id, insert_giveaway_log, get_campaign
# from app.models.donation import list_succeeded_for_campaign
# from app.models.org_user import get_user_role_in_org

from app.models.campaign import get_campaign_by_id, insert_giveaway_log
from app.models.donation import list_succeeded_for_campaign, get_donation
from app.models.org_user import get_user_role_in_org


def _mask_email(e: Optional[str]) -> Optional[str]:
    if not e:
        return None
    local, _, domain = e.partition("@")
    if not domain:
        return e
    if len(local) <= 2:
        masked = local[:1] + "***"
    else:
        masked = local[0] + "***" + local[-1]
    return masked + "@" + domain


def _population_hash(donation_ids: List[str], mode: str, min_amount_cents: int) -> str:
    m = hashlib.sha256()
    m.update(f"{mode}|{min_amount_cents}|".encode("utf-8"))
    m.update(",".join(donation_ids).encode("utf-8"))
    return m.hexdigest()


def _serialize_donation_row(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "campaign_id": row["campaign_id"],
        "org_id": row["org_id"],
        "amount_cents": int(row["amount_cents"]),
        "amount": round(int(row["amount_cents"]) / 100.0, 2),
        "currency": row.get("currency", "usd"),
        "donor_email": row.get("donor_email"),
        "donor": _mask_email(row.get("donor_email")),
        "created_at": (
            row["created_at"].isoformat() if row.get("created_at") else None
        ),
    }


def _serialize_winner(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Accepts either a full donation row (get_donation)
    or the minimal population dict from list_succeeded_for_campaign.
    """
    donation_id = row.get("id") or row.get("donation_id")
    amount_cents = int(row.get("amount_cents") or 0)
    donor_email = row.get("donor_email")
    currency = row.get("currency", "usd")

    created_at = row.get("created_at")
    if hasattr(created_at, "isoformat"):
        created_at = created_at.isoformat()

    return {
        "id": donation_id,
        "amount_cents": amount_cents,
        "amount": round(amount_cents / 100.0, 2),
        "currency": currency,
        "donor_email": donor_email,
        "donor": _mask_email(donor_email),
        "created_at": created_at,
    }


def _serialize_donation(row: Dict[str, Any]) -> Dict[str, Any]:
    # Ensure all fields are JSON-safe
    return {
        "id": row["id"],
        "campaign_id": row["campaign_id"],
        "org_id": row["org_id"],
        "amount_cents": int(row["amount_cents"]),
        "amount": round(int(row["amount_cents"]) / 100.0, 2),
        "currency": row.get("currency", "usd"),
        "donor_email": row.get("donor_email"),
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
    }


def draw_winner_for_campaign(
    campaign_id: str,
    current_user_id: str,
    mode: str = "per_donation",
    min_amount_cents: int = 0,
    notes: Optional[str] = None,
) -> Tuple[int, Dict[str, Any]]:
    camp = get_campaign_by_id(campaign_id)
    if not camp:
        return 404, {"error": "campaign not found"}

    org_id = camp["org_id"]

    role = get_user_role_in_org(current_user_id, org_id)
    if role not in ("owner", "admin"):
        return 403, {"error": "forbidden"}

    population: List[Dict[str, Any]] = list_succeeded_for_campaign(
        campaign_id=campaign_id,
        mode=mode,
        min_amount_cents=min_amount_cents,
    )
    if not population:
        return 400, {"error": "no eligible donations"}

    donation_ids = [p["donation_id"] for p in population]
    pop_hash = _population_hash(donation_ids, mode, min_amount_cents)

    winner = choice(population)
    winner_id = winner["donation_id"]

    # Load the full donation row for clean JSON
    full = get_donation(winner_id)
    if not full:
        # extremely unlikely, fallback to minimal info
        full = {
            "id": winner_id,
            "campaign_id": campaign_id,
            "org_id": org_id,
            "amount_cents": int(winner.get("amount_cents", 0)),
            "currency": "usd",
            "donor_email": winner.get("donor_email"),
            "created_at": None,
        }

    log = insert_giveaway_log(
        org_id=org_id,
        campaign_id=campaign_id,
        winner_donation_id=winner_id,
        created_by_user_id=current_user_id,
        mode=mode,
        population_count=len(population),
        population_hash=pop_hash,
        notes=notes,
    )

    payload = {
        "winner": _serialize_donation_row(full),
        "draw": {
            "mode": mode,
            "population_count": int(len(population)),
            "population_hash": pop_hash,
            "created_at": (
                log["created_at"].isoformat()
                if isinstance(log, dict) and log.get("created_at")
                else datetime.utcnow().isoformat()
            ),
            "notes": notes,
        },
    }
    return 200, payload
