"""Camel-case request/response schemas for the local coach API."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import ConfigDict, Field

from mi_fitness_mcp.web.schemas import ApiModel, _to_camel

GoalType = Literal[
    "weekly_frequency",
    "weekly_duration",
    "race",
    "distance",
    "body_composition",
]
SportType = Literal[
    "any", "running", "cycling", "walking", "strength", "swimming", "other"
]
GoalMode = Literal["target", "trend"]
TargetUnit = Literal[
    "sessions_per_week", "minutes_per_week", "meters", "kg", "percent", "seconds"
]
GoalPeriod = Literal["week", "month", "target_date", "rolling_28d"]
GoalStatus = Literal["active", "achieved", "archived"]
RaceDistance = Literal["5k", "10k", "half", "full"]


class CoachRequest(ApiModel):
    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
        extra="forbid",
    )


class CoachGoal(ApiModel):
    id: str
    goal_type: GoalType
    sport: SportType = "any"
    title: str
    mode: GoalMode = "target"
    target_value: float | None = None
    baseline_value: float | None = None
    target_unit: TargetUnit
    period: GoalPeriod = "week"
    start_date: date
    target_date: date | None = None
    race_distance: RaceDistance | None = None
    target_time_seconds: int | None = None
    available_days: int | None = None
    max_sessions_per_week: int | None = None
    notes: str | None = None
    status: GoalStatus = "active"
    achieved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class CoachProgress(ApiModel):
    goal_id: str
    status: Literal["ok", "behind", "achieved", "insufficient_data"]
    current_value: float | None = None
    target_value: float | None = None
    unit: TargetUnit
    period_start: date | None = None
    period_end: date | None = None
    days_elapsed: int | None = None
    days_remaining: int | None = None
    expected_value: float | None = None
    completion_ratio: float | None = None
    on_track: bool | None = None
    data_quality: dict[str, Any] = Field(default_factory=dict)
    evidence: list[str] = Field(default_factory=list)
    trend: list[dict[str, Any]] = Field(default_factory=list)


class CoachGoalWithProgress(ApiModel):
    goal: CoachGoal
    progress: CoachProgress


class CoachRecommendation(ApiModel):
    goal_type: GoalType
    sport: SportType = "any"
    title: str
    mode: GoalMode = "target"
    target_value: float | None = None
    baseline_value: float | None = None
    target_unit: TargetUnit
    period: GoalPeriod = "week"
    start_date: date
    target_date: date | None = None
    race_distance: RaceDistance | None = None
    target_time_seconds: int | None = None
    rationale: str
    evidence: list[str] = Field(default_factory=list)
    confidence: Literal["low", "medium", "high"] = "low"
    data_gaps: list[str] = Field(default_factory=list)
    source: Literal["rule_based", "ai_recommended"] = "rule_based"


class CoachPlan(ApiModel):
    id: str
    goal_id: str
    status: Literal["draft", "active", "superseded", "archived"]
    title: str
    start_date: date
    end_date: date
    weeks: int
    generated_by: Literal["llm", "fallback", "manual"]
    provider: str | None = None
    model: str | None = None
    prompt_version: str | None = None
    schema_version: str
    ai_run_id: str | None = None
    goal_snapshot: dict[str, Any] = Field(default_factory=dict)
    plan: dict[str, Any] = Field(default_factory=dict)
    validation_status: Literal["passed", "warnings", "failed"]
    validation_warnings: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    activated_at: datetime | None = None
    archived_at: datetime | None = None


class CoachStatus(ApiModel):
    enabled: bool
    language: str
    profile_weeks: int
    default_plan_weeks: int
    allow_deterministic_fallback: bool
    provider: str
    model: str
    base_url: str | None = None
    key_configured: bool
    anthropic_extra_available: bool = False
    remote_consent_at: str | None = None
    schema_initialized: bool
    goal_count: int
    plan_count: int
    latest_ai_run: dict[str, Any] | None = None


class CoachOverview(ApiModel):
    status: CoachStatus
    profile: dict[str, Any] = Field(default_factory=dict)
    goals: list[CoachGoalWithProgress] = Field(default_factory=list)
    plans: list[CoachPlan] = Field(default_factory=list)
    recommendations: list[CoachRecommendation] = Field(default_factory=list)
    data_quality: dict[str, Any] = Field(default_factory=dict)


class CoachGoalCreateRequest(CoachRequest):
    goal_type: GoalType
    sport: SportType = "any"
    title: str = Field(min_length=1, max_length=200)
    mode: GoalMode = "target"
    target_value: float | None = Field(default=None, gt=0, le=10_000_000)
    target_unit: TargetUnit | None = None
    period: GoalPeriod | None = None
    start_date: date | None = None
    target_date: date | None = None
    race_distance: RaceDistance | None = None
    target_time_seconds: int | None = Field(default=None, gt=0, le=36_000)
    available_days: int | None = Field(default=None, ge=2, le=7)
    max_sessions_per_week: int | None = Field(default=None, ge=1, le=7)
    notes: str | None = Field(default=None, max_length=2000)


class CoachGoalUpdateRequest(CoachRequest):
    sport: SportType | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)
    mode: GoalMode | None = None
    target_value: float | None = Field(default=None, gt=0, le=10_000_000)
    target_unit: TargetUnit | None = None
    period: GoalPeriod | None = None
    start_date: date | None = None
    target_date: date | None = None
    race_distance: RaceDistance | None = None
    target_time_seconds: int | None = Field(default=None, gt=0, le=36_000)
    available_days: int | None = Field(default=None, ge=2, le=7)
    max_sessions_per_week: int | None = Field(default=None, ge=1, le=7)
    notes: str | None = Field(default=None, max_length=2000)


class CoachRecommendRequest(CoachRequest):
    weeks: int | None = Field(default=None, ge=4, le=52)
    use_llm: bool = False
    consent: bool = False


class CoachGeneratePlanRequest(CoachRequest):
    goal_id: str = Field(min_length=1, max_length=200)
    weeks: int | None = Field(default=None, ge=4, le=24)
    days_per_week: int | None = Field(default=None, ge=2, le=6)
    session_minutes: int | None = Field(default=None, ge=20, le=180)
    use_llm: bool = False
    consent: bool = False
    activate: bool = False
