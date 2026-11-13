"""Coach LLM provider contracts: fake providers and respx only."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import timedelta
from types import SimpleNamespace

import httpx
import pytest
import respx

from mi_fitness_mcp.coach.llm.anthropic_provider import AnthropicProvider
from mi_fitness_mcp.coach.llm.base import (
    LLMErrorCode,
    LLMProviderError,
    LLMRequest,
    LLMResult,
    LLMUsage,
)
from mi_fitness_mcp.coach.llm.openai_compatible import OpenAICompatibleProvider
from mi_fitness_mcp.coach.models import GoalCreate, PlanGenerationConstraints
from mi_fitness_mcp.coach.service import CoachService
from mi_fitness_mcp.coach.templates import build_template_plan
from mi_fitness_mcp.config import CoachConfig, CoachLLMConfig
from mi_fitness_mcp.services.query_service import QueryService
from mi_fitness_mcp.storage import Database
from mi_fitness_mcp.storage.coach import CoachStore
from tests.coach_fixtures import seed_coach_db


class FakeProvider:
    name = "fake"
    endpoint_kind = "local"
    model = "fake-model"

    def __init__(self, data: dict, *, refused: bool = False, error: Exception | None = None):
        self.data = data
        self.refused = refused
        self.error = error
        self.calls = 0

    async def generate_structured(self, request: LLMRequest) -> LLMResult:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return LLMResult(
            data=self.data,
            provider=self.name,
            model=self.model,
            usage=LLMUsage(10, 20, 30),
            provider_request_id="req-fake",
            refused=self.refused,
        )


def _service(tmp_path, *, data: dict, refused: bool = False, error: Exception | None = None):
    db_path, user_id, today = seed_coach_db(tmp_path)
    db = Database(db_path)
    store = CoachStore(db)
    fake = FakeProvider(data, refused=refused, error=error)
    config = CoachConfig(
        enabled=True,
        language="zh-CN",
        profile_weeks=12,
        default_plan_weeks=8,
        llm=CoachLLMConfig(
            provider="openai_compatible",
            model="fake-model",
            base_url="http://127.0.0.1:11434/v1",
        ),
    )
    service = CoachService(
        store,
        QueryService(db, user_id),
        config,
        timezone="UTC",
        today=today,
        provider_factory=lambda _config: fake,
    )
    return service, store, fake, today


def _goal_data() -> dict:
    return {
        "recommendations": [
            {
                "goal_type": "weekly_frequency",
                "sport": "any",
                "title": "每周训练 3 次",
                "mode": "target",
                "target_value": 3,
                "target_unit": "sessions_per_week",
                "period": "week",
                "weeks_until_target": None,
                "rationale": "近期训练频率稳定，保持可持续节奏。",
                "evidence": ["observed_frequency"],
                "confidence": "medium",
                "data_gaps": [],
            }
        ],
        "overall_assessment": "维持频率。",
        "data_gaps": [],
        "disclaimer": "仅供运动参考。",
    }


def _plan_data(service: CoachService, goal_id: str, today) -> dict:
    goal = service.get_goal(goal_id).goal
    profile = service.profile(8)
    start = today + timedelta(days=(7 - today.weekday()) % 7 or 7)
    constraints = PlanGenerationConstraints(
        weeks=8, days_per_week=3, session_minutes=60, start_date=start
    )
    plan = build_template_plan(goal, profile, constraints, today=today)
    return {
        "title": plan.title,
        "summary": plan.summary,
        "weeks": [
            {
                "week_index": week.week_index,
                "focus": week.focus,
                "is_recovery_week": week.is_recovery_week,
                "sessions": [
                    {
                        "day_of_week": session.date.weekday(),
                        "sport": session.sport,
                        "session_type": session.session_type,
                        "duration_minutes": session.duration_minutes,
                        "distance_km": (
                            session.distance_m / 1000 if session.distance_m else None
                        ),
                        "intensity": session.intensity,
                        "description": session.description,
                        "purpose": session.purpose,
                        "optional": session.optional,
                    }
                    for session in week.sessions
                ],
            }
            for week in plan.weeks
        ],
        "progression_rules": plan.progression_rules,
        "weekly_habits": plan.weekly_habits,
        "safety": plan.safety.model_dump(),
        "assumptions": plan.assumptions,
        "data_gaps": plan.data_gaps,
    }


def test_ai_goal_recommendation_validates_and_records_metadata(tmp_path):
    service, store, fake, _ = _service(tmp_path, data=_goal_data())
    recommendations = asyncio.run(service.recommend_goals_ai(weeks=12, consent=True))
    assert fake.calls == 1
    assert recommendations
    assert recommendations[0].source == "ai_recommended"
    run = store.latest_ai_run()
    assert run is not None
    assert run["status"] == "ok"
    assert run["kind"] == "goal_recommendation"
    assert run["total_tokens"] == 30


def test_ai_goal_recommendation_falls_back_on_refusal(tmp_path):
    service, _, _, _ = _service(tmp_path, data={}, refused=True)
    recommendations = asyncio.run(service.recommend_goals_ai(weeks=12, consent=True))
    assert recommendations
    assert all(item.source == "rule_based" for item in recommendations)


def test_ai_plan_generation_materializes_and_activates(tmp_path):
    service, store, fake, today = _service(tmp_path, data={})
    goal = service.create_goal(
        GoalCreate(
            goal_type="weekly_frequency",
            title="每周 3 次",
            target_value=3,
            target_unit="sessions_per_week",
            period="week",
            start_date=today,
        )
    )
    fake.data = _plan_data(service, goal.id, today)
    plan = asyncio.run(
        service.generate_plan_ai(goal.id, weeks=8, consent=True, activate=True)
    )
    assert fake.calls == 1
    assert plan.generated_by == "llm"
    assert plan.status == "active"
    assert plan.validation_status == "passed"
    assert plan.ai_run_id
    assert plan.plan.weeks[0].sessions[0].date >= plan.plan.weeks[0].start_date


def test_ai_plan_generation_falls_back_on_provider_error(tmp_path):
    service, _, _, today = _service(
        tmp_path,
        data={},
        error=LLMProviderError(LLMErrorCode.TIMEOUT, "timeout", retryable=True),
    )
    goal = service.create_goal(
        GoalCreate(
            goal_type="weekly_frequency",
            title="每周 3 次",
            target_value=3,
            target_unit="sessions_per_week",
            period="week",
            start_date=today,
        )
    )
    plan = asyncio.run(service.generate_plan_ai(goal.id, weeks=8, consent=True))
    assert plan.generated_by == "fallback"
    assert any("AI_FALLBACK" in warning for warning in plan.validation_warnings)


def test_remote_endpoint_requires_consent_before_provider_construction(tmp_path, monkeypatch):
    db_path, user_id, today = seed_coach_db(tmp_path)
    db = Database(db_path)
    store = CoachStore(db)
    config = CoachConfig(
        enabled=True,
        llm=CoachLLMConfig(
            provider="openai_compatible",
            model="fake-model",
            base_url="https://api.example.com/v1",
        ),
    )
    service = CoachService(
        store,
        QueryService(db, user_id),
        config,
        timezone="UTC",
        today=today,
        provider_factory=lambda _config: (_ for _ in ()).throw(
            AssertionError("provider must not be constructed")
        ),
    )
    monkeypatch.setattr(
        "mi_fitness_mcp.coach.service.coach_llm_key_configured", lambda _p: True
    )
    with pytest.raises(LLMProviderError) as exc_info:
        asyncio.run(service.recommend_goals_ai(weeks=12, consent=True))
    assert exc_info.value.code == LLMErrorCode.CONSENT_REQUIRED


def _request() -> LLMRequest:
    return LLMRequest(
        system="system",
        user="user",
        schema_name="test",
        schema={"type": "object", "properties": {}, "additionalProperties": False},
        max_output_tokens=100,
    )


def test_anthropic_provider_parses_text_and_refusal():
    payload = {"recommendations": []}

    class Messages:
        def __init__(self, response):
            self.response = response
            self.calls = 0

        async def create(self, **kwargs):
            self.calls += 1
            return self.response

    response = SimpleNamespace(
        content=[SimpleNamespace(type="text", text=json.dumps(payload))],
        stop_reason="end_turn",
        usage=SimpleNamespace(input_tokens=10, output_tokens=20),
        _request_id="req-1",
    )
    messages = Messages(response)
    provider = AnthropicProvider(
        api_key="test",
        model="fake",
        client_factory=lambda: SimpleNamespace(messages=messages),
    )
    result = asyncio.run(provider.generate_structured(_request()))
    assert result.data == payload
    assert result.usage.total_tokens == 30

    refusal = SimpleNamespace(
        content=[],
        stop_reason="refusal",
        stop_details=SimpleNamespace(category="cyber"),
        usage=SimpleNamespace(input_tokens=1, output_tokens=0),
        _request_id="req-2",
    )
    provider = AnthropicProvider(
        api_key="test",
        model="fake",
        client_factory=lambda: SimpleNamespace(
            messages=Messages(refusal)
        ),
    )
    result = asyncio.run(provider.generate_structured(_request()))
    assert result.refused is True
    assert result.refusal_reason_code == "cyber"


def test_anthropic_provider_retries_without_unsupported_thinking():
    payload = {"recommendations": []}

    class Messages:
        def __init__(self):
            self.calls = 0

        async def create(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("thinking adaptive is not supported")
            return SimpleNamespace(
                content=[SimpleNamespace(type="text", text=json.dumps(payload))],
                stop_reason="end_turn",
                usage=None,
                _request_id=None,
            )

    messages = Messages()
    provider = AnthropicProvider(
        api_key="test",
        model="fake",
        client_factory=lambda: SimpleNamespace(messages=messages),
    )
    result = asyncio.run(provider.generate_structured(_request()))
    assert result.data == payload
    assert messages.calls == 2


def test_openai_compatible_falls_back_from_json_schema():
    url = "https://api.example.com/v1/chat/completions"
    provider = OpenAICompatibleProvider(
        base_url="https://api.example.com/v1",
        api_key="test-key",
        model="fake-model",
        max_retries=0,
    )
    with respx.mock(assert_all_called=False) as mock:
        mock.post(url).mock(
            side_effect=[
                httpx.Response(
                    400, json={"error": {"message": "response_format unsupported"}}
                ),
                httpx.Response(
                    200,
                    json={
                        "model": "fake-model",
                        "choices": [
                            {
                                "message": {"content": json.dumps({"ok": True})},
                                "finish_reason": "stop",
                            }
                        ],
                        "usage": {
                            "prompt_tokens": 11,
                            "completion_tokens": 7,
                            "total_tokens": 18,
                        },
                    },
                ),
            ]
        )
        result = asyncio.run(provider.generate_structured(_request()))
    assert result.data == {"ok": True}
    assert result.usage.total_tokens == 18


def test_openai_compatible_auth_error_is_not_retried():
    url = "https://api.example.com/v1/chat/completions"
    provider = OpenAICompatibleProvider(
        base_url="https://api.example.com/v1",
        api_key="test-key",
        model="fake-model",
        max_retries=2,
    )
    with respx.mock(assert_all_called=False) as mock:
        route = mock.post(url).mock(return_value=httpx.Response(401, json={}))
        with pytest.raises(LLMProviderError) as exc_info:
            asyncio.run(provider.generate_structured(_request()))
    assert exc_info.value.code == LLMErrorCode.AUTH_FAILED
    assert route.call_count == 1


def test_coach_logs_do_not_contain_payload_sentinels(tmp_path, caplog):
    service, _, _, _ = _service(tmp_path, data=_goal_data())
    caplog.set_level(logging.DEBUG)
    asyncio.run(service.recommend_goals_ai(weeks=12, consent=True))
    assert "SENTINEL" not in caplog.text
