"""Run Scout ingest jobs and startup prewarm."""

from __future__ import annotations

import asyncio
import csv
import json
import logging
from pathlib import Path

from app.agents.scout import ingest
from app.config import get_settings
from app.errors import ApiError
from app.hf.cache import DiskCache
from app.hf.client import HFClient, HubUnavailable
from app.hf.live import LiveHub
from app.hf.parse import load_normalise
from app.jobs.registry import jobs
from app.paths import repo_root

log = logging.getLogger("modelbrain.jobs")

_prewarm_task: asyncio.Task[None] | None = None


def _hub_resources() -> tuple[dict[str, str], set[str]]:
    root = repo_root()
    seed = json.loads((root / "data" / "clauses.seed.json").read_text())
    roots = set(json.loads((root / "data" / "roots.json").read_text())["orgs"])
    return load_normalise(seed), roots


async def _ingest_once(model_id: str, *, children: bool = False) -> None:
    table, roots = _hub_resources()
    settings = get_settings()
    client = HFClient(token=settings.hf_token, cache=DiskCache(Path("/tmp/modelbrain-hf")))
    try:
        result = await ingest(
            model_id,
            LiveHub(client),
            table=table,
            roots=roots,
            graph="hub",
            children=children,
        )
    except HubUnavailable as exc:
        raise ApiError(
            "HUB_UNAVAILABLE",
            "The Hugging Face Hub is unavailable and this model is not cached.",
            hint="Try again shortly.",
            retry_after_s=exc.retry_after_s,
        ) from exc
    finally:
        await client.aclose()
    try:
        from app.engine.dna import after_ingest

        await after_ingest(result.model_ids)
    except Exception:
        log.exception("weight DNA after ingest failed", extra={"model_id": model_id})


async def start_ingest(
    model_id: str,
    *,
    children: bool = False,
    wait_s: float | None = None,
) -> tuple[str | None, str]:
    """Return (queued_job_id, job_id). queued_job_id is set when wait_s elapsed before completion."""
    registry = jobs()
    record = await registry.create(model_id)
    asyncio.create_task(_run_job(record.id, model_id, children=children))
    if wait_s is None:
        return None, record.id
    try:
        await asyncio.wait_for(record.done.wait(), timeout=wait_s)
    except TimeoutError:
        return record.id, record.id
    if record.status == "failed":
        raise ApiError(
            "HUB_UNAVAILABLE",
            record.error or "Ingest failed.",
            hint="Try again shortly.",
            retry_after_s=30,
        )
    return None, record.id


async def _run_job(job_id: str, model_id: str, *, children: bool) -> None:
    table, roots = _hub_resources()
    settings = get_settings()
    client = HFClient(token=settings.hf_token, cache=DiskCache(Path("/tmp/modelbrain-hf")))
    registry = jobs()

    done: dict[str, object] = {}

    def emit(event: dict[str, object]) -> None:
        # Hold "done" until weight DNA has run, so the first verdict sees weight lineage.
        if event.get("type") == "done":
            done.update(event)
            return
        registry.emit(job_id, event)

    try:
        result = await ingest(
            model_id,
            LiveHub(client),
            table=table,
            roots=roots,
            graph="hub",
            children=children,
            emit=emit,
        )
        try:
            from app.engine.dna import after_ingest

            report = await after_ingest(result.model_ids)
            if report.get("fingerprinted"):
                registry.emit(job_id, {"type": "dna", **report})
        except Exception:
            log.exception("weight DNA after ingest failed", extra={"model_id": model_id})
        registry.emit(job_id, done or {"type": "done"})
    except HubUnavailable as exc:
        registry.emit(job_id, {"type": "error", "message": str(exc)})
    except Exception:
        log.exception("ingest job %s failed", job_id)
        registry.emit(job_id, {"type": "error", "message": "ingest failed"})
    finally:
        await client.aclose()


def prewarm_model_ids() -> list[tuple[str, bool]]:
    root = repo_root()
    payload = json.loads((root / "data" / "prewarm.json").read_text())
    demo = list(payload.get("demo") or [])
    with_children = set(payload.get("with_children") or [])
    seen: set[str] = set()
    ordered: list[tuple[str, bool]] = []
    for model_id in demo:
        if model_id not in seen:
            seen.add(model_id)
            ordered.append((model_id, model_id in with_children))
    csv_path = root / "eval" / "models.csv"
    if csv_path.is_file():
        with csv_path.open(newline="") as handle:
            for row in csv.DictReader(handle):
                model_id = (row.get("model_id") or "").strip()
                if model_id and model_id not in seen:
                    seen.add(model_id)
                    ordered.append((model_id, False))
    return ordered


async def run_prewarm() -> None:
    items = prewarm_model_ids()
    log.info("prewarm starting for %s models", len(items))
    for model_id, children in items:
        try:
            await _ingest_once(model_id, children=children)
        except ApiError as exc:
            log.warning("prewarm skipped %s: %s", model_id, exc.message)
        except Exception:
            log.exception("prewarm failed for %s", model_id)
        await asyncio.sleep(0)
    try:
        from app.engine.resolver import run_resolver, set_declared_differs

        run_resolver("hub")
        set_declared_differs("hub")
    except Exception:
        log.exception("resolver after prewarm failed")
    log.info("prewarm finished")


def schedule_prewarm() -> None:
    global _prewarm_task
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    if _prewarm_task is not None and not _prewarm_task.done():
        return
    _prewarm_task = loop.create_task(run_prewarm())
