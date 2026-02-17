from __future__ import annotations

import json
import urllib.request
from typing import Any


class SpendGuardClient:
    def __init__(self, base_url: str, api_key: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def create_agent(self, name: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if name is not None:
            payload["name"] = name
        return self._request_json("POST", "/v1/agents", payload)

    def list_agents(self) -> dict[str, Any]:
        return self._request_json("GET", "/v1/agents")

    def set_budget(self, agent_id: str, hard_limit_cents: int, topup_cents: int = 0) -> dict[str, Any]:
        payload = {
            "hard_limit_cents": int(hard_limit_cents),
            "topup_cents": int(topup_cents),
        }
        return self._request_json("POST", f"/v1/agents/{agent_id}/budget", payload)

    def get_budget(self, agent_id: str) -> dict[str, Any]:
        return self._request_json("GET", f"/v1/agents/{agent_id}/budget")

    def create_run(self, agent_id: str) -> dict[str, Any]:
        return self._request_json("POST", f"/v1/agents/{agent_id}/runs", {})

    def openai_chat_completions(self, agent_id: str, run_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request_json(
            "POST",
            f"/v1/agents/{agent_id}/runs/{run_id}/openai/chat/completions",
            payload,
        )

    def openai_responses(self, agent_id: str, run_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request_json(
            "POST",
            f"/v1/agents/{agent_id}/runs/{run_id}/openai/responses",
            payload,
        )

    def grok_chat_completions(self, agent_id: str, run_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request_json(
            "POST",
            f"/v1/agents/{agent_id}/runs/{run_id}/grok/chat/completions",
            payload,
        )

    def grok_responses(self, agent_id: str, run_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request_json(
            "POST",
            f"/v1/agents/{agent_id}/runs/{run_id}/grok/responses",
            payload,
        )

    def _request_json(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        body = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if self.api_key:
            headers["x-api-key"] = self.api_key

        req = urllib.request.Request(f"{self.base_url}{path}", data=body, method=method, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read().decode("utf-8")
        parsed = json.loads(raw) if raw else {}
        if not isinstance(parsed, dict):
            raise RuntimeError("Expected JSON object response")
        return parsed
