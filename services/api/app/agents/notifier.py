"""Notifier (FLOWS F10, G088): draft a neutral notice to a model's authors; post only after a
human approves, and only to repos on HF_POST_ALLOWLIST with HF_WRITE_TOKEN. Everything else
becomes READY_TO_COPY for a person to send themselves.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from app import llm
from app.config import get_settings
from app.errors import ApiError
from app.graph import db
from app.graph.queries import W16, X14, X26, X27, X28
from app.graph.rows import as_rows
from app.ids import new_id

log = logging.getLogger("modelbrain.notifier")
HUB = "https://huggingface.co"
SIGNATURE = "Sent with ModelBrain (automated screening, not legal advice)."


def template(
    model_id: str, parent: str, sim: float, licence: str, card_licence: str | None
) -> tuple[str, str]:
    title = "Lineage and licence metadata"
    body = (
        f"Hello, and thank you for publishing {model_id}.\n\n"
        f"An automated comparison of a small sample of this model's weights found that they closely "
        f"match {parent} (cosine similarity {sim:.3f}). The model card "
        f"{'declares ' + card_licence if card_licence else 'does not declare a licence'} and does not "
        f"declare a base model, while {parent} carries the {licence} licence.\n\n"
        f"If {parent} is the base, adding `base_model: {parent}` and the upstream licence to the card's "
        f"metadata would let downstream users see the obligations that may apply. If this match is "
        f"wrong, we would be glad to hear it.\n\n{SIGNATURE}"
    )
    return title, body


async def draft_for(
    model_id: str, *, target_repo: str | None = None, hub: str = "hub"
) -> dict[str, Any]:
    settings = get_settings()
    rows = as_rows(
        db.ro_query(
            hub, W16, {"id": model_id, "k": 50, "min_sim": settings.dna_derived_min, "min_tier": 1}
        )
    )
    if not rows:
        raise ApiError(
            "MODEL_NOT_FOUND",
            "No weight match to write about.",
            hint="Fingerprint the model first.",
        )
    top = rows[-1]  # deepest licence row: the root the obligations come from
    card = as_rows(db.ro_query(hub, X14, {"id": model_id}))
    title, body = template(
        model_id,
        str(rows[0]["weights_parent"]),
        float(rows[0]["sim"]),
        str(top["license"]),
        card[0].get("declared_license") if card else None,
    )
    source = "template"
    phrased = await llm.complete(
        "Rewrite this message so it stays neutral, specific and polite. Keep every fact and the last "
        f"line exactly. Do not accuse anyone.\n\n{body}"
    )
    if phrased and SIGNATURE in phrased:
        body, source = phrased, "llm"
    draft_id = new_id("draft")
    db.query(
        hub,
        X26,
        {
            "id": draft_id,
            "model_id": model_id,
            "target_repo": target_repo or model_id,
            "title": title,
            "body": body,
            "now": int(time.time() * 1000),
            "source": source,
        },
    )
    return {
        "id": draft_id,
        "target_repo": target_repo or model_id,
        "title": title,
        "body": body,
        "state": "AWAITING_APPROVAL",
        "source": source,
    }


def manual_draft(
    model_id: str, title: str, body: str, target_repo: str | None, hub: str = "hub"
) -> dict[str, Any]:
    if SIGNATURE not in body:
        body = f"{body.rstrip()}\n\n{SIGNATURE}"
    draft_id = new_id("draft")
    db.query(
        hub,
        X26,
        {
            "id": draft_id,
            "model_id": model_id,
            "target_repo": target_repo or model_id,
            "title": title,
            "body": body,
            "now": int(time.time() * 1000),
            "source": "manual",
        },
    )
    return {
        "id": draft_id,
        "target_repo": target_repo or model_id,
        "title": title,
        "body": body,
        "state": "AWAITING_APPROVAL",
        "source": "manual",
    }


async def approve(
    draft_id: str, *, hub: str = "hub", transport: httpx.AsyncBaseTransport | None = None
) -> dict[str, Any]:
    settings = get_settings()
    drafts = [d for d in as_rows(db.ro_query(hub, X28, {"limit": 500})) if d["id"] == draft_id]
    if not drafts:
        raise ApiError("MODEL_NOT_FOUND", f"No draft '{draft_id}'.")
    draft = drafts[0]
    repo = str(draft["target_repo"])
    now = int(time.time() * 1000)
    if repo not in settings.hf_post_allowlist or not settings.hf_write_token:
        rows = as_rows(
            db.query(
                hub, X27, {"id": draft_id, "state": "READY_TO_COPY", "posted_url": None, "now": now}
            )
        )
        return {**rows[0], "community_url": f"{HUB}/{repo}/discussions"}
    async with httpx.AsyncClient(timeout=20.0, transport=transport) as client:
        response = await client.post(
            f"{HUB}/api/models/{repo}/discussions",
            headers={"Authorization": f"Bearer {settings.hf_write_token}"},
            json={"title": draft["title"], "description": draft["body"], "pullRequest": False},
        )
    if response.status_code not in (200, 201):
        log.warning("discussion post failed", extra={"repo": repo, "status": response.status_code})
        raise ApiError(
            "HUB_UNAVAILABLE",
            f"The Hub refused the post ({response.status_code}).",
            hint="Check the token's write scope for this repo.",
        )
    num = response.json().get("num")
    url = f"{HUB}/{repo}/discussions/{num}" if num is not None else f"{HUB}/{repo}/discussions"
    rows = as_rows(
        db.query(hub, X27, {"id": draft_id, "state": "POSTED", "posted_url": url, "now": now})
    )
    log.info("notice posted", extra={"repo": repo, "url": url})
    return rows[0]


def list_drafts(limit: int = 50, hub: str = "hub") -> list[dict[str, Any]]:
    return as_rows(db.ro_query(hub, X28, {"limit": limit}))
