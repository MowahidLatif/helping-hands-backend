"""
Custom domain validation for campaigns.

Validates format only (DNS/ownership verification would require external checks).
"""

import re

# Valid domain: letters, numbers, hyphens, dots; min 2 labels (e.g. example.com)
# No leading/trailing hyphen or dot; labels 1-63 chars; total max 253
_DOMAIN_RE = re.compile(
    r"^(?!-)[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
    r"(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*\.[a-z]{2,}$",
    re.IGNORECASE,
)


def validate_custom_domain(domain: str | None) -> tuple[bool, str | None]:
    """
    Validate custom domain format. Returns (valid, error_message).
    """
    if not domain or not domain.strip():
        return True, None  # empty is allowed (clears domain)
    d = domain.strip().lower()
    if len(d) > 253:
        return False, "domain too long"
    if d.startswith(".") or d.endswith(".") or ".." in d:
        return False, "invalid domain format"
    if not _DOMAIN_RE.match(d):
        return False, "invalid domain format (use example.com or sub.example.com)"
    # Disallow common reserved/local patterns
    if d.startswith("localhost") or d.startswith("127.") or ".local" in d:
        return False, "localhost and .local domains not allowed"
    return True, None
