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
    from app.models.campaign import get_campaign
    from app.models.org import get_organization
    camp = get_campaign(campaign_id)
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
    from app.services.raffle_service import RAFFLE_CLAIM_WINDOW_HOURS
    to_email = entry.get("donor_email")
    if not to_email:
        return
    name = entry.get("donor_first_name") or "Congratulations"
    prize = raffle.get("prize_name", "the prize")
    subject = f"You won the raffle for {prize}!"
    body = (
        f"Hi {name},\n\n"
        f"Great news — you've been drawn as the winner of the raffle for \"{prize}\"!\n\n"
        f"You have {RAFFLE_CLAIM_WINDOW_HOURS} hours to claim your prize. "
        f"Click the link below to claim:\n"
        f"{claim_url}\n\n"
        f"You will be asked to confirm the email address you used to enter the raffle.\n\n"
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
    from app.services.raffle_service import RAFFLE_CLAIM_WINDOW_HOURS
    org = _get_org(raffle.get("campaign_id", ""))
    if not org:
        return
    owner_email = org.get("billing_email") or org.get("email")
    if not owner_email:
        return
    prize = raffle.get("prize_name", "the prize")
    winner_email = winner_entry.get("donor_email", "unknown")
    subject = "A winner has been drawn for your raffle!"
    body = (
        f"Hi {org.get('name', 'there')},\n\n"
        f"A winner has been drawn for your raffle \"{prize}\".\n\n"
        f"Winner: {winner_email}\n\n"
        f"They have {RAFFLE_CLAIM_WINDOW_HOURS} hours to claim their prize via the link sent to them.\n"
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
    subject = "Your raffle winner has claimed their prize!"
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
    subject = "Your raffle ended with no winner claiming the prize"
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
    subject = "Your raffle ended with no entries"
    body = (
        f"Hi {org.get('name', 'there')},\n\n"
        f"Your campaign ended with no entries in the raffle for \"{prize}\".\n"
        f"The raffle has been cancelled.\n\n"
        f"— HelpingHandsFund\n"
    )
    _send(owner_email, subject, body, org_id=org.get("id"))


def send_raffle_org_winner_voided(
    raffle: Dict[str, Any],
    voided_entry: Dict[str, Any],
    reason: str,
) -> None:
    """Notify org that a winner's donation was refunded/disputed and a new draw has been triggered."""
    org = _get_org(raffle.get("campaign_id", ""))
    if not org:
        return
    owner_email = org.get("billing_email") or org.get("email")
    if not owner_email:
        return
    prize = raffle.get("prize_name", "the prize")
    prev_email = voided_entry.get("donor_email", "unknown")
    reason_label = "disputed" if reason == "chargeback" else "refunded"
    subject = f"Raffle winner update — previous winner's donation was {reason_label}"
    body = (
        f"Hi {org.get('name', 'there')},\n\n"
        f"The previous winner's donation for your raffle \"{prize}\" was {reason_label}.\n"
        f"A new winner has been drawn automatically.\n\n"
        f"Previous winner: {prev_email}\n\n"
        f"You will receive a separate notification about the new winner.\n\n"
        f"— HelpingHandsFund\n"
    )
    _send(owner_email, subject, body, org_id=org.get("id"))


def send_raffle_threshold_not_met(raffle: Dict[str, Any], actual_count: int) -> None:
    """Notify org and all entrants when min_entries threshold was not met."""
    from app.models.raffle import get_raffle_entries
    org = _get_org(raffle.get("campaign_id", ""))
    prize = raffle.get("prize_name", "the prize")
    min_e = raffle.get("min_entries", 0)

    # Org notification
    if org:
        owner_email = org.get("billing_email") or org.get("email")
        if owner_email:
            subject = f"Raffle cancelled — minimum entries not reached for \"{prize}\""
            body = (
                f"Hi {org.get('name', 'there')},\n\n"
                f"Your raffle for \"{prize}\" required a minimum of {min_e} entries "
                f"but only received {actual_count}. The raffle has been cancelled.\n\n"
                f"All entrants will be notified by email.\n\n"
                f"— HelpingHandsFund\n"
            )
            _send(owner_email, subject, body, org_id=org.get("id"))

    # Entrant notifications
    entries = get_raffle_entries(raffle["id"])
    for entry in entries:
        to_email = entry.get("donor_email")
        if not to_email or entry.get("voided"):
            continue
        name = entry.get("donor_first_name") or "there"
        campaign_title = org.get("name", "the campaign") if org else "the campaign"
        subject = f"Raffle update for \"{prize}\""
        body = (
            f"Hi {name},\n\n"
            f"The raffle for \"{prize}\" hosted by {campaign_title} was cancelled because "
            f"it did not reach the minimum required number of entries.\n\n"
            f"Your support for the campaign still made a difference — thank you!\n\n"
            f"— HelpingHandsFund\n"
        )
        try:
            _send(to_email, subject, body, org_id=(org or {}).get("id"))
        except Exception as e:
            print(f"[raffle-email] threshold_not_met entrant {to_email}: {e}", flush=True)


def send_deletion_confirmation_email(donor_email: str, raffle: Dict[str, Any]) -> None:
    """Confirm to the user that their entry data has been deleted."""
    prize = raffle.get("prize_name", "the raffle")
    subject = f"Your data has been removed from the \"{prize}\" raffle"
    body = (
        f"Hi,\n\n"
        f"As requested, your entry data has been permanently deleted from the raffle for "
        f"\"{prize}\".\n\n"
        f"If you did not request this, please contact us.\n\n"
        f"— HelpingHandsFund\n"
    )
    org = _get_org(raffle.get("campaign_id", ""))
    _send(donor_email, subject, body, org_id=(org or {}).get("id"))


def send_raffle_non_winner_email(entry: Dict[str, Any], raffle: Dict[str, Any]) -> None:
    """Thank non-winners after a raffle is claimed."""
    to_email = entry.get("donor_email")
    if not to_email:
        return
    org = _get_org(raffle.get("campaign_id", ""))
    org_name = (org or {}).get("name", "the organization")
    prize = raffle.get("prize_name", "the prize")
    name = entry.get("donor_first_name") or "there"
    subject = f"Raffle results for \"{prize}\""
    body = (
        f"Hi {name},\n\n"
        f"Thank you for entering the raffle for \"{prize}\".\n\n"
        f"Unfortunately you weren't selected as the winner this time, but your support of "
        f"{org_name} made a real difference. ❤️\n\n"
        f"We hope to see you in future campaigns!\n\n"
        f"— HelpingHandsFund\n"
    )
    _send(to_email, subject, body, org_id=(org or {}).get("id"))


def send_raffle_purge_notifications(raffle: Dict[str, Any], emails: list) -> None:
    """Notify entrants that their data has been purged after the 30-day retention period."""
    if not emails:
        return
    org = _get_org(raffle.get("campaign_id", ""))
    prize = raffle.get("prize_name", "the raffle")
    subject = f"Your data from the \"{prize}\" raffle has been deleted"
    body_template = (
        "Hi,\n\n"
        f"Your entry data from the raffle for \"{prize}\" has been permanently deleted from "
        "our platform as part of our 30-day data retention policy.\n\n"
        "We keep personal information only as long as needed — that's a promise.\n\n"
        "— HelpingHandsFund\n"
    )
    org_id = (org or {}).get("id")
    # Send in chunks of 500
    chunk_size = 500
    for i in range(0, len(emails), chunk_size):
        chunk = emails[i:i + chunk_size]
        for to_email in chunk:
            try:
                _send(to_email, subject, body_template, org_id=org_id)
            except Exception as e:
                print(f"[purge email] {to_email}: {e}", flush=True)


def send_raffle_free_entry_confirmation(
    entry: Dict[str, Any],
    raffle: Dict[str, Any],
) -> None:
    """Confirm free entry to the entrant."""
    to_email = entry.get("donor_email")
    if not to_email:
        return
    prize = raffle.get("prize_name", "the prize")
    name = entry.get("donor_first_name") or "there"
    subject = f"You're entered in the raffle for {prize}"
    body = (
        f"Hi {name},\n\n"
        f"You've been entered in the raffle for \"{prize}\"!\n\n"
        f"This email address is how we'll contact you if you win.\n\n"
        f"Good luck!\n\n"
        f"— The HelpingHandsFund Team\n"
    )
    org = _get_org(raffle.get("campaign_id", ""))
    _send(to_email, subject, body, org_id=(org or {}).get("id"))
