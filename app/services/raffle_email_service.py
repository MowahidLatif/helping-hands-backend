"""Email notifications for raffle lifecycle events."""
from __future__ import annotations
import os
from typing import Any, Dict, Optional

from app.utils.email_sender import send_email
from app.models.org_email_settings import get_email_settings

DEV_EMAIL_LOG_ONLY = os.getenv("DEV_EMAIL_LOG_ONLY", "1") == "1"
FROM_DEFAULT = "noreply@helpinghandsfund.io"
FROM_NAME_DEFAULT = "HelpingHandsFund"


def _get_org(campaign_id: str) -> Optional[Dict[str, Any]]:
    from app.models.campaign import get_campaign_by_id
    from app.models.org import get_organization
    camp = get_campaign_by_id(campaign_id)
    if not camp:
        return None
    return get_organization(camp["org_id"])


def _send(to_email: str, subject: str, body_text: str, org_id: Optional[str] = None) -> None:
    settings = get_email_settings(org_id) if org_id else {}
    from_email = (settings or {}).get("from_email") or FROM_DEFAULT
    from_name = (settings or {}).get("from_name") or FROM_NAME_DEFAULT
    reply_to = (settings or {}).get("reply_to")
    bcc = (settings or {}).get("bcc_to")

    if DEV_EMAIL_LOG_ONLY:
        print(f"[raffle-email][dev] to={to_email} subj={subject}", flush=True)
        print(body_text, flush=True)
        return

    send_email(
        to_email=to_email,
        subject=subject,
        body_text=body_text,
        body_html=None,
        from_email=from_email,
        from_name=from_name,
        reply_to=reply_to,
        bcc=bcc,
    )


def send_raffle_winner_email(
    entry: Dict[str, Any],
    raffle: Dict[str, Any],
    claim_url: str,
) -> None:
    """Notify the winner with their claim link."""
    to_email = entry.get("donor_email")
    if not to_email:
        return
    name = entry.get("donor_first_name") or "Congratulations"
    prize = raffle.get("prize_name", "the prize")
    subject = f"You won the raffle for {prize}!"
    body = (
        f"Hi {name},\n\n"
        f"Great news — you've been drawn as the winner of the raffle for \"{prize}\"!\n\n"
        f"You have 24 hours to claim your prize. Click the link below to claim:\n"
        f"{claim_url}\n\n"
        f"If you did not enter this raffle or have any questions, please ignore this email.\n\n"
        f"— The HelpingHandsFund Team\n"
    )
    org = _get_org(raffle.get("campaign_id", ""))
    _send(to_email, subject, body, org_id=(org or {}).get("id"))


def send_raffle_org_winner_drawn(
    raffle: Dict[str, Any],
    winner_entry: Dict[str, Any],
) -> None:
    """Notify org that a winner has been drawn."""
    org = _get_org(raffle.get("campaign_id", ""))
    if not org:
        return
    owner_email = org.get("billing_email") or org.get("email")
    if not owner_email:
        return
    prize = raffle.get("prize_name", "the prize")
    winner_email = winner_entry.get("donor_email", "unknown")
    subject = f"A winner has been drawn for your raffle!"
    body = (
        f"Hi {org.get('name', 'there')},\n\n"
        f"A winner has been drawn for your raffle \"{prize}\".\n\n"
        f"Winner: {winner_email}\n\n"
        f"They have 24 hours to claim their prize via the link sent to them.\n"
        f"You'll receive another notification when they claim.\n\n"
        f"— HelpingHandsFund\n"
    )
    _send(owner_email, subject, body, org_id=org.get("id"))


def send_raffle_org_winner_claimed(
    raffle: Dict[str, Any],
    winner_entry: Dict[str, Any],
) -> None:
    """Notify org that the winner has claimed their prize."""
    org = _get_org(raffle.get("campaign_id", ""))
    if not org:
        return
    owner_email = org.get("billing_email") or org.get("email")
    if not owner_email:
        return
    prize = raffle.get("prize_name", "the prize")
    winner_email = winner_entry.get("donor_email", "unknown")
    winner_name = " ".join(filter(None, [
        winner_entry.get("donor_first_name"),
        winner_entry.get("donor_last_name"),
    ])) or winner_email
    subject = f"Your raffle winner has claimed their prize!"
    body = (
        f"Hi {org.get('name', 'there')},\n\n"
        f"Your raffle winner for \"{prize}\" has claimed their prize!\n\n"
        f"Winner: {winner_name}\n"
        f"Contact: {winner_email}\n\n"
        f"Please arrange prize delivery at your earliest convenience.\n\n"
        f"— HelpingHandsFund\n"
    )
    _send(owner_email, subject, body, org_id=org.get("id"))


def send_raffle_org_unclaimed(raffle: Dict[str, Any], draw_count: int) -> None:
    """Notify org that no winner claimed after max redraws."""
    org = _get_org(raffle.get("campaign_id", ""))
    if not org:
        return
    owner_email = org.get("billing_email") or org.get("email")
    if not owner_email:
        return
    prize = raffle.get("prize_name", "the prize")
    subject = f"Your raffle ended with no winner claiming the prize"
    body = (
        f"Hi {org.get('name', 'there')},\n\n"
        f"After {draw_count} draw(s), no winner claimed the raffle prize for \"{prize}\".\n\n"
        f"The prize is yours to award at your discretion.\n\n"
        f"— HelpingHandsFund\n"
    )
    _send(owner_email, subject, body, org_id=org.get("id"))


def send_raffle_org_no_entries(raffle: Dict[str, Any]) -> None:
    """Notify org that the raffle ended with zero entries."""
    org = _get_org(raffle.get("campaign_id", ""))
    if not org:
        return
    owner_email = org.get("billing_email") or org.get("email")
    if not owner_email:
        return
    prize = raffle.get("prize_name", "the prize")
    subject = f"Your raffle ended with no entries"
    body = (
        f"Hi {org.get('name', 'there')},\n\n"
        f"Your campaign ended with no entries in the raffle for \"{prize}\".\n"
        f"The raffle has been cancelled.\n\n"
        f"— HelpingHandsFund\n"
    )
    _send(owner_email, subject, body, org_id=org.get("id"))
