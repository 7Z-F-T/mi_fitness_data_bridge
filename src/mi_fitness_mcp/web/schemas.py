"""Pydantic response schemas for the local read-only web API.

Field names are snake_case in Python and camelCase in JSON via ``to_camel``,
matching the TypeScript contract in ``frontend/src/api/types.ts``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

SummaryRange = Literal["day", "week", "month", "year"]
SleepStageName = Literal["deep", "light", "rem", "awake"]
SleepScoreSource = Literal["sleep_record", "daily_report"]
HeartRateSampleType = Literal["resting", "active", "passive", "workout"]
SyncStatusValue = Literal[
    "ok", "partial", "error", "running", "cancelled", "never", "unknown"
]
SyncState = Literal["idle", "running", "completed", "error"]


def _to_camel(value: str) -> str:
    parts = value.split("_")
    return parts[0] + "".join(part.capitalize() for part in parts[1:])


class ApiModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class DailyActivity(ApiModel):
    date: str = Field(description="Local calendar date, YYYY-MM-DD")
    steps: int = Field(ge=0)
    distance_m: float = Field(ge=0)
    active_kcal: float = Field(ge=0)
    total_kcal: float | None = None
    floors: int | None = None
    active_minutes: int | None = None


class SleepStage(ApiModel):
    stage: SleepStageName
    minutes: int = Field(ge=0)


class SleepSession(ApiModel):
    id: str
    start_at: datetime
    end_at: datetime
    duration_minutes: int = Field(ge=0)
    time_asleep_minutes: int = Field(ge=0)
    time_awake_minutes: int = Field(ge=0)
    sleep_score: int | None = Field(None, ge=0, le=100)
    is_nap: bool = False
    stages: list[SleepStage] = Field(default_factory=list)
    score_source: SleepScoreSource | None = None


class Workout(ApiModel):
    id: str
    workout_id: str
    activity_type: str
    start_at: datetime
    end_at: datetime
    duration_minutes: int = Field(ge=0)
    distance_m: float | None = None
    calories_kcal: float | None = None
    avg_heart_rate_bpm: int | None = None
    max_heart_rate_bpm: int | None = None
    min_heart_rate_bpm: int | None = None
    avg_pace_sec_per_km: float | None = None
    max_pace_sec_per_km: float | None = None
    min_pace_sec_per_km: float | None = None
    avg_speed_mps: float | None = None
    total_steps: int | None = None
    avg_cadence: int | None = None
    max_cadence: int | None = None
    avg_stride: int | None = None
    avg_height_m: float | None = None
    max_height_m: float | None = None
    min_height_m: float | None = None
    rise_height_m: float | None = None
    fall_height_m: float | None = None
    total_climbing_m: float | None = None
    valid_duration_seconds: int | None = None
    vo2max: int | None = None
    train_effect: float | None = None
    anaerobic_train_effect: float | None = None
    training_load: int | None = None
    recovery_time: int | None = None
    avg_spo2_pct: int | None = None


class WorkoutSample(ApiModel):
    offset_seconds: int
    timestamp: datetime
    heart_rate_bpm: int | None = None
    cadence: int | None = None
    pace_sec_per_km: float | None = None
    speed_mps: float | None = None
    altitude_m: float | None = None
    distance_m: float | None = None


class GpsPoint(ApiModel):
    offset_seconds: int
    timestamp: datetime
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    accuracy: float | None = None
    speed_mps: float | None = None
    gps_source: int | None = None
    altitude_m: float | None = None
    hdop: float | None = None


class WorkoutDetail(ApiModel):
    workout: Workout
    samples: list[WorkoutSample] = Field(default_factory=list)
    gps: list[GpsPoint] = Field(default_factory=list)


class HeartRateSample(ApiModel):
    timestamp: datetime
    bpm: int = Field(ge=0)
    sample_type: HeartRateSampleType = "passive"


class HomeSummary(ApiModel):
    date: str
    activity: DailyActivity
    sleep: SleepSession | None = None
    resting_heart_rate: int | None = None
    latest_heart_rate: int | None = None
    hr_samples: list[HeartRateSample] = Field(default_factory=list)
    weekly_activity: list[DailyActivity] = Field(default_factory=list)
    recent_workouts: list[Workout] = Field(default_factory=list)


class WorkoutSummaryBucket(ApiModel):
    key: str
    workouts: int = 0
    duration_minutes: int = 0
    distance_m: float = 0
    calories_kcal: float = 0


class WorkoutTypeSummary(ApiModel):
    type: str
    workouts: int = 0
    duration_minutes: int = 0
    distance_m: float = 0


class WorkoutTotals(ApiModel):
    workouts: int = 0
    duration_minutes: int = 0
    distance_m: float = 0
    calories_kcal: float = 0
    avg_heart_rate_bpm: int | None = None


class WorkoutSummary(ApiModel):
    range: SummaryRange
    anchor: str
    buckets: list[WorkoutSummaryBucket] = Field(default_factory=list)
    totals: WorkoutTotals = Field(default_factory=WorkoutTotals)
    by_type: list[WorkoutTypeSummary] = Field(default_factory=list)
    workouts: list[Workout] = Field(default_factory=list)


class Goal(ApiModel):
    id: str
    title: str
    target: float
    current: float
    unit: str
    period: str


class HealthResponse(ApiModel):
    status: Literal["ok"] = "ok"
    database: Literal["ok"] = "ok"


class SyncStatusItem(ApiModel):
    data_type: str
    last_status: SyncStatusValue
    last_synced_at: datetime | None = None
    records_added: int = 0
    records_updated: int = 0
    records_skipped: int = 0
    error_code: str | None = None
    source: str = "never"
    incremental: bool = True
    requested_start_date: str | None = None
    requested_end_date: str | None = None


class SyncStatus(ApiModel):
    active: bool = False
    sync_id: str | None = None
    state: SyncState = "idle"
    last_error_code: str | None = None
    last_error_message: str | None = None
    items: list[SyncStatusItem] = Field(default_factory=list)


class SyncRequest(BaseModel):
    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
        extra="forbid",
    )

    data_types: list[str] | None = None
    full: bool = False


class SyncStartResponse(ApiModel):
    sync_id: str
    status: Literal["accepted"] = "accepted"
    message: str = "同步已开始，请轮询同步状态。"


class ApiErrorDetail(ApiModel):
    code: str
    message: str
    request_id: str | None = None
    details: Any | None = None


class ApiErrorResponse(ApiModel):
    error: ApiErrorDetail
