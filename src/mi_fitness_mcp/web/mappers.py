"""Mapping helpers between SQLite/query-service rows and API models."""

from __future__ import annotations

import calendar
import json
from contextlib import suppress
from datetime import date, timedelta
from typing import Any

from mi_fitness_mcp.web.schemas import (
    DailyActivity,
    GpsPoint,
    HeartRateSample,
    SleepSession,
    SummaryRange,
    Workout,
    WorkoutSample,
)


def activity_from_summary(
    summary: dict[str, Any] | None, date_str: str
) -> DailyActivity:
    """Build a zero-filled activity row when a day has no records."""
    item = summary or {}
    # Optional aggregates are 0-filled by QueryService. The project treats
    # missing optional values as unavailable, never as measured zero.
    return DailyActivity(
        date=date_str,
        steps=int(item.get("steps") or 0),
        distance_m=float(item.get("distance_m") or 0),
        active_kcal=float(item.get("active_kcal") or 0),
        total_kcal=item.get("total_kcal") or None,
        floors=item.get("floors") or None,
        active_minutes=item.get("active_minutes") or None,
    )


def _truthy(value: Any) -> bool:
    return value is True or str(value).lower() in {"1", "true", "yes"}


def sleep_from_payload(payload: dict[str, Any]) -> SleepSession:
    stages = payload.get("stages")
    if isinstance(stages, str):
        with suppress(json.JSONDecodeError):
            stages = json.loads(stages)
    if not isinstance(stages, list):
        stages = []
    source = payload.get("sleep_score_source")
    if source not in {"sleep_record", "daily_report"}:
        source = None
    return SleepSession(
        id=str(payload.get("sleep_id") or ""),
        start_at=payload["start_at"],
        end_at=payload["end_at"],
        duration_minutes=int(payload.get("duration_minutes") or 0),
        time_asleep_minutes=int(payload.get("time_asleep_minutes") or 0),
        time_awake_minutes=int(payload.get("time_awake_minutes") or 0),
        sleep_score=payload.get("sleep_score"),
        is_nap=_truthy(payload.get("is_nap")),
        stages=stages,
        score_source=source,
    )


def workout_from_payload(payload: dict[str, Any]) -> Workout:
    return Workout.model_validate(
        {**payload, "id": payload.get("workout_id") or ""}
    )


def sample_from_row(row: dict[str, Any]) -> WorkoutSample:
    return WorkoutSample.model_validate(row)


def gps_from_row(row: dict[str, Any]) -> GpsPoint:
    return GpsPoint.model_validate(row)


def heart_rate_from_row(row: dict[str, Any]) -> HeartRateSample:
    sample_type = row.get("sample_type") or "passive"
    if sample_type not in {"resting", "active", "passive", "workout"}:
        sample_type = "passive"
    return HeartRateSample(
        timestamp=row["timestamp"],
        bpm=int(row["bpm"]),
        sample_type=sample_type,
    )


def normalize_activity_type(value: str | None) -> str:
    """Keep the frontend's activity identities stable across raw provider names."""
    text = (value or "").lower()
    if "run" in text:
        return "running"
    if any(token in text for token in ("cycl", "bike", "riding")):
        return "cycling"
    if any(token in text for token in ("walk", "hike")):
        return "walking"
    if any(token in text for token in ("strength", "weight", "free_training")):
        return "strength"
    if "swim" in text:
        return "swimming"
    return "other"


def range_bounds(range_: SummaryRange, anchor: date) -> tuple[date, date]:
    if range_ == "day":
        return anchor, anchor
    if range_ == "week":
        start = anchor - timedelta(days=anchor.weekday())
        return start, start + timedelta(days=6)
    if range_ == "month":
        start = anchor.replace(day=1)
        last_day = calendar.monthrange(anchor.year, anchor.month)[1]
        return start, anchor.replace(day=last_day)
    return date(anchor.year, 1, 1), date(anchor.year, 12, 31)


def bucket_keys(range_: SummaryRange, start: date, end: date) -> list[str]:
    if range_ == "day":
        return [start.isoformat()]
    if range_ == "year":
        return [f"{start.year}-{month:02d}" for month in range(1, 13)]
    keys: list[str] = []
    cursor = start
    while cursor <= end:
        keys.append(cursor.isoformat())
        cursor += timedelta(days=1)
    return keys


def workout_bucket_key(workout: Workout, range_: SummaryRange) -> str:
    started = workout.start_at.date()
    if range_ == "year":
        return f"{started.year}-{started.month:02d}"
    return started.isoformat()


def weighted_avg_heart_rate(workouts: list[Workout]) -> int | None:
    total_minutes = sum(
        workout.duration_minutes
        for workout in workouts
        if workout.avg_heart_rate_bpm is not None
    )
    if not total_minutes:
        return None
    weighted = sum(
        workout.avg_heart_rate_bpm * workout.duration_minutes
        for workout in workouts
        if workout.avg_heart_rate_bpm is not None
    )
    return round(weighted / total_minutes)
