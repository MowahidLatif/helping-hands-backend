"""
Extract design tokens (colors, fonts, border-radius) from a public URL or verbal description.
"""

from __future__ import annotations

import json
import logging
import os
import re
import urllib.parse
from collections import Counter
from typing import Any

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_AI_SITE_MODEL", "gpt-4o-mini")

_HEX_RE = re.compile(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")
_RGB_RE = re.compile(r"rgb\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*\)")
_FONT_RE = re.compile(r"font-family\s*:\s*['\"]?([A-Za-z][A-Za-z0-9 \-]+)", re.IGNORECASE)
_RADIUS_RE = re.compile(r"border-radius\s*:\s*([\d.]+(?:px|rem|em|%))", re.IGNORECASE)

_NEAR_WHITE_THRESHOLD = 230  # r,g,b all above this → skip as background
_NEAR_BLACK_THRESHOLD = 30   # r,g,b all below this → skip as text

_GENERIC_FONTS = frozenset(
    {"serif", "sans-serif", "monospace", "cursive", "fantasy", "system-ui",
     "-apple-system", "blinkmacsystemfont", "segoe ui", "helvetica neue",
     "arial", "helvetica", "times new roman", "georgia", "verdana"}
)

_MAX_CSS_BYTES = 200_000


def _hex3_to_hex6(h: str) -> str:
    return h[0] * 2 + h[1] * 2 + h[2] * 2


def _normalize_hex(raw: str) -> str:
    raw = raw.lstrip("#").lower()
    if len(raw) == 3:
        raw = _hex3_to_hex6(raw)
    return "#" + raw.upper()


def _rgb_to_hex(r: int, g: int, b: int) -> str:
    return "#{:02X}{:02X}{:02X}".format(r, g, b)


def _is_near_white(hex_color: str) -> bool:
    h = hex_color.lstrip("#")
    try:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except (ValueError, IndexError):
        return False
    return r > _NEAR_WHITE_THRESHOLD and g > _NEAR_WHITE_THRESHOLD and b > _NEAR_WHITE_THRESHOLD


def _is_near_black(hex_color: str) -> bool:
    h = hex_color.lstrip("#")
    try:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except (ValueError, IndexError):
        return False
    return r < _NEAR_BLACK_THRESHOLD and g < _NEAR_BLACK_THRESHOLD and b < _NEAR_BLACK_THRESHOLD


def _parse_css_tokens(css_text: str) -> dict[str, Any]:
    # Collect colors
    color_counts: Counter[str] = Counter()
    for m in _HEX_RE.finditer(css_text):
        raw = m.group(1)
        if len(raw) == 3:
            raw = _hex3_to_hex6(raw)
        color_counts["#" + raw.upper()] += 1
    for m in _RGB_RE.finditer(css_text):
        r, g, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
        color_counts[_rgb_to_hex(r, g, b)] += 1

    # Filter and rank
    candidates = [
        c for c, _ in color_counts.most_common()
        if not _is_near_white(c) and not _is_near_black(c)
    ]
    primary = candidates[0] if candidates else "#1D9E75"
    secondary = candidates[1] if len(candidates) > 1 else primary

    # Font
    font_name = "Inter"
    for m in _FONT_RE.finditer(css_text):
        name = m.group(1).strip().strip("'\"")
        if name.lower() not in _GENERIC_FONTS and len(name) > 2:
            font_name = name
            break

    # Border radius
    border_radius = "8px"
    for m in _RADIUS_RE.finditer(css_text):
        border_radius = m.group(1)
        break

    return {
        "primary_color": primary,
        "secondary_color": secondary,
        "font_family": font_name,
        "border_radius": border_radius,
    }


def extract_tokens_from_url(url: str) -> dict[str, Any]:
    """
    Fetch a public URL, extract CSS from <style> tags and linked stylesheets,
    then derive primary color, secondary color, font family, and border radius.
    Raises ValueError with a user-readable message on failure.
    """
    import httpx
    from bs4 import BeautifulSoup

    url = url.strip()
    if not url.startswith(("http://", "https://")):
        raise ValueError("URL must start with http:// or https://")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    try:
        resp = httpx.get(url, follow_redirects=True, timeout=10, headers=headers)
        resp.raise_for_status()
        html = resp.text
    except httpx.TimeoutException:
        raise ValueError(f"Timed out fetching {url}. Try a different URL.")
    except httpx.HTTPStatusError as e:
        raise ValueError(f"Server returned {e.response.status_code} for {url}.")
    except Exception as e:
        raise ValueError(f"Could not fetch {url}: {e}")

    soup = BeautifulSoup(html, "html.parser")

    # Collect CSS text
    css_parts: list[str] = []

    # Inline <style> tags
    for tag in soup.find_all("style"):
        css_parts.append(tag.get_text())

    # Inline style attributes on key elements
    for selector in ["body", "header", "nav", "footer", "button", "a"]:
        for el in soup.select(selector)[:5]:
            style_attr = el.get("style", "")
            if style_attr:
                css_parts.append(style_attr)

    # External stylesheets (follow up to 3)
    parsed_base = urllib.parse.urlparse(url)
    base_url = f"{parsed_base.scheme}://{parsed_base.netloc}"
    followed = 0
    for link in soup.find_all("link", rel=lambda r: r and "stylesheet" in r):
        if followed >= 3:
            break
        href = link.get("href", "")
        if not href or href.startswith("data:"):
            continue
        css_url = urllib.parse.urljoin(base_url, href) if not href.startswith("http") else href
        try:
            css_resp = httpx.get(css_url, follow_redirects=True, timeout=8, headers=headers)
            css_resp.raise_for_status()
            css_parts.append(css_resp.text[:_MAX_CSS_BYTES])
            followed += 1
        except Exception:
            pass

    combined_css = "\n".join(css_parts)
    tokens = _parse_css_tokens(combined_css)
    tokens["source"] = "url"
    return tokens


def extract_tokens_from_description(description: str) -> dict[str, Any]:
    """
    Use OpenAI to derive design tokens from a verbal brand description.
    Raises ValueError on failure.
    """
    import urllib.request
    import urllib.error

    if not OPENAI_API_KEY:
        raise ValueError("AI token generation is not configured.")

    description = description.strip()[:2000]
    if not description:
        raise ValueError("Description is required.")

    system = (
        "You are a brand designer. Given a description of a company or brand, "
        "return ONLY valid JSON (no markdown, no explanation) with these fields:\n"
        '{ "primary_color": "<hex>", "secondary_color": "<hex>", '
        '"font_family": "<font name>", "border_radius": "<e.g. 8px>" }'
    )
    body = json.dumps({
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": description},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.5,
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {OPENAI_API_KEY}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
        content = raw["choices"][0]["message"]["content"]
        parsed = json.loads(content)
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")[:500]
        raise ValueError(f"AI service error: {err}")
    except Exception as e:
        raise ValueError(f"Could not generate tokens: {e}")

    # Normalize and validate output
    tokens: dict[str, Any] = {
        "primary_color": "#1D9E75",
        "secondary_color": "#0F6B50",
        "font_family": "Inter",
        "border_radius": "8px",
        "source": "description",
    }
    for field in ("primary_color", "secondary_color"):
        val = parsed.get(field, "")
        if isinstance(val, str) and re.match(r"^#[0-9a-fA-F]{3,8}$", val.strip()):
            tokens[field] = _normalize_hex(val.strip())
    if isinstance(parsed.get("font_family"), str) and parsed["font_family"].strip():
        tokens["font_family"] = parsed["font_family"].strip()[:80]
    if isinstance(parsed.get("border_radius"), str) and parsed["border_radius"].strip():
        tokens["border_radius"] = parsed["border_radius"].strip()[:20]

    return tokens
