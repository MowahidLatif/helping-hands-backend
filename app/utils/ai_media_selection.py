"""
Select a balanced subset of campaign media for the AI site prompt.

Round-robin across image / video / doc / embed so image-heavy campaigns still
surface other types (instead of taking the first N rows by sort order).
"""

from __future__ import annotations

from typing import Any

_QUEUE_ORDER = ("image", "video", "doc", "embed")


def select_media_for_ai_prompt(
    items: list[dict[str, Any]], max_total: int
) -> list[dict[str, Any]]:
    if max_total <= 0 or not items:
        return []
    queues: dict[str, list[dict[str, Any]]] = {
        "image": [],
        "video": [],
        "doc": [],
        "embed": [],
    }
    for m in items:
        t = str(m.get("type") or "image").lower()
        if t not in queues:
            t = "image"
        queues[t].append(m)

    selected: list[dict[str, Any]] = []
    ptrs = {k: 0 for k in _QUEUE_ORDER}
    while len(selected) < max_total:
        progressed = False
        for k in _QUEUE_ORDER:
            if len(selected) >= max_total:
                break
            q = queues[k]
            i = ptrs[k]
            if i < len(q):
                selected.append(q[i])
                ptrs[k] += 1
                progressed = True
        if not progressed:
            break
    return selected
