"""Pydantic models for the optional coach extension."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

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
PlanStatus = Literal["draft", "active", "superseded", "archived"]
PlanGeneratedBy = Literal["llm", "fallback", "manual"]
PlanValidationStatus = Literal["passed", "warnings", "failed"]
SessionType = Literal[
    "easy", "long", "tempo", "interval", "recovery", "strength", "mobility", "rest", "race"
]
ProgressStatus = Literal["ok", "behind", "achieved", "insufficient_data"]
DataQualityStatus = Literal["ok", "partial", "insufficient"]
RecommendationSource = Literal["rule_based", "ai_recommended"]


class CoachModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Goal(CoachModel):
    id: str
    user_id: str = "local"
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
    available_days: int | None = Field(default=None, ge=2, le=7)
    max_sessions_per_week: int | None = Field(default=None, ge=1, le=7)
    notes: str | None = None
    status: GoalStatus = "active"
    achieved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class GoalCreate(CoachModel):
    goal_type: GoalType
    sport: SportType = "any"
    title: str = Field(min_length=1, max_length=200)
    mode: GoalMode = "target"
    target_value: float | None = Field(default=None, gt=0, le=10_000_000)
    baseline_value: float | None = Field(default=None, gt=0, le=10_000_000)
    target_unit: TargetUnit
    period: GoalPeriod = "week"
    start_date: date
    target_date: date | None = None
    race_distance: RaceDistance | None = None
    target_time_seconds: int | None = Field(default=None, gt=0, le=36_000)
    available_days: int | None = Field(default=None, ge=2, le=7)
    max_sessions_per_week: int | None = Field(default=None, ge=1, le=7)
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _validate_goal_shape(self) -> GoalCreate:
        if self.goal_type == "weekly_frequency":
            if self.mode != "target" or self.target_unit != "sessions_per_week":
                raise ValueError("weekly_frequency requires target/sessions_per_week")
            if self.period != "week":
                raise ValueError("weekly_frequency requires period='week'")
            if self.target_value is None or not 1 <= self.target_value <= 14:
                raise ValueError("weekly_frequency target must be between 1 and 14")
        elif self.goal_type == "weekly_duration":
            if self.mode != "target" or self.target_unit != "minutes_per_week":
                raise ValueError("weekly_duration requires target/minutes_per_week")
            if self.period != "week":
                raise ValueError("weekly_duration requires period='week'")
            if self.target_value is None or not 30 <= self.target_value <= 1440:
                raise ValueError("weekly_duration target must be 30-1440 minutes")
        elif self.goal_type == "race":
            if self.sport != "running":
                raise ValueError("race goals currently support running only")
            if self.target_unit != "seconds" or self.period != "target_date":
                raise ValueError("race requires seconds/target_date")
            if self.target_date is None or self.race_distance is None:
                raise ValueError("race requires target_date and race_distance")
            if self.target_time_seconds is None:
                raise ValueError("race requires target_time_seconds")
            self.target_value = float(self.target_time_seconds)
        elif self.goal_type == "distance":
            if self.target_unit != "meters":
                raise ValueError("distance requires target_unit='meters'")
            if self.target_value is None:
                raise ValueError("distance requires target_value")
            if self.period not in {"week", "month", "target_date"}:
                raise ValueError("distance period must be week, month, or target_date")
            if self.period == "target_date" and self.target_date is None:
                raise ValueError("distance target_date period requires target_date")
        elif self.goal_type == "body_composition":
            if self.target_unit not in {"kg", "percent"}:
                raise ValueError("body_composition requires kg or percent")
            if self.period not in {"target_date", "rolling_28d"}:
                raise ValueError("body_composition period must be target_date or rolling_28d")
            if self.mode == "trend":
                if self.target_value is not None:
                    raise ValueError("body_composition trend mode must not set target_value")
            else:
                if self.period != "target_date":
                    raise ValueError("body_composition target mode requires target_date period")
                if self.target_value is None:
                    raise ValueError("body_composition target mode requires target_value")
                if self.target_unit == "kg" and not 20 <= self.target_value <= 300:
                    raise ValueError("body weight target must be 20-300 kg")
                if self.target_unit == "percent" and not 3 <= self.target_value <= 60:
                    raise ValueError("body fat target must be 3-60 percent")
                if self.target_date is None:
                    raise ValueError("body_composition target_date requires target_date")
        return self


class GoalUpdate(CoachModel):
    goal_type: GoalType | None = None
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


class GoalProgress(CoachModel):
    goal_id: str
    status: ProgressStatus
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


class GoalWithProgress(CoachModel):
    goal: Goal
    progress: GoalProgress


class GoalRecommendation(CoachModel):
    goal_type: GoalType
    sport: SportType = "any"
    title: str
    mode: GoalMode = "target"
    target_value: float | None = None
    target_unit: TargetUnit
    period: GoalPeriod = "week"
    start_date: date
    target_date: date | None = None
    race_distance: RaceDistance | None = None
    target_time_seconds: int | None = None
    baseline_value: float | None = None
    rationale: str
    evidence: list[str] = Field(default_factory=list)
    confidence: Literal["low", "medium", "high"] = "low"
    data_gaps: list[str] = Field(default_factory=list)
    source: RecommendationSource = "rule_based"


class WindowInfo(CoachModel):
    start_date: date
    end_date: date
    weeks: int
    weeks_without_records: int = 0


class WeeklyBucket(CoachModel):
    week_offset: int
    week_start: date
    sessions: int = 0
    duration_minutes: int = 0
    distance_km: float = 0
    calories_kcal: float = 0
    longest_session_minutes: int = 0
    hard_sessions: int = 0
    load_proxy: float = 0
    by_sport: dict[str, int] = Field(default_factory=dict)


class ObservedFrequency(CoachModel):
    mean_per_week: float = 0
    max_per_week: int = 0
    active_weeks: int = 0
    weeks_with_3plus: int = 0


class LongestSession(CoachModel):
    sport: str | None = None
    distance_km: float | None = None
    duration_minutes: int | None = None


class Best5kProxy(CoachModel):
    estimated_5k_seconds: int | None = None
    source_distance_km: float | None = None
    source_workout_date: date | None = None
    method: str = "average_pace_scaled_v1"
    confidence: Literal["low", "medium", "high"] = "low"


class SleepContext(CoachModel):
    nights: int = 0
    mean_duration_minutes: float | None = None
    mean_score: float | None = None
    coverage_ratio: float | None = None


class BodyContext(CoachModel):
    measurements: int = 0
    latest_weight_kg: float | None = None
    latest_body_fat_pct: float | None = None
    weight_change_kg: float | None = None
    body_fat_change_pct: float | None = None
    span_days: int | None = None


class TrendContext(CoachModel):
    current_4w_sessions: int = 0
    prior_4w_sessions: int = 0
    sessions_change_ratio: float | None = None
    current_4w_duration_minutes: int = 0
    prior_4w_duration_minutes: int = 0
    duration_change_ratio: float | None = None


class DataQualityInfo(CoachModel):
    status: DataQualityStatus = "insufficient"
    workout_days: int = 0
    coverage: dict[str, Any] = Field(default_factory=dict)
    missing_metrics: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)


class TrainingProfile(CoachModel):
    window: WindowInfo
    weekly: list[WeeklyBucket] = Field(default_factory=list)
    observed_frequency: ObservedFrequency = Field(default_factory=ObservedFrequency)
    longest_session: LongestSession = Field(default_factory=LongestSession)
    best_5k_proxy: Best5kProxy = Field(default_factory=Best5kProxy)
    trend: TrendContext = Field(default_factory=TrendContext)
    sleep: SleepContext = Field(default_factory=SleepContext)
    body: BodyContext | None = None
    data_quality: DataQualityInfo = Field(default_factory=DataQualityInfo)
    method_version: str = "coach-profile-v1"


class PlanSession(CoachModel):
    date: date
    sport: str = "running"
    session_type: SessionType = "easy"
    duration_minutes: int = Field(ge=0, le=600)
    distance_m: float | None = Field(default=None, ge=0)
    intensity: str = ""
    description: str = ""
    purpose: str = ""
    optional: bool = False


class PlanWeek(CoachModel):
    week_index: int = Field(ge=1)
    start_date: date
    focus: str = ""
    is_recovery_week: bool = False
    target_duration_minutes: int | None = Field(default=None, ge=0)
    target_distance_m: float | None = Field(default=None, ge=0)
    sessions: list[PlanSession] = Field(default_factory=list)


class PlanSafety(CoachModel):
    stop_rules: list[str] = Field(default_factory=list)
    disclaimer: str = ""


class TrainingPlanContent(CoachModel):
    title: str
    summary: str = ""
    weeks: list[PlanWeek] = Field(default_factory=list)
    progression_rules: list[str] = Field(default_factory=list)
    weekly_habits: list[str] = Field(default_factory=list)
    safety: PlanSafety = Field(default_factory=PlanSafety)
    assumptions: list[str] = Field(default_factory=list)
    data_gaps: list[str] = Field(default_factory=list)


class TrainingPlan(CoachModel):
    id: str
    user_id: str = "local"
    goal_id: str
    status: PlanStatus = "draft"
    title: str
    start_date: date
    end_date: date
    weeks: int
    generated_by: PlanGeneratedBy
    provider: str | None = None
    model: str | None = None
    prompt_version: str | None = None
    schema_version: str
    ai_run_id: str | None = None
    goal_snapshot: dict[str, Any] = Field(default_factory=dict)
    plan: TrainingPlanContent
    validation_status: PlanValidationStatus = "passed"
    validation_warnings: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    activated_at: datetime | None = None
    archived_at: datetime | None = None


class PlanValidationIssue(CoachModel):
    code: str
    message: str
    severity: Literal["error", "warning"] = "error"
    week_index: int | None = None


class PlanValidationResult(CoachModel):
    status: PlanValidationStatus
    issues: list[PlanValidationIssue] = Field(default_factory=list)

    @property
    def errors(self) -> list[PlanValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[PlanValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "warning"]


class PlanGenerationConstraints(CoachModel):
    weeks: int = Field(default=8, ge=4, le=24)
    days_per_week: int = Field(default=3, ge=2, le=6)
    session_minutes: int = Field(default=60, ge=20, le=180)
    start_date: date | None = None
    use_llm: bool = False
    activate: bool = False
