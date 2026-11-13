"""Coach storage/config contracts: synthetic data only."""

from __future__ import annotations

import sqlite3

import pytest
from pydantic import ValidationError

from mi_fitness_mcp.config import CoachConfig, CoachLLMConfig, Config
from mi_fitness_mcp.storage import Database
from mi_fitness_mcp.storage.coach import CoachNotInitializedError, CoachStore


def _goal_payload() -> dict:
    return {
        "goal_type": "weekly_frequency",
        "sport": "any",
        "title": "每周训练 3 次",
        "mode": "target",
        "target_value": 3,
        "target_unit": "sessions_per_week",
        "period": "week",
        "start_date": "2026-01-01",
        "status": "active",
    }


def _plan_payload(goal_id: str, plan_id: str = "plan-1") -> dict:
    return {
        "id": plan_id,
        "goal_id": goal_id,
        "title": "4 周基础计划",
        "start_date": "2026-01-05",
        "end_date": "2026-02-01",
        "weeks": 4,
        "generated_by": "fallback",
        "schema_version": "coach-plan-schema-v1",
        "goal_snapshot": {"goal_type": "weekly_frequency"},
        "plan": {"weeks": []},
        "validation_status": "passed",
        "validation_warnings": [],
    }


def test_coach_schema_and_goal_crud(tmp_path):
    db = Database(tmp_path / "coach.db")
    store = CoachStore(db)
    assert store.schema_initialized()

    goal = store.insert_goal(_goal_payload())
    assert goal["id"]
    assert goal["user_id"] == "local"
    assert goal["status"] == "active"

    assert store.get_goal(goal["id"])["title"] == "每周训练 3 次"
    assert len(store.list_goals()) == 1
    assert store.count_goals() == 1

    updated = store.update_goal(goal["id"], {"title": "每周 4 次"})
    assert updated is not None
    assert updated["title"] == "每周 4 次"

    archived = store.update_goal(goal["id"], {"status": "archived"})
    assert archived is not None
    assert archived["status"] == "archived"
    assert store.list_goals(status="active") == []


def test_one_active_plan_per_goal(tmp_path):
    db = Database(tmp_path / "coach.db")
    store = CoachStore(db)
    goal = store.insert_goal(_goal_payload())

    first = store.insert_plan(_plan_payload(goal["id"], "plan-1"))
    second = store.insert_plan(_plan_payload(goal["id"], "plan-2"))
    assert first["status"] == "draft"
    assert second["status"] == "draft"

    assert store.activate_plan("plan-1", goal["id"])["status"] == "active"
    store.activate_plan("plan-2", goal["id"])

    active = store.get_active_plan(goal["id"])
    assert active is not None
    assert active["id"] == "plan-2"
    assert store.get_plan("plan-1")["status"] == "superseded"
    assert len(store.list_plans(goal_id=goal["id"], status="active")) == 1


def test_ai_run_allowlist_drops_payloads(tmp_path):
    db = Database(tmp_path / "coach.db")
    store = CoachStore(db)
    run_id = store.record_ai_run(
        {
            "kind": "plan_generation",
            "provider": "anthropic",
            "model": "claude-opus-5-5",
            "endpoint_kind": "remote",
            "prompt_version": "coach-plan-v1",
            "schema_version": "coach-plan-schema-v1",
            "status": "ok",
            "prompt": "SENTINEL PROMPT",
            "response": "SENTINEL RESPONSE",
            "api_key": "SENTINEL KEY",
        }
    )
    runs = store.list_ai_runs()
    assert len(runs) == 1
    assert runs[0]["id"] == run_id
    serialized = str(runs[0])
    assert "SENTINEL" not in serialized
    assert "prompt" not in runs[0]
    assert "response" not in runs[0]
    assert "api_key" not in runs[0]


def test_read_only_missing_coach_schema(tmp_path):
    path = tmp_path / "empty.db"
    sqlite3.connect(path).close()
    db = Database(path, read_only=True)
    store = CoachStore(db)
    assert store.schema_initialized() is False
    with pytest.raises(CoachNotInitializedError):
        store.list_goals()


def test_coach_config_defaults_and_url_validation():
    assert Config().coach.enabled is False
    assert Config().coach.llm.model == "claude-opus-5-5"
    assert CoachConfig().profile_weeks == 8

    local = CoachLLMConfig(
        provider="openai_compatible",
        base_url="http://127.0.0.1:11434/v1",
    )
    assert local.base_url == "http://127.0.0.1:11434/v1"

    remote = CoachLLMConfig(
        provider="openai_compatible",
        base_url="https://api.example.com/v1",
    )
    assert remote.base_url == "https://api.example.com/v1"

    with pytest.raises(ValidationError):
        CoachLLMConfig(provider="openai_compatible", base_url="http://api.example.com/v1")
    with pytest.raises(ValidationError):
        CoachLLMConfig(
            provider="openai_compatible",
            base_url="https://user:pass@api.example.com/v1",
        )
