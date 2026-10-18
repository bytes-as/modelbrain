# Addendum: weight DNA, merge DNA, GGUF DNA — decided 18 Oct 2026

Status: **binding**. Adds goals **G139-G155** (milestone **M6b**) and cuts G079, G135, G136, G137. Where it conflicts with an older document, this addendum wins (it ranks with GOALS.md in BLUEPRINT section 0). G139 merges it into the other documents; keep this file as the record.

Why: the owner's review found ModelBrain easy to copy (public APIs plus Cypher). This addendum adds the moat: **provenance from the weights themselves, not from the model card**, plus a fingerprint index of the Hub that only we compute, stored and searched in FalkorDB.

## 1. Evidence (all live, 18 Oct 2026)

### 1.1 Separation
Two windows of weight values per model, read with HTTP Range requests (about 100-250 KB per model including headers; never the whole file).

| Comparison | Cosine |
|---|---|
| Real fine-tunes vs parent (5 Llama-3.2-1B fine-tunes, both tensors) | 0.98 - 0.9995 |
| Base vs Instruct pairs | 0.987 - 0.9999 |
| Heavily trained derivatives (continued pre-training, e.g. Bielik-7B vs Mistral) | 0.56 - 0.95 |
| Same shape, different family (Llama-3 vs Mistral-7B, TinyLlama vs Llama-3.2-1B, independent 7-8B models) | -0.013 - +0.035 |

A scan of 543 public models: lowest known-derived similarity 0.643, highest unrelated 0.035, at 512 values per tensor (8,192 values gave 0.668 / 0.009). 512 values per tensor is enough.

### 1.2 Real findings (scan of 570 popular models against 38 reference bases; full list in `data/dna_scout_findings.json`)
472 matched a reference at >= 0.95. Of those, 225 declare no base model, 107 declare no base model and a licence that differs from the base family, 90 declare a base but a different licence family, and 5 declare the **wrong** base model. 273 of 287 checked have file hashes different from the nearest known model, so hash matching misses them.

Demo-grade cases (independently re-checked; three tensors each):

| Model | Card metadata | Weights |
|---|---|---|
| `CMSManhattan/JiRackUltra_1b` (2.54M downloads) | MIT, no base model; card describes a redesigned architecture | 1.0000 on every tensor vs `deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B` (itself derived from Qwen2.5-Math-1.5B); file hashes differ |
| `microsoft/UserLM-8b` | declares `meta-llama/Llama-3.1-8B` | 0.9989-0.9999 vs Llama-3-8B, 0.986-0.991 vs Llama-3.1-8B |
| `BayesRL/Llama3.1-IVON-SFT-8B` | declares `Qwen/Qwen2.5-Math-7B`, apache-2.0 | Llama-3.1-8B (0.98); the declared base has a different shape |
| `XCurOS/XCurOS0.1-8B-Instruct` | licence "other", card claims a proprietary model | identical to Qwen2.5-7B-Instruct (Apache-2.0) |
| `pravdin/Qwen2.5-0.5B-linear-merge` (known recipe 0.6 / 0.4) | merge | recovered **0.600 / 0.402** from 512 values per window |
| `paloalma/ECE-TW3-JRGL-V1` (70B) | apache-2.0, no base model | 0.31 x `152334H/miqu-1-70b-sf` + 0.69 x `ShinojiResearch/Senku-70B-Full` at layer 40 (R² 1.0000), matching its own mergekit recipe |
| `artnfull/llama-3.2-1b-aiartnfullmodel-V2` (GGUF only) | no licence, no base model | `blk.5.ffn_down` 0.9989 vs Llama-3.2-1B-Instruct, 0.9831 vs Base: names the exact parent |
| `bartowski/Llama-3.2-1B-Instruct-GGUF` Q8_0 | GGUF header says `general.license = llama3.2` | 1.0000 vs Llama-3.2-1B-Instruct |

Vocab fingerprint (section 5.3): `tokenizer.json` of Llama-3.2-1B and -Instruct and the Q8_0 GGUF all hash to `b5ff30b87f7a2edf` (128,256 tokens); Qwen2.5 differs.

**Wording rule (hard, applies to UI, README, video, MCP output):** say "metadata and weights disagree", "weights closely match", "the card does not declare this parent", "obligations of the parent may apply". Never say stolen, leaked, fake, violates, infringes, or attribute intent. Many cards explain lineage in prose that the metadata omits (for example the DeepSeek and Salesforce distills); say "machine-readable metadata" when that is the case. Every finding links to both Hub pages. Global disclaimer stays: "Automated screening, not legal advice."

## 2. Weight DNA sampling (exact)
Module `services/api/app/hf/dna.py`. All HTTP goes through the existing HF client (shared limiter, 30 s timeout, one retry with backoff, optional `HF_TOKEN`). Always use the canonical repo id (section 7) and the model's current `sha` in URLs.

1. **File for a tensor.** GET `https://huggingface.co/{repo}/resolve/{sha}/model.safetensors.index.json`; if 200, `weight_map[tensor]` names the shard; if 404, use `model.safetensors`. Neither: try GGUF (section 5); no GGUF either: status `NO_SAFETENSORS`. 401/403: `GATED`.
2. **Header.** Range `bytes=0-7` → `N` (little-endian u64); Range `bytes=8-(8+N-1)` → JSON `{tensor: {dtype, shape, data_offsets:[s,e]}}`. Reject `N > 25_000_000` (`ERROR`). Cache headers per (repo, sha, file).
3. **Layer prefix.** First of `model.layers.`, `language_model.model.layers.`, `model.language_model.layers.` for which `<prefix>0.self_attn.o_proj.weight` exists. None: `UNSUPPORTED_ARCH`.
4. **Shape signature** `dna_sig = "h{hidden}|L{layers}|i{intermediate}"`: `layers` = 1 + largest `N` in keys `<prefix>N.`; `[hidden, intermediate]` = shape of `<prefix>{b}.mlp.down_proj.weight`. (No model type or vocab size in the signature: GGUF calls Mistral `llama`, and vocab padding differs between formats.)
5. **Tensors.** `a = floor(L * 0.25)` → `<prefix>{a}.self_attn.o_proj.weight`; `b = floor(L * 0.6)` → `<prefix>{b}.mlp.down_proj.weight`. **Not q_proj or k_proj**: llama.cpp permutes those in GGUF files, so they can't be compared across formats. o_proj verified: fine-tunes 0.988-0.996, unrelated -0.013.
6. **Window.** `DNA_PER_TENSOR = 512` values starting at element `start = floor(floor(total_elements * 0.37) / 32) * 32` (a multiple of 32 so Q8_0 blocks align). Byte offset = `8 + N + s + start * size`. Dtypes: `BF16` (2 bytes; value = the 16 bits as the high half of an f32), `F16` (2), `F32` (4). Anything else: `QUANTIZED`.
7. **Vector** = window(a) ++ window(b), length **1024**. Reject NaN/Inf or all zeros (`ERROR`). **Validate the length before writing: FalkorDB silently accepts a wrong-length vector and doesn't index it** (verified).
8. Statuses: `OK`, `NO_SAFETENSORS`, `GATED`, `QUANTIZED`, `UNSUPPORTED_ARCH`, `ERROR`. Every non-OK result logs `{repo, sha, status, reason}` at INFO and writes W1B.

## 3. Graph changes (hub)
- `Model` gains `dna_reference` (bool, true for every id in `data/dna_references.json`), `dna` (vecf32, 1024), `dna_sig`, `dna_status`, `dna_at`, `format` (`safetensors` or `gguf`), `gguf_file`, `gguf_license`, `gguf_basename`, `aliases` (list of non-canonical ids).
- Vector index W0. `db.idx.vector.queryNodes` returns cosine **distance**: similarity = `1 - score` (verified).
- `DERIVED_FROM` gains `method` (`weights` or `weights_merge`), `weights_sim`, `share` (merge edges only), `weights_share`, `weights_r2`.
- `DECLARES` gains `source: 'gguf_meta'` when the licence comes from a GGUF header.
- `Fingerprint.kind` gains `vocab_dna` (section 5.3); it joins the existing `HAS_FP` / WCC resolver (R1).
- **Tiers:** weight similarity >= `DNA_DERIVED_MIN` (default **0.60**) → tier **1**; between `DNA_RELATED_MIN` (default **0.25**) and `DNA_DERIVED_MIN` → tier **0**. Defaults come from the scan (lowest known-derived 0.643, highest unrelated 0.035); G143 confirms them on human labels. Default verdicts (tier >= 1) inherit obligations through weight edges; strict mode (tier >= 2) does not and still answers CANNOT DETERMINE. Q1 is unchanged; it already walks every `DERIVED_FROM` path.
- **Foundation models never get weight edges.** A model with `dna_reference = true` (listed in `data/dna_references.json`, 36 official base and instruct models) is never a child in W2/W7: Llama-3.1-8B scores 0.989 against Llama-3-8B, and without this rule Llama 3's licence would be pulled onto every Llama 3.1 model. **Do not use `is_root` for this**: `is_root` marks any allowlisted-org repo without a declared parent, which includes findings such as `deepseek-ai/DeepSeek-R1-Distill-Llama-8B` (MIT metadata, Llama-3.1-8B weights). Verified by test: a reference gets no candidates; a non-reference `is_root` model still does.
- Never overwrite a declared edge. If weights point to a different family than the declared parent, keep both edges: Q1 applies the stricter obligations, W5 lists the conflict.

## 4. Resolver step (FLOWS F20; runs after the hash resolver in G093)
For each model with `dna_status = 'OK'`, `dna_reference` not true, and no `weights` / `weights_merge` edge yet:
1. W2 with `k = 50`, `min_sim = DNA_RELATED_MIN` → up to 5 candidates (same `dna_sig`, older `created_at`; models without `created_at` are never candidates).
2. **Merge check (section 6) first.** If it accepts a pair, write W7 and stop.
3. Otherwise take the first W2 row (highest similarity; ties go to roots, then the earliest) and write W3 with `tier = 1` if `sim >= DNA_DERIVED_MIN` else `0`, `evidence = "weights cosine {sim:.4f} over o_proj+down_proj, 2x512 values"`.
4. Audit: `/api/admin/resolver/last` gains `dna: {ok, gated, quantized, unsupported, no_safetensors, error, edges_created, edges_corroborated, merges_found, gguf_ok}`.

## 5. GGUF DNA
Module `services/api/app/hf/gguf.py`. GGUF is the format people run in Ollama and LM Studio; 248 of 500 GGUF repos in a "llama-3.2" search declare no base model.

### 5.1 Header parse (range reads)
- Pick the file: from `siblings`, the `.gguf` file with the best type in the order F16/BF16 > Q8_0 > anything else (skip `mmproj` files). Store it in `Model.gguf_file`.
- Read with a buffered range reader in 4 MB chunks (the header holds the token list; Llama-3.2 Q8_0 header is 7.8 MB, so expect two chunks). Cap at 32 MB (`ERROR` above that).
- Layout (little-endian): magic `GGUF`, u32 version (accept 2 and 3), u64 tensor count, u64 kv count; each kv = string key (u64 length + bytes), u32 type, value; value types 0-12 per the GGUF spec (8 = string, 9 = array: u32 element type + u64 count + elements). Then per tensor: name, u32 n_dims, u64 dims[n_dims], u32 ggml type, u64 offset. Data starts at the header end rounded up to `general.alignment` (default 32).
- Keep: `general.architecture`, `general.license`, `general.basename`, `general.finetune`, `general.name`, `{arch}.block_count`, `{arch}.embedding_length`, `{arch}.feed_forward_length`, and the token list `tokenizer.ggml.tokens` (hash it while streaming; don't store it).

### 5.2 GGUF weight sample
- `dna_sig = "h{embedding_length}|L{block_count}|i{feed_forward_length}"`; tensors `blk.{a}.attn_output.weight` and `blk.{b}.ffn_down.weight` with the same `a`, `b`, `start` as section 2. The flat element order matches the safetensors tensor (verified: Q8_0 file vs safetensors 1.0000).
- ggml type 1 (F16): 2 bytes per value. Type 0 (F32): 4. Type 8 (Q8_0): blocks of 34 bytes = f16 scale `d` + 32 int8 `q`; value = `d * q`; read blocks `start/32` to `start/32 + 512/32`. Type 30 (BF16): as safetensors. Any other type (Q4_K, Q6_K, ...): `QUANTIZED` (a K-quant dequantiser is out of scope tonight).
- A GGUF-only repo becomes an ordinary `Model` with `format = 'gguf'`; its vector goes into the same index, so W2, W3, W7 and W4 work unchanged.

### 5.3 Licence and vocab from the header
- `general.license` → `Model.gguf_license`; when it normalises to a known licence key and the card declares none, write W9 (`DECLARES {source:'gguf_meta'}`).
- **Vocab DNA** (both formats, same function): token strings in id order, ids 0..n-1; each token `json.dumps(t, ensure_ascii=False)` encoded UTF-8 followed by `\n`; sha256; first 16 hex chars. From `tokenizer.json`: `model.vocab` (token → id) merged with `added_tokens[].{id, content}`; missing ids are `""`. From GGUF: `tokenizer.ggml.tokens`. Write `Fingerprint {key:'vocab_dna:<hash>', kind:'vocab_dna'}` with `HAS_FP`. In the 6.3 resolver, a shared `vocab_dna` alone never creates an edge (whole families share a vocab); it only adds to `evidence` and lets R1 group a GGUF repo with its safetensors family.

## 6. Merge DNA
Many popular models are merges of two parents whose cards declare neither. A merge's weights are (nearly) a linear mix of its parents', so a least-squares fit recovers the shares.

- **Input:** the child's stored `dna` and the stored `dna` of each W2 candidate (read the vectors back from FalkorDB; no extra HTTP).
- **Fit:** for each pair (P, Q) among the top 5 W2 candidates (at most 10 pairs) and **for each window separately** (values 0-511 = o_proj at layer a, 512-1023 = down_proj at layer b; slerp merges vary the mix by layer), solve `child ≈ α·P + β·Q` by least squares (closed form 2x2). Compute R² and the best single-parent R².
- **Accept a pair** when in both windows: `α >= 0.10`, `β >= 0.10`, `0.90 <= α + β <= 1.10`, `R² >= 0.995`. Among accepted pairs pick the highest mean R². Share per parent = mean of its two window coefficients, normalised so the shares sum to 1.
- Verified: known 0.6/0.4 merge → (0.600, 0.402) and (0.601, 0.401), R² 1.0. Plain fine-tunes (GRMR, Finnish) fit with β ≈ -0.02 → rejected. The wrong pair (two near-identical roots) gives a poor fit and loses to the true pair.
- **Write W7:** `DERIVED_FROM {relation:'merge', source:'inferred', method:'weights_merge', share, tier}` to each parent, with `tier = 1` when both parents' cosine to the child >= `DNA_RELATED_MIN`, else 0. Evidence: `"merge fit: {share_p:.2f} x {P} + {share_q:.2f} x {Q}, R² {r2:.4f} (o_proj L{a}, down_proj L{b})"`.
- **Exposure W8:** sums, over every path to a root or parentless ancestor, the product of `share` along the path (1.0 for non-merge edges), capped at 1.0. Product copy: "About {exposure:.0%} of the sampled weights trace to {root} ({licence})". Shown on the verdict page under the path.
- Out of scope tonight: TIES/DARE sparse merges (they fit poorly and simply produce no merge edge) and merges of more than two parents.

## 7. Canonical ids (bug fix found during the research)
Renamed repos redirect (`meta-llama/Meta-Llama-3.1-8B-Instruct` → `meta-llama/Llama-3.1-8B-Instruct`). Today the ingest would create two `Model` nodes and split edges. Rule: always key `Model.id` by the `id` field that `GET /api/models/{id}` returns; when a declared `base_model` or a requested id differs from it, write the edge to the canonical node and append the requested id to `Model.aliases`. `GET /api/verdict` and MCP tools accept an alias and resolve it (MATCH on `id` or `$id IN m.aliases`).

## 8. Queries (all tested on falkordb/falkordb:latest, 18 Oct 2026)
Add to `docs/queries.cypher` under `// --- Weight DNA ---` and copy into `queries.py` verbatim. Parameters are passed by falkordb-py (maps and lists included).

```cypher
// W0: vector index over weight fingerprints (dimension = 2 * DNA_PER_TENSOR)
CREATE VECTOR INDEX FOR (m:Model) ON (m.dna) OPTIONS {dimension:1024, similarityFunction:'cosine'}

// W1: write a fingerprint (validate length 1024 in Python first)
MATCH (m:Model {id:$id}) SET m.dna = vecf32($dna), m.dna_sig = $sig, m.dna_status = 'OK', m.dna_at = $now RETURN m.id

// W1B: record a non-OK fingerprint status
MATCH (m:Model {id:$id}) SET m.dna_status = $status, m.dna_at = $now RETURN m.id

// W2: candidate parents by weight similarity (never for foundation references; same shape class; older models only)
MATCH (c:Model {id:$id}) WHERE c.dna_status = 'OK' AND NOT coalesce(c.dna_reference, false)
CALL db.idx.vector.queryNodes('Model', 'dna', $k, c.dna) YIELD node, score
WITH c, node, 1 - score AS sim
WHERE node <> c AND node.dna_sig = c.dna_sig AND node.created_at < c.created_at AND sim >= $min_sim
RETURN node.id AS parent, sim, coalesce(node.is_root, false) AS is_root, node.created_at AS created_at
ORDER BY sim DESC, is_root DESC, created_at ASC LIMIT 5

// W3: write or corroborate a single-parent weight edge (never changes a declared edge's source or tier)
MATCH (c:Model {id:$child}), (p:Model {id:$parent})
MERGE (c)-[e:DERIVED_FROM]->(p)
ON CREATE SET e.relation = 'inferred', e.source = 'inferred', e.method = 'weights', e.conf = $sim, e.tier = $tier,
  e.evidence = $evidence, e.confirmations = 0, e.confirmers = []
SET e.weights_sim = $sim
RETURN e.source AS source, e.method AS method, e.tier AS tier, e.weights_sim AS weights_sim

// W4: models whose weights match a parent the card does not declare (the headline finding); root = the top-most root above the parent
MATCH (c:Model)-[e:DERIVED_FROM]->(p:Model)
WHERE e.method IN ['weights', 'weights_merge'] AND NOT (c)-[:DERIVED_FROM {source:'declared'}]->()
OPTIONAL MATCH path = (p)-[:DERIVED_FROM*0..6]->(r:Model {is_root:true})
WITH c, e, p, r, path ORDER BY length(path) DESC
WITH c, e, p, collect(r)[0] AS root
RETURN c.id AS model, c.declared_license AS card_license, c.format AS format, p.id AS weights_parent,
  coalesce(e.weights_sim, e.weights_r2) AS score, e.share AS share, root.id AS root, root.declared_license AS root_license
ORDER BY score DESC LIMIT $limit

// W5: declared parent and weights disagree (different families)
MATCH (c:Model)-[:DERIVED_FROM {source:'declared'}]->(dp:Model), (c)-[w:DERIVED_FROM {method:'weights'}]->(wp:Model)
WHERE dp <> wp AND NOT (dp)-[:DERIVED_FROM*1..6]->(wp) AND NOT (wp)-[:DERIVED_FROM*1..6]->(dp)
RETURN c.id AS model, dp.id AS declared_parent, wp.id AS weights_parent, w.weights_sim AS sim
ORDER BY sim DESC LIMIT $limit

// W6: fingerprint coverage
MATCH (m:Model) RETURN coalesce(m.dna_status, 'NOT_RUN') AS status, count(*) AS models ORDER BY models DESC

// W7: write merge edges ($parents = [{id, share, r2, evidence}, ...]); never alters a declared edge
MATCH (c:Model {id:$child})
UNWIND $parents AS pr
MATCH (p:Model {id:pr.id})
MERGE (c)-[e:DERIVED_FROM]->(p)
ON CREATE SET e.relation = 'merge', e.source = 'inferred', e.method = 'weights_merge', e.conf = pr.r2, e.tier = $tier,
  e.share = pr.share, e.evidence = pr.evidence, e.confirmations = 0, e.confirmers = []
SET e.weights_share = pr.share, e.weights_r2 = pr.r2
RETURN p.id AS parent, e.source AS source, e.method AS method, e.share AS share, e.weights_share AS weights_share

// W8: weight exposure per root or parentless ancestor (product of merge shares along each path, capped at 1)
MATCH p = (m:Model {id:$id})-[:DERIVED_FROM*1..6]->(r:Model)
WHERE (coalesce(r.is_root, false) OR NOT (r)-[:DERIVED_FROM]->()) AND all(e IN relationships(p) WHERE e.tier >= $min_tier)
WITH r, sum(reduce(s = 1.0, e IN relationships(p) | s * coalesce(e.share, 1.0))) AS raw
RETURN r.id AS root, coalesce(r.is_root, false) AS is_root, r.declared_license AS root_license, CASE WHEN raw > 1.0 THEN 1.0 ELSE raw END AS exposure
ORDER BY exposure DESC

// W9: GGUF header facts and licence ($license_key null when the header licence is unknown)
MATCH (m:Model {id:$id})
SET m.format = $format, m.gguf_file = $file, m.gguf_license = $gguf_license, m.gguf_basename = $basename
WITH m WHERE $license_key IS NOT NULL
MATCH (l:License {key:$license_key})
MERGE (m)-[d:DECLARES]->(l) ON CREATE SET d.source = 'gguf_meta', d.as_of_sha = $sha
RETURN m.id, d.source
```

Test results (synthetic 1024-dim vectors):
- **W2:**
  - The hidden fine-tune returned its base (0.996), as did the declared fine-tune (0.990) and the conflict case (0.994).
  - It returned no candidates for an unrelated model, for the base itself, for a foundation reference close to another reference, or across shape classes. A non-reference `is_root` model (an org distill) still found its parent (0.990).
  - It returned all three candidates for the merge child (two close roots and the true second parent at 0.40).
- **W3:** created a tier-1 `weights` edge. On a declared edge it only set `weights_sim`; the declared source and tier 2 were kept.
- **W4:** listed only the hidden model, showing root licence `llama3_2` against card licence `apache-2.0`. On a chain (JiRack → R1-Distill-Qwen-1.5B, an `is_root` org repo → Qwen2.5-Math-1.5B) it reports the top-most root, Qwen2.5-Math-1.5B (apache-2.0), not the distill.
- **W5:** listed only the conflict model.
- **Strict mode:** the tier filter excluded weight edges.
- **W7:** created two merge edges with shares 0.31 and 0.69.
- **W8:** returned `llama3` root 0.69 and the parentless second parent 0.31.
- **W9:** wrote `DECLARES {source:'gguf_meta'}`; with a null key it set the properties only.

## 9. API, MCP and UI
- `GET /api/dna/hidden?limit=50` (W4), `GET /api/dna/conflicts?limit=50` (W5), `GET /api/dna/coverage` (W6), `GET /api/dna/exposure/{model_id}` (W8). Admin: `POST /api/admin/dna/crawl {limit, include_gguf}`, `GET /api/admin/dna/crawl/{job}`.
- Verdict response: each edge in `paths` gains `method`, `weights_sim`, `share`; the response gains `exposure` (W8 rows) when any merge edge is on a path.
- MCP tool `trace_weights(model_id)` → `{dna_status, format, dna_sig, candidates (W2), merge (accepted pair or null), edges_written, exposure (W8)}`; fingerprints on demand if missing.
- Verdict page chips: `weights` edge → **"Weights match {parent} · similarity {sim}"** (tooltip: *"We compared a small sample of the actual weight values. The model card does not declare this parent."*); declared edge with `weights_sim` → **"Declared · confirmed by weights {sim}"**; merge edge → **"Merge · {share:.0%} of sampled weights from {parent}"**; licence from GGUF → **"Licence read from the GGUF file header"**.
- Page `/findings`, title **"Where metadata and weights disagree"**. Three tables: W4 ("Weights match a parent the card does not declare"; columns model, format, card licence, weights parent, score or share, root, root licence), W5 ("Declared parent and weights disagree"), and the top merges with exposure. Coverage line from W6: "Fingerprinted {ok} of {total} models; {gated} gated; {quantized} in formats we don't sample yet." Each row links to the Hub pages of the model and the matched parent. The wording rule in section 1.2 applies.

## 10. Crawl
`services/api/app/jobs/dna_crawl.py` (also `python -m app.jobs.dna_crawl --limit 2000 --gguf 300`):
- Candidates: `/api/models?filter=safetensors&pipeline_tag=text-generation&sort=downloads&direction=-1&limit=100&full=true` (follow the `Link` header), plus GGUF repos from `/api/models?filter=gguf&sort=downloads&direction=-1`, plus `data/roots.json`, `data/prewarm.json`, the ids in `data/dna_scout_findings.json` (demo_cases, confirmed_findings_licence_or_wrong_base, wrong_base_model_cases), and every declared parent found. Ingest each through the normal Scout path first (canonical id, `created_at`, licence, `is_root`), then fingerprint, then run the resolver step.
- Reference bases are fingerprinted first: every entry of `data/dna_references.json`. Fingerprint `fingerprint_from` (the public unsloth mirror for gated Meta and Google repos; the official repo otherwise), write the vector to the **official** node with `dna_reference = true`, and write a `mirror` edge from the mirror node to the official node as section 6.3 already does.
- Rate: <= 400 huggingface.co requests per 5 minutes anonymous (`HF_REQ_PER_5MIN`); CDN range reads are not counted against it but use a separate limit of 10 in flight. Measured: about 4.5 requests and 190 KB per safetensors model, 2 requests and about 8 MB per GGUF header; 570 models in 15 minutes at 10 threads with zero 429s.
- Resumable: skip models whose `dna_at` is newer than `last_modified`. Checkpoint every 25 models in `DnaCrawl {id, started_at, done, total, status}`. A failing model never stops the job.
- Runs on Railway against the deployed FalkorDB (AOF keeps the result). **Never commit sampled weight values**; tests use synthetic safetensors and GGUF files.

## 11. Goals (GOALS.md section 10, milestone **M6b**: right after M5, before any add-on except G126)
- [ ] **G139** Merge this addendum into GOALS.md, BLUEPRINT.md (5.1, 6.3, 14, 18), FLOWS.md (new F20), API.md, UI.md, queries.cypher; strike G079, G135, G136, G137 with "cut 18 Oct 2026 to fund weight DNA". **Accept:** every W-query, G139-G155 and F20 is defined once and referenced. **Verify:** grep the ids.
- [ ] **G140** `app/hf/dna.py` per section 2. **Accept:** unit tests against a local HTTP server serving synthetic safetensors (single file and two shards; BF16, F16, F32; I8 → `QUANTIZED`; no o_proj → `UNSUPPORTED_ARCH`; 403 → `GATED`; truncated header → `ERROR`); asserts the Range headers and the 32-aligned start. **Verify:** `pytest tests/test_dna.py`.
- [ ] **G141** W0 in the hub bootstrap; W1/W1B writer rejecting wrong length, NaN/Inf, all zeros. **Accept:** integration test writes a valid vector, refuses a 2-element vector with a logged error, W6 counts statuses. **Verify:** `pytest tests/test_dna_graph.py`.
- [ ] **G142** Resolver step (section 4) with W2/W3, root exclusion and thresholds from config. **Accept:** the section 8 synthetic scenario reproduces exactly, including "foundation reference close to another reference → no edge" and "non-reference org model → edge". **Verify:** `pytest tests/test_dna_resolver.py`.
- [ ] **G143** *(human)* E-DNA calibration: a person picks 15 declared parent/child pairs and 15 unrelated same-shape pairs and writes `eval/dna_labels.json`; the eval prints the lowest derived similarity, the highest unrelated similarity and false links at the thresholds. **Accept:** zero false links at `DNA_DERIVED_MIN`; `.env.example` holds the calibrated values. **Verify:** `/eval` E-DNA block. Cursor stops and asks.
- [ ] **G144** Crawl job (section 10) with admin endpoints, limits, checkpoint and resume. **Accept:** a 50-model live run completes with zero unhandled errors and resumes after being killed midway. **Verify:** job report and logs.
- [ ] **G145** `/api/dna/*` endpoints, verdict fields, MCP `trace_weights`. **Accept:** API contract tests; `mcp_smoke` traces a synthetic child to its synthetic parent; one manual live call `trace_weights("qingy2024/GRMR-V3-L1B")` returns `unsloth/Llama-3.2-1B` (screenshot in `docs/evidence/`). **Verify:** pytest, mcp_smoke, evidence.
- [ ] **G146** UI chips and `/findings` page with the exact copy in section 9. **Accept:** Playwright checks chips, the three tables, the coverage line and the disclaimer, and fails if any forbidden word from section 1.2 appears. **Verify:** Playwright.
- [ ] **G147** Canonical ids and aliases (section 7). **Accept:** a fixture where `base_model` names a redirected id produces one node with the alias, and `GET /api/verdict?model=<alias>` returns the canonical verdict. **Verify:** `pytest tests/test_canonical.py`.
- [ ] **G148** `app/hf/gguf.py` header parser (5.1) and sampler (5.2) for F16, F32, BF16 and Q8_0. **Accept:** unit tests on synthetic GGUF v3 files (written by the test with the layout in 5.1) recover the planted values, alignment and kv fields; Q4_K → `QUANTIZED`; a header over 32 MB → `ERROR`. **Verify:** `pytest tests/test_gguf.py`.
- [ ] **G149** GGUF repos in the pipeline: file choice, `format`, W9 licence, `vocab_dna` fingerprints from both formats (5.3), and R1 grouping. **Accept:** a synthetic GGUF repo with planted weights equal to a synthetic safetensors parent gets a W3 edge, `DECLARES {source:'gguf_meta'}` and the same `vocab_dna` key as the parent. Manual live check: `artnfull/llama-3.2-1b-aiartnfullmodel-V2` resolves to `unsloth/Llama-3.2-1B-Instruct` (evidence screenshot). **Verify:** pytest and evidence.
- [ ] **G150** Merge fit (section 6) and W7. **Accept:** unit test on synthetic vectors (0.6/0.4 and 0.3/0.7 mixes recovered within 0.01; a pure fine-tune with noise and a wrong close pair are rejected). Live check: `pravdin/Qwen2.5-0.5B-linear-merge` gets merge edges to `Qwen/Qwen2.5-0.5B-Instruct` (~0.6) and `Qwen/Qwen2.5-0.5B` (~0.4). **Verify:** `pytest tests/test_merge.py` and evidence.
- [ ] **G151** W8 exposure in the verdict response, the verdict page and `trace_weights`. **Accept:** integration test reproduces the section 8 exposure rows. **Verify:** pytest and Playwright.
- [ ] **G152** Include merges and GGUF in `/findings` and in the crawl (`include_gguf`, default 300 GGUF repos). **Accept:** the deployed `/findings` shows at least one merge row and one GGUF row. **Verify:** public URL.
- [ ] **G153** Run the crawl on the deployed instance: at least 1,500 safetensors models and 300 GGUF repos. **Accept:** W6 coverage reported; `/findings` lists the section 1.2 demo models that were reachable, each linked to both Hub pages; W2 for one model runs in under 50 ms (FalkorDB `Query internal execution time`). **Verify:** public URL.
- [ ] **G154** Demo and video: replace the voice segment with one weight-DNA shot. Paste a model id whose card says MIT and whose weights resolve to its true parent; show the path, the chip and the verdict change. Then one merge shot with exposure. README "Weight DNA" section (linked from G118) and EXPLAINER lines. **Accept:** script and README reviewed by the owner; the wording rule holds. **Verify:** owner review.
- [ ] **G155** Performance and failure modes: fingerprinting one model p50 <= 6 s and p95 <= 15 s; a GGUF header <= 12 s; HF down → `/api/health` stays green and the crawl backs off; FalkorDB down → `/api/dna/*` returns 503. **Accept:** measured numbers in `docs/evidence/perf.md`. **Verify:** owner review.

## 12. Cut order (updated)
Add-ons first, in this order: voice and Ask (already cut), custom licence resolution, web fetcher adapter, licence text watch, hosted path, multi-LLM baseline. Then, inside M6b: G152 (merges/GGUF on `/findings`; keep the verdict chips), G153 crawl size (fall back to prewarm + 500 models + 100 GGUF), G149's live GGUF check, G150 (merge). **G140-G142, G145, G147 and G148 are not cuttable once started.**

## 13. Integration notes
- FalkorDB stays the heart: similarity search, edges, tiers, exposure and findings are all FalkorDB queries. Python only samples bytes, validates and solves the 2x2 fit.
- Sandboxes copy the tenant template, not the hub, so the vector index lives only in `hub`. If code ever copies the hub, re-run W0 on the copy and ignore an "already indexed" error.
- `data/dna_scout_findings.json` is research output (similarities and metadata only, no weight values) used to seed the crawl and the demo; it is not ground truth for the eval.
- Eval G050 is unaffected; G143 is a separate block.
