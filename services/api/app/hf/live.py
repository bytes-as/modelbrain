"""Hugging Face calls used by Scout, through the shared client."""

from __future__ import annotations

from app.hf.client import HFClient, HubUnavailable


class LiveHub:
    def __init__(self, client: HFClient) -> None:
        self.client = client

    async def model(self, model_id: str) -> tuple[int, dict | None]:
        url = f"https://huggingface.co/api/models/{model_id}?blobs=true"
        try:
            response = await self.client.get(url)
        except HubUnavailable:
            raise
        if response.status != 200:
            return response.status, None
        payload = response.json()
        return 200, payload if isinstance(payload, dict) else None

    async def file_at_sha(self, model_id: str, sha: str, filename: str) -> tuple[int, str | None]:
        url = f"https://huggingface.co/{model_id}/raw/{sha}/{filename}"
        try:
            response = await self.client.get(
                url, cache_key=f"{model_id}@{sha}:{filename}", ttl_s=None
            )
        except HubUnavailable:
            return 503, None
        if response.status != 200:
            return response.status, None
        return 200, response.body.decode("utf-8", "replace")

    async def children(self, model_id: str, relation: str, limit: int) -> list[str]:
        url = (
            "https://huggingface.co/api/models?filter="
            f"base_model:{relation}:{model_id}&limit={limit}"
        )
        try:
            response = await self.client.get(url)
        except HubUnavailable:
            return []
        if response.status != 200:
            return []
        payload = response.json()
        if not isinstance(payload, list):
            return []
        found: list[str] = []
        for item in payload:
            if isinstance(item, dict):
                model_id_value = item.get("id") or item.get("modelId")
                if isinstance(model_id_value, str):
                    found.append(model_id_value)
        return found
