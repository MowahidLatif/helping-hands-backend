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
