from __future__ import annotations

import os
import uuid
from typing import Any

from app.models.campaign import get_campaign
from app.models.donation import summarize_succeeded_donations
from app.models.org import get_organization
from app.models.settlement import (
    create_campaign_payout,
    get_campaign_settlement,
    increment_settlement_attempt,
    list_campaign_payouts,
    set_payout_status_by_payout_id,
    set_payout_status_by_transfer_id,
    set_settlement_status,
    upsert_campaign_settlement,
)
from app.services.fee_policy_service import FEE_POLICY_VERSION, normalize_fee_option

STRIPE_SECRET = (os.getenv("STRIPE_SECRET_KEY") or "").strip()
STRIPE_CURRENCY = (os.getenv("STRIPE_CURRENCY") or "usd").strip().lower()


def _serialize(out: dict[str, Any] | None) -> dict[str, Any] | None:
    if out is None:
        return None
    data = dict(out)
    for k, v in list(data.items()):
        if hasattr(v, "isoformat"):
            data[k] = v.isoformat()
    return data


def build_campaign_settlement(campaign_id: str) -> dict[str, Any]:
    campaign = get_campaign(campaign_id)
    if not campaign:
        return {"error": "campaign not found"}
    fee_option = normalize_fee_option(campaign.get("fee_option"))
    summary = summarize_succeeded_donations(campaign_id)
    settlement = upsert_campaign_settlement(
        campaign_id=campaign_id,
        org_id=campaign["org_id"],
        fee_option=fee_option,
        fee_policy_version=campaign.get("fee_policy_version") or FEE_POLICY_VERSION,
        gross_raised_cents=summary["gross_raised_cents"],
        stripe_fee_cents=summary["stripe_fee_cents"],
        platform_fee_cents=summary["platform_fee_cents"],
        donor_covered_fee_cents=summary["donor_covered_fee_cents"],
        platform_absorbed_fee_cents=summary["platform_absorbed_fee_cents"],
        refunded_cents=0,
        disputed_cents=0,
        net_payout_cents=summary["net_payout_cents"],
        status="pending",
    )
    return {"campaign": _serialize(campaign), "settlement": _serialize(settlement)}


def execute_campaign_payout(campaign_id: str) -> dict[str, Any]:
    built = build_campaign_settlement(campaign_id)
    if built.get("error"):
        return built
    settlement = built["settlement"] or {}
    campaign = built["campaign"] or {}
    org = get_organization(campaign.get("org_id"))
    if not org:
        return {"error": "organization not found"}
    if not org.get("stripe_connect_account_id"):
        return {"error": "organization payout account is not configured"}
    if not org.get("payouts_enabled"):
        return {"error": "organization payouts are disabled"}

    settlement_id = str(settlement["id"])
    amount_cents = int(settlement.get("net_payout_cents") or 0)
    if amount_cents <= 0:
        return {"error": "no payable balance for this campaign"}

    idempotency_key = f"campaign:{campaign_id}:settlement:{settlement_id}:attempt:{uuid.uuid4().hex[:12]}"
    increment_settlement_attempt(settlement_id, status="processing")

    if not STRIPE_SECRET:
        payout = create_campaign_payout(
            settlement_id=settlement_id,
            campaign_id=campaign_id,
            org_id=org["id"],
            amount_cents=amount_cents,
            currency=STRIPE_CURRENCY,
            idempotency_key=idempotency_key,
            stripe_transfer_id=None,
            stripe_payout_id=None,
            status="simulated",
            raw={"dev_mode": True},
        )
        set_settlement_status(settlement_id, "paid")
        return {
            "dev_mode": True,
            "settlement": _serialize(get_campaign_settlement(campaign_id)),
            "payout": _serialize(payout),
        }

    try:
        import stripe

        stripe.api_key = STRIPE_SECRET
        transfer = stripe.Transfer.create(
            amount=amount_cents,
            currency=STRIPE_CURRENCY,
            destination=org["stripe_connect_account_id"],
            metadata={
                "campaign_id": campaign_id,
                "org_id": str(org["id"]),
                "settlement_id": settlement_id,
            },
            idempotency_key=idempotency_key,
        )
        payout = create_campaign_payout(
            settlement_id=settlement_id,
            campaign_id=campaign_id,
            org_id=org["id"],
            amount_cents=amount_cents,
            currency=STRIPE_CURRENCY,
            idempotency_key=idempotency_key,
            stripe_transfer_id=transfer.get("id"),
            stripe_payout_id=transfer.get("destination_payment"),
            status="submitted",
            raw=(
                transfer.to_dict_recursive()
                if hasattr(transfer, "to_dict_recursive")
                else dict(transfer)
            ),
        )
        set_settlement_status(settlement_id, "paid")
        return {
            "settlement": _serialize(get_campaign_settlement(campaign_id)),
            "payout": _serialize(payout),
        }
    except Exception as exc:
        set_settlement_status(settlement_id, "failed", last_error=str(exc))
        payout = create_campaign_payout(
            settlement_id=settlement_id,
            campaign_id=campaign_id,
            org_id=org["id"],
            amount_cents=amount_cents,
            currency=STRIPE_CURRENCY,
            idempotency_key=idempotency_key,
            stripe_transfer_id=None,
            stripe_payout_id=None,
            status="failed",
            failure_reason=str(exc),
            raw={"error": str(exc)},
        )
        return {
            "error": "payout failed",
            "details": str(exc),
            "settlement": _serialize(get_campaign_settlement(campaign_id)),
            "payout": _serialize(payout),
        }


def get_campaign_finance_summary(campaign_id: str) -> dict[str, Any]:
    campaign = get_campaign(campaign_id)
    if not campaign:
        return {"error": "campaign not found"}
    running = summarize_succeeded_donations(campaign_id)
    settlement = get_campaign_settlement(campaign_id)
    payouts = list_campaign_payouts(campaign_id)
    return {
        "campaign_id": campaign_id,
        "org_id": campaign["org_id"],
        "fee_option": normalize_fee_option(campaign.get("fee_option")),
        "fee_policy_version": campaign.get("fee_policy_version") or FEE_POLICY_VERSION,
        "fee_option_locked": bool(campaign.get("fee_option_locked")),
        "running_totals": running,
        "pending_payout_cents": int(running.get("net_payout_cents") or 0),
        "settlement": _serialize(settlement),
        "payouts": [_serialize(p) for p in payouts],
    }


def reconcile_payout_event(event_type: str, obj: dict[str, Any]) -> None:
    if event_type in {"transfer.created", "transfer.updated", "transfer.paid"}:
        transfer_id = obj.get("id")
        if transfer_id:
            set_payout_status_by_transfer_id(
                transfer_id,
                status="submitted" if event_type != "transfer.paid" else "paid",
                raw=obj,
            )
    elif event_type in {"transfer.failed", "transfer.reversed"}:
        transfer_id = obj.get("id")
        if transfer_id:
            set_payout_status_by_transfer_id(transfer_id, status="failed", raw=obj)
    elif event_type in {"payout.paid", "payout.updated"}:
        payout_id = obj.get("id")
        if payout_id:
            set_payout_status_by_payout_id(payout_id, status="paid", raw=obj)
    elif event_type in {"payout.failed", "payout.canceled"}:
        payout_id = obj.get("id")
        if payout_id:
            set_payout_status_by_payout_id(payout_id, status="failed", raw=obj)
