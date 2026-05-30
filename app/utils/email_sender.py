"""
SES / SendGrid email sending wrapper.

Configure via env:
- EMAIL_PROVIDER: "ses" | "sendgrid" (default: "ses" if AWS region set, else "sendgrid" if API key set)
- For SES: AWS_REGION, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY (or use default creds)
- For SendGrid: SENDGRID_API_KEY
- FROM_EMAIL, FROM_NAME: fallback sender when org settings don't provide
"""

from __future__ import annotations
import os
from typing import Tuple, Optional
from app.utils.secrets import get_secret_or_env

DEFAULT_FROM_EMAIL = os.getenv("FROM_EMAIL", "no-reply@example.com")
DEFAULT_FROM_NAME = os.getenv("FROM_NAME", "Donations")
SENDGRID_API_KEY = get_secret_or_env(
    "SENDGRID_API_KEY", secret_name_env="SENDGRID_SECRET_NAME"
)


def resolve_email_provider() -> str | None:
    provider = os.getenv("EMAIL_PROVIDER", "").strip().lower()
    if provider:
        return provider
    if SENDGRID_API_KEY:
        return "sendgrid"
    if os.getenv("AWS_REGION") or os.getenv("AWS_ACCESS_KEY_ID"):
        return "ses"
    return None


def validate_email_configuration(*, strict: bool = False) -> tuple[bool, str | None]:
    """
    Validate whether email delivery has enough configuration to operate.
    strict=True is intended for production startup guards.
    """
    provider = resolve_email_provider()
    if not provider:
        return (
            False,
            "EMAIL_PROVIDER is not set and no SENDGRID key or SES credentials are available.",
        )
    if provider == "sendgrid" and not SENDGRID_API_KEY:
        return (
            False,
            "Email provider is sendgrid but no SENDGRID key is configured.",
        )
    if provider == "ses" and not (os.getenv("AWS_REGION") or os.getenv("AWS_ACCESS_KEY_ID")):
        return (
            False,
            "Email provider is ses but no AWS region/credentials were found.",
        )
    if provider not in {"sendgrid", "ses"}:
        return False, f"Unknown EMAIL_PROVIDER: {provider}"
    if strict and provider == "ses" and not os.getenv("AWS_REGION"):
        return False, "EMAIL_PROVIDER=ses requires AWS_REGION."
    return True, None


def send_email(
    *,
    to_email: str,
    subject: str,
    body_text: str,
    body_html: Optional[str] = None,
    from_email: Optional[str] = None,
    from_name: Optional[str] = None,
    reply_to: Optional[str] = None,
    bcc: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Send an email via SES or SendGrid.
    Returns (provider, provider_msg_id) or (None, error_message) on failure.
    """
    from_addr = from_email or DEFAULT_FROM_EMAIL
    from_display = from_name or DEFAULT_FROM_NAME

    provider = resolve_email_provider()
    if not provider:
        return None, "EMAIL_PROVIDER not set and no SendGrid or SES configuration found"

    if provider == "sendgrid":
        return _send_via_sendgrid(
            to_email=to_email,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            from_email=from_addr,
            from_name=from_display,
            reply_to=reply_to,
            bcc=bcc,
        )
    if provider == "ses":
        return _send_via_ses(
            to_email=to_email,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            from_email=from_addr,
            from_name=from_display,
            reply_to=reply_to,
            bcc=bcc,
        )
    return None, f"Unknown EMAIL_PROVIDER: {provider}"


def _send_via_sendgrid(
    *,
    to_email: str,
    subject: str,
    body_text: str,
    body_html: Optional[str],
    from_email: str,
    from_name: str,
    reply_to: Optional[str] = None,
    bcc: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str]]:
    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail, Email, To, Content, Bcc, ReplyTo

        api_key = SENDGRID_API_KEY.strip()
        if not api_key:
            return None, "SENDGRID_API_KEY not set"

        html = body_html if body_html else f"<pre>{body_text}</pre>"
        message = Mail(
            from_email=Email(from_email, from_name),
            to_emails=To(to_email),
            subject=subject,
            plain_text_content=Content("text/plain", body_text),
            html_content=Content("text/html", html),
        )
        if reply_to:
            message.reply_to = ReplyTo(reply_to)
        if bcc:
            message.bcc = [Bcc(bcc)]

        sg = SendGridAPIClient(api_key)
        response = sg.send(message)

        msg_id = None
        if response.headers and "X-Message-Id" in response.headers:
            msg_id = response.headers.get("X-Message-Id")
        if not msg_id and hasattr(response, "headers") and response.headers:
            msg_id = getattr(response.headers, "get", lambda k: None)("X-Message-Id")

        return "sendgrid", msg_id or str(response.status_code)
    except Exception as e:
        return None, str(e)


def _send_via_ses(
    *,
    to_email: str,
    subject: str,
    body_text: str,
    body_html: Optional[str],
    from_email: str,
    from_name: str,
    reply_to: Optional[str] = None,
    bcc: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str]]:
    try:
        import boto3
        from botocore.exceptions import ClientError

        client = boto3.client("ses", region_name=os.getenv("AWS_REGION", "us-east-1"))

        body = {"Text": {"Data": body_text, "Charset": "UTF-8"}}
        if body_html:
            body["Html"] = {"Data": body_html, "Charset": "UTF-8"}

        destination: dict = {"ToAddresses": [to_email]}
        if bcc:
            destination["BccAddresses"] = [bcc]

        kwargs: dict = {
            "Source": f"{from_name} <{from_email}>",
            "Destination": destination,
            "Message": {
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": body,
            },
        }
        if reply_to:
            kwargs["ReplyToAddresses"] = [reply_to]

        response = client.send_email(**kwargs)
        msg_id = response.get("MessageId")
        return "ses", msg_id or "unknown"
    except ClientError as e:
        return None, str(e.response.get("Error", {}).get("Message", str(e)))
    except Exception as e:
        return None, str(e)
