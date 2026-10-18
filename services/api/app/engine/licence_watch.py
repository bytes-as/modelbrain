"""Licence text watch and custom licence resolution (FLOWS F17, G132, G134).

Watch: every licence text the clauses come from is fetched, normalised and hashed. A new
hash is a new (:LicenseText) version linked to its clauses (L1); every active ruling that
rests on one of those clauses reopens for its owner (T8 -> T4). The first fetch is a baseline.

Custom licences: a model declaring 'other' with a license_link gets its linked text fetched;
when at least two clause locators of one known licence appear in it, the declaration becomes
that licence (source matched_text). Anything else stays 'other', which is NEEDS_COUNSEL.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any

from app.engine.watcher import company_graphs
from app.fetch import Fetcher, normalise
from app.graph import db
from app.graph.queries import L1, L2, T4, T8, X24, X25, X29
from app.graph.rows import as_rows
from app.ids import new_id
from app.paths import repo_root

log = logging.getLogger("modelbrain.licence_watch")
MIN_LOCATORS = 2
_last: dict[str, Any] = {}


def _seed() -> dict[str, Any]:
    return json.loads((repo_root() / "data" / "clauses.seed.json").read_text())


def sources() -> dict[str, list[str]]:
    """source_raw_url -> clause ids that quote it."""
    found: dict[str, list[str]] = {}
    for licence in _seed()["licenses"]:
        for clause in licence.get("clauses", []):
            url = clause.get("source_raw_url")
            if url:
                found.setdefault(str(url), []).append(str(clause["id"]))
    return found


def locators() -> dict[str, list[str]]:
    """licence key -> distinctive clause locator phrases (normalised, lower case)."""
    found: dict[str, list[str]] = {}
    for licence in _seed()["licenses"]:
        phrases = [
            normalise(str(c["locator"])).lower()
            for c in licence.get("clauses", [])
            if c.get("locator")
        ]
        if phrases:
            found[str(licence["key"])] = phrases
    return found


# Each licence's own name must appear verbatim: clause locators alone ("copy of this
# Agreement") are generic and matched unrelated custom licences.
NAME_PHRASES: dict[str, tuple[str, ...]] = {
    "llama3": ("meta llama 3 community license",),
    "llama3_1": ("llama 3.1 community license",),
    "llama3_2": ("llama 3.2 community license",),
    "llama3_3": ("llama 3.3 community license",),
    "llama4": ("llama 4 community license",),
    "gemma": ("gemma terms of use",),
    "apache-2.0": ("apache license", "version 2.0"),
    "mit": ("mit license",),
    "cc-by-nc-4.0": ("attribution-noncommercial 4.0",),
    "cc-by-4.0": ("attribution 4.0 international",),
    "cc-by-sa-4.0": ("attribution-sharealike 4.0",),
}


def match_licence(text: str) -> str | None:
    low = normalise(text).lower()
    best: tuple[int, str] | None = None
    for key, phrases in locators().items():
        names = NAME_PHRASES.get(key)
        if not names or not all(name in low for name in names):
            continue
        hits = sum(1 for phrase in phrases if phrase and phrase in low)
        if hits >= min(MIN_LOCATORS, len(phrases)) and (best is None or hits > best[0]):
            best = (hits, key)
    return best[1] if best else None


def undo_matches(hub: str = "hub") -> int:
    rows = as_rows(db.query(hub, X29))
    return int(rows[0]["restored"]) if rows else 0


def _sha(text: str) -> str:
    return hashlib.sha256(normalise(text).encode("utf-8")).hexdigest()


async def run_watch(
    fetcher: Fetcher | None = None, hub: str = "hub", graphs: list[str] | None = None
) -> dict[str, Any]:
    own = fetcher is None
    fetcher = fetcher or Fetcher()
    now = int(time.time() * 1000)
    report: dict[str, Any] = {
        "sources": 0,
        "baseline": 0,
        "changed": [],
        "unreachable": 0,
        "reopened": 0,
    }
    try:
        for url, clause_ids in sources().items():
            report["sources"] += 1
            text = await fetcher.text(url)
            if not text:
                report["unreachable"] += 1
                continue
            sha = _sha(text)
            previous = as_rows(db.ro_query(hub, L2, {"url": url}))
            if previous and previous[0].get("sha") == sha:
                continue
            text_id = f"{url}@{sha[:16]}"
            db.query(
                hub,
                L1,
                {
                    "text_id": text_id,
                    "url": url,
                    "sha": sha,
                    "now": now,
                    "clause_ids": clause_ids,
                },
            )
            if not previous:
                report["baseline"] += 1
                continue
            reason = f"licence text changed at {url}"
            report["changed"].append({"url": url, "clauses": clause_ids})
            for graph in company_graphs() if graphs is None else graphs:
                for row in as_rows(db.ro_query(graph, T8, {"clause_ids": clause_ids})):
                    db.query(
                        graph,
                        T4,
                        {
                            "ruling_id": row["ruling_id"],
                            "owner_id": row["owner_id"],
                            "event_id": new_id("evt"),
                            "task_id": new_id("task"),
                            "now": now,
                            "reason": reason,
                        },
                    )
                    report["reopened"] += 1
    finally:
        if own:
            await fetcher.aclose()
    report["at"] = now
    _last.clear()
    _last.update(report)
    return report


async def resolve_custom_licences(
    client: Any, fetcher: Fetcher | None = None, hub: str = "hub", limit: int = 100
) -> dict[str, Any]:
    own = fetcher is None
    fetcher = fetcher or Fetcher()
    report: dict[str, Any] = {"checked": 0, "no_link": 0, "matched": [], "unmatched": 0}
    try:
        for row in as_rows(db.ro_query(hub, X24))[:limit]:
            model_id = str(row["id"])
            info = await client.get_json(f"https://huggingface.co/api/models/{model_id}")
            card = (info or {}).get("cardData") or {} if isinstance(info, dict) else {}
            link = card.get("license_link") if isinstance(card, dict) else None
            report["checked"] += 1
            if not isinstance(link, str) or not link.startswith(("http://", "https://")):
                if isinstance(link, str) and link:
                    link = f"https://huggingface.co/{model_id}/raw/main/{link.lstrip('/')}"
                else:
                    report["no_link"] += 1
                    continue
            text = await fetcher.text(link)
            key = match_licence(text) if text else None
            if not key:
                report["unmatched"] += 1
                continue
            db.query(
                hub,
                X25,
                {
                    "id": model_id,
                    "license_key": key,
                    "sha": row.get("sha") or "",
                    "text_sha": _sha(text),
                },
            )
            report["matched"].append({"model_id": model_id, "license": key, "link": link})
    finally:
        if own:
            await fetcher.aclose()
    return report


def last_report() -> dict[str, Any]:
    return dict(_last)
