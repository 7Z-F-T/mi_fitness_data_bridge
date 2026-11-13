"""Anthropic Claude provider using the official SDK."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from mi_fitness_mcp.coach.llm.base import (
    LLMErrorCode,
    LLMProviderError,
    LLMRequest,
    LLMResult,
    LLMUsage,
)

ClientFactory = Callable[[], Any]


class AnthropicProvider:
    name = "anthropic"
    endpoint_kind = "remote"

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "claude-opus-5-5",
        timeout_seconds: float = 180.0,
        max_retries: int = 1,
        fallback_models: list[str] | None = None,
        client_factory: ClientFactory | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.fallback_models = fallback_models or []
        self._client_factory = client_factory
        self._client: Any | None = None

    def _client_or_create(self) -> Any:
        if self._client is not None:
            return self._client
        if self._client_factory is not None:
            self._client = self._client_factory()
            return self._client
        import anthropic

        self._client = anthropic.AsyncAnthropic(
            api_key=self.api_key,
            timeout=self.timeout_seconds,
            max_retries=self.max_retries,
        )
        return self._client

    async def generate_structured(self, request: LLMRequest) -> LLMResult:
        client = self._client_or_create()
        attempts = 0
        mode = "full"
        last_error: Exception | None = None
        while attempts < 3:
            attempts += 1
            try:
                response = await self._create(client, request, mode)
                return self._parse(response, request, attempts=attempts)
            except Exception as exc:  # noqa: BLE001 - mapped below
                last_error = exc
                next_mode = self._next_mode(exc, mode)
                if next_mode is not None:
                    mode = next_mode
                    continue
                raise self._map_error(exc) from exc
        raise self._map_error(last_error or RuntimeError("Anthropic request failed"))

    async def _create(
        self, client: Any, request: LLMRequest, mode: str
    ) -> Any:
        system = request.system
        output_config: dict[str, Any] | None = None
        thinking: dict[str, Any] | None = None
        if mode == "full":
            thinking = {"type": "adaptive"}
            output_config = {
                "effort": "medium",
                "format": {"type": "json_schema", "schema": request.schema},
            }
        elif mode == "no_thinking":
            output_config = {
                "effort": "medium",
                "format": {"type": "json_schema", "schema": request.schema},
            }
        else:  # plain JSON-only fallback
            system = (
                f"{system}\nReturn only JSON matching this schema:\n"
                f"{json.dumps(request.schema, ensure_ascii=False)}"
            )

        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": request.max_output_tokens,
            "system": system,
            "messages": [{"role": "user", "content": request.user}],
        }
        if output_config is not None:
            kwargs["output_config"] = output_config
        if thinking is not None:
            kwargs["thinking"] = thinking

        if mode == "full" and self.fallback_models and hasattr(client, "beta"):
            return await client.beta.messages.create(
                **kwargs,
                betas=["server-side-fallback-2026-06-01"],
                fallbacks=[{"model": model} for model in self.fallback_models],
            )
        return await client.messages.create(**kwargs)

    @staticmethod
    def _next_mode(exc: Exception, mode: str) -> str | None:
        message = str(exc).lower()
        if mode == "full":
            if any(
                token in message
                for token in ("thinking", "adaptive", "output_config", "format", "schema")
            ):
                return "no_thinking" if "thinking" in message or "adaptive" in message else "plain"
            if isinstance(exc, (TypeError, AttributeError)):
                return "no_thinking"
        if mode == "no_thinking" and any(
            token in message for token in ("output_config", "format", "schema", "unknown")
        ):
            return "plain"
        return None

    def _parse(self, response: Any, request: LLMRequest, *, attempts: int) -> LLMResult:
        stop_reason = getattr(response, "stop_reason", None)
        if stop_reason == "refusal":
            details = getattr(response, "stop_details", None)
            reason = getattr(details, "category", None)
            if reason is None and isinstance(details, dict):
                reason = details.get("category")
            return LLMResult(
                data={},
                provider=self.name,
                model=self.model,
                usage=self._usage(response),
                provider_request_id=getattr(response, "_request_id", None),
                refused=True,
                refusal_reason_code=reason,
                attempts=attempts,
            )
        if stop_reason == "max_tokens":
            raise LLMProviderError(
                LLMErrorCode.INVALID_OUTPUT,
                "Model output was truncated before valid JSON was complete.",
            )
        text = "".join(
            block.text
            for block in getattr(response, "content", [])
            if getattr(block, "type", None) == "text"
        )
        data = self._load_json(text)
        return LLMResult(
            data=data,
            provider=self.name,
            model=self.model,
            usage=self._usage(response),
            provider_request_id=getattr(response, "_request_id", None),
            attempts=attempts,
        )

    @staticmethod
    def _load_json(text: str) -> dict[str, Any]:
        candidate = text.strip()
        if candidate.startswith("```"):
            candidate = candidate.strip("`")
            if candidate.startswith("json"):
                candidate = candidate[4:]
            candidate = candidate.strip()
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError as exc:
            raise LLMProviderError(
                LLMErrorCode.INVALID_OUTPUT,
                "Model did not return valid JSON.",
            ) from exc
        if not isinstance(data, dict):
            raise LLMProviderError(
                LLMErrorCode.INVALID_OUTPUT,
                "Model returned JSON that is not an object.",
            )
        return data

    @staticmethod
    def _usage(response: Any) -> LLMUsage:
        usage = getattr(response, "usage", None)
        if usage is None:
            return LLMUsage()
        return LLMUsage(
            input_tokens=getattr(usage, "input_tokens", None),
            output_tokens=getattr(usage, "output_tokens", None),
            total_tokens=(
                (getattr(usage, "input_tokens", 0) or 0)
                + (getattr(usage, "output_tokens", 0) or 0)
            ),
        )

    @staticmethod
    def _map_error(exc: Exception) -> LLMProviderError:
        try:
            import anthropic
        except ImportError:
            anthropic = None  # type: ignore[assignment]
        if anthropic is not None:
            if isinstance(exc, anthropic.AuthenticationError):
                return LLMProviderError(LLMErrorCode.AUTH_FAILED, "Anthropic authentication failed.")
            if isinstance(exc, anthropic.PermissionDeniedError):
                return LLMProviderError(
                    LLMErrorCode.MODEL_ACCESS_DENIED,
                    "Anthropic denied access to this model.",
                )
            if isinstance(exc, anthropic.NotFoundError):
                return LLMProviderError(
                    LLMErrorCode.MODEL_NOT_FOUND, "Anthropic model or endpoint not found."
                )
            if isinstance(exc, anthropic.RateLimitError):
                return LLMProviderError(
                    LLMErrorCode.RATE_LIMITED,
                    "Anthropic rate limit exceeded.",
                    retryable=True,
                    http_status=429,
                )
            if isinstance(exc, anthropic.APITimeoutError):
                return LLMProviderError(
                    LLMErrorCode.TIMEOUT, "Anthropic request timed out.", retryable=True
                )
            if isinstance(exc, anthropic.APIConnectionError):
                return LLMProviderError(
                    LLMErrorCode.CONNECTION_FAILED,
                    "Could not connect to Anthropic.",
                    retryable=True,
                )
            if isinstance(exc, anthropic.APIStatusError):
                status = getattr(exc, "status_code", None)
                if status and status >= 500:
                    return LLMProviderError(
                        LLMErrorCode.PROVIDER_UNAVAILABLE,
                        "Anthropic is temporarily unavailable.",
                        retryable=True,
                        http_status=status,
                    )
                return LLMProviderError(
                    LLMErrorCode.INVALID_REQUEST,
                    "Anthropic rejected the request.",
                    http_status=status,
                )
        if isinstance(exc, LLMProviderError):
            return exc
        return LLMProviderError(
            LLMErrorCode.PROVIDER_UNAVAILABLE,
            "Anthropic request failed.",
            retryable=True,
        )
