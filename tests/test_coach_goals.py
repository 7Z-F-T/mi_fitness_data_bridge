"""Coach goal CRUD, progress, recommendations, and safety validation."""

from __future__ import annotations

from datetime import timedelta

import pytest

from mi_fitness_mcp.coach.goals import GoalService
from mi_fitness_mcp.coach.models import GoalCreate, GoalUpdate
from mi_fitness_mcp.coach.profile import TrainingProfileBuilder
from mi_fitness_mcp.services.query_service import QueryService
from mi_fitness_mcp.storage import Database
from mi_fitness_mcp.storage.coach import CoachStore
from tests.coach_fixtures import seed_coach_db


def _service(tmp_path):
    db_path, user_id, today = seed_coach_db(tmp_path)
    db = Database(db_path)
    query = QueryService(db, user_id)
    store = CoachStore(db)
    service = GoalService(store, query, "Asia/Shanghai", today=today)
    builder = TrainingProfileBuilder(query, timezone="Asia/Shanghai", today=today)
    return service, builder, today, db


def test_weekly_goal_progress_and_archive(tmp_path):
    service, _, today, _ = _service(tmp_path)
    goal = service.create(
        GoalCreate(
            goal_type="weekly_frequency",
            title="每周训练 3 次",
            target_value=3,
            target_unit="sessions_per_week",
            period="week",
            start_date=today,
        )
    )
    item = service.get(goal.id)
    assert item.progress.current_value is not None
    assert item.progress.current_value >= 3
    assert item.progress.status in {"achieved", "ok", "behind"}

    updated = service.update(goal.id, GoalUpdate(title="每周训练 4 次"))
    assert updated.title == "每周训练 4 次"
    archived = service.archive(goal.id)
    assert archived.status == "archived"
    assert service.list(status="active") == []


def test_distance_goal_progress(tmp_path):
    service, _, today, _ = _service(tmp_path)
    goal = service.create(
        GoalCreate(
            goal_type="distance",
            sport="running",
            title="每周跑步 15 公里",
            target_value=15000,
            target_unit="meters",
            period="week",
            start_date=today,
        )
    )
    progress = service.get(goal.id).progress
    assert progress.current_value is not None
    assert progress.current_value > 0
    assert progress.unit == "meters"


def test_race_goal_uses_recent_estimate(tmp_path):
    service, _, today, _ = _service(tmp_path)
    goal = service.create(
        GoalCreate(
            goal_type="race",
            sport="running",
            title="5K 25 分钟",
            target_unit="seconds",
            period="target_date",
            start_date=today,
            target_date=today + timedelta(weeks=12),
            race_distance="5k",
            target_time_seconds=1500,
        )
    )
    progress = service.get(goal.id).progress
    assert progress.current_value is not None
    assert progress.current_value > 0
    assert progress.target_value == 1500


class _StubQuery:
    def __init__(self, workouts: list[dict]):
        self.workouts = workouts

    def get_workouts(self, start_date: str, end_date: str) -> list[dict]:
        return self.workouts


def test_race_estimate_uses_exact_seconds(tmp_path):
    service, _, today, _ = _service(tmp_path)
    service.query = _StubQuery(
        [
            {
                "activity_type": "outdoor_running",
                "distance_m": 5012.0,
                "duration_minutes": 26,
                "avg_pace_sec_per_km": 323.0,
                "start_at": f"{today.isoformat()}T07:00:00+08:00",
                "end_at": f"{today.isoformat()}T07:26:59+08:00",
            }
        ]
    )
    goal = GoalCreate(
        goal_type="race",
        sport="running",
        title="5K 25 分钟",
        target_unit="seconds",
        period="target_date",
        start_date=today,
        target_date=today + timedelta(weeks=12),
        race_distance="5k",
        target_time_seconds=1500,
    )
    estimate = service._race_estimate(goal, as_of=today)
    assert estimate is not None
    # 1619 s over 5.012 km is 26:55; the old 26-minute field gave 25:56.
    assert estimate[0] == pytest.approx(1615.1, abs=0.1)
    assert estimate[1] == today


def test_body_trend_and_target_goals(tmp_path):
    service, _, today, _ = _service(tmp_path)
    trend = service.create(
        GoalCreate(
            goal_type="body_composition",
            title="体重趋势",
            mode="trend",
            target_unit="kg",
            period="rolling_28d",
            start_date=today,
        )
    )
    trend_progress = service.get(trend.id).progress
    assert trend_progress.status == "ok"
    assert trend_progress.current_value is not None

    target = service.create(
        GoalCreate(
            goal_type="body_composition",
            title="体重目标",
            mode="target",
            target_value=72.5,
            target_unit="kg",
            period="target_date",
            start_date=today,
            target_date=today + timedelta(weeks=8),
        )
    )
    target_progress = service.get(target.id).progress
    assert target_progress.current_value is not None
    assert target_progress.target_value == 72.5
    assert target_progress.data_quality["measurements"] >= 4


def test_body_target_rejects_extreme_rate(tmp_path):
    service, _, today, _ = _service(tmp_path)
    with pytest.raises(ValueError):
        service.create(
            GoalCreate(
                goal_type="body_composition",
                title="快速减重",
                mode="target",
                target_value=68.0,
                target_unit="kg",
                period="target_date",
                start_date=today,
                target_date=today + timedelta(weeks=4),
            )
        )


def test_deterministic_recommendations_are_explainable(tmp_path):
    service, builder, _, _ = _service(tmp_path)
    profile = builder.build(weeks=12)
    recommendations = service.recommend(profile, limit=3)
    assert recommendations
    assert recommendations[0].goal_type == "race"
    for item in recommendations:
        assert item.rationale
        assert item.evidence
        assert item.source == "rule_based"


def test_llm_recommendation_validation_filters_and_rejects_medical_language(tmp_path):
    service, _, today, _ = _service(tmp_path)
    valid = {
        "goal_type": "weekly_frequency",
        "title": "每周训练 3 次",
        "target_value": 3,
        "target_unit": "sessions_per_week",
        "period": "week",
        "start_date": today.isoformat(),
        "rationale": "基于近期频率保持可持续训练。",
        "evidence": ["observed_frequency"],
        "confidence": "medium",
        "extra_field": "ignored",
    }
    goal = service.validate_llm_recommendation(valid)
    assert goal.target_value == 3

    with pytest.raises(ValueError):
        service.validate_llm_recommendation(
            {
                "goal_type": "weekly_frequency",
                "title": "治疗方案",
                "target_value": 3,
                "target_unit": "sessions_per_week",
                "period": "week",
                "start_date": today.isoformat(),
                "rationale": "诊断后治疗",
            }
        )
