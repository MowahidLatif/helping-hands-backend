"""
Sanitize user-provided strings before inclusion in LLM prompts (prompt-injection mitigation).
"""

from __future__ import annotations

import re

_DESCRIPTION_MAX_LEN = 120

# If description matches any of these (case-insensitive), drop entirely
_DENY_PATTERNS = re.compile(
    r"(ignore\s+(previous|all|above|prior)|disregard\s+(previous|all)|"
    r"system\s*:|assistant\s*:|###\s*instruction|override\s+instructions|"
    r"new\s+instructions\s*:|you\s+are\s+now)",
    re.IGNORECASE | re.DOTALL,
)


def sanitize_asset_description(
    s: str | None, max_len: int = _DESCRIPTION_MAX_LEN
) -> str:
    if not s or not isinstance(s, str):
        return ""
    t = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", s)
    t = re.sub(r"\s+", " ", t).strip()
    if not t:
        return ""
    if _DENY_PATTERNS.search(t):
        return ""
    return t[:max_len]
