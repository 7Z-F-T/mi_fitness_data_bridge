"""Deterministic recent-training profile used by goals and plan generation."""

from __future__ import annotations

import re
import statistics
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from mi_fitness_mcp.coach.load import estimate_training_load
from mi_fitness_mcp.coach.models import (
    Best5kProxy,
    BodyContext,
    DataQualityInfo,
    LongestSession,
    ObservedFrequency,
    SleepContext,
    TrainingProfile,
    TrendContext,
    WeeklyBucket,
    WindowInfo,
)
from mi_fitness_mcp.services.query_service import QueryService
from mi_fitness_mcp.web.mappers import normalize_activity_type

DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
BANNED_PAYLOAD_KEYS = {
    "user_id",
    "userId",
    "device_id",
    "latitude",
    "longitude",
    "timestamp",
    "start_at",
    "end_at",
    "workout_id",
    "sleep_id",
    "notes",
    "api_key",
    "pass_token",
    "title",
    "rationale",
}
PAYLOAD_VERSION = "coach-payload-v1"


def _safe_zone(timezone: str):
    try:
        return ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError):
        # Windows installs without the optional tzdata package still need a
        # working clock for local-date bucketing.
        return UTC


def _parse_timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _workout_date(workout: dict[str, Any]) -> date | None:
    parsed = _parse_timestamp(workout.get("start_at"))
    return parsed.date() if parsed else None


def _number(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _goal_value(goal: Any, key: str, default: Any = None) -> Any:
    if isinstance(goal, dict):
        return goal.get(key, default)
    return getattr(goal, key, default)


def _round(value: float | None, digits: int = 1) -> float | None:
    return round(value, digits) if value is not None else None


class TrainingProfileBuilder:
    """Build a compact, deterministic view of the user's recent training."""

    def __init__(
        self,
        query: QueryService,
        *,
        timezone: str = "UTC",
        today: date | None = None,
    ) -> None:
        self.query = query
        self.timezone = _safe_zone(timezone)
        self.today = today or datetime.now(self.timezone).date()

    def build(self, weeks: int = 8, goal: Any | None = None) -> TrainingProfile:
        weeks = max(4, min(52, int(weeks)))
        current_week_start = self.today - timedelta(days=self.today.weekday())
        start_date = current_week_start - timedelta(weeks=weeks - 1)
        end_date = self.today
        workouts = self.query.get_workouts(start_date.isoformat(), end_date.isoformat())
        parsed_workouts = self._parse_workouts(workouts)
        all_weeks = self._weekly_buckets(parsed_workouts, start_date, current_week_start)
        observed_max_hr = self._observed_max_hr(parsed_workouts)
        resting_hr = self._resting_hr(start_date, end_date)
        self._apply_load(all_weeks, parsed_workouts, observed_max_hr, resting_hr)
        active_weeks_list = [bucket for bucket in all_weeks if bucket.sessions > 0]
        total_sessions = sum(bucket.sessions for bucket in active_weeks_list)
        active_weeks = len(active_weeks_list)
        weeks_without_records = sum(
            1
            for bucket in all_weeks
            if bucket.sessions == 0 and bucket.week_start < current_week_start
        )
        observed_frequency = ObservedFrequency(
            mean_per_week=round(total_sessions / active_weeks, 2) if active_weeks else 0,
            max_per_week=max((bucket.sessions for bucket in active_weeks_list), default=0),
            active_weeks=active_weeks,
            weeks_with_3plus=sum(1 for bucket in active_weeks_list if bucket.sessions >= 3),
        )
        longest_session = self._longest_session(parsed_workouts)
        best_5k_proxy = self._best_5k_proxy(parsed_workouts)
        trend = self._trend(active_weeks_list)
        sleep = self._sleep_context(start_date, end_date)
        body = self._body_context(start_date, end_date)
        data_quality = self._data_quality(
            parsed_workouts, active_weeks_list, active_weeks, sleep, body
        )
        return TrainingProfile(
            window=WindowInfo(
                start_date=start_date,
                end_date=end_date,
                weeks=weeks,
                weeks_without_records=weeks_without_records,
            ),
            weekly=active_weeks_list,
            observed_frequency=observed_frequency,
            longest_session=longest_session,
            best_5k_proxy=best_5k_proxy,
            trend=trend,
            sleep=sleep,
            body=body,
            data_quality=data_quality,
        )

    def build_llm_payload(
        self,
        profile: TrainingProfile,
        goal: Any | None = None,
        language: str = "zh-CN",
        include_body_context: bool = False,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": PAYLOAD_VERSION,
            "language": language,
            "window_weeks": profile.window.weeks,
            "weeks": [
                {
                    "week_offset": bucket.week_offset,
                    "sessions": bucket.sessions,
                    "duration_minutes": bucket.duration_minutes,
                    "distance_km": bucket.distance_km,
                    "by_sport": bucket.by_sport,
                    "longest_session_minutes": bucket.longest_session_minutes,
                    "hard_sessions": bucket.hard_sessions,
                    "load_proxy": bucket.load_proxy,
                }
                for bucket in profile.weekly
            ],
            "weeks_without_records": profile.window.weeks_without_records,
            "observed_frequency": profile.observed_frequency.model_dump(),
            "longest_session": profile.longest_session.model_dump(),
            "best_5k_proxy": {
                key: value
                for key, value in profile.best_5k_proxy.model_dump().items()
                if key != "source_workout_date"
            },
            "sleep": profile.sleep.model_dump(),
            "data_quality": profile.data_quality.model_dump(),
            "data_gaps": list(profile.data_quality.caveats),
        }
        if include_body_context or (
            goal is not None and _goal_value(goal, "goal_type") == "body_composition"
        ):
            payload["body"] = profile.body.model_dump() if profile.body else None
        if goal is not None:
            payload["goal"] = self._goal_payload(goal)
        assert_minimized(payload)
        return payload

    def _parse_workouts(self, workouts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        parsed: list[dict[str, Any]] = []
        for workout in workouts:
            workout_date = _workout_date(workout)
            if workout_date is None:
                continue
            duration = _number(workout.get("duration_minutes")) or 0
            distance_m = _number(workout.get("distance_m"))
            parsed.append(
                {
                    **workout,
                    "_date": workout_date,
                    "_sport": normalize_activity_type(workout.get("activity_type")),
                    "_duration": max(0.0, duration),
                    "_distance_m": distance_m,
                    "_calories": _number(workout.get("calories_kcal")) or 0,
                    "_avg_hr": _number(workout.get("avg_heart_rate_bpm")),
                    "_max_hr": _number(workout.get("max_heart_rate_bpm")),
                    "_train_effect": _number(workout.get("train_effect")),
                    "_anaerobic_effect": _number(workout.get("anaerobic_train_effect")),
                    "_training_load": _number(workout.get("training_load")),
                    "_pace": _number(workout.get("avg_pace_sec_per_km")),
                }
            )
        parsed.sort(key=lambda item: item["_date"])
        return parsed

    @staticmethod
    def _weekly_buckets(
        workouts: list[dict[str, Any]], start_date: date, current_week_start: date
    ) -> list[WeeklyBucket]:
        bucket_count = ((current_week_start - start_date).days // 7) + 1
        buckets: list[WeeklyBucket] = []
        for offset in range(bucket_count):
            week_start = start_date + timedelta(weeks=offset)
            week_end = week_start + timedelta(days=6)
            week_workouts = [
                item
                for item in workouts
                if week_start <= item["_date"] <= week_end
            ]
            by_sport: dict[str, int] = defaultdict(int)
            for item in week_workouts:
                by_sport[item["_sport"]] += 1
            buckets.append(
                WeeklyBucket(
                    week_offset=offset + 1,
                    week_start=week_start,
                    sessions=len(week_workouts),
                    duration_minutes=round(sum(item["_duration"] for item in week_workouts)),
                    distance_km=round(
                        sum(
                            item["_distance_m"]
                            for item in week_workouts
                            if item["_distance_m"] is not None
                        )
                        / 1000,
                        1,
                    ),
                    calories_kcal=round(sum(item["_calories"] for item in week_workouts)),
                    longest_session_minutes=round(
                        max((item["_duration"] for item in week_workouts), default=0)
                    ),
                    by_sport=dict(by_sport),
                )
            )
        return buckets

    @staticmethod
    def _observed_max_hr(workouts: list[dict[str, Any]]) -> float | None:
        values = [item["_max_hr"] for item in workouts if item["_max_hr"]]
        return max(values) if values else None

    def _resting_hr(self, start_date: date, end_date: date) -> float | None:
        try:
            samples = self.query.get_heart_rate_samples(
                start_date.isoformat(),
                end_date.isoformat(),
                sample_type="resting",
                limit=5000,
            )
        except Exception:
            return None
        values = [
            float(sample["bpm"])
            for sample in samples
            if sample.get("bpm") is not None and float(sample["bpm"]) >= 30
        ]
        return round(statistics.median(values), 1) if values else None

    def _apply_load(
        self,
        buckets: list[WeeklyBucket],
        workouts: list[dict[str, Any]],
        observed_max_hr: float | None,
        resting_hr: float | None,
    ) -> None:
        loads: dict[date, float] = defaultdict(float)
        hard: dict[date, int] = defaultdict(int)
        for item in workouts:
            estimate = estimate_training_load(
                duration_minutes=item["_duration"],
                avg_hr_bpm=item["_avg_hr"],
                observed_max_hr=observed_max_hr,
                resting_hr=resting_hr,
            )
            week_start = item["_date"] - timedelta(days=item["_date"].weekday())
            loads[week_start] += estimate.load
            is_hard = estimate.bucket == "high_intensity" or (
                item["_train_effect"] is not None and item["_train_effect"] >= 3.5
            ) or (
                item["_anaerobic_effect"] is not None
                and item["_anaerobic_effect"] >= 2.5
            )
            if is_hard:
                hard[week_start] += 1
        for bucket in buckets:
            bucket.load_proxy = round(loads.get(bucket.week_start, 0.0), 2)
            bucket.hard_sessions = hard.get(bucket.week_start, 0)

    @staticmethod
    def _longest_session(workouts: list[dict[str, Any]]) -> LongestSession:
        if not workouts:
            return LongestSession()
        longest = max(
            workouts,
            key=lambda item: (
                item["_duration"],
                item["_distance_m"] or 0,
            ),
        )
        return LongestSession(
            sport=longest["_sport"],
            distance_km=_round(
                (longest["_distance_m"] / 1000) if longest["_distance_m"] else None
            ),
            duration_minutes=round(longest["_duration"]),
        )

    @staticmethod
    def _best_5k_proxy(workouts: list[dict[str, Any]]) -> Best5kProxy:
        candidates: list[tuple[float, dict[str, Any]]] = []
        for item in workouts:
            if item["_sport"] != "running":
                continue
            distance_m = item["_distance_m"]
            if not distance_m or distance_m < 5000:
                continue
            if item["_duration"] > 0:
                estimate = item["_duration"] * 60 * 5000 / distance_m
            elif item["_pace"]:
                estimate = item["_pace"] * 5
            else:
                continue
            if 600 <= estimate <= 36_000:
                candidates.append((estimate, item))
        if not candidates:
            return Best5kProxy()
        estimate, source = min(candidates, key=lambda pair: pair[0])
        return Best5kProxy(
            estimated_5k_seconds=round(estimate),
            source_distance_km=_round((source["_distance_m"] or 0) / 1000),
            source_workout_date=source["_date"],
            method="average_pace_scaled_v1",
            confidence="low",
        )

    @staticmethod
    def _trend(buckets: list[WeeklyBucket]) -> TrendContext:
        current = buckets[-4:]
        prior = buckets[-8:-4]
        current_sessions = sum(bucket.sessions for bucket in current)
        prior_sessions = sum(bucket.sessions for bucket in prior)
        current_duration = sum(bucket.duration_minutes for bucket in current)
        prior_duration = sum(bucket.duration_minutes for bucket in prior)
        return TrendContext(
            current_4w_sessions=current_sessions,
            prior_4w_sessions=prior_sessions,
            sessions_change_ratio=(
                round(current_sessions / prior_sessions - 1, 3)
                if prior_sessions
                else None
            ),
            current_4w_duration_minutes=current_duration,
            prior_4w_duration_minutes=prior_duration,
            duration_change_ratio=(
                round(current_duration / prior_duration - 1, 3)
                if prior_duration
                else None
            ),
        )

    def _sleep_context(self, start_date: date, end_date: date) -> SleepContext:
        try:
            summary = self.query.get_sleep_summary(
                start_date.isoformat(), end_date.isoformat()
            )
        except Exception:
            return SleepContext()
        metrics = summary.get("metrics", {})
        nights = int(metrics.get("duration_minutes", {}).get("days_with_value") or 0)
        if nights < 3:
            return SleepContext(nights=nights)
        return SleepContext(
            nights=nights,
            mean_duration_minutes=metrics.get("duration_minutes", {}).get("mean"),
            mean_score=metrics.get("sleep_score", {}).get("mean"),
            coverage_ratio=summary.get("data_quality", {}).get("coverage_ratio"),
        )

    def _body_context(self, start_date: date, end_date: date) -> BodyContext | None:
        try:
            measurements = self.query.get_body_measurements(
                start_date.isoformat(), end_date.isoformat()
            )
        except Exception:
            return None
        dated: list[tuple[date, dict[str, Any]]] = []
        for measurement in measurements:
            parsed = _parse_timestamp(measurement.get("timestamp"))
            if parsed is not None and measurement.get("weight_kg") is not None:
                dated.append((parsed.date(), measurement))
        if len(dated) < 4:
            return None
        dated.sort(key=lambda pair: pair[0])
        span_days = (dated[-1][0] - dated[0][0]).days
        if span_days < 21:
            return None
        _, first = dated[0]
        _, last = dated[-1]
        first_weight = _number(first.get("weight_kg"))
        last_weight = _number(last.get("weight_kg"))
        first_body_fat = _number(first.get("body_fat_pct"))
        last_body_fat = _number(last.get("body_fat_pct"))
        return BodyContext(
            measurements=len(dated),
            latest_weight_kg=_round(last_weight),
            latest_body_fat_pct=_round(last_body_fat),
            weight_change_kg=(
                _round(last_weight - first_weight)
                if first_weight is not None and last_weight is not None
                else None
            ),
            body_fat_change_pct=(
                _round(last_body_fat - first_body_fat)
                if first_body_fat is not None and last_body_fat is not None
                else None
            ),
            span_days=span_days,
        )

    @staticmethod
    def _data_quality(
        workouts: list[dict[str, Any]],
        buckets: list[WeeklyBucket],
        active_weeks: int,
        sleep: SleepContext,
        body: BodyContext | None,
    ) -> DataQualityInfo:
        total_sessions = len(workouts)
        missing: list[str] = []
        caveats: list[str] = []
        if total_sessions and any(item["_distance_m"] is None for item in workouts):
            missing.append("workout_distance")
            caveats.append("部分运动缺少距离记录，周距离只合计已记录的距离。")
        if total_sessions and not any(item["_avg_hr"] for item in workouts):
            missing.append("workout_heart_rate")
            caveats.append("运动记录缺少心率，负荷只能按未校准代理估算。")
        if sleep.nights == 0:
            missing.append("sleep")
            caveats.append("睡眠数据不足 3 晚，恢复上下文置信度低。")
        if body is None:
            missing.append("body_composition")
            caveats.append("体重/体脂测量不足 4 次或跨度不足 21 天。")
        caveats.append("缺失的周不会被当作 0 训练；只统计有记录的周。")
        caveats.append("best_5k_proxy 是按近期跑步配速缩放的代理值，不是正式 5K PB。")
        if total_sessions < 3 or active_weeks < 2:
            status = "insufficient"
        elif total_sessions < 6 or active_weeks < 4:
            status = "partial"
        else:
            status = "ok"
        return DataQualityInfo(
            status=status,
            workout_days=len({item["_date"] for item in workouts}),
            coverage={"weeks_with_records": active_weeks},
            missing_metrics=missing,
            caveats=caveats,
        )

    def _goal_payload(self, goal: Any) -> dict[str, Any]:
        target_date = _goal_value(goal, "target_date")
        weeks_until_target = None
        if target_date is not None and isinstance(target_date, str):
            try:
                target_date = date.fromisoformat(target_date)
            except ValueError:
                target_date = None
        if target_date is not None:
            weeks_until_target = max(
                0, ((target_date - self.today).days + 6) // 7
            )
        return {
            "goal_type": _goal_value(goal, "goal_type"),
            "sport": _goal_value(goal, "sport", "any"),
            "target_value": _goal_value(goal, "target_value"),
            "target_unit": _goal_value(goal, "target_unit"),
            "weeks_until_target": weeks_until_target,
            "race_distance": _goal_value(goal, "race_distance"),
            "target_time_seconds": _goal_value(goal, "target_time_seconds"),
            "constraints": {
                "available_days": _goal_value(goal, "available_days"),
                "max_sessions_per_week": _goal_value(goal, "max_sessions_per_week"),
            },
        }


def assert_minimized(payload: Any, path: str = "") -> None:
    """Reject identifiers, exact dates, notes, and raw-location fields."""
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in BANNED_PAYLOAD_KEYS:
                raise ValueError(f"Coach payload contains banned key: {path}{key}")
            assert_minimized(value, f"{path}{key}.")
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            assert_minimized(value, f"{path}{index}.")
    elif isinstance(payload, str) and DATE_RE.search(payload):
        raise ValueError(f"Coach payload contains an exact date at {path.rstrip('.')}")
