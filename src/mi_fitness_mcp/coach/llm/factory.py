"""Provider construction and consent gates."""

from __future__ import annotations

import hashlib
import importlib.util
import ipaddress
from collections.abc import Callable
from typing import Any
from urllib.parse import urlsplit

from mi_fitness_mcp.auth import coach_llm_key_configured, load_coach_llm_api_key
from mi_fitness_mcp.coach.llm.base import LLMErrorCode, LLMProvider, LLMProviderError
from mi_fitness_mcp.config import CoachLLMConfig

ANTHROPIC_HOST = "api.anthropic.com"


def is_local_endpoint(base_url: str | None) -> bool:
    if not base_url:
        return False
    host = (urlsplit(base_url).hostname or "").lower()
    if host == "localhost" or host.endswith(".localhost"):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def endpoint_host(config: CoachLLMConfig) -> str:
    if config.provider == "anthropic":
        return ANTHROPIC_HOST
    return (urlsplit(config.base_url or "").hostname or "").lower()


def endpoint_kind(config: CoachLLMConfig) -> str:
    if config.provider == "anthropic":
        return "remote"
    return "local" if is_local_endpoint(config.base_url) else "remote"


def consent_fingerprint(provider: str, host: str, model: str) -> str:
    return hashlib.sha256(f"{provider}|{host}|{model}".encode()).hexdigest()[:16]


def require_egress_allowed(config: CoachLLMConfig, *, per_call_consent: bool) -> None:
    if not per_call_consent:
        raise LLMProviderError(
            LLMErrorCode.CONSENT_REQUIRED,
            "Explicit per-call consent is required before an AI request.",
        )
    if endpoint_kind(config) == "local":
        return
    host = endpoint_host(config)
    if not (
        config.remote_consent_at
        and config.remote_consent_provider == config.provider
        and config.remote_consent_host == host
    ):
        raise LLMProviderError(
            LLMErrorCode.CONSENT_REQUIRED,
            "Remote LLM consent is missing; run `mi-fitness-bridge coach setup`.",
        )
    expected = consent_fingerprint(config.provider, host, config.model)
    if config.remote_consent_fingerprint and config.remote_consent_fingerprint != expected:
        raise LLMProviderError(
            LLMErrorCode.CONSENT_REQUIRED,
            "Remote LLM consent is stale; run `mi-fitness-bridge coach setup` again.",
        )


def _anthropic_available() -> bool:
    return importlib.util.find_spec("anthropic") is not None


def provider_status(config: CoachLLMConfig) -> dict[str, Any]:
    return {
        "provider": config.provider,
        "model": config.model,
        "base_url": config.base_url,
        "endpoint_kind": endpoint_kind(config),
        "key_configured": coach_llm_key_configured(config.provider),
        "anthropic_extra_available": _anthropic_available(),
        "remote_consent_at": config.remote_consent_at,
        "remote_consent_host": config.remote_consent_host,
        "consent_fingerprint": config.remote_consent_fingerprint,
    }


ProviderFactory = Callable[[CoachLLMConfig], LLMProvider]


def build_provider(
    config: CoachLLMConfig,
    *,
    provider_factory: ProviderFactory | None = None,
) -> LLMProvider:
    if provider_factory is not None:
        return provider_factory(config)
    if config.provider == "anthropic":
        if not _anthropic_available():
            raise LLMProviderError(
                LLMErrorCode.EXTRA_MISSING,
                "Anthropic SDK is not installed; run `pip install -e \".[coach]\"`.",
            )
        api_key = load_coach_llm_api_key("anthropic")
        if not api_key:
            raise LLMProviderError(
                LLMErrorCode.KEY_MISSING,
                "Anthropic API key is not configured; run `mi-fitness-bridge coach setup`.",
            )
        from mi_fitness_mcp.coach.llm.anthropic_provider import AnthropicProvider

        return AnthropicProvider(
            api_key=api_key,
            model=config.model,
            timeout_seconds=config.timeout_seconds,
            max_retries=config.max_retries,
            fallback_models=config.anthropic_fallback_models,
        )
    if config.provider == "openai_compatible":
        if not config.base_url:
            raise LLMProviderError(
                LLMErrorCode.INVALID_REQUEST,
                "openai_compatible requires a base_url.",
            )
        api_key = load_coach_llm_api_key("openai_compatible")
        if endpoint_kind(config) == "remote" and not api_key:
            raise LLMProviderError(
                LLMErrorCode.KEY_MISSING,
                "Remote OpenAI-compatible endpoint requires an API key.",
            )
        from mi_fitness_mcp.coach.llm.openai_compatible import (
            OpenAICompatibleProvider,
        )

        return OpenAICompatibleProvider(
            base_url=config.base_url,
            api_key=api_key,
            model=config.model,
            timeout_seconds=config.timeout_seconds,
            max_retries=config.max_retries,
            temperature=config.temperature,
        )
    raise LLMProviderError(
        LLMErrorCode.INVALID_REQUEST, f"Unknown LLM provider: {config.provider}"
    )
