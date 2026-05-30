"""
Fetch secrets from AWS Secrets Manager with a plain-string fallback for local dev.

Usage pattern (module-level, resolved once at import time):
    from app.utils.secrets import get_secret_or_env
    OPENAI_API_KEY = get_secret_or_env("OPENAI_API_KEY", secret_name_env="OPENAI_SECRET_NAME")
"""

from __future__ import annotations

import json
import logging
import os

logger = logging.getLogger(__name__)
_SECRET_CACHE: dict[str, str] = {}


def get_secret_or_env(
    env_var: str,
    *,
    secret_name_env: str,
    json_keys: tuple[str, ...] = (),
) -> str:
    """
    Return a secret value using this priority order:
      1. AWS Secrets Manager — if ``secret_name_env`` points to a secret name in the environment.
         The secret is expected to be either a plain string or JSON with a key matching ``env_var``.
      2. Plain environment variable ``env_var`` — local dev / docker-compose fallback.

    Raises RuntimeError if Secrets Manager is configured but the fetch fails, so the
    process crashes loudly rather than silently running with an empty key.
    """
    secret_name = os.getenv(secret_name_env, "").strip()
    if secret_name:
        return _fetch_from_secrets_manager(
            secret_name,
            env_var,
            json_keys=json_keys,
        )
    return os.getenv(env_var, "")


def _fetch_from_secrets_manager(
    secret_name: str, env_var: str, *, json_keys: tuple[str, ...]
) -> str:
    if secret_name in _SECRET_CACHE:
        return _extract_value(_SECRET_CACHE[secret_name], secret_name, env_var, json_keys)

    try:
        import boto3
        from botocore.exceptions import ClientError
    except ImportError as e:
        raise RuntimeError(
            f"boto3 is required to fetch secrets from AWS Secrets Manager: {e}"
        ) from e

    region = os.getenv("AWS_REGION", "us-east-2")
    client = boto3.session.Session().client(
        service_name="secretsmanager", region_name=region
    )
    try:
        response = client.get_secret_value(SecretId=secret_name)
    except ClientError as e:
        raise RuntimeError(
            f"Failed to fetch secret '{secret_name}' from Secrets Manager: {e}"
        ) from e

    raw = response.get("SecretString", "")
    _SECRET_CACHE[secret_name] = raw
    return _extract_value(raw, secret_name, env_var, json_keys)


def _extract_value(
    raw: str, secret_name: str, env_var: str, json_keys: tuple[str, ...]
) -> str:
    # Try JSON first (RDS-style secrets store multiple fields); fall back to plain string.
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            candidate_keys = [env_var, env_var.lower(), *json_keys]
            for key in candidate_keys:
                value = parsed.get(key)
                if value:
                    logger.info(
                        "Loaded %s from Secrets Manager secret '%s' (JSON field '%s').",
                        env_var,
                        secret_name,
                        key,
                    )
                    return str(value)
    except (json.JSONDecodeError, TypeError):
        pass

    # Plain-string secret (most common for API keys).
    if raw:
        logger.info(
            "Loaded %s from Secrets Manager secret '%s' (plain string).",
            env_var,
            secret_name,
        )
        return raw

    raise RuntimeError(
        f"Secret '{secret_name}' was found in Secrets Manager but contained no usable value for {env_var}."
    )
