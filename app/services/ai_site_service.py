"""
Build master prompts, call OpenAI, validate recipe, persist to campaign.
"""

from __future__ import annotations

import json
import os
import re
import threading
import urllib.error
import urllib.request
from typing import Any

from app.models.ai_generation_job import update_job
from app.models.campaign import get_campaign, set_ai_site_recipe
from app.models.media import list_media_for_campaign
from app.utils.ai_site_recipe import recipe_schema_description, validate_ai_site_recipe

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_AI_SITE_MODEL", "gpt-4o-mini")
MAX_USER_PROMPT_LEN = 8000
MAX_ASSETS_IN_PROMPT = 24


def _strip_control(s: str) -> str:
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", s)[:MAX_USER_PROMPT_LEN]


def build_asset_context(campaign_id: str) -> list[dict[str, Any]]:
    items = list_media_for_campaign(campaign_id)[:MAX_ASSETS_IN_PROMPT]
    out = []
    for m in items:
        url = m.get("url") or ""
        if not url and m.get("s3_key"):
            from app.utils.s3_helpers import public_url

            url = public_url(m["s3_key"])
        out.append(
            {
                "id": str(m.get("id", "")),
                "type": m.get("type"),
                "url": url,
                "description": (m.get("description") or "")[:500],
            }
        )
    return out


def build_master_prompt(
    *,
    user_prompt: str,
    campaign_title: str,
    assets: list[dict[str, Any]],
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
    user_msg = (
        "User request:\n"
        + user_prompt
        + "\n\nAvailable media assets (use these URLs in the layout):\n"
        + json.dumps(assets, indent=2)[:12000]
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
    assets = build_asset_context(campaign_id)
    system, user_msg = build_master_prompt(
        user_prompt=user_prompt,
        campaign_title=str(camp.get("title") or ""),
        assets=assets,
    )
    parsed = _openai_chat_json(system, user_msg)
    recipe, err = validate_ai_site_recipe(parsed)
    if err or not recipe:
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
