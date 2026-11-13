"""LLM execution wrapper: timing, metadata, and stable error codes."""

from __future__ import annotations

import time
from dataclasses import replace
from typing import Any

from mi_fitness_mcp.coach.llm.base import (
    LLMErrorCode,
    LLMProvider,
    LLMProviderError,
    LLMRequest,
    LLMResult,
)
from mi_fitness_mcp.config import CoachConfig
from mi_fitness_mcp.storage.coach import CoachStore


class LLMRunner:
    def __init__(self, store: CoachStore | None, config: CoachConfig) -> None:
        self.store = store
        self.config = config

    async def run(
        self,
        provider: LLMProvider,
        request: LLMRequest,
        *,
        kind: str,
        prompt_version: str,
        schema_version: str,
        goal_id: str | None = None,
        plan_id: str | None = None,
    ) -> LLMResult:
        started = time.perf_counter()
        try:
            result = await provider.generate_structured(request)
        except LLMProviderError as exc:
            self._record(
                provider=provider,
                kind=kind,
                prompt_version=prompt_version,
                schema_version=schema_version,
                status="error",
                error_code=exc.code.value,
                attempts=1,
                fallback_used=False,
                usage=None,
                request_id=None,
                latency_ms=self._latency(started),
                goal_id=goal_id,
                plan_id=plan_id,
            )
            raise
        status = "refused" if result.refused else "ok"
        run_id = self._record(
            provider=provider,
            kind=kind,
            prompt_version=prompt_version,
            schema_version=schema_version,
            status=status,
            error_code=result.refusal_reason_code,
            attempts=result.attempts,
            fallback_used=False,
            usage=result.usage,
            request_id=result.provider_request_id,
            latency_ms=self._latency(started),
            goal_id=goal_id,
            plan_id=plan_id,
        )
        return replace(result, run_id=run_id)

    def record_semantic_failure(
        self,
        result: LLMResult,
        *,
        provider: LLMProvider,
        kind: str,
        prompt_version: str,
        schema_version: str,
        error_code: str = LLMErrorCode.INVALID_OUTPUT.value,
        goal_id: str | None = None,
        plan_id: str | None = None,
    ) -> None:
        self._record(
            provider=provider,
            kind=kind,
            prompt_version=prompt_version,
            schema_version=schema_version,
            status="invalid_output",
            error_code=error_code,
            attempts=result.attempts,
            fallback_used=True,
            usage=result.usage,
            request_id=result.provider_request_id,
            latency_ms=0,
            goal_id=goal_id,
            plan_id=plan_id,
        )

    def record_fallback(
        self,
        *,
        provider: LLMProvider | None,
        kind: str,
        prompt_version: str,
        schema_version: str,
        goal_id: str | None = None,
        plan_id: str | None = None,
    ) -> None:
        if provider is None:
            return
        self._record(
            provider=provider,
            kind=kind,
            prompt_version=prompt_version,
            schema_version=schema_version,
            status="fallback",
            error_code="DETERMINISTIC_FALLBACK",
            attempts=0,
            fallback_used=True,
            usage=None,
            request_id=None,
            latency_ms=0,
            goal_id=goal_id,
            plan_id=plan_id,
        )

    def _record(
        self,
        *,
        provider: LLMProvider,
        kind: str,
        prompt_version: str,
        schema_version: str,
        status: str,
        error_code: str | None,
        attempts: int,
        fallback_used: bool,
        usage: Any,
        request_id: str | None,
        latency_ms: int,
        goal_id: str | None,
        plan_id: str | None,
    ) -> str | None:
        if self.store is None:
            return None
        return self.store.record_ai_run(
            {
                "goal_id": goal_id,
                "plan_id": plan_id,
                "kind": kind,
                "provider": provider.name,
                "model": getattr(provider, "model", self.config.llm.model),
                "endpoint_kind": getattr(provider, "endpoint_kind", "remote"),
                "prompt_version": prompt_version,
                "schema_version": schema_version,
                "status": status,
                "error_code": error_code,
                "attempts": attempts,
                "fallback_used": int(fallback_used),
                "input_tokens": getattr(usage, "input_tokens", None) if usage else None,
                "output_tokens": getattr(usage, "output_tokens", None) if usage else None,
                "total_tokens": getattr(usage, "total_tokens", None) if usage else None,
                "latency_ms": latency_ms,
                "provider_request_id": request_id,
            }
        )

    @staticmethod
    def _latency(started: float) -> int:
        return max(0, round((time.perf_counter() - started) * 1000))
