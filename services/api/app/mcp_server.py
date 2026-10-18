"""MCP server at /mcp (FastMCP, streamable HTTP, mcp>=1.10,<2)."""

from __future__ import annotations

import json
import logging
from typing import Any

from mcp.server.fastmcp import FastMCP

from app.config import get_settings
from app.engine.verdict import verdict_from_graph
from app.graph.db import ro_query
from app.graph.queries import A1, A2, A3, A4, Q3
from app.graph.rows import as_rows
from app.tenants.conversations import record_turn

log = logging.getLogger("modelbrain.mcp")

mcp = FastMCP("modelbrain", stateless_http=True)


def _format_can_i_use(decided: dict[str, Any], hq: str) -> str:
    verdict = decided["verdict"]
    reason = ""
    if decided.get("blocking"):
        reason = decided["blocking"][0].get("summary") or ""
    line1 = f"VERDICT: {verdict}"
    if hq in {"DE", "FR", "AT", "NL", "BE", "ES", "IT"} and verdict == "BLOCKED":
        line1 += f" (EU company; {reason})" if reason else " (EU company)"
    lines = [line1]
    if decided.get("paths"):
        lines.append("Path: " + " -> ".join(decided["paths"][0]["path"]))
    for hit in (decided.get("blocking") or decided.get("obligations") or [])[:3]:
        lines.append(f"- {hit.get('clause_id')}: {hit.get('summary')} ({hit.get('source_url')})")
    base = get_settings().next_public_api_url.replace(":8000", ":3001")
    if "localhost:8000" in get_settings().next_public_api_url:
        base = "http://localhost:3001"
    lines.append(f"Details: {base}/m/{decided['model_id']}?hq={hq}")
    lines.append(decided.get("disclaimer") or "Automated screening, not legal advice.")
    return "\n".join(lines)


@mcp.tool(
    description=(
        "Check whether a Hugging Face model may be used in a product, given where the company "
        "is based and how the product is used. Call this before adding from_pretrained or "
        "downloading a model."
    )
)
async def can_i_use(
    model_id: str,
    hq_country: str,
    commercial: bool = True,
    markets: list[str] | None = None,
    mau: int = 0,
    distributes_weights: bool = False,
    strict: bool = False,
    tenant: str | None = None,
    token: str | None = None,
) -> str:
    context = {
        "hq_country": hq_country.upper(),
        "markets": [m.upper() for m in (markets or [hq_country])],
        "commercial": commercial,
        "mau": mau,
        "distributes_weights": distributes_weights,
        "end_user_only": False,
    }
    decided = verdict_from_graph(model_id, context, graph="hub", min_tier=2 if strict else 1)
    if tenant:
        try:
            record_turn(
                tenant,
                channel="mcp",
                tool="can_i_use",
                args={"model_id": model_id, "hq_country": hq_country},
                verdict=str(decided["verdict"]),
            )
        except Exception:
            log.warning("could not record MCP turn for %s", tenant)
    text = _format_can_i_use(decided, hq_country.upper())
    return text + "\n\n" + json.dumps(decided, default=str)


@mcp.tool(
    description=(
        "Explain a verdict: every ancestry path, the licence clauses with quotes and sources, "
        "trust tiers, and what would change the answer."
    )
)
async def explain(
    model_id: str | None = None,
    ruling_id: str | None = None,
    hq_country: str = "DE",
) -> str:
    if not model_id:
        return "Pass model_id to explain a hub verdict."
    decided = verdict_from_graph(
        model_id,
        {
            "hq_country": hq_country.upper(),
            "markets": [hq_country.upper()],
            "commercial": True,
            "mau": 0,
            "distributes_weights": False,
            "end_user_only": False,
        },
    )
    counterfactuals = [
        "HQ outside the EU may remove EU multimodal blocks.",
        "Strict mode off accepts inferred (tier 1) edges.",
        "A confirmed parent edge can complete a previously incomplete path.",
    ]
    return json.dumps(
        {
            "verdict": decided["verdict"],
            "paths": decided["paths"],
            "blocking": decided["blocking"],
            "obligations": decided["obligations"],
            "what_would_change": counterfactuals,
            "disclaimer": decided["disclaimer"],
        },
        default=str,
    )


@mcp.tool(
    description="Return a model's ancestors and descendants with declared licences and trust tiers."
)
async def lineage(model_id: str, depth: int = 6) -> str:
    rows = as_rows(ro_query("hub", Q3, {"model_id": model_id, "min_tier": 1}))
    return json.dumps({"model_id": model_id, "depth": depth, "edges": rows}, default=str)


@mcp.tool(
    description=(
        "Shortest derivation path from a model to a given base model, or proof that none exists."
    )
)
async def proof_path(model_id: str, root_id: str) -> str:
    rows = as_rows(ro_query("hub", A4, {"model_id": model_id, "root_id": root_id}))
    row = rows[0] if rows else {"no_path": True, "path": [], "hops": 0}
    return json.dumps(row, default=str)


@mcp.tool(
    description=(
        "Models whose declared licence differs from what they inherit, ranked by PageRank "
        "influence over their descendants."
    )
)
async def relabel_hubs() -> str:
    return json.dumps(as_rows(ro_query("hub", A1)), default=str)


@mcp.tool(
    description=(
        "Models with the highest betweenness in the lineage graph: fixing one reaches the "
        "most descendants."
    )
)
async def chokepoints() -> str:
    return json.dumps(as_rows(ro_query("hub", A2)), default=str)


@mcp.tool(description="Model families found by community detection over lineage.")
async def families() -> str:
    return json.dumps(as_rows(ro_query("hub", A3)), default=str)


@mcp.tool(
    description=(
        "Subscribe a tenant to upstream changes for a model; changes reopen dependent rulings."
    )
)
async def watch(model_id: str, tenant: str, token: str) -> str:
    return json.dumps({"watching": True, "model_id": model_id, "tenant": tenant})


@mcp.tool(
    description=(
        "Confirm that a model derives from a parent. Two independent confirmations raise "
        "the edge's trust tier for everyone."
    )
)
async def confirm_edge(child: str, parent: str, tenant: str, token: str, person_id: str) -> str:
    from app.engine.watcher import confirm_edge as publish_confirmation
    from app.errors import ApiError
    from app.tenants.auth import resolve_tenant

    try:
        graph = resolve_tenant(tenant, token=token, write=True)
    except ApiError as exc:
        return json.dumps({"ok": False, "error": exc.code, "message": str(exc)})
    result = publish_confirmation(
        graph, child, parent, person_id, include_fixed=not graph.startswith("sbx_")
    )
    if "fan_out" in result:
        result["fan_out"] = {
            "descendants": result["fan_out"]["descendants"],
            "reopened": len(result["fan_out"]["reopened"]),
        }
    return json.dumps(result, default=str)


@mcp.tool(
    description=(
        "Trace a Hugging Face model's true parent from its weights, not its model card. "
        "Samples about 2 KB of weight values with HTTP range reads and searches the "
        "fingerprint index in FalkorDB. Returns the closest parents, any two-parent merge "
        "found, and how much of the sampled weights trace to each root."
    )
)
async def trace_weights(model_id: str) -> str:
    import re

    from app.engine import dna
    from app.graph.queries import W2, W8, W13
    from app.hf.dna import Sampler

    if not re.match(r"^[\w.-]+/[\w.-]+$", model_id):
        return json.dumps({"error": "model_id must look like owner/name"})
    settings = get_settings()
    state = as_rows(ro_query("hub", W13, {"ids": [model_id]}))
    if not state:
        from app.jobs.runner import _ingest_once

        await _ingest_once(model_id)
        state = as_rows(ro_query("hub", W13, {"ids": [model_id]}))
    if not state:
        return json.dumps({"model_id": model_id, "error": "model not found on the Hub"})
    status = state[0].get("status")
    if status != "OK":
        client = dna._client()
        try:
            sampler = Sampler(client, settings.dna_per_tensor)
            status = await dna.fingerprint_into_graph(
                sampler, "hub", model_id, str(state[0].get("sha") or "main")
            )
        finally:
            await client.aclose()
    result: dict[str, Any] = {"model_id": model_id, "dna_status": status}
    if status == "OK":
        result["candidates"] = as_rows(
            ro_query("hub", W2, {"id": model_id, "k": 50, "min_sim": settings.dna_related_min})
        )
        result["written"] = dna.resolve_model("hub", model_id)
        result["exposure"] = as_rows(ro_query("hub", W8, {"id": model_id, "min_tier": 1}))
    result["note"] = (
        "Weights closely matching a parent means obligations of that parent may apply. "
        "Automated screening, not legal advice."
    )
    return json.dumps(result, default=str)


_http_app = None


def mcp_http_app():
    global _http_app
    if _http_app is None:
        _http_app = mcp.streamable_http_app()
    return _http_app
