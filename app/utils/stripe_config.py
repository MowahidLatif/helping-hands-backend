"""
Shared Stripe configuration. Loads keys from AWS Secrets Manager when
STRIPE_SECRET_NAME is set; falls back to plain env vars for local dev.

AWS secret format (JSON):
  { "STRIPE_SECRET_KEY": "sk_live_...", "STRIPE_WEBHOOK_SECRET": "whsec_..." }
"""

from __future__ import annotations

import os

from app.utils.secrets import get_secret_or_env

STRIPE_SECRET_KEY: str = get_secret_or_env(
    "STRIPE_SECRET_KEY", secret_name_env="STRIPE_SECRET_NAME"
)
STRIPE_WEBHOOK_SECRET: str = get_secret_or_env(
    "STRIPE_WEBHOOK_SECRET", secret_name_env="STRIPE_SECRET_NAME"
)
STRIPE_CURRENCY: str = os.getenv("STRIPE_CURRENCY", "usd").strip().lower()

# Legacy monthly-only price IDs (fallback when *_MONTHLY unset)
STRIPE_PRICE_STARTER: str = (os.getenv("STRIPE_PRICE_STARTER") or "").strip()
STRIPE_PRICE_GROW: str = (os.getenv("STRIPE_PRICE_GROW") or "").strip()
STRIPE_PRICE_SCALE: str = (os.getenv("STRIPE_PRICE_SCALE") or "").strip()

STRIPE_PRICE_STARTER_MONTHLY: str = (
    os.getenv("STRIPE_PRICE_STARTER_MONTHLY") or STRIPE_PRICE_STARTER
).strip()
STRIPE_PRICE_STARTER_ANNUAL: str = (os.getenv("STRIPE_PRICE_STARTER_ANNUAL") or "").strip()
STRIPE_PRICE_GROW_MONTHLY: str = (
    os.getenv("STRIPE_PRICE_GROW_MONTHLY") or STRIPE_PRICE_GROW
).strip()
STRIPE_PRICE_GROW_ANNUAL: str = (os.getenv("STRIPE_PRICE_GROW_ANNUAL") or "").strip()
STRIPE_PRICE_SCALE_MONTHLY: str = (
    os.getenv("STRIPE_PRICE_SCALE_MONTHLY") or STRIPE_PRICE_SCALE
).strip()
STRIPE_PRICE_SCALE_ANNUAL: str = (os.getenv("STRIPE_PRICE_SCALE_ANNUAL") or "").strip()

STRIPE_TRIAL_DAYS: int = max(0, int(os.getenv("STRIPE_TRIAL_DAYS", "7") or "7"))
STRIPE_PAYMENT_GRACE_DAYS: int = max(0, int(os.getenv("STRIPE_PAYMENT_GRACE_DAYS", "5") or "5"))

STRIPE_BILLING_SUCCESS_URL: str = (os.getenv("STRIPE_BILLING_SUCCESS_URL") or "").strip()
STRIPE_BILLING_CANCEL_URL: str = (os.getenv("STRIPE_BILLING_CANCEL_URL") or "").strip()
STRIPE_BILLING_PORTAL_RETURN_URL: str = (
    os.getenv("STRIPE_BILLING_PORTAL_RETURN_URL") or ""
).strip()

STRIPE_CONNECT_REFRESH_URL: str = (os.getenv("STRIPE_CONNECT_REFRESH_URL") or "").strip()
STRIPE_CONNECT_RETURN_URL: str = (os.getenv("STRIPE_CONNECT_RETURN_URL") or "").strip()
