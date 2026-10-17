"""ModelBrain API entrypoint. FalkorDB health wiring is G002."""

from fastapi import FastAPI

app = FastAPI(title="ModelBrain", version="0.1.0")


@app.get("/api/health")
def health() -> dict[str, object]:
    return {
        "ok": False,
        "falkordb": "down",
        "graphs": [],
        "hub_models": 0,
        "clauses": {"resolved": 0, "unresolved": 0},
        "hf": "degraded",
        "version": "0.1.0",
    }
