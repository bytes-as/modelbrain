"""G143: weight-DNA calibration (E-DNA). Similarity is computed by FalkorDB in Cypher.

  python eval/run_dna_eval.py pick --host falkordb   # once: choose pairs, write eval/dna_labels.json
  python eval/run_dna_eval.py --host falkordb        # score them, write eval/dna_report.json

Derived pairs: a card declares the parent (DERIVED_FROM source 'declared'), both are
fingerprinted with the same tensor shapes, relation finetune. One pair per root family.
Unrelated pairs: same tensor shapes, different organisations, and no lineage path of
any source between them, in either direction, nor a shared ancestor within six hops.
The password is read from FALKORDB_PASSWORD.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

from falkordb import FalkorDB

ROOT = Path(__file__).resolve().parents[1]
LABELS = ROOT / "eval" / "dna_labels.json"
REPORT = ROOT / "eval" / "dna_report.json"

DERIVED = """
MATCH (c:Model)-[d:DERIVED_FROM {source:'declared'}]->(p:Model)
WHERE c.dna IS NOT NULL AND p.dna IS NOT NULL AND c.dna_sig = p.dna_sig
  AND d.relation = 'finetune' AND c.dna_status = 'OK' AND p.dna_status = 'OK'
OPTIONAL MATCH (p)-[:DERIVED_FROM*0..6]->(r:Model {is_root:true})
RETURN c.id AS child, p.id AS parent, c.dna_sig AS sig, coalesce(r.id, p.id) AS family
ORDER BY family, child
"""

ANCESTRY = """
MATCH (m:Model)
WHERE m.dna IS NOT NULL AND m.dna_status = 'OK'
OPTIONAL MATCH (m)-[:DERIVED_FROM*1..6]->(x:Model)
RETURN m.id AS id, m.dna_sig AS sig, collect(DISTINCT x.id) AS ancestors
ORDER BY sig, id
"""

# Families by name, checked before similarity is ever computed: an undeclared re-upload of
# the same family must never be counted as "unrelated".
FAMILIES = (
    "tinyllama",
    "llama",
    "mistral",
    "mixtral",
    "qwen",
    "gemma",
    "phi",
    "deepseek",
    "falcon",
    "olmo",
    "smollm",
    "yi-",
    "internlm",
    "granite",
    "stablelm",
    "pythia",
    "gpt2",
    "bloom",
    "mpt",
    "bielik",
    "zephyr",
    "openchat",
    "starcoder",
    "codegen",
)


def families(model_id: str) -> set[str]:
    name = model_id.lower()
    found = {f for f in FAMILIES if f in name}
    if "tinyllama" in found:
        found.discard("llama")
    return found


COSINE = """
MATCH (a:Model {id:$a}), (b:Model {id:$b})
RETURN 1 - vec.cosineDistance(a.dna, b.dna) AS sim
"""


def _graph(host: str, port: int):
    return FalkorDB(
        host=host, port=port, password=os.environ.get("FALKORDB_PASSWORD") or None
    ).select_graph("hub")


def pick(g, n: int = 15) -> dict:
    derived, roots, children = [], set(), set()
    for child, parent, sig, root in g.ro_query(DERIVED).result_set:
        if root in roots or child in children:
            continue
        roots.add(root)
        children.add(child)
        derived.append({"a": child, "b": parent, "sig": sig, "expect": "derived", "family": root})
        if len(derived) == n:
            break
    unrelated, used_sigs, used = [], {}, {}
    models = [(i, sig, set(anc)) for i, sig, anc in g.ro_query(ANCESTRY).result_set]
    candidates = []
    for x, (a, sig_a, anc_a) in enumerate(models):
        for b, sig_b, anc_b in models[x + 1 :]:
            if sig_a != sig_b or a.split("/")[0] == b.split("/")[0]:
                continue
            # No lineage between them and no shared ancestor within six hops.
            if a in anc_b or b in anc_a or anc_a & anc_b:
                continue
            candidates.append((a, b, sig_a))
    for a, b, sig in candidates:
        fa, fb = families(a), families(b)
        # Both families known and disjoint. Distilled models are left out: their base is
        # often another family's weights, which the name does not say.
        if not fa or not fb or fa & fb or "distill" in a.lower() or "distill" in b.lower():
            continue
        if used.get(a, 0) >= 3 or used.get(b, 0) >= 3:
            continue
        used[a] = used.get(a, 0) + 1
        used[b] = used.get(b, 0) + 1
        used_sigs[sig] = used_sigs.get(sig, 0) + 1
        unrelated.append({"a": a, "b": b, "sig": sig, "expect": "unrelated"})
        if len(unrelated) == n:
            break
    return {
        "written_by": "agent, at the owner's request",
        "written_on": "2026-10-18",
        "method": __doc__.split("\n\n")[1].strip().replace("\n", " ")
        if len(__doc__.split("\n\n")) > 1
        else "",
        "pairs": derived + unrelated,
    }


def score(g, labels: dict, derived_min: float, related_min: float) -> dict:
    rows = []
    for pair in labels["pairs"]:
        found = g.ro_query(COSINE, {"a": pair["a"], "b": pair["b"]}).result_set
        sim = float(found[0][0]) if found and found[0][0] is not None else None
        rows.append({**pair, "sim": None if sim is None else round(sim, 4)})
    derived = [r["sim"] for r in rows if r["expect"] == "derived" and r["sim"] is not None]
    unrelated = [r["sim"] for r in rows if r["expect"] == "unrelated" and r["sim"] is not None]
    return {
        "labels_sha256": hashlib.sha256(LABELS.read_bytes()).hexdigest(),
        "derived_pairs": len(derived),
        "unrelated_pairs": len(unrelated),
        "lowest_derived": min(derived) if derived else None,
        "highest_unrelated": max(unrelated) if unrelated else None,
        "thresholds": {"DNA_DERIVED_MIN": derived_min, "DNA_RELATED_MIN": related_min},
        # A false link is an unrelated pair the resolver would connect at that threshold.
        "false_links_at_derived_min": sum(1 for s in unrelated if s >= derived_min),
        "false_links_at_related_min": sum(1 for s in unrelated if s >= related_min),
        "missed_derived_at_derived_min": sum(1 for s in derived if s < derived_min),
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", nargs="?", default="score", choices=("pick", "score"))
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=6379)
    parser.add_argument(
        "--derived-min", type=float, default=float(os.environ.get("DNA_DERIVED_MIN", 0.60))
    )
    parser.add_argument(
        "--related-min", type=float, default=float(os.environ.get("DNA_RELATED_MIN", 0.25))
    )
    args = parser.parse_args()
    g = _graph(args.host, args.port)
    if args.command == "pick":
        labels = pick(g)
        LABELS.write_text(json.dumps(labels, indent=2) + "\n")
        kinds = [p["expect"] for p in labels["pairs"]]
        print(
            f"wrote {LABELS}: {kinds.count('derived')} derived, {kinds.count('unrelated')} unrelated"
        )
        return 0
    report = score(g, json.loads(LABELS.read_text()), args.derived_min, args.related_min)
    REPORT.write_text(json.dumps(report, indent=2) + "\n")
    print(
        f"lowest derived {report['lowest_derived']}, highest unrelated {report['highest_unrelated']}, "
        f"false links at {args.derived_min}: {report['false_links_at_derived_min']}, "
        f"at {args.related_min}: {report['false_links_at_related_min']}, "
        f"missed derived: {report['missed_derived_at_derived_min']}"
    )
    return 0 if report["false_links_at_derived_min"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
