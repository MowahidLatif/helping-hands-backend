"""
Validate AI-generated site recipe JSON (DSL v1). No executable code — declarative nodes only.
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.utils.recipe_url_allowlist import assert_allowed_media_url

MAX_NODES = 40
MAX_GALLERY_ITEMS = 20
MAX_HERO_TITLE_LEN = 200
MAX_HERO_SUBTITLE_LEN = 500
MAX_TEXT_BODY_LEN = 8000
MAX_FOOTER_TEXT_LEN = 500
MAX_DONATE_LABEL_LEN = 120
MAX_ALT_LEN = 500
MAX_PROP_URL_LEN = 2048
MAX_RECIPE_JSON_BYTES = 131_072  # 128 KiB
MAX_THEME_FONT_LEN = 80
MAX_THEME_RADIUS_LEN = 20
_HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{3,8}$")

ALLOWED_TYPES = frozenset(
    {
        "hero",
        "text",
        "image",
        "video",
        "gallery",
        "donate_section",
        "progress_section",
        "footer",
        "spacer",
    }
)


def normalize_recipe(raw: Any) -> dict[str, Any]:
    """
    Best-effort normalization for forward compatibility. Coerces version, clamps string props.
    """
    if not isinstance(raw, dict):
        return {"version": "1", "nodes": []}
    version = raw.get("version")
    if version is None or version == "":
        ver = "1"
    elif version in (1, "1"):
        ver = "1"
    else:
        ver = str(version)
    nodes_in = raw.get("nodes")
    if not isinstance(nodes_in, list):
        return {"version": ver, "nodes": []}
    out_nodes: list[dict[str, Any]] = []
    for node in nodes_in:
        if not isinstance(node, dict):
            continue
        nid = node.get("id")
        ntype = node.get("type")
        props = node.get("props") if isinstance(node.get("props"), dict) else {}
        props = dict(props)
        if isinstance(ntype, str) and ntype == "hero":
            if isinstance(props.get("title"), str):
                props["title"] = props["title"][:MAX_HERO_TITLE_LEN]
            if isinstance(props.get("subtitle"), str):
                props["subtitle"] = props["subtitle"][:MAX_HERO_SUBTITLE_LEN]
            if isinstance(props.get("background_image_url"), str):
                props["background_image_url"] = props["background_image_url"][
                    :MAX_PROP_URL_LEN
                ]
        elif ntype == "text" and isinstance(props.get("body"), str):
            props["body"] = props["body"][:MAX_TEXT_BODY_LEN]
        elif ntype == "image":
            if isinstance(props.get("url"), str):
                props["url"] = props["url"][:MAX_PROP_URL_LEN]
            if isinstance(props.get("alt"), str):
                props["alt"] = props["alt"][:MAX_ALT_LEN]
        elif ntype == "video" and isinstance(props.get("url"), str):
            props["url"] = props["url"][:MAX_PROP_URL_LEN]
        elif ntype == "gallery" and isinstance(props.get("items"), list):
            items = []
            for it in props["items"][:MAX_GALLERY_ITEMS]:
                if isinstance(it, dict):
                    d = dict(it)
                    if isinstance(d.get("url"), str):
                        d["url"] = d["url"][:MAX_PROP_URL_LEN]
                    if isinstance(d.get("alt"), str):
                        d["alt"] = d["alt"][:MAX_ALT_LEN]
                    items.append(d)
            props["items"] = items
        elif ntype == "donate_section":
            if isinstance(props.get("label"), str):
                props["label"] = props["label"][:MAX_DONATE_LABEL_LEN]
        elif ntype == "footer" and isinstance(props.get("text"), str):
            props["text"] = props["text"][:MAX_FOOTER_TEXT_LEN]
        sid = str(nid).strip() if nid is not None else ""
        out_nodes.append({"id": sid, "type": ntype, "props": props})
    return {"version": ver, "nodes": out_nodes}


def _is_str(v: Any) -> bool:
    return isinstance(v, str) and len(v.strip()) > 0


def _is_optional_str(v: Any) -> bool:
    return v is None or isinstance(v, str)


def _recipe_url_error(field_path: str, url: str) -> str | None:
    err = assert_allowed_media_url(url)
    if err:
        return f"{field_path}: {err}"
    return None


def _validate_recipe_urls_for_node(
    ntype: str, props: dict[str, Any], node_index: int
) -> str | None:
    prefix = f"nodes[{node_index}]"
    if ntype == "hero":
        u = props.get("background_image_url")
        if u is not None and isinstance(u, str) and u.strip():
            e = _recipe_url_error(f"{prefix}.props.background_image_url", u)
            if e:
                return e
    if ntype == "image":
        u = props.get("url")
        if isinstance(u, str):
            e = _recipe_url_error(f"{prefix}.props.url", u)
            if e:
                return e
    if ntype == "video":
        u = props.get("url")
        if isinstance(u, str):
            e = _recipe_url_error(f"{prefix}.props.url", u)
            if e:
                return e
    if ntype == "gallery":
        items = props.get("items")
        if isinstance(items, list):
            for gi, it in enumerate(items[:MAX_GALLERY_ITEMS]):
                if isinstance(it, dict) and isinstance(it.get("url"), str):
                    e = _recipe_url_error(
                        f"{prefix}.gallery.items[{gi}].url", it["url"]
                    )
                    if e:
                        return e
    return None


def _validate_props(node_type: str, props: dict[str, Any]) -> str | None:
    if not isinstance(props, dict):
        return "props must be an object"
    if node_type == "hero":
        if not _is_str(props.get("title")):
            return "hero requires non-empty string title"
        if len(str(props.get("title")).strip()) > MAX_HERO_TITLE_LEN:
            return f"hero title exceeds {MAX_HERO_TITLE_LEN} characters"
        if not _is_optional_str(props.get("subtitle")):
            return "hero subtitle must be a string"
        if (
            props.get("subtitle")
            and len(str(props["subtitle"])) > MAX_HERO_SUBTITLE_LEN
        ):
            return f"hero subtitle exceeds {MAX_HERO_SUBTITLE_LEN} characters"
        if props.get("background_image_url") is not None and not isinstance(
            props.get("background_image_url"), str
        ):
            return "hero background_image_url must be a string"
        return None
    if node_type == "text":
        body = props.get("body")
        if not _is_str(body):
            return "text requires non-empty string body"
        if len(str(body)) > MAX_TEXT_BODY_LEN:
            return f"text body exceeds {MAX_TEXT_BODY_LEN} characters"
        align = props.get("align")
        if align is not None and align not in ("left", "center", "right"):
            return "text align must be left, center, or right"
        return None
    if node_type == "image":
        if not _is_str(props.get("url")):
            return "image requires non-empty string url"
        if len(str(props.get("url"))) > MAX_PROP_URL_LEN:
            return f"image url exceeds {MAX_PROP_URL_LEN} characters"
        if not _is_optional_str(props.get("alt")):
            return "image alt must be a string"
        if props.get("alt") is not None and (
            not isinstance(props.get("alt"), str)
            or len(str(props["alt"])) > MAX_ALT_LEN
        ):
            return f"image alt must be a string (max {MAX_ALT_LEN} chars)"
        return None
    if node_type == "video":
        if not _is_str(props.get("url")):
            return "video requires non-empty string url"
        if len(str(props.get("url"))) > MAX_PROP_URL_LEN:
            return f"video url exceeds {MAX_PROP_URL_LEN} characters"
        return None
    if node_type == "gallery":
        items = props.get("items")
        if not isinstance(items, list) or len(items) == 0:
            return "gallery requires non-empty items array"
        if len(items) > MAX_GALLERY_ITEMS:
            return f"gallery allows at most {MAX_GALLERY_ITEMS} items"
        for i, it in enumerate(items):
            if not isinstance(it, dict) or not _is_str(it.get("url")):
                return f"gallery.items[{i}] must have url string"
            if len(str(it.get("url"))) > MAX_PROP_URL_LEN:
                return f"gallery.items[{i}] url exceeds maximum length"
            alt = it.get("alt")
            if alt is not None and (not isinstance(alt, str) or len(alt) > MAX_ALT_LEN):
                return (
                    f"gallery.items[{i}] alt must be a string (max {MAX_ALT_LEN} chars)"
                )
        return None
    if node_type == "donate_section":
        if not _is_optional_str(props.get("label")):
            return "donate_section label must be a string"
        if props.get("label") and len(str(props["label"])) > MAX_DONATE_LABEL_LEN:
            return f"donate_section label exceeds {MAX_DONATE_LABEL_LEN} characters"
        presets = props.get("preset_amounts")
        if presets is not None:
            if not isinstance(presets, list) or len(presets) > 12:
                return "donate_section preset_amounts must be a list (max 12)"
            for p in presets:
                if not isinstance(p, (int, float)) or p <= 0:
                    return "donate_section preset amounts must be positive numbers"
        return None
    if node_type == "progress_section":
        for key in ("show_goal", "show_count", "show_progress_bar"):
            if (
                key in props
                and props[key] is not None
                and not isinstance(props[key], bool)
            ):
                return f"progress_section {key} must be boolean"
        return None
    if node_type == "footer":
        if not _is_optional_str(props.get("text")):
            return "footer text must be a string"
        if props.get("text") and len(str(props["text"])) > MAX_FOOTER_TEXT_LEN:
            return f"footer text exceeds {MAX_FOOTER_TEXT_LEN} characters"
        return None
    if node_type == "spacer":
        h = props.get("height_px")
        if h is not None and (not isinstance(h, (int, float)) or h < 0 or h > 400):
            return "spacer height_px must be between 0 and 400"
        return None
    return None


def _validate_theme(theme: Any) -> dict[str, Any] | None:
    """Return a clean theme dict if valid, else None (theme is optional — invalid = ignored)."""
    if not isinstance(theme, dict):
        return None
    out: dict[str, Any] = {}
    for field in ("primary_color", "secondary_color"):
        val = theme.get(field)
        if val is None:
            continue
        if isinstance(val, str) and _HEX_COLOR_RE.match(val.strip()):
            out[field] = val.strip().upper() if val.strip().startswith("#") else "#" + val.strip().upper()
    for field, max_len in (("font_family", MAX_THEME_FONT_LEN), ("border_radius", MAX_THEME_RADIUS_LEN)):
        val = theme.get(field)
        if val is None:
            continue
        if isinstance(val, str) and val.strip():
            out[field] = val.strip()[:max_len]
    return out if out else None


def validate_ai_site_recipe(raw: Any) -> tuple[dict[str, Any] | None, str | None]:
    """
    Returns (normalized_recipe, None) on success, or (None, error_message).
    """
    if not isinstance(raw, dict):
        return None, "recipe must be a JSON object"
    normalized = normalize_recipe(raw)
    version = normalized.get("version")
    if version != "1":
        return None, 'recipe.version must be "1"'
    nodes = normalized.get("nodes")
    if not isinstance(nodes, list):
        return None, "recipe.nodes must be an array"
    if len(nodes) > MAX_NODES:
        return None, f"at most {MAX_NODES} nodes allowed"
    seen_ids: set[str] = set()
    out_nodes: list[dict[str, Any]] = []
    has_donate = False
    has_progress = False
    for i, node in enumerate(nodes):
        if not isinstance(node, dict):
            return None, f"nodes[{i}] must be an object"
        nid = node.get("id")
        if not _is_str(nid):
            return None, f"nodes[{i}].id must be a non-empty string"
        nid = str(nid).strip()
        if nid in seen_ids:
            return None, f"duplicate node id: {nid}"
        seen_ids.add(nid)
        ntype = node.get("type")
        if not isinstance(ntype, str) or ntype not in ALLOWED_TYPES:
            return None, f"nodes[{i}].type must be one of: {sorted(ALLOWED_TYPES)}"
        props = node.get("props") or {}
        err = _validate_props(ntype, props)
        if err:
            return None, f"nodes[{i}]: {err}"
        url_err = _validate_recipe_urls_for_node(ntype, props, i)
        if url_err:
            return None, url_err
        if ntype == "donate_section":
            has_donate = True
        if ntype == "progress_section":
            has_progress = True
        out_nodes.append({"id": nid, "type": ntype, "props": dict(props)})
    if not has_donate:
        return None, "recipe must include at least one donate_section node"
    if not has_progress:
        return None, "recipe must include at least one progress_section node"
    out: dict[str, Any] = {"version": "1", "nodes": out_nodes}
    theme = _validate_theme(raw.get("theme"))
    if theme:
        out["theme"] = theme
    try:
        encoded = json.dumps(out, ensure_ascii=False)
    except (TypeError, ValueError):
        return None, "recipe is not JSON-serializable"
    if len(encoded.encode("utf-8")) > MAX_RECIPE_JSON_BYTES:
        return None, f"recipe JSON exceeds maximum size ({MAX_RECIPE_JSON_BYTES} bytes)"
    return out, None


def recipe_schema_description() -> str:
    return """
Return ONLY valid JSON (no markdown) matching this shape:
{
  "version": "1",
  "nodes": [ ... ]
}

Each node: { "id": "unique-string", "type": "<type>", "props": { ... } }

Required: include at least one "donate_section" and one "progress_section" so visitors can donate and see fundraising progress.

IMPORTANT for all image/video URLs (hero.background_image_url, image.url, video.url, gallery item urls):
Use ONLY the exact "url" strings from the "Available media assets" list in the user message. Do not invent or use external URLs.

Types and props:
- hero: props.title (string, required, max 200 chars), props.subtitle (string, max 500), props.background_image_url (optional; must be one of the provided asset URLs)
- text: props.body (string, max 8000 chars; plain text, line breaks ok), props.align: "left"|"center"|"right"
- image: props.url (required; must be a provided asset URL), props.alt (string, max 500)
- video: props.url (required; must be a provided asset URL for uploaded video)
- gallery: props.items: [ { "url": "...", "alt": "..." }, ... ] (max 20 items; urls must be from provided assets)
- donate_section: props.label (string, max 120), props.preset_amounts (optional array of positive numbers, max 12)
- progress_section: props.show_goal (bool), props.show_count (bool), props.show_progress_bar (bool)
- footer: props.text (string, max 500)
- spacer: props.height_px (number 0-400)

Maximum 40 nodes total.
"""
