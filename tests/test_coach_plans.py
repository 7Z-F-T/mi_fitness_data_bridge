"""Deterministic plan generation and safety validation."""

from __future__ import annotations

from datetime import timedelta

from mi_fitness_mcp.coach.models import GoalCreate, PlanGenerationConstraints
from mi_fitness_mcp.coach.service import CoachService
from mi_fitness_mcp.coach.templates import build_template_plan
from mi_fitness_mcp.coach.validation import PlanValidator
from mi_fitness_mcp.config import CoachConfig
from mi_fitness_mcp.services.query_service import QueryService
from mi_fitness_mcp.storage import Database
from mi_fitness_mcp.storage.coach import CoachStore
from tests.coach_fixtures import seed_coach_db


def _service(tmp_path):
    db_path, user_id, today = seed_coach_db(tmp_path)
    db = Database(db_path)
    store = CoachStore(db)
    service = CoachService(
        store,
        QueryService(db, user_id),
        CoachConfig(enabled=False, default_plan_weeks=8),
        timezone="UTC",
        today=today,
    )
    return service, today


def _goal(service, data):
    return service.create_goal(data)


def test_template_plans_are_valid_for_each_goal_type(tmp_path):
    service, today = _service(tmp_path)
    goals = [
        GoalCreate(
            goal_type="weekly_frequency",
            title="每周 3 次",
            target_value=3,
            target_unit="sessions_per_week",
            period="week",
            start_date=today,
        ),
        GoalCreate(
            goal_type="weekly_duration",
            title="每周 180 分钟",
            target_value=180,
            target_unit="minutes_per_week",
            period="week",
            start_date=today,
        ),
        GoalCreate(
            goal_type="distance",
            sport="running",
            title="每周 15 公里",
            target_value=15000,
            target_unit="meters",
            period="week",
            start_date=today,
        ),
        GoalCreate(
            goal_type="body_composition",
            title="体重趋势",
            mode="trend",
            target_unit="kg",
            period="rolling_28d",
            start_date=today,
        ),
        GoalCreate(
            goal_type="race",
            sport="running",
            title="5K",
            target_unit="seconds",
            period="target_date",
            start_date=today,
            target_date=today + timedelta(weeks=8),
            race_distance="5k",
            target_time_seconds=1500,
        ),
    ]
    for data in goals:
        goal = _goal(service, data)
        plan = service.generate_plan(goal.id, activate=True)
        assert plan.weeks >= 4
        assert plan.status == "active"
        assert plan.validation_status == "passed"
        assert plan.plan.safety.stop_rules
        assert plan.plan.safety.disclaimer
        assert plan.plan.weeks
        assert all(week.sessions for week in plan.plan.weeks)


def test_activation_supersedes_previous_plan(tmp_path):
    service, today = _service(tmp_path)
    goal = _goal(
        service,
        GoalCreate(
            goal_type="weekly_frequency",
            title="每周 3 次",
            target_value=3,
            target_unit="sessions_per_week",
            period="week",
            start_date=today,
        ),
    )
    first = service.generate_plan(goal.id, activate=True)
    second = service.generate_plan(goal.id, activate=True)
    assert first.id != second.id
    active = service.list_plans(goal_id=goal.id, status="active")
    assert len(active) == 1
    assert active[0]["id"] == second.id


def test_validator_rejects_unsafe_plans(tmp_path):
    service, today = _service(tmp_path)
    goal = _goal(
        service,
        GoalCreate(
            goal_type="weekly_frequency",
            title="每周 3 次",
            target_value=3,
            target_unit="sessions_per_week",
            period="week",
            start_date=today,
        ),
    )
    goal_model = service.get_goal(goal.id).goal
    profile = service.profile()
    constraints = PlanGenerationConstraints(
        weeks=8, days_per_week=3, session_minutes=60, start_date=today
    )
    valid = build_template_plan(goal_model, profile, constraints, today=today)
    validator = PlanValidator()
    assert validator.validate(valid, goal_model, profile).status == "passed"

    no_safety = valid.model_copy(
        update={"safety": valid.safety.model_copy(update={"stop_rules": [], "disclaimer": ""})}
    )
    result = validator.validate(no_safety, goal_model, profile)
    assert any(issue.code == "SAFETY_TEXT_MISSING" for issue in result.issues)

    bad_progression = valid.model_copy(deep=True)
    week_two = bad_progression.weeks[1]
    week_two.is_recovery_week = False
    week_two.sessions[0].duration_minutes = bad_progression.weeks[0].sessions[0].duration_minutes * 2
    result = validator.validate(bad_progression, goal_model, profile)
    assert any(issue.code == "WEEKLY_PROGRESSION_EXCEEDED" for issue in result.issues)


def test_validator_rejects_no_rest_day_and_consecutive_hard_days(tmp_path):
    service, today = _service(tmp_path)
    goal = _goal(
        service,
        GoalCreate(
            goal_type="weekly_frequency",
            title="每周 3 次",
            target_value=3,
            target_unit="sessions_per_week",
            period="week",
            start_date=today,
        ),
    )
    goal_model = service.get_goal(goal.id).goal
    profile = service.profile()
    constraints = PlanGenerationConstraints(
        weeks=4, days_per_week=3, session_minutes=60, start_date=today
    )
    plan = build_template_plan(goal_model, profile, constraints, today=today)
    week = plan.weeks[0]
    template_session = week.sessions[0]
    week.sessions = [
        template_session.model_copy(
            update={
                "date": week.start_date + timedelta(days=index),
                "session_type": "interval",
            }
        )
        for index in range(7)
    ]
    result = PlanValidator().validate(plan, goal_model, profile)
    assert any(issue.code == "NO_REST_DAY" for issue in result.issues)
    assert any(issue.code == "CONSECUTIVE_HARD_DAYS" for issue in result.issues)


def test_validator_rejects_body_diet_language_and_missing_race_day(tmp_path):
    service, today = _service(tmp_path)
    body_goal = _goal(
        service,
        GoalCreate(
            goal_type="body_composition",
            title="体重趋势",
            mode="trend",
            target_unit="kg",
            period="rolling_28d",
            start_date=today,
        ),
    )
    body_model = service.get_goal(body_goal.id).goal
    profile = service.profile()
    constraints = PlanGenerationConstraints(
        weeks=4, days_per_week=3, session_minutes=60, start_date=today
    )
    body_plan = build_template_plan(body_model, profile, constraints, today=today)
    body_plan.summary = "制造热量缺口"
    result = PlanValidator().validate(body_plan, body_model, profile)
    assert any(issue.code == "BODY_COMPOSITION_DIET_LANGUAGE" for issue in result.issues)

    race_goal = _goal(
        service,
        GoalCreate(
            goal_type="race",
            sport="running",
            title="5K",
            target_unit="seconds",
            period="target_date",
            start_date=today,
            target_date=today + timedelta(weeks=8),
            race_distance="5k",
            target_time_seconds=1500,
        ),
    )
    race_model = service.get_goal(race_goal.id).goal
    race_plan = build_template_plan(race_model, profile, constraints, today=today)
    for week in race_plan.weeks:
        week.sessions = [
            session for session in week.sessions if session.session_type != "race"
        ]
    result = PlanValidator().validate(race_plan, race_model, profile)
    assert any(issue.code == "RACE_DAY_MISSING" for issue in result.issues)
