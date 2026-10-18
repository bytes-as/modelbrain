"""In-memory ingest jobs with SSE fan-out. Jobs kept 10 minutes (FLOWS F2)."""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field

JOB_TTL_S = 600


@dataclass
class JobRecord:
    id: str
    status: str = "running"
    nodes: int = 0
    error: str | None = None
    model_id: str = ""
    created_at: float = field(default_factory=time.time)
    history: list[dict[str, object]] = field(default_factory=list)
    _queues: list[asyncio.Queue[dict[str, object] | None]] = field(default_factory=list)
    done: asyncio.Event = field(default_factory=asyncio.Event)

    def subscribe(self) -> asyncio.Queue[dict[str, object] | None]:
        queue: asyncio.Queue[dict[str, object] | None] = asyncio.Queue()
        for past in self.history:
            queue.put_nowait(past)
        if self.status != "running":
            queue.put_nowait(None)
        else:
            self._queues.append(queue)
        return queue

    def _fanout(self, event: dict[str, object]) -> None:
        self.history.append(event)
        dead: list[asyncio.Queue[dict[str, object] | None]] = []
        for queue in self._queues:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                dead.append(queue)
        self._queues = [item for item in self._queues if item not in dead]

    def finish(self, *, nodes: int) -> None:
        self.status = "done"
        self.nodes = nodes
        self.done.set()
        self._fanout({"type": "done", "nodes": nodes})
        for queue in self._queues:
            queue.put_nowait(None)
        self._queues.clear()

    def fail(self, message: str) -> None:
        self.status = "failed"
        self.error = message
        self.done.set()
        self._fanout({"type": "error", "message": message})
        for queue in self._queues:
            queue.put_nowait(None)
        self._queues.clear()


class JobRegistry:
    def __init__(self) -> None:
        self._jobs: dict[str, JobRecord] = {}
        self._lock = asyncio.Lock()

    async def create(self, model_id: str) -> JobRecord:
        await self._purge()
        job_id = f"job_{uuid.uuid4().hex[:12]}"
        record = JobRecord(id=job_id, model_id=model_id)
        async with self._lock:
            self._jobs[job_id] = record
        return record

    def get(self, job_id: str) -> JobRecord | None:
        return self._jobs.get(job_id)

    def emit(self, job_id: str, event: dict[str, object]) -> None:
        record = self._jobs.get(job_id)
        if record is None:
            return
        kind = event.get("type")
        if kind == "done":
            record.finish(nodes=int(event.get("nodes") or 0))
            return
        if kind == "error":
            record.fail(str(event.get("message") or "ingest failed"))
            return
        if kind == "node":
            record.nodes += 1
        record._fanout(event)

    async def _purge(self) -> None:
        cutoff = time.time() - JOB_TTL_S
        async with self._lock:
            expired = [job_id for job_id, job in self._jobs.items() if job.created_at < cutoff]
            for job_id in expired:
                del self._jobs[job_id]


_registry = JobRegistry()


def jobs() -> JobRegistry:
    return _registry
