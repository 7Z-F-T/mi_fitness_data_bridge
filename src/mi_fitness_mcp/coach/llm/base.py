"""Provider-neutral contracts for structured coach LLM calls."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol


class LLMErrorCode(StrEnum):
    AUTH_FAILED = "AUTH_FAILED"
    MODEL_NOT_FOUND = "MODEL_NOT_FOUND"
    MODEL_ACCESS_DENIED = "MODEL_ACCESS_DENIED"
    RATE_LIMITED = "RATE_LIMITED"
    TIMEOUT = "TIMEOUT"
    CONNECTION_FAILED = "CONNECTION_FAILED"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    INVALID_REQUEST = "INVALID_REQUEST"
    INVALID_OUTPUT = "INVALID_OUTPUT"
    REFUSED = "REFUSED"
    CONTENT_FILTERED = "CONTENT_FILTERED"
    SCHEMA_UNSUPPORTED = "SCHEMA_UNSUPPORTED"
    CONSENT_REQUIRED = "CONSENT_REQUIRED"
    KEY_MISSING = "KEY_MISSING"
    EXTRA_MISSING = "EXTRA_MISSING"


@dataclass(frozen=True)
class LLMRequest:
    system: str
    user: str
    schema_name: str
    schema: dict[str, Any]
    max_output_tokens: int = 16_000
    temperature: float = 0.3


@dataclass(frozen=True)
class LLMUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True)
class LLMResult:
    data: dict[str, Any]
    provider: str
    model: str
    usage: LLMUsage = field(default_factory=LLMUsage)
    provider_request_id: str | None = None
    refused: bool = False
    refusal_reason_code: str | None = None
    attempts: int = 1
    run_id: str | None = None


class LLMProviderError(RuntimeError):
    def __init__(
        self,
        code: LLMErrorCode,
        message: str,
        *,
        retryable: bool = False,
        http_status: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.http_status = http_status


class LLMProvider(Protocol):
    name: str
    endpoint_kind: str

    async def generate_structured(self, request: LLMRequest) -> LLMResult:
        """Return parsed JSON matching ``request.schema`` or raise LLMProviderError."""
