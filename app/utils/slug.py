import re

_slug_re = re.compile(r"[^a-z0-9]+")


def slugify(text: str) -> str:
    s = text.strip().lower()
    s = _slug_re.sub("-", s).strip("-")
    return s or "campaign"


def slugify_with_fallback(text: str, fallback: str = "campaign") -> str:
    s = slugify(text)
    if not s or s.isnumeric():
        return fallback
    return s
