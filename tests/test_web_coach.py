"""Local coach web API: synthetic DB, no real keyring or provider calls."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from mi_fitness_mcp.config import CoachConfig, Config
from mi_fitness_mcp.storage import Database
from mi_fitness_mcp.storage.coach import CoachStore
from mi_fitness_mcp.web.app import create_app
from tests.coach_fixtures import seed_coach_db


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path, user_id, today = seed_coach_db(tmp_path)
    CoachStore(Database(db_path))
    monkeypatch.setattr(
        "mi_fitness_mcp.web.coach_service.load_config",
        lambda: Config(coach=CoachConfig(enabled=False)),
    )
    monkeypatch.setattr(
        "mi_fitness_mcp.web.coach_service.load_mi_fitness_token",
        lambda: (None, None),
    )
    monkeypatch.setattr(
        "mi_fitness_mcp.web.coach_service.coach_llm_key_configured",
        lambda _provider: False,
    )
    monkeypatch.setattr(
        "mi_fitness_mcp.coach.service.coach_llm_key_configured",
        lambda _provider: False,
    )
    app = create_app(db_path=db_path)
    with TestClient(app) as test_client:
        test_client.today = today  # type: ignore[attr-defined]
        test_client.user_id = user_id  # type: ignore[attr-defined]
        yield test_client


def test_coach_status_and_overview(client):
    status = client.get("/api/coach/status")
    assert status.status_code == 200
    body = status.json()
    assert body["schemaInitialized"] is True
    assert body["enabled"] is False
    assert "keyConfigured" in body

    overview = client.get("/api/coach/overview", params={"weeks": 12})
    assert overview.status_code == 200
    data = overview.json()
    assert "status" in data
    assert "profile" in data
    assert data["goals"] == []


def test_coach_goal_write_requires_confirmation_and_uses_camel_case(client):
    payload = {
        "goalType": "weekly_frequency",
        "title": "每周训练 3 次",
        "targetValue": 3,
        "targetUnit": "sessions_per_week",
        "period": "week",
        "startDate": client.today.isoformat(),
    }
    denied = client.post("/api/coach/goals", json=payload)
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "COACH_CONFIRMATION_REQUIRED"

    created = client.post(
        "/api/coach/goals",
        json=payload,
        headers={"X-Mi-Fitness-Confirm": "coach"},
    )
    assert created.status_code == 200
    goal = created.json()["goal"]
    assert goal["goalType"] == "weekly_frequency"
    assert goal["targetUnit"] == "sessions_per_week"
    assert "userId" not in goal
    goal_id = goal["id"]

    listed = client.get("/api/coach/goals")
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["progress"]["goalId"] == goal_id

    generated = client.post(
        "/api/coach/plans/generate",
        json={"goalId": goal_id, "weeks": 8, "useLlm": False},
        headers={"X-Mi-Fitness-Confirm": "coach"},
    )
    assert generated.status_code == 200
    plan = generated.json()
    assert plan["generatedBy"] == "fallback"
    assert "userId" not in plan
    assert "user_id" not in plan["goalSnapshot"]
    assert plan["plan"]["weeks"]
    plan_id = plan["id"]

    active = client.post(
        f"/api/coach/plans/{plan_id}/activate",
        headers={"X-Mi-Fitness-Confirm": "coach"},
    )
    assert active.status_code == 200
    assert active.json()["status"] == "active"

    fetched = client.get(f"/api/coach/plans/{plan_id}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == plan_id


def test_coach_rejects_credentials_in_body_and_ai_without_config(client):
    response = client.post(
        "/api/coach/goals",
        json={
            "goalType": "weekly_frequency",
            "title": "bad",
            "targetUnit": "sessions_per_week",
            "apiKey": "must-not-be-accepted",
        },
        headers={"X-Mi-Fitness-Confirm": "coach"},
    )
    assert response.status_code == 422

    ai = client.post(
        "/api/coach/recommendations",
        json={"weeks": 12, "useLlm": True, "consent": True},
        headers={"X-Mi-Fitness-Confirm": "coach"},
    )
    assert ai.status_code == 409
    assert ai.json()["error"]["code"] == "COACH_DISABLED"


def test_missing_coach_schema_returns_409(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "mi_fitness_mcp.web.coach_service.load_config",
        lambda: Config(coach=CoachConfig(enabled=False)),
    )
    monkeypatch.setattr(
        "mi_fitness_mcp.web.coach_service.load_mi_fitness_token",
        lambda: (None, None),
    )
    monkeypatch.setattr(
        "mi_fitness_mcp.coach.service.coach_llm_key_configured",
        lambda _provider: False,
    )
    app = create_app(db_path=tmp_path / "missing.db")
    with TestClient(app) as client:
        status = client.get("/api/coach/status")
        assert status.status_code == 200
        assert status.json()["schemaInitialized"] is False
        goals = client.get("/api/coach/goals")
        assert goals.status_code == 409
        assert goals.json()["error"]["code"] == "COACH_NOT_INITIALIZED"
