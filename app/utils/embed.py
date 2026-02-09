"""
Validate YouTube, Vimeo, and other embed URLs.
"""

import re
from typing import Tuple
from urllib.parse import urlparse

# YouTube: youtube.com/watch?v=ID, youtu.be/ID, youtube.com/embed/ID
_YOUTUBE_PATTERNS = [
    r"(?:youtube\.com/watch\?v=)([a-zA-Z0-9_-]{11})",
    r"(?:youtu\.be/)([a-zA-Z0-9_-]{11})",
    r"(?:youtube\.com/embed/)([a-zA-Z0-9_-]{11})",
]
# Vimeo: vimeo.com/ID, player.vimeo.com/video/ID
_VIMEO_PATTERNS = [
    r"(?:vimeo\.com/)(\d+)",
    r"(?:player\.vimeo\.com/video/)(\d+)",
]


def parse_embed_url(url: str) -> Tuple[str | None, str | None]:
    """
    Parse embed URL. Returns (provider, embed_id) or (None, None) if invalid.
    """
    if not url or not url.strip():
        return None, None
    u = url.strip()
    if not u.startswith(("http://", "https://")):
        u = "https://" + u
    # parsed = urlparse(u)
    # host = parsed.netloc.lower().replace("www.", "")

    for pat in _YOUTUBE_PATTERNS:
        m = re.search(pat, u)
        if m:
            return "youtube", m.group(1)

    for pat in _VIMEO_PATTERNS:
        m = re.search(pat, u)
        if m:
            return "vimeo", m.group(1)

    return None, None


def validate_embed_url(url: str) -> Tuple[bool, str | None]:
    """
    Validate embed URL. Returns (valid, error_message).
    Checks: must be http/https, not localhost, valid YouTube or Vimeo format.
    """
    if not url or not url.strip():
        return False, "URL required"
    u = url.strip()
    if not u.startswith(("http://", "https://")):
        return False, "URL must start with http:// or https://"
    parsed = urlparse(u)
    host = (parsed.netloc or "").lower().replace("www.", "")
    if (
        not host
        or host in ("localhost", "127.0.0.1", "0.0.0.0")
        or host.endswith(".local")
    ):
        return False, "localhost and .local URLs are not allowed"
    if len(u) > 2000:
        return False, "URL too long"
    provider, eid = parse_embed_url(url)
    if not provider:
        return False, "invalid YouTube or Vimeo URL"
    return True, None


def embed_url_to_iframe_src(url: str) -> str | None:
    """Convert embed URL to iframe src."""
    provider, eid = parse_embed_url(url)
    if provider == "youtube":
        return f"https://www.youtube.com/embed/{eid}"
    if provider == "vimeo":
        return f"https://player.vimeo.com/video/{eid}"
    return None
