"""JSON schemas and materialization for model-generated drafts.

The model never receives or returns exact calendar dates.  It works with week
offsets and day-of-week indices; the server materializes real dates locally.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Literal

from pydantic import Field

from mi_fitness_mcp.coach.models import (
    CoachModel,
    GoalMode,
    GoalPeriod,
    GoalType,
    PlanSafety,
    PlanSession,
    PlanWeek,
    RaceDistance,
    SessionType,
    SportType,
    TargetUnit,
    TrainingPlanContent,
)


class GoalRecommendationDraft(CoachModel):
    goal_type: GoalType
    sport: SportType = "any"
    title: str = Field(min_length=1, max_length=200)
    mode: GoalMode = "target"
    target_value: float | None = Field(default=None, gt=0, le=10_000_000)
    target_unit: TargetUnit
    period: GoalPeriod = "week"
    race_distance: RaceDistance | None = None
    target_time_seconds: int | None = Field(default=None, gt=0, le=36_000)
    weeks_until_target: int | None = Field(default=None, ge=2, le=104)
    rationale: str = Field(min_length=1, max_length=2000)
    evidence: list[str] = Field(default_factory=list)
    confidence: Literal["low", "medium", "high"] = "low"
    data_gaps: list[str] = Field(default_factory=list)


class GoalRecommendationBatch(CoachModel):
    recommendations: list[GoalRecommendationDraft] = Field(default_factory=list)
    overall_assessment: str = ""
    data_gaps: list[str] = Field(default_factory=list)
    disclaimer: str = ""


class PlanSessionDraft(CoachModel):
    day_of_week: int = Field(ge=0, le=6, description="0=Monday, 6=Sunday")
    sport: str = "running"
    session_type: SessionType = "easy"
    duration_minutes: int = Field(ge=10, le=600)
    distance_km: float | None = Field(default=None, ge=0, le=100)
    intensity: str = ""
    description: str = ""
    purpose: str = ""
    optional: bool = False


class PlanWeekDraft(CoachModel):
    week_index: int = Field(ge=1, le=52)
    focus: str = ""
    is_recovery_week: bool = False
    sessions: list[PlanSessionDraft] = Field(default_factory=list)


class TrainingPlanDraft(CoachModel):
    title: str = Field(min_length=1, max_length=200)
    summary: str = ""
    weeks: list[PlanWeekDraft] = Field(default_factory=list)
    progression_rules: list[str] = Field(default_factory=list)
    weekly_habits: list[str] = Field(default_factory=list)
    safety: PlanSafety = Field(default_factory=PlanSafety)
    assumptions: list[str] = Field(default_factory=list)
    data_gaps: list[str] = Field(default_factory=list)


def materialize_plan(draft: TrainingPlanDraft, start_date: date) -> TrainingPlanContent:
    """Convert week/day offsets into a date-bearing local plan."""
    weeks: list[PlanWeek] = []
    for week in draft.weeks:
        week_start = start_date + timedelta(weeks=week.week_index - 1)
        sessions = [
            PlanSession(
                date=week_start + timedelta(days=session.day_of_week),
                sport=session.sport,
                session_type=session.session_type,
                duration_minutes=session.duration_minutes,
                distance_m=(
                    round(session.distance_km * 1000, 1)
                    if session.distance_km is not None
                    else None
                ),
                intensity=session.intensity,
                description=session.description,
                purpose=session.purpose,
                optional=session.optional,
            )
            for session in week.sessions
        ]
        weeks.append(
            PlanWeek(
                week_index=week.week_index,
                start_date=week_start,
                focus=week.focus,
                is_recovery_week=week.is_recovery_week,
                target_duration_minutes=sum(
                    session.duration_minutes
                    for session in sessions
                    if session.session_type != "rest"
                ),
                target_distance_m=sum(
                    session.distance_m or 0
                    for session in sessions
                    if session.session_type != "rest"
                )
                or None,
                sessions=sessions,
            )
        )
    return TrainingPlanContent(
        title=draft.title,
        summary=draft.summary,
        weeks=weeks,
        progression_rules=draft.progression_rules,
        weekly_habits=draft.weekly_habits,
        safety=draft.safety,
        assumptions=draft.assumptions,
        data_gaps=draft.data_gaps,
    )


def to_provider_schema(model: type[CoachModel]) -> dict[str, Any]:
    return model.model_json_schema()
