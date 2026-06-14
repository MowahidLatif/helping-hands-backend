from __future__ import annotations
import os
import hashlib
import hmac
import base64

HARD_BOUNCE_EVENTS = {"bounce", "blocked"}


def _verify_signature(payload: bytes, signature: str | None, timestamp: str | None) -> bool:
    """Verify SendGrid ECDSA webhook signature. Returns True if valid or key not configured."""
    public_key_pem = os.getenv("SENDGRID_WEBHOOK_PUBLIC_KEY", "").strip()
    if not public_key_pem:
        print("[sendgrid webhook] SENDGRID_WEBHOOK_PUBLIC_KEY not set — skipping verification", flush=True)
        return True
    if not signature or not timestamp:
        return False
    try:
        from cryptography.hazmat.primitives.asymmetric.ec import ECDSA
        from cryptography.hazmat.primitives.hashes import SHA256
        from cryptography.hazmat.primitives.serialization import load_pem_public_key
        key = load_pem_public_key(public_key_pem.encode())
        msg = (timestamp + payload.decode("utf-8")).encode()
        sig_bytes = base64.b64decode(signature)
        key.verify(sig_bytes, msg, ECDSA(SHA256()))  # type: ignore[arg-type]
        return True
    except Exception as e:
        print(f"[sendgrid webhook] signature verification failed: {e}", flush=True)
        return False


def process_sendgrid_events(events: list[dict]) -> None:
    """Handle inbound SendGrid event stream. Only processes hard-bounce events."""
    for event in events:
        if event.get("event") not in HARD_BOUNCE_EVENTS:
            continue
        email = (event.get("email") or "").strip().lower()
        if not email:
            continue
        try:
            _handle_hard_bounce(email)
        except Exception as e:
            print(f"[sendgrid webhook] hard bounce handling error for {email}: {e}", flush=True)


def _handle_hard_bounce(email: str) -> None:
    from app.models.raffle import get_draw_log_by_winner_email, update_draw_log, get_raffle_by_id, update_raffle
    from app.services.raffle_service import execute_raffle_draw

    rows = get_draw_log_by_winner_email(email)
    for row in rows:
        raffle = get_raffle_by_id(row["raffle_id"])
        if not raffle or raffle["status"] != "winner_pending":
            continue
        update_draw_log(row["id"], outcome="expired", expire_reason="bounced")
        update_raffle(row["raffle_id"], status="drawing")
        try:
            execute_raffle_draw(row["raffle_id"], triggered_by="bounce_redraw")
        except Exception as e:
            print(f"[sendgrid webhook] bounce redraw failed for raffle={row['raffle_id']}: {e}", flush=True)
            update_raffle(row["raffle_id"], status="active")
