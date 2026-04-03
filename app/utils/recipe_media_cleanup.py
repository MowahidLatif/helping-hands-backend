"""
Remove references to deleted media URLs from ai_site_recipe and page_layout.

Also exposes helpers to detect recipe URLs that are not backed by campaign_media rows.
"""

from __future__ import annotations

import copy
from typing import Any

from app.models.campaign import get_campaign
from app.models.media import list_media_for_campaign
from app.utils.ai_site_recipe import validate_ai_site_recipe
from app.utils.page_layout import validate_layout
from app.utils.s3_helpers import public_url


def removed_media_url_set(*, stored_url: str | None, s3_key: str | None) -> set[str]:
    out: set[str] = set()
    if stored_url and isinstance(stored_url, str) and stored_url.strip():
        out.add(stored_url.strip())
    if s3_key and isinstance(s3_key, str) and s3_key.strip():
        out.add(public_url(s3_key.strip()))
    return out


def _collect_urls_from_recipe_dict(recipe: dict[str, Any]) -> set[str]:
    urls: set[str] = set()
    nodes = recipe.get("nodes")
    if not isinstance(nodes, list):
        return urls
    for node in nodes:
        if not isinstance(node, dict):
            continue
        ntype = node.get("type")
        props = node.get("props")
        if not isinstance(props, dict):
            continue
        if ntype == "hero":
            u = props.get("background_image_url")
            if isinstance(u, str) and u.strip():
                urls.add(u.strip())
        elif ntype in ("image", "video"):
            u = props.get("url")
            if isinstance(u, str) and u.strip():
                urls.add(u.strip())
        elif ntype == "gallery":
            items = props.get("items")
            if isinstance(items, list):
                for it in items:
                    if isinstance(it, dict):
                        u = it.get("url")
                        if isinstance(u, str) and u.strip():
                            urls.add(u.strip())
    return urls


def collect_recipe_media_urls(recipe: Any) -> list[str]:
    """Sorted unique http(s) URLs referenced by media-related recipe nodes."""
    if not isinstance(recipe, dict):
        return []
    return sorted(_collect_urls_from_recipe_dict(recipe))


def list_recipe_urls_missing_from_campaign_media(campaign_id: str) -> list[str]:
    """
    URLs present in ai_site_recipe but not matching any campaign_media.url
    or derived public URL for campaign_media.s3_key.
    """
    camp = get_campaign(campaign_id)
    if not camp:
        return []
    recipe = camp.get("ai_site_recipe")
    if not isinstance(recipe, dict):
        return []
    in_recipe = _collect_urls_from_recipe_dict(recipe)
    if not in_recipe:
        return []
    allowed: set[str] = set()
    for row in list_media_for_campaign(campaign_id):
        u = row.get("url")
        if isinstance(u, str) and u.strip():
            allowed.add(u.strip())
        sk = row.get("s3_key")
        if isinstance(sk, str) and sk.strip():
            allowed.add(public_url(sk.strip()))
    return sorted(u for u in in_recipe if u not in allowed)


def strip_removed_urls_from_recipe(
    recipe: dict[str, Any], removed: set[str]
) -> tuple[dict[str, Any] | None, bool]:
    """
    Return a deep-copied recipe with references to any URL in `removed` cleared or nodes dropped.
    If the result does not validate, returns (None, False) and the caller should not persist.
    """
    if not removed:
        return recipe, False
    r = copy.deepcopy(recipe)
    nodes = r.get("nodes")
    if not isinstance(nodes, list):
        return None, False
    changed = False
    new_nodes: list[dict[str, Any]] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        ntype = node.get("type")
        props = node.get("props")
        if not isinstance(props, dict):
            new_nodes.append(node)
            continue
        if ntype == "hero":
            bg = props.get("background_image_url")
            if isinstance(bg, str) and bg in removed:
                props.pop("background_image_url", None)
                changed = True
            new_nodes.append(node)
        elif ntype == "image":
            u = props.get("url")
            if isinstance(u, str) and u in removed:
                changed = True
                continue
            new_nodes.append(node)
        elif ntype == "video":
            u = props.get("url")
            if isinstance(u, str) and u in removed:
                changed = True
                continue
            new_nodes.append(node)
        elif ntype == "gallery":
            items = props.get("items")
            if isinstance(items, list):
                kept = []
                for it in items:
                    if not isinstance(it, dict):
                        continue
                    u = it.get("url")
                    if isinstance(u, str) and u in removed:
                        changed = True
                        continue
                    kept.append(it)
                if len(kept) != len(items):
                    props["items"] = kept
                if len(kept) == 0:
                    changed = True
                    continue
            new_nodes.append(node)
        else:
            new_nodes.append(node)
    r["nodes"] = new_nodes
    if not changed:
        return recipe, False
    valid, _err = validate_ai_site_recipe(r)
    if valid is None:
        return None, False
    return valid, True


def strip_removed_urls_from_page_layout(
    layout: dict[str, Any], removed: set[str]
) -> tuple[dict[str, Any] | None, bool]:
    if not removed:
        return layout, False
    lo = copy.deepcopy(layout)
    blocks = lo.get("blocks")
    if not isinstance(blocks, list):
        return None, False
    changed = False
    for block in blocks:
        if not isinstance(block, dict):
            continue
        btype = block.get("type")
        props = block.get("props")
        if not isinstance(props, dict):
            continue
        if btype == "hero":
            u = props.get("image_url")
            if isinstance(u, str) and u in removed:
                props.pop("image_url", None)
                changed = True
        elif btype == "embed":
            u = props.get("url")
            if isinstance(u, str) and u in removed:
                props.pop("url", None)
                changed = True
    if not changed:
        return layout, False
    ok, _err = validate_layout(lo)
    if not ok:
        return None, False
    return lo, True
