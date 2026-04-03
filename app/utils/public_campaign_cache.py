"""HTTP caching (ETag, Cache-Control) and optional Redis for public campaign JSON."""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from flask import jsonify, make_response, request

from app.utils.cache import r

logger = logging.getLogger(__name__)

PUBLIC_JSON_REDIS_TTL = 30
PUBLIC_CACHE_CONTROL = "public, max-age=30, stale-while-revalidate=120"


def _cache_key(campaign_id: str) -> str:
    return f"public:json:v1:{campaign_id}"


def invalidate_public_campaign_cache(campaign_id: str) -> None:
    try:
        r().delete(_cache_key(campaign_id))
    except Exception as e:
        logger.debug("public campaign cache invalidate skipped: %s", e)


def _etag_for_dict(body: dict[str, Any]) -> str:
    raw = json.dumps(body, sort_keys=True, default=str)
    h = hashlib.sha256(raw.encode()).hexdigest()[:32]
    return f'"{h}"'


def respond_public_campaign_json(resp_dict: dict[str, Any], campaign_id: str):
    """
    Merge Redis cache (optional), set ETag + Cache-Control, honor If-None-Match → 304.
    """
    key = _cache_key(campaign_id)
    body: dict[str, Any] | None = None
    try:
        cached = r().get(key)
        if cached:
            body = json.loads(cached)
    except Exception as e:
        logger.debug("public campaign redis read skipped: %s", e)

    if body is None:
        body = resp_dict
        try:
            r().setex(key, PUBLIC_JSON_REDIS_TTL, json.dumps(resp_dict, default=str))
        except Exception as e:
            logger.debug("public campaign redis write skipped: %s", e)

    etag = _etag_for_dict(body)
    inm = request.headers.get("If-None-Match")
    if inm and inm.strip() == etag:
        out = make_response("", 304)
        out.headers["ETag"] = etag
        out.headers["Cache-Control"] = PUBLIC_CACHE_CONTROL
        return out

    out = make_response(jsonify(body), 200)
    out.headers["ETag"] = etag
    out.headers["Cache-Control"] = PUBLIC_CACHE_CONTROL
    return out
