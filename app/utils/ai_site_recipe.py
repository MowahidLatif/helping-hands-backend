"""
Validate AI-generated site recipe JSON (DSL v1). No executable code — declarative nodes only.
"""

from __future__ import annotations

from typing import Any

MAX_NODES = 40
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


def _is_str(v: Any) -> bool:
    return isinstance(v, str) and len(v.strip()) > 0


def _is_optional_str(v: Any) -> bool:
    return v is None or isinstance(v, str)


def _validate_props(node_type: str, props: dict[str, Any]) -> str | None:
    if not isinstance(props, dict):
        return "props must be an object"
    if node_type == "hero":
        if not _is_str(props.get("title")):
            return "hero requires non-empty string title"
        if not _is_optional_str(props.get("subtitle")):
            return "hero subtitle must be a string"
        if props.get("background_image_url") is not None and not isinstance(
            props.get("background_image_url"), str
        ):
            return "hero background_image_url must be a string"
        return None
    if node_type == "text":
        body = props.get("body")
        if not _is_str(body):
            return "text requires non-empty string body"
        align = props.get("align")
        if align is not None and align not in ("left", "center", "right"):
            return "text align must be left, center, or right"
        return None
    if node_type == "image":
        if not _is_str(props.get("url")):
            return "image requires non-empty string url"
        if not _is_optional_str(props.get("alt")):
            return "image alt must be a string"
        return None
    if node_type == "video":
        if not _is_str(props.get("url")):
            return "video requires non-empty string url"
        return None
    if node_type == "gallery":
        items = props.get("items")
        if not isinstance(items, list) or len(items) == 0:
            return "gallery requires non-empty items array"
        for i, it in enumerate(items[:20]):
            if not isinstance(it, dict) or not _is_str(it.get("url")):
                return f"gallery.items[{i}] must have url string"
        return None
    if node_type == "donate_section":
        if not _is_optional_str(props.get("label")):
            return "donate_section label must be a string"
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
        return None
    if node_type == "spacer":
        h = props.get("height_px")
        if h is not None and (not isinstance(h, (int, float)) or h < 0 or h > 400):
            return "spacer height_px must be between 0 and 400"
        return None
    return None


def validate_ai_site_recipe(raw: Any) -> tuple[dict[str, Any] | None, str | None]:
    """
    Returns (normalized_recipe, None) on success, or (None, error_message).
    """
    if not isinstance(raw, dict):
        return None, "recipe must be a JSON object"
    version = raw.get("version")
    if version != "1" and version != 1:
        return None, 'recipe.version must be "1"'
    nodes = raw.get("nodes")
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
        if ntype == "donate_section":
            has_donate = True
        if ntype == "progress_section":
            has_progress = True
        out_nodes.append({"id": nid, "type": ntype, "props": dict(props)})
    if not has_donate:
        return None, "recipe must include at least one donate_section node"
    if not has_progress:
        return None, "recipe must include at least one progress_section node"
    return {"version": "1", "nodes": out_nodes}, None


def recipe_schema_description() -> str:
    return """
Return ONLY valid JSON (no markdown) matching this shape:
{
  "version": "1",
  "nodes": [ ... ]
}

Each node: { "id": "unique-string", "type": "<type>", "props": { ... } }

Required: include at least one "donate_section" and one "progress_section" so visitors can donate and see fundraising progress.

Types and props:
- hero: props.title (string, required), props.subtitle (string), props.background_image_url (string URL from assets when appropriate)
- text: props.body (string, HTML allowed as plain text only — use line breaks, no script tags), props.align: "left"|"center"|"right"
- image: props.url (string URL), props.alt (string)
- video: props.url (string — use asset URL for uploaded video or a public embed URL if provided)
- gallery: props.items: [ { "url": "...", "alt": "..." }, ... ] (max 20)
- donate_section: props.label (string, e.g. "Donate now"), props.preset_amounts (optional array of positive numbers, e.g. [5,10,25,50])
- progress_section: props.show_goal (bool), props.show_count (bool), props.show_progress_bar (bool)
- footer: props.text (string)
- spacer: props.height_px (number 0-400)

Use the provided asset URLs in image, video, gallery, and hero.background_image_url where they fit the user's request.
"""
