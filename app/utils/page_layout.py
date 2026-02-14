"""
Campaign page layout schema and validation.

Pre-defined block types for drag-and-drop donation page builder.
Layout format: { "blocks": [ { "id": "...", "type": "...", "props": {...} }, ... ] }
"""

from typing import Any

# Allowed block types and their optional prop schemas
BLOCK_TYPES = frozenset(
    {
        "hero",
        "campaign_info",
        "donate_button",
        "media_gallery",
        "text",
        "embed",
        "footer",
    }
)

# Max blocks to prevent abuse
MAX_BLOCKS = 50

# Max length for string props
MAX_STRING_LEN = 10000

# Schema for frontend builders
BLOCK_SCHEMA = {
    "hero": {
        "props": {
            "title": "string",
            "subtitle": "string",
            "image_url": "string",
            "background_color": "string",
        },
    },
    "campaign_info": {
        "props": {
            "show_goal": "boolean",
            "show_progress_bar": "boolean",
            "show_donations_count": "boolean",
            "show_winner": "boolean",
        },
    },
    "donate_button": {
        "props": {
            "preset_amounts": "number[]",
            "label": "string",
            "min_amount": "number",
        },
    },
    "media_gallery": {
        "props": {"columns": "1-4", "aspect_ratio": "square|landscape|portrait|auto"},
    },
    "text": {
        "props": {"content": "string", "align": "left|center|right"},
    },
    "embed": {
        "props": {"url": "string", "height": "number"},
    },
    "footer": {
        "props": {"text": "string", "show_org_name": "boolean"},
    },
}


def _valid_id(s: Any) -> bool:
    return (
        isinstance(s, str)
        and len(s) <= 100
        and s.replace("-", "").replace("_", "").isalnum()
    )


def _valid_props_for_type(block_type: str, props: Any) -> tuple[bool, str | None]:
    """Validate props for a block type. Returns (valid, error)."""
    if props is None:
        return True, None
    if not isinstance(props, dict):
        return False, "props must be an object"
    if block_type == "hero":
        for k in props:
            if k not in ("title", "subtitle", "image_url", "background_color"):
                return False, f"hero: unknown prop '{k}'"
        for k in ("title", "subtitle", "image_url", "background_color"):
            if k in props and not isinstance(props[k], str):
                return False, f"hero.{k} must be string"
            if k in props and len(props[k]) > MAX_STRING_LEN:
                return False, f"hero.{k} too long"
    elif block_type == "campaign_info":
        for k in props:
            if k not in (
                "show_goal",
                "show_progress_bar",
                "show_donations_count",
                "show_winner",
            ):
                return False, f"campaign_info: unknown prop '{k}'"
        for k in (
            "show_goal",
            "show_progress_bar",
            "show_donations_count",
            "show_winner",
        ):
            if k in props and not isinstance(props[k], bool):
                return False, f"campaign_info.{k} must be boolean"
    elif block_type == "donate_button":
        for k in props:
            if k not in ("preset_amounts", "label", "min_amount"):
                return False, f"donate_button: unknown prop '{k}'"
        if "preset_amounts" in props:
            pa = props["preset_amounts"]
            if not isinstance(pa, list):
                return False, "donate_button.preset_amounts must be array"
            if len(pa) > 20:
                return False, "donate_button.preset_amounts max 20"
            for x in pa:
                if not isinstance(x, (int, float)) or x < 0:
                    return (
                        False,
                        "donate_button.preset_amounts values must be non-negative numbers",
                    )
        if "label" in props and (
            not isinstance(props["label"], str) or len(props["label"]) > 200
        ):
            return False, "donate_button.label must be string max 200"
        if "min_amount" in props:
            m = props["min_amount"]
            if not isinstance(m, (int, float)) or m < 0:
                return False, "donate_button.min_amount must be non-negative number"
    elif block_type == "media_gallery":
        for k in props:
            if k not in ("columns", "aspect_ratio"):
                return False, f"media_gallery: unknown prop '{k}'"
        if "columns" in props:
            c = props["columns"]
            if not isinstance(c, int) or c < 1 or c > 4:
                return False, "media_gallery.columns must be 1-4"
        if "aspect_ratio" in props:
            ar = props["aspect_ratio"]
            if ar not in ("square", "landscape", "portrait", "auto"):
                return (
                    False,
                    "media_gallery.aspect_ratio must be square|landscape|portrait|auto",
                )
    elif block_type == "text":
        for k in props:
            if k not in ("content", "align"):
                return False, f"text: unknown prop '{k}'"
        if "content" in props:
            c = props["content"]
            if not isinstance(c, str):
                return False, "text.content must be string"
            if len(c) > MAX_STRING_LEN:
                return False, "text.content too long"
        if "align" in props and props["align"] not in ("left", "center", "right"):
            return False, "text.align must be left|center|right"
    elif block_type == "embed":
        for k in props:
            if k not in ("url", "height"):
                return False, f"embed: unknown prop '{k}'"
        if "url" in props:
            u = props["url"]
            if not isinstance(u, str) or len(u) > 2000:
                return False, "embed.url must be string max 2000"
        if "height" in props:
            h = props["height"]
            if not isinstance(h, (int, float)) or h < 100 or h > 1000:
                return False, "embed.height must be 100-1000"
    elif block_type == "footer":
        for k in props:
            if k not in ("text", "show_org_name"):
                return False, f"footer: unknown prop '{k}'"
        if "text" in props:
            t = props["text"]
            if not isinstance(t, str) or len(t) > 2000:
                return False, "footer.text must be string max 2000"
        if "show_org_name" in props and not isinstance(props["show_org_name"], bool):
            return False, "footer.show_org_name must be boolean"
    return True, None


def validate_layout(layout: Any) -> tuple[bool, str | None]:
    """
    Validate a page layout. Returns (valid, error_message).
    """
    if layout is None:
        return True, None
    if not isinstance(layout, dict):
        return False, "layout must be an object"
    blocks = layout.get("blocks")
    if blocks is None:
        return True, None
    if not isinstance(blocks, list):
        return False, "blocks must be an array"
    if len(blocks) > MAX_BLOCKS:
        return False, f"blocks max {MAX_BLOCKS}"
    seen_ids = set()
    for i, block in enumerate(blocks):
        if not isinstance(block, dict):
            return False, f"block {i} must be an object"
        bid = block.get("id")
        btype = block.get("type")
        props = block.get("props")
        if not bid or not _valid_id(bid):
            return False, f"block {i}: id required and must be alphanumeric with -_"
        if bid in seen_ids:
            return False, f"block {i}: duplicate id '{bid}'"
        seen_ids.add(bid)
        if not btype or btype not in BLOCK_TYPES:
            return False, f"block {i}: type must be one of {sorted(BLOCK_TYPES)}"
        ok, err = _valid_props_for_type(btype, props)
        if not ok:
            return False, f"block {i}: {err}"
    return True, None
