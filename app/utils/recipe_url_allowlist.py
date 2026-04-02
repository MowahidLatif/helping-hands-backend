"""
Allowlist for media URLs embedded in ai_site_recipe (SSRF / tracking mitigation).
"""

from __future__ import annotations

import os
from urllib.parse import urlparse

from app.utils import s3_helpers

# Comma-separated extra hostnames (CDN, CloudFront, public asset domain)
_ENV_EXTRA_HOSTS = "AI_SITE_MEDIA_URL_HOSTS"
_ENV_PUBLIC_MEDIA_BASE = "PUBLIC_MEDIA_BASE_URL"
# Allow HTTP only on these patterns (dev)
_MAX_URL_LEN = 2048


def _is_dev_host(hostname: str) -> bool:
    h = (hostname or "").lower()
    if h in ("127.0.0.1", "localhost", "::1"):
        return True
    if h.endswith(".local"):
        return True
    return False


def allowed_media_hosts() -> set[str]:
    hosts: set[str] = set()
    try:
        ep = urlparse(s3_helpers.S3_ENDPOINT)
        if ep.hostname:
            hosts.add(ep.hostname.lower())
    except Exception:
        pass
    extra = os.getenv(_ENV_EXTRA_HOSTS, "")
    for part in extra.split(","):
        p = part.strip().lower()
        if p:
            hosts.add(p)
    pub = (os.getenv(_ENV_PUBLIC_MEDIA_BASE) or "").strip()
    if pub:
        u = urlparse(pub)
        if u.hostname:
            hosts.add(u.hostname.lower())
    return hosts


def assert_allowed_media_url(url: str) -> str | None:
    """
    Returns None if URL is allowed for recipe image/video/gallery/hero backgrounds.
    Otherwise returns error message.
    """
    if not url or not isinstance(url, str):
        return "url must be a non-empty string"
    url = url.strip()
    if not url:
        return "url must be a non-empty string"
    if len(url) > _MAX_URL_LEN:
        return "url exceeds maximum length"
    parsed = urlparse(url)
    if parsed.username or parsed.password:
        return "url must not contain user credentials"
    if not parsed.scheme or not parsed.hostname:
        return "invalid url"
    scheme = parsed.scheme.lower()
    host = parsed.hostname.lower()
    allowed = allowed_media_hosts()
    if not allowed:
        return "media URL allowlist is empty; configure S3_ENDPOINT and/or AI_SITE_MEDIA_URL_HOSTS"
    if scheme == "https":
        pass
    elif scheme == "http" and _is_dev_host(host):
        pass
    else:
        return (
            "url must use https (http only allowed for localhost / *.local dev hosts)"
        )
    if host not in allowed:
        return f"url host not in allowlist: {host}"
    return None
