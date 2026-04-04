import os
import json
from typing import Tuple, Dict, Any

from app.models.donation import (
    get_donation_by_pi,
    set_status_by_pi,
    attach_pi_to_donation,
    set_status_by_id,
    get_donation,
    update_donation_accounting,
)
from app.models.campaign import (
    get_campaign,
    recompute_total_raised,
    complete_campaign_if_goal_reached,
    record_platform_fee_if_goal_reached,
)
from app.utils.cache import r
from app.utils.public_campaign_cache import invalidate_public_campaign_cache
from app.realtime import socketio
from app.models.stripe_event import mark_event_processed
from app.tasks import enqueue_receipt_email, enqueue_campaign_payout
from app.services.fee_policy_service import (
    build_donation_accounting,
    estimate_stripe_processing_fee_cents,
    normalize_fee_option,
)
from app.services.settlement_service import reconcile_payout_event

STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()
DEV_SKIP = os.getenv("DEV_STRIPE_NO_VERIFY") == "1"
STRIPE_SECRET = os.getenv("STRIPE_SECRET_KEY", "").strip()


def _mask_email(e: str | None) -> str | None:
    if not e:
        return None
    local, _, domain = e.partition("@")
    if not domain:
        return e
    if len(local) <= 2:
        masked = local[0:1] + "***"
    else:
        masked = local[0] + "***" + local[-1]
    return masked + "@" + domain


def _extract_event(
    payload: bytes, sig_header: str | None
) -> tuple[str | None, dict | None, dict]:
    """
    Return (event_type, data.object, raw_event_dict).

    - If STRIPE_WEBHOOK_SECRET is set and DEV_STRIPE_NO_VERIFY != 1, verify the signature.
    - Otherwise (dev mode), parse the JSON payload as-is.
    """
    if STRIPE_WEBHOOK_SECRET and not DEV_SKIP:
        import stripe

        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header or "",
            secret=STRIPE_WEBHOOK_SECRET,
        )
        event_dict = event.to_dict() if hasattr(event, "to_dict") else dict(event)
        ev_type = event_dict.get("type")
        obj = (event_dict.get("data") or {}).get("object") or {}
        return ev_type, obj, event_dict

    try:
        raw = json.loads(payload.decode("utf-8") or "{}")
    except Exception:
        raw = {}

    if isinstance(raw, dict) and "type" in raw and "data" in raw:
        ev_type = raw.get("type")
        obj = (raw.get("data") or {}).get("object") or {}
        return ev_type, obj, raw

    wrapped = {"type": raw.get("type") or "", "data": {"object": raw}}
    ev_type = wrapped["type"]
    obj = raw
    return ev_type, obj, wrapped


def _find_donation(pi_id: str | None, donation_id: str | None) -> dict | None:
    if donation_id:
        d = get_donation(donation_id)
        if d:
            return d
    if pi_id:
        return get_donation_by_pi(pi_id)
    return None


def _extract_stripe_fee_from_obj(obj: dict | None) -> tuple[str | None, int]:
    data = obj or {}
    bt = data.get("balance_transaction")
    if isinstance(bt, dict):
        fee = bt.get("fee")
        bt_id = bt.get("id")
        if fee is not None:
            return bt_id, int(fee)
    if isinstance(bt, str):
        if STRIPE_SECRET:
            try:
                import stripe

                stripe.api_key = STRIPE_SECRET
                row = stripe.BalanceTransaction.retrieve(bt)
                return bt, int(row.get("fee") or 0)
            except Exception:
                return bt, 0
        return bt, 0
    if STRIPE_SECRET:
        charge_id = data.get("latest_charge")
        if isinstance(charge_id, str):
            try:
                import stripe

                stripe.api_key = STRIPE_SECRET
                charge = stripe.Charge.retrieve(
                    charge_id, expand=["balance_transaction"]
                )
                balance_tx = charge.get("balance_transaction")
                if isinstance(balance_tx, dict):
                    return balance_tx.get("id"), int(balance_tx.get("fee") or 0)
            except Exception:
                pass
    return None, 0


def _resolve_event_context(
    obj: dict | None,
) -> tuple[str | None, str | None, str | None]:
    data = obj or {}
    metadata = data.get("metadata") or {}

    donation_id = metadata.get("donation_id")
    campaign_id = metadata.get("campaign_id")

    pi_id = data.get("id") if str(data.get("id", "")).startswith("pi_") else None
    if not pi_id:
        maybe_pi = data.get("payment_intent")
        if isinstance(maybe_pi, str) and maybe_pi.startswith("pi_"):
            pi_id = maybe_pi

    return pi_id, donation_id, campaign_id


def _apply_status_update(
    *,
    pi_id: str | None,
    donation_id: str | None,
    campaign_id: str | None,
    new_status: str,
    enqueue_receipt: bool = False,
    emit_socket: bool = False,
    event_obj: dict | None = None,
) -> None:
    d = _find_donation(pi_id=pi_id, donation_id=donation_id)
    if d and pi_id and not d.get("stripe_payment_intent_id"):
        attach_pi_to_donation(d["id"], pi_id)

    if d and d.get("stripe_payment_intent_id"):
        set_status_by_pi(d["stripe_payment_intent_id"], new_status)
        d = get_donation(d["id"])
    elif donation_id:
        set_status_by_id(donation_id, new_status)
        d = get_donation(donation_id)

    if enqueue_receipt and (d or {}).get("id"):
        try:
            enqueue_receipt_email((d or {}).get("id"))
        except Exception as e:
            print("[email receipt error]", str(e))

    if new_status == "succeeded" and d:
        campaign = get_campaign((d or {}).get("campaign_id"))
        if campaign:
            fee_option = normalize_fee_option(campaign.get("fee_option"))
            stripe_bt_id, stripe_fee_cents = _extract_stripe_fee_from_obj(event_obj)
            if stripe_fee_cents <= 0:
                metadata = (event_obj or {}).get("metadata") or {}
                try:
                    charge_amount_cents = int(
                        metadata.get("charge_amount_cents")
                        or int((d or {}).get("amount_cents") or 0)
                    )
                except Exception:
                    charge_amount_cents = int((d or {}).get("amount_cents") or 0)
                stripe_fee_cents = estimate_stripe_processing_fee_cents(
                    charge_amount_cents
                )
            accounting = build_donation_accounting(
                fee_option=fee_option,
                campaign_total_dollars=float(campaign.get("total_raised") or 0)
                + (int((d or {}).get("amount_cents") or 0) / 100.0),
                amount_cents=int((d or {}).get("amount_cents") or 0),
                stripe_processing_fee_cents=int(stripe_fee_cents),
            )
            update_donation_accounting(
                donation_id=str(d["id"]),
                fee_option=accounting.fee_option,
                fee_policy_version=campaign.get("fee_policy_version")
                or accounting.fee_policy_version,
                stripe_balance_transaction_id=stripe_bt_id,
                stripe_processing_fee_cents=accounting.stripe_processing_fee_cents,
                platform_fee_percent=accounting.platform_fee_percent,
                platform_fee_cents=accounting.platform_fee_cents,
                donor_fee_cents=accounting.donor_fee_cents,
                platform_absorbed_fee_cents=accounting.platform_absorbed_fee_cents,
                net_to_org_cents=accounting.net_to_org_cents,
            )

    cid = (d or {}).get("campaign_id") or campaign_id
    if not cid:
        return

    totals = recompute_total_raised(cid)
    try:
        r().delete(f"campaign:{cid}:progress:v1")
    except Exception as e:
        print(f"[error] redis cache bust campaign:{cid}: {e}", flush=True)
    invalidate_public_campaign_cache(str(cid))

    if new_status == "succeeded":
        try:
            record_platform_fee_if_goal_reached(cid)
        except Exception as fee_err:
            print("[platform fee error]", str(fee_err))
        try:
            completed_now = complete_campaign_if_goal_reached(cid)
            if completed_now:
                enqueue_campaign_payout(cid)
        except Exception as completion_err:
            print("[campaign complete/payout error]", str(completion_err))

    if emit_socket and new_status == "succeeded":
        amount_cents = int((d or {}).get("amount_cents") or 0)
        donor_email = (d or {}).get("donor_email")
        payload_out = {
            "campaign_id": cid,
            "amount_cents": amount_cents,
            "amount": round(amount_cents / 100.0, 2),
            "donor": _mask_email(donor_email),
            "total_raised": float(totals["total_raised"]),
            "currency": (d or {}).get("currency", "usd"),
        }
        try:
            socketio.emit("donation", payload_out, to=f"campaign:{cid}")
        except Exception as e:
            print(
                f"[error] socketio emit donation campaign:{cid}: {e}",
                flush=True,
            )


def process_stripe_event(
    payload: bytes, sig_header: str | None
) -> Tuple[int, Dict[str, Any]]:
    """
    Handle selected Stripe events idempotently.
    """
    ev_type, obj, raw_event = _extract_event(payload, sig_header)

    pi_id = (obj or {}).get("id")
    donation_id = ((obj or {}).get("metadata") or {}).get("donation_id")
    event_id = (raw_event or {}).get(
        "id"
    ) or f"dev:{ev_type}:{pi_id or 'nopi'}:{donation_id or 'nodon'}"

    try:
        inserted = mark_event_processed(event_id, ev_type or "unknown", raw_event or {})
    except Exception as e:
        print("[webhook error]", str(e))
        return 400, {"error": "bad payload"}

    if not inserted:
        return 200, {"ok": True, "duplicate": True}

    if ev_type in {
        "payment_intent.succeeded",
        "payment_intent.payment_failed",
        "payment_intent.canceled",
    }:
        pi_id, donation_id, campaign_id = _resolve_event_context(obj)
        new_status = (
            "succeeded"
            if ev_type == "payment_intent.succeeded"
            else "canceled" if ev_type == "payment_intent.canceled" else "failed"
        )
        _apply_status_update(
            pi_id=pi_id,
            donation_id=donation_id,
            campaign_id=campaign_id,
            new_status=new_status,
            enqueue_receipt=new_status == "succeeded",
            emit_socket=new_status == "succeeded",
            event_obj=obj,
        )
        return 200, {"ok": True}

    if ev_type == "charge.refunded":
        pi_id, donation_id, campaign_id = _resolve_event_context(obj)
        _apply_status_update(
            pi_id=pi_id,
            donation_id=donation_id,
            campaign_id=campaign_id,
            new_status="refunded",
            event_obj=obj,
        )
        return 200, {"ok": True}

    if ev_type in {
        "charge.dispute.created",
        "charge.dispute.updated",
        "charge.dispute.funds_withdrawn",
        "charge.dispute.funds_reinstated",
        "charge.dispute.closed",
    }:
        pi_id, donation_id, campaign_id = _resolve_event_context(obj)
        dispute_status = ((obj or {}).get("status") or "").lower()
        if ev_type in {"charge.dispute.funds_reinstated"}:
            new_status = "succeeded"
        elif ev_type == "charge.dispute.closed" and dispute_status == "won":
            new_status = "succeeded"
        else:
            new_status = "refunded"
        _apply_status_update(
            pi_id=pi_id,
            donation_id=donation_id,
            campaign_id=campaign_id,
            new_status=new_status,
            event_obj=obj,
        )
        return 200, {"ok": True}

    if ev_type in {
        "transfer.created",
        "transfer.updated",
        "transfer.paid",
        "transfer.failed",
        "transfer.reversed",
        "payout.paid",
        "payout.updated",
        "payout.failed",
        "payout.canceled",
    }:
        try:
            reconcile_payout_event(ev_type, obj or {})
        except Exception as e:
            print("[payout reconcile error]", str(e))
        return 200, {"ok": True}

    return 200, {"ignored": ev_type or "unknown"}
