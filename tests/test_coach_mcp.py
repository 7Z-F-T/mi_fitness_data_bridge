"""Coach MCP handlers with synthetic data and no provider calls."""

from __future__ import annotations

import json

import pytest

from mi_fitness_mcp import server
from mi_fitness_mcp.coach.service import CoachService
from mi_fitness_mcp.config import CoachConfig
from mi_fitness_mcp.services.query_service import QueryService
from mi_fitness_mcp.storage import Database
from mi_fitness_mcp.storage.coach import CoachStore
from tests.coach_fixtures import seed_coach_db


def _coach_service(tmp_path, monkeypatch):
    db_path, user_id, today = seed_coach_db(tmp_path)
    db = Database(db_path)
    query = QueryService(db, user_id)
    service = CoachService(
        CoachStore(db),
        query,
        CoachConfig(enabled=False, default_plan_weeks=8),
        timezone="UTC",
        today=today,
    )
    monkeypatch.setattr(server, "db", db)
    monkeypatch.setattr(server, "query_service", query)
    monkeypatch.setattr(server, "coach_service", service)
    return service, today


def _payload(response) -> dict:
    return json.loads(response[0].text)


@pytest.mark.asyncio
async def test_coach_save_goal_overview_and_plan(tmp_path, monkeypatch):
    _, today = _coach_service(tmp_path, monkeypatch)
    saved = _payload(
        await server.call_tool(
            "coach_save_goal",
            {
                "goal_type": "weekly_frequency",
                "title": "每周训练 3 次",
                "target_value": 3,
                "target_unit": "sessions_per_week",
                "period": "week",
                "start_date": today.isoformat(),
            },
        )
    )
    assert saved["status"] == "ok"
    assert "user_id" not in saved["data"]["goal"]
    goal_id = saved["data"]["goal"]["id"]

    overview = _payload(await server.call_tool("coach_get_overview", {"weeks": 12}))
    assert overview["status"] == "ok"
    assert overview["data"]["goals"]
    assert overview["data"]["status"]["schema_initialized"] is True

    recommendations = _payload(
        await server.call_tool(
            "coach_recommend_goals", {"weeks": 12, "use_llm": False}
        )
    )
    assert recommendations["status"] == "ok"
    assert recommendations["data"]["ai_used"] is False
    assert recommendations["data"]["recommendations"]

    generated = _payload(
        await server.call_tool(
            "coach_generate_plan",
            {"goal_id": goal_id, "weeks": 8, "use_llm": False},
        )
    )
    assert generated["status"] == "ok"
    assert generated["data"]["plan"]["generated_by"] == "fallback"
    assert "user_id" not in generated["data"]["plan"]
    assert "user_id" not in generated["data"]["plan"]["goal_snapshot"]
    plan_id = generated["data"]["plan"]["id"]

    fetched = _payload(
        await server.call_tool("coach_get_plan", {"plan_id": plan_id})
    )
    assert fetched["status"] == "ok"
    assert "user_id" not in fetched["data"]["plan"]
    assert fetched["data"]["plan"]["plan"]["weeks"]


@pytest.mark.asyncio
async def test_coach_ai_requires_configuration(tmp_path, monkeypatch):
    _coach_service(tmp_path, monkeypatch)
    response = _payload(
        await server.call_tool(
            "coach_recommend_goals",
            {"weeks": 12, "use_llm": True, "consent": True},
        )
    )
    assert response["status"] == "error"
    assert "disabled" in response["error"].lower() or "consent" in response["error"].lower()
