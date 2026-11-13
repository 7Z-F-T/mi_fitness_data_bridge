"""OpenAI-compatible chat-completions provider using httpx."""

from __future__ import annotations

import asyncio
import ipaddress
import json
from typing import Any
from urllib.parse import urlsplit

import httpx

from mi_fitness_mcp.coach.llm.base import (
    LLMErrorCode,
    LLMProviderError,
    LLMRequest,
    LLMResult,
    LLMUsage,
)


def _is_local(base_url: str) -> bool:
    host = (urlsplit(base_url).hostname or "").lower()
    if host == "localhost" or host.endswith(".localhost"):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


class OpenAICompatibleProvider:
    name = "openai_compatible"

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None,
        model: str,
        timeout_seconds: float = 180.0,
        max_retries: int = 1,
        temperature: float = 0.3,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.temperature = temperature
        self.endpoint_kind = "local" if _is_local(base_url) else "remote"
        self._client = client
        self._owns_client = client is None

    def _client_or_create(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(self.timeout_seconds))
        return self._client

    async def aclose(self) -> None:
        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None

    async def generate_structured(self, request: LLMRequest) -> LLMResult:
        client = self._client_or_create()
        formats: list[str] = ["json_schema", "json_object", "plain"]
        last_error: LLMProviderError | None = None
        attempts = 0
        for fmt in formats:
            attempts += 1
            body = self._body(request, fmt)
            try:
                response = await self._post(client, body)
            except LLMProviderError as exc:
                last_error = exc
                if exc.code in {
                    LLMErrorCode.INVALID_REQUEST,
                    LLMErrorCode.SCHEMA_UNSUPPORTED,
                } and fmt != "plain":
                    continue
                raise
            return self._parse(response, request, attempts=attempts)
        raise last_error or LLMProviderError(
            LLMErrorCode.INVALID_REQUEST, "OpenAI-compatible request failed."
        )

    def _body(self, request: LLMRequest, fmt: str) -> dict[str, Any]:
        system = request.system
        response_format: dict[str, Any] | None = None
        if fmt == "json_schema":
            response_format = {
                "type": "json_schema",
                "json_schema": {
                    "name": request.schema_name,
                    "strict": True,
                    "schema": request.schema,
                },
            }
        elif fmt == "json_object":
            response_format = {"type": "json_object"}
            system = (
                f"{system}\nReturn only JSON matching this schema:\n"
                f"{json.dumps(request.schema, ensure_ascii=False)}"
            )
        else:
            system = (
                f"{system}\nReturn only JSON matching this schema:\n"
                f"{json.dumps(request.schema, ensure_ascii=False)}"
            )
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": request.user},
            ],
            "max_tokens": request.max_output_tokens,
            "temperature": self.temperature,
        }
        if response_format is not None:
            body["response_format"] = response_format
        return body

    async def _post(
        self, client: httpx.AsyncClient, body: dict[str, Any]
    ) -> httpx.Response:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        url = f"{self.base_url}/chat/completions"
        attempts = 0
        while True:
            attempts += 1
            try:
                response = await client.post(url, headers=headers, json=body)
            except httpx.TimeoutException as exc:
                raise LLMProviderError(
                    LLMErrorCode.TIMEOUT, "LLM request timed out.", retryable=True
                ) from exc
            except httpx.HTTPError as exc:
                raise LLMProviderError(
                    LLMErrorCode.CONNECTION_FAILED,
                    "Could not connect to the LLM endpoint.",
                    retryable=True,
                ) from exc
            if response.status_code < 400:
                return response
            error = self._map_status(response)
            if not error.retryable or attempts > self.max_retries:
                if response.status_code in {400, 422}:
                    raise LLMProviderError(
                        LLMErrorCode.INVALID_REQUEST,
                        "Endpoint rejected the request or response_format.",
                        http_status=response.status_code,
                    )
                raise error
            await asyncio.sleep(self._retry_delay(response, attempts))

    @staticmethod
    def _retry_delay(response: httpx.Response, attempt: int) -> float:
        retry_after = response.headers.get("retry-after")
        if retry_after:
            try:
                return min(30.0, max(0.0, float(retry_after)))
            except ValueError:
                pass
        return min(8.0, 0.5 * (2 ** (attempt - 1)))

    @staticmethod
    def _map_status(response: httpx.Response) -> LLMProviderError:
        status = response.status_code
        if status == 401:
            return LLMProviderError(
                LLMErrorCode.AUTH_FAILED, "LLM authentication failed.", http_status=status
            )
        if status == 403:
            return LLMProviderError(
                LLMErrorCode.MODEL_ACCESS_DENIED,
                "LLM endpoint denied access.",
                http_status=status,
            )
        if status == 404:
            return LLMProviderError(
                LLMErrorCode.MODEL_NOT_FOUND,
                "LLM model or endpoint not found.",
                http_status=status,
            )
        if status == 429:
            return LLMProviderError(
                LLMErrorCode.RATE_LIMITED,
                "LLM rate limit exceeded.",
                retryable=True,
                http_status=status,
            )
        if status >= 500:
            return LLMProviderError(
                LLMErrorCode.PROVIDER_UNAVAILABLE,
                "LLM endpoint is temporarily unavailable.",
                retryable=True,
                http_status=status,
            )
        return LLMProviderError(
            LLMErrorCode.INVALID_REQUEST,
            "LLM endpoint rejected the request.",
            http_status=status,
        )

    def _parse(
        self, response: httpx.Response, request: LLMRequest, *, attempts: int
    ) -> LLMResult:
        try:
            payload = response.json()
        except ValueError as exc:
            raise LLMProviderError(
                LLMErrorCode.INVALID_OUTPUT, "LLM returned a non-JSON HTTP response."
            ) from exc
        choices = payload.get("choices") or []
        if not choices:
            raise LLMProviderError(
                LLMErrorCode.INVALID_OUTPUT, "LLM response had no choices."
            )
        choice = choices[0]
        if choice.get("finish_reason") == "content_filter":
            return LLMResult(
                data={},
                provider=self.name,
                model=payload.get("model") or self.model,
                usage=self._usage(payload),
                provider_request_id=response.headers.get("x-request-id"),
                refused=True,
                refusal_reason_code="content_filter",
                attempts=attempts,
            )
        message = choice.get("message") or {}
        content = message.get("content")
        if isinstance(content, list):
            content = "".join(
                part.get("text", "")
                for part in content
                if isinstance(part, dict) and part.get("type") == "text"
            )
        if not isinstance(content, str):
            raise LLMProviderError(
                LLMErrorCode.INVALID_OUTPUT, "LLM response did not contain text."
            )
        data = self._load_json(content)
        return LLMResult(
            data=data,
            provider=self.name,
            model=payload.get("model") or self.model,
            usage=self._usage(payload),
            provider_request_id=response.headers.get("x-request-id"),
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
                LLMErrorCode.INVALID_OUTPUT, "LLM did not return valid JSON."
            ) from exc
        if not isinstance(data, dict):
            raise LLMProviderError(
                LLMErrorCode.INVALID_OUTPUT, "LLM returned JSON that is not an object."
            )
        return data

    @staticmethod
    def _usage(payload: dict[str, Any]) -> LLMUsage:
        usage = payload.get("usage") or {}
        return LLMUsage(
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
            total_tokens=usage.get("total_tokens"),
        )
