import json
import os
import time
import urllib.error
import urllib.request
from typing import Protocol

from pydantic import ValidationError

from src.features.generation.models import OrchestrateRequest, PlannerDecision


PLANNER_SYSTEM_PROMPT = """You are a strict planning service for a typed image generation API.
Return only JSON matching this schema:
{
  "workflow_name": "extraction|composition|identity|flux2_txt2img",
  "asset_roles": {"role_name": "selected_asset_id"},
  "params": {},
  "confidence": 0.0,
  "clarification": null,
  "missing_assets": []
}
Never return ComfyUI nodes, workflow graphs, model filenames, or raw execution payloads.
Ask for clarification when intent or required parameters are ambiguous.
Use missing_assets when a required selected asset role is absent.
"""

# Retry configuration for transient provider errors.
_MAX_RETRIES = 3
_INITIAL_BACKOFF_S = 1.0
_BACKOFF_MULTIPLIER = 2.0
# Transient HTTP statuses that trigger a retry.
_RETRYABLE_STATUSES = {429, 500, 502, 503, 504}


class PlannerClient(Protocol):
    def plan(self, request: OrchestrateRequest) -> PlannerDecision:
        """Return a schema-validated planner decision for the request."""


def parse_planner_decision(raw_output: str | bytes | dict) -> PlannerDecision:
    try:
        if isinstance(raw_output, bytes):
            raw_output = raw_output.decode("utf-8")
        data = json.loads(raw_output) if isinstance(raw_output, str) else raw_output
        return PlannerDecision.model_validate(data)
    except (json.JSONDecodeError, TypeError, ValidationError) as exc:
        raise ValueError(f"planner_schema_invalid: {exc}") from exc


class EnvPlannerClient:
    """OpenAI-compatible planner client configured by environment variables.

    Includes bounded retry with exponential backoff for transient errors
    (HTTP 429/5xx from the upstream LLM provider).
    """

    def __init__(self, api_url: str | None = None, api_key: str | None = None, model: str | None = None):
        self.api_url = api_url or os.environ.get("PLANNER_API_URL")
        self.api_key = api_key or os.environ.get("PLANNER_API_KEY")
        self.model = model or os.environ.get("PLANNER_MODEL")

    def plan(self, request: OrchestrateRequest) -> PlannerDecision:
        if not self.api_url or not self.model:
            raise ValueError("planner_unconfigured: PLANNER_API_URL and PLANNER_MODEL are required")

        # Build the planner context from the request, including optional fields
        # like workflow_hint and selected_assets so the prompt-aware planner
        # can consider user intent and asset metadata.
        planner_ctx = {
            "prompt": request.prompt,
            "selected_asset_ids": request.selected_asset_ids,
            "workspace_context": request.workspace_context or {},
        }
        if request.workflow_hint:
            planner_ctx["workflow_hint"] = request.workflow_hint
        if request.selected_assets is not None:
            planner_ctx["selected_assets"] = [
                a.model_dump(exclude_none=True) for a in request.selected_assets
            ]

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(planner_ctx),
                },
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0,
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        http_request = urllib.request.Request(
            self.api_url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                with urllib.request.urlopen(http_request, timeout=30) as response:
                    body = json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                last_exc = exc
                if exc.code in _RETRYABLE_STATUSES and attempt < _MAX_RETRIES - 1:
                    _sleep_backoff(attempt)
                    continue
                raise ValueError("planner_provider_unavailable: Planner provider is unavailable") from exc
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES - 1:
                    _sleep_backoff(attempt)
                    continue
                raise ValueError("planner_provider_unavailable: Planner provider is unavailable") from exc
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                raise ValueError("planner_provider_invalid_response: Planner provider returned malformed JSON") from exc

            try:
                content = body["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError) as exc:
                raise ValueError("planner_provider_invalid_response: Planner provider response shape is invalid") from exc
            return parse_planner_decision(content)

        # Should not reach here, but satisfy the type-checker / linter.
        raise ValueError("planner_provider_unavailable: All retry attempts exhausted") from last_exc


def _sleep_backoff(attempt: int) -> None:
    """Sleep with exponential backoff before retrying."""
    delay = _INITIAL_BACKOFF_S * (_BACKOFF_MULTIPLIER**attempt)
    time.sleep(delay)
