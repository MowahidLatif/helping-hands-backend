"""
Build master prompts, call OpenAI, validate recipe, persist to campaign.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import urllib.error
import urllib.request
from typing import Any

from app.models.ai_generation_job import update_job
from app.models.campaign import get_campaign, set_ai_site_recipe
from app.models.media import list_media_for_campaign
from app.utils.ai_media_selection import select_media_for_ai_prompt
from app.utils.ai_site_recipe import recipe_schema_description, validate_ai_site_recipe
from app.utils.prompt_sanitize import sanitize_asset_description

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_AI_SITE_MODEL", "gpt-4o-mini")
MAX_USER_PROMPT_LEN = 8000
# Balanced round-robin cap (see ai_media_selection); override with OPENAI_AI_SITE_MAX_ASSETS (1–80)
_MAX_ASSETS_RAW = int(os.getenv("OPENAI_AI_SITE_MAX_ASSETS", "32"))
MAX_ASSETS_IN_PROMPT = max(1, min(80, _MAX_ASSETS_RAW))
_ASSETS_JSON_RAW = int(os.getenv("OPENAI_AI_SITE_ASSETS_JSON_MAX", "20000"))
ASSETS_JSON_BUDGET = max(4000, min(100_000, _ASSETS_JSON_RAW))


def _strip_control(s: str) -> str:
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", s)[:MAX_USER_PROMPT_LEN]


def build_asset_context(campaign_id: str) -> tuple[list[dict[str, Any]], int]:
    """
    Returns (assets_for_prompt, total_media_count_for_campaign).
    Selection is round-robin by type so videos/docs are not drowned out by many images.
    """
    raw = list_media_for_campaign(campaign_id)
    total = len(raw)
    selected = select_media_for_ai_prompt(raw, MAX_ASSETS_IN_PROMPT)
    out: list[dict[str, Any]] = []
    for m in selected:
        url = m.get("url") or ""
        if not url and m.get("s3_key"):
            from app.utils.s3_helpers import public_url

            url = public_url(m["s3_key"])
        out.append(
            {
                "id": str(m.get("id", "")),
                "type": m.get("type"),
                "url": url,
                "description": sanitize_asset_description(m.get("description")),
            }
        )
    return out, total


def build_master_prompt(
    *,
    user_prompt: str,
    campaign_title: str,
    assets: list[dict[str, Any]],
    total_campaign_assets: int,
) -> tuple[str, str]:
    """
    Returns (system_message, user_message).
    """
    user_prompt = _strip_control(user_prompt)
    system = (
        "You are a web designer producing a single-page fundraising site layout as JSON. "
        + recipe_schema_description()
        + "\nCampaign title (context): "
        + _strip_control(campaign_title or "Fundraiser")[:200]
    )
    n = len(assets)
    total = total_campaign_assets
    assets_json = json.dumps(assets, indent=2)
    if len(assets_json) > ASSETS_JSON_BUDGET:
        assets_json = assets_json[:ASSETS_JSON_BUDGET] + "\n... (truncated)"
    user_msg = (
        "User request:\n"
        + user_prompt
        + f"\n\nNote: Listed below are up to {n} of {total} total campaign assets "
        "(balanced across image, video, document, and embed types where present). "
        "Use only URLs from this list in the recipe.\n\n"
        + "Available media assets (use these URLs in the layout):\n"
        + assets_json
    )
    return system, user_msg


def _openai_chat_json(system: str, user: str) -> dict[str, Any]:
    if not OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY is not configured; set it to enable AI site generation."
        )
    body = json.dumps(
        {
            "model": OPENAI_MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.7,
        }
    ).encode("utf-8")
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
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")[:2000]
        raise RuntimeError(f"OpenAI HTTP {e.code}: {err_body}") from e
    except Exception as e:
        raise RuntimeError(f"OpenAI request failed: {e}") from e

    try:
        content = raw["choices"][0]["message"]["content"]
        parsed = json.loads(content)
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        raise RuntimeError(f"Invalid OpenAI response shape: {e}") from e
    return parsed


def generate_and_validate_recipe(
    *,
    user_prompt: str,
    campaign_id: str,
) -> dict[str, Any]:
    camp = get_campaign(campaign_id)
    if not camp:
        raise RuntimeError("campaign not found")
    assets, total_assets = build_asset_context(campaign_id)
    system, user_msg = build_master_prompt(
        user_prompt=user_prompt,
        campaign_title=str(camp.get("title") or ""),
        assets=assets,
        total_campaign_assets=total_assets,
    )
    parsed = _openai_chat_json(system, user_msg)
    recipe, err = validate_ai_site_recipe(parsed)
    if err or not recipe:
        try:
            parsed_size = len(json.dumps(parsed, ensure_ascii=False))
        except (TypeError, ValueError):
            parsed_size = -1
        logger.warning(
            "ai_site_recipe validation failed (campaign_id=%s, parsed_json_chars=%s): %s",
            campaign_id,
            parsed_size,
            err or "unknown",
        )
        # One repair attempt: ask model to fix
        repair_system = (
            "You output invalid JSON for a site recipe. Fix it. "
            + recipe_schema_description()
            + "\nValidation error: "
            + (err or "unknown")
        )
        repair_user = "Previous (invalid) JSON:\n" + json.dumps(parsed)[:8000]
        parsed2 = _openai_chat_json(repair_system, repair_user)
        recipe, err = validate_ai_site_recipe(parsed2)
        if err or not recipe:
            logger.error(
                "ai_site_recipe validation failed after repair (campaign_id=%s): %s",
                campaign_id,
                err or "unknown",
            )
            raise RuntimeError(err or "recipe validation failed after repair")
    return recipe


def run_generation_in_background(
    app: Any,
    job_id: str,
    campaign_id: str,
    user_prompt: str,
) -> None:
    def _work() -> None:
        with app.app_context():
            try:
                update_job(
                    job_id,
                    status="running",
                    step="Analyzing assets and prompt",
                    progress_percent=15,
                )
                update_job(
                    job_id,
                    step="Calling AI model",
                    progress_percent=40,
                )
                recipe = generate_and_validate_recipe(
                    user_prompt=user_prompt,
                    campaign_id=campaign_id,
                )
                update_job(
                    job_id,
                    step="Saving site recipe",
                    progress_percent=85,
                )
                set_ai_site_recipe(campaign_id, recipe)
                update_job(
                    job_id,
                    status="completed",
                    step="Done",
                    progress_percent=100,
                    error_message=None,
                )
            except Exception as e:
                msg = str(e)[:2000]
                update_job(
                    job_id,
                    status="failed",
                    step="Failed",
                    error_message=msg,
                )

    t = threading.Thread(target=_work, daemon=True)
    t.start()
