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

STRIPE_PRICE_STARTER: str = (os.getenv("STRIPE_PRICE_STARTER") or "").strip()
STRIPE_PRICE_GROW: str = (os.getenv("STRIPE_PRICE_GROW") or "").strip()
STRIPE_PRICE_SCALE: str = (os.getenv("STRIPE_PRICE_SCALE") or "").strip()

STRIPE_BILLING_SUCCESS_URL: str = (os.getenv("STRIPE_BILLING_SUCCESS_URL") or "").strip()
STRIPE_BILLING_CANCEL_URL: str = (os.getenv("STRIPE_BILLING_CANCEL_URL") or "").strip()
STRIPE_BILLING_PORTAL_RETURN_URL: str = (
    os.getenv("STRIPE_BILLING_PORTAL_RETURN_URL") or ""
).strip()

STRIPE_CONNECT_REFRESH_URL: str = (os.getenv("STRIPE_CONNECT_REFRESH_URL") or "").strip()
STRIPE_CONNECT_RETURN_URL: str = (os.getenv("STRIPE_CONNECT_RETURN_URL") or "").strip()
