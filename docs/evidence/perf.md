# Performance and failure modes (G155), measured locally on 18 Oct 2026

| What | Measured | Target |
|---|---|---|
| Weight DNA, single-file safetensors (1-1.5B models) | 4.1-4.5 s per model, cold cache | p50 <= 6 s |
| Weight DNA, sharded safetensors (7-8B models) | 6.0-6.6 s per model, cold cache | p95 <= 15 s |
| GGUF header + windows (Llama 3.2 1B F16, 7.8 MB header) | 7.3-7.7 s | <= 12 s |
| Crawl throughput (HF token, 10-way limiter) | 285 models in about 25 minutes, 0 unhandled errors | |
| W2 / W16 vector search + traversal | 3-6 ms (FalkorDB internal time) | < 50 ms |
| Verdict (Q1) | 7 ms internal; 17 ms end to end for OPEA | |
| 50 concurrent verdict and weight-DNA reads | 0 errors, p95 308 ms | p95 < 2 s |
| 100 concurrent | 0 errors, p95 594 ms | |

Failure modes, verified by hand and by tests:

- Hugging Face down or rate-limiting: `/api/health` stays `ok: true` with `hf: "degraded"` for five minutes; the crawl backs off on `HubUnavailable`; models already in the graph keep answering.
- FalkorDB down: every route returns `503 GRAPH_UNAVAILABLE` (`tests/test_graph_down.py`), never a cached answer.
- A server that ignores HTTP Range is detected and never trusted (`tests/test_dna.py`).
