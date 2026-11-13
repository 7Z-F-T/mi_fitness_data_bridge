"""Goal persistence, progress calculation, and explainable recommendations."""

from __future__ import annotations

import statistics
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from mi_fitness_mcp.coach.models import (
    Goal,
    GoalCreate,
    GoalProgress,
    GoalRecommendation,
    GoalUpdate,
    GoalWithProgress,
    TrainingProfile,
)
from mi_fitness_mcp.coach.profile import workout_duration_seconds
from mi_fitness_mcp.services.query_service import QueryService
from mi_fitness_mcp.storage.coach import CoachStore
from mi_fitness_mcp.web.mappers import normalize_activity_type

RACE_DISTANCES_M = {"5k": 5000.0, "10k": 10000.0, "half": 21097.5, "full": 42195.0}
RACE_TIME_BOUNDS = {
    "5k": (720, 5400),
    "10k": (1500, 10800),
    "half": (3600, 18000),
    "full": (7200, 36000),
}
MEDICAL_CLAIM_TERMS = (
    "诊断",
    "治疗",
    "药物",
    "处方",
    "病因",
    "治愈",
    "diagnose",
    "diagnosis",
    "treatment",
    "medication",
    "prescribe",
    "cure",
)
EXTREME_DIET_TERMS = (
    "热量缺口",
    "断食",
    "节食",
    "calorie deficit",
    "fasting",
    "starvation",
)


def _safe_zone(timezone: str):
    try:
        return ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError):
        return UTC


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _number(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _format_seconds(value: float | None) -> str:
    if value is None:
        return "-"
    seconds = max(0, int(round(value)))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


class GoalService:
    """Create goals, calculate progress, and produce deterministic suggestions."""

    def __init__(
        self,
        store: CoachStore,
        query: QueryService | None,
        timezone: str = "UTC",
        *,
        today: date | None = None,
        language: str = "zh-CN",
    ) -> None:
        self.store = store
        self.query = query
        self.timezone = _safe_zone(timezone)
        self.today = today or datetime.now(self.timezone).date()
        self.language = language

    # ----------------------------------------------------------------- CRUD

    def create(self, data: GoalCreate | dict[str, Any]) -> Goal:
        goal = data if isinstance(data, GoalCreate) else GoalCreate.model_validate(data)
        self._validate_dates(goal)
        self._validate_race_time(goal)
        baseline = goal.baseline_value
        if goal.goal_type == "body_composition":
            baseline = self._baseline_for_body_goal(goal)
        elif goal.goal_type == "race" and baseline is None:
            estimate = self._race_estimate(goal)
            baseline = estimate[0] if estimate else None
        elif (
            goal.goal_type in {"weekly_frequency", "weekly_duration", "distance"}
            and baseline is None
        ):
            baseline = self._recent_metric_baseline(goal)
        payload = goal.model_dump()
        payload["baseline_value"] = baseline
        row = self.store.insert_goal(payload)
        return Goal.model_validate(row)

    def update(self, goal_id: str, changes: GoalUpdate | dict[str, Any]) -> Goal:
        current_row = self.store.get_goal(goal_id)
        if current_row is None:
            raise KeyError(f"Goal not found: {goal_id}")
        current = Goal.model_validate(current_row)
        change_data = (
            changes.model_dump(exclude_unset=True)
            if isinstance(changes, GoalUpdate)
            else dict(changes)
        )
        merged = current.model_dump()
        merged.update({key: value for key, value in change_data.items() if value is not None})
        merged["start_date"] = _parse_date(merged["start_date"]) or self.today
        merged["target_date"] = _parse_date(merged.get("target_date"))
        validated = GoalCreate.model_validate(
            {key: merged[key] for key in GoalCreate.model_fields}
        )
        self._validate_dates(validated)
        self._validate_race_time(validated)
        if validated.goal_type == "body_composition":
            baseline = self._baseline_for_body_goal(validated)
        else:
            baseline = validated.baseline_value
        update_payload = validated.model_dump()
        update_payload["baseline_value"] = baseline
        updated = self.store.update_goal(goal_id, update_payload)
        if updated is None:
            raise KeyError(f"Goal not found: {goal_id}")
        return Goal.model_validate(updated)

    def archive(self, goal_id: str) -> Goal:
        updated = self.store.update_goal(goal_id, {"status": "archived"})
        if updated is None:
            raise KeyError(f"Goal not found: {goal_id}")
        return Goal.model_validate(updated)

    def get(self, goal_id: str) -> GoalWithProgress:
        row = self.store.get_goal(goal_id)
        if row is None:
            raise KeyError(f"Goal not found: {goal_id}")
        goal = Goal.model_validate(row)
        return GoalWithProgress(goal=goal, progress=self.progress(goal))

    def list(self, status: str = "active") -> list[GoalWithProgress]:
        result: list[GoalWithProgress] = []
        for row in self.store.list_goals(status=status):
            goal = Goal.model_validate(row)
            result.append(GoalWithProgress(goal=goal, progress=self.progress(goal)))
        return result

    def evaluate_and_persist(self, goal_id: str) -> GoalWithProgress:
        # Progress is derived from immutable workout/body records.  Goal status
        # changes only through explicit user writes, never on a read.
        return self.get(goal_id)

    # ------------------------------------------------------------- progress

    def progress(self, goal: Goal, as_of: date | None = None) -> GoalProgress:
        as_of = as_of or self.today
        if goal.goal_type in {"weekly_frequency", "weekly_duration"}:
            return self._weekly_progress(goal, as_of)
        if goal.goal_type == "distance":
            return self._distance_progress(goal, as_of)
        if goal.goal_type == "race":
            return self._race_progress(goal, as_of)
        return self._body_progress(goal, as_of)

    def _weekly_progress(self, goal: Goal, as_of: date) -> GoalProgress:
        week_start = as_of - timedelta(days=as_of.weekday())
        week_end = week_start + timedelta(days=6)
        workouts = self._workouts(week_start, min(week_end, as_of), goal)
        target = float(goal.target_value or 0)
        if goal.goal_type == "weekly_frequency":
            current = float(len(workouts))
        else:
            current = float(sum(_number(item.get("duration_minutes")) or 0 for item in workouts))
        days_elapsed = (as_of - week_start).days + 1
        expected = target * days_elapsed / 7 if target else None
        quality = self._quality("workouts")
        if quality["status"] == "insufficient":
            return self._insufficient(goal, week_start, week_end, quality)
        completion = _clamp(current / target) if target else None
        on_track = current >= (expected or 0) * 0.9
        status = (
            "achieved"
            if target and current >= target
            else "ok"
            if on_track
            else "behind"
        )
        return GoalProgress(
            goal_id=goal.id,
            status=status,
            current_value=round(current, 1),
            target_value=target,
            unit=goal.target_unit,
            period_start=week_start,
            period_end=week_end,
            days_elapsed=days_elapsed,
            days_remaining=max(0, 7 - days_elapsed),
            expected_value=round(expected, 1) if expected is not None else None,
            completion_ratio=round(completion, 3) if completion is not None else None,
            on_track=on_track,
            data_quality=quality,
            evidence=[f"本周已记录 {len(workouts)} 次训练"],
            trend=self._weekly_trend(goal, as_of),
        )

    def _distance_progress(self, goal: Goal, as_of: date) -> GoalProgress:
        if goal.period == "week":
            period_start = as_of - timedelta(days=as_of.weekday())
            period_end = period_start + timedelta(days=6)
            query_end = min(period_end, as_of)
        elif goal.period == "month":
            period_start = as_of.replace(day=1)
            next_month = (period_start.replace(day=28) + timedelta(days=4)).replace(day=1)
            period_end = next_month - timedelta(days=1)
            query_end = min(period_end, as_of)
        else:
            period_start = goal.start_date
            period_end = goal.target_date or as_of
            query_end = as_of
        workouts = self._workouts(period_start, query_end, goal)
        target = float(goal.target_value or 0)
        distances = [
            _number(item.get("distance_m"))
            for item in workouts
            if _number(item.get("distance_m")) is not None
        ]
        current = float(sum(distances))
        quality = self._quality("workouts")
        if quality["status"] == "insufficient":
            return self._insufficient(goal, period_start, period_end, quality)
        total_days = max(1, (period_end - period_start).days + 1)
        elapsed_days = max(1, min(total_days, (query_end - period_start).days + 1))
        expected = target * elapsed_days / total_days if target else None
        completion = _clamp(current / target) if target else None
        on_track = current >= (expected or 0) * 0.9
        status = (
            "achieved"
            if target and current >= target
            else "ok"
            if on_track
            else "behind"
        )
        return GoalProgress(
            goal_id=goal.id,
            status=status,
            current_value=round(current, 1),
            target_value=target,
            unit=goal.target_unit,
            period_start=period_start,
            period_end=period_end,
            days_elapsed=elapsed_days,
            days_remaining=max(0, total_days - elapsed_days),
            expected_value=round(expected, 1) if expected is not None else None,
            completion_ratio=round(completion, 3) if completion is not None else None,
            on_track=on_track,
            data_quality=quality,
            evidence=[f"本周期已记录 {len(workouts)} 次相关运动"],
            trend=self._weekly_trend(goal, as_of),
        )

    def _race_progress(self, goal: Goal, as_of: date) -> GoalProgress:
        estimate = self._race_estimate(goal, as_of)
        period_start = goal.start_date
        period_end = goal.target_date or as_of
        quality = self._quality("workouts")
        if estimate is None:
            return self._insufficient(goal, period_start, period_end, quality)
        current, source_date, method = estimate
        target = float(goal.target_time_seconds or 0)
        if not target:
            return self._insufficient(goal, period_start, period_end, quality)
        completion = _clamp(target / current) if current > 0 else None
        on_track = current <= target * 1.05
        status = "achieved" if current <= target else "ok" if on_track else "behind"
        if str(self.language).lower().startswith("en"):
            method_label = (
                "scaled from recent running pace"
                if method == "recent_distance_scaled"
                else "scaled from recent average pace"
            )
            evidence = [
                f"Estimated race-distance time from recent runs: "
                f"{_format_seconds(current)} ({method_label})"
            ]
            if source_date:
                evidence.append(f"Reference workout date: {source_date.isoformat()}")
        else:
            method_label = (
                "按近期跑步配速折算"
                if method == "recent_distance_scaled"
                else "按近期平均配速折算"
            )
            evidence = [
                f"近期跑步估算目标距离用时 {_format_seconds(current)}（{method_label}）"
            ]
            if source_date:
                evidence.append(f"参考记录日期 {source_date.isoformat()}")
        return GoalProgress(
            goal_id=goal.id,
            status=status,
            current_value=round(current, 1),
            target_value=target,
            unit=goal.target_unit,
            period_start=period_start,
            period_end=period_end,
            days_elapsed=max(0, (as_of - period_start).days),
            days_remaining=max(0, (period_end - as_of).days),
            expected_value=None,
            completion_ratio=round(completion, 3) if completion is not None else None,
            on_track=on_track,
            data_quality=quality,
            evidence=evidence,
        )

    def _body_progress(self, goal: Goal, as_of: date) -> GoalProgress:
        series = self._body_series(goal, as_of)
        quality = self._quality("body_measurements")
        quality["measurements"] = len(series)
        if not series:
            return self._insufficient(goal, goal.start_date, goal.target_date or as_of, quality)
        current = series[-1][1]
        if goal.mode == "trend" or goal.target_value is None:
            return GoalProgress(
                goal_id=goal.id,
                status="ok",
                current_value=round(current, 2),
                target_value=None,
                unit=goal.target_unit,
                period_start=series[0][0],
                period_end=as_of,
                days_elapsed=max(0, (as_of - series[0][0]).days),
                days_remaining=None,
                expected_value=None,
                completion_ratio=None,
                on_track=None,
                data_quality=quality,
                evidence=[f"近期共 {len(series)} 次测量，最新值 {current:.2f}"],
            )
        baseline = goal.baseline_value if goal.baseline_value is not None else series[0][1]
        target = float(goal.target_value)
        period_start = goal.start_date
        period_end = goal.target_date or as_of
        total_days = max(1, (period_end - period_start).days)
        elapsed_days = max(0, min(total_days, (as_of - period_start).days))
        fraction = elapsed_days / total_days
        if target < baseline:
            completion = _clamp((baseline - current) / (baseline - target)) if baseline != target else None
            expected = baseline + (target - baseline) * fraction
            on_track = current <= expected + (0.1 if goal.target_unit == "kg" else 0.05)
        elif target > baseline:
            completion = _clamp((current - baseline) / (target - baseline)) if target != baseline else None
            expected = baseline + (target - baseline) * fraction
            on_track = current >= expected - (0.1 if goal.target_unit == "kg" else 0.05)
        else:
            completion = 1.0 if abs(current - target) <= 0.1 else 0.0
            expected = target
            on_track = abs(current - target) <= 0.1
        status = (
            "achieved"
            if abs(current - target) <= (0.1 if goal.target_unit == "kg" else 0.05)
            else "ok"
            if on_track
            else "behind"
        )
        return GoalProgress(
            goal_id=goal.id,
            status=status,
            current_value=round(current, 2),
            target_value=target,
            unit=goal.target_unit,
            period_start=period_start,
            period_end=period_end,
            days_elapsed=elapsed_days,
            days_remaining=max(0, total_days - elapsed_days),
            expected_value=round(expected, 2),
            completion_ratio=round(completion, 3) if completion is not None else None,
            on_track=on_track,
            data_quality=quality,
            evidence=[f"baseline {baseline:.2f}，最新 {current:.2f}，目标 {target:.2f}"],
        )

    def _insufficient(
        self,
        goal: Goal,
        period_start: date | None,
        period_end: date | None,
        quality: dict[str, Any],
    ) -> GoalProgress:
        return GoalProgress(
            goal_id=goal.id,
            status="insufficient_data",
            current_value=None,
            target_value=(
                float(goal.target_value)
                if goal.target_value is not None
                else float(goal.target_time_seconds or 0) or None
            ),
            unit=goal.target_unit,
            period_start=period_start,
            period_end=period_end,
            data_quality=quality,
            evidence=[],
        )

    # --------------------------------------------------------- recommendations

    def recommend(self, profile: TrainingProfile, limit: int = 3) -> list[GoalRecommendation]:
        if profile.data_quality.status == "insufficient" or not profile.weekly:
            return []
        candidates: list[GoalRecommendation] = []
        active_buckets = [bucket for bucket in profile.weekly if bucket.sessions > 0]
        if not active_buckets:
            return []
        active_weeks = profile.observed_frequency.active_weeks
        gaps = list(profile.data_quality.caveats)
        baseline_frequency = profile.observed_frequency.mean_per_week
        if baseline_frequency > 0:
            increment = (
                active_weeks >= 4
                and (
                    profile.trend.sessions_change_ratio is None
                    or profile.trend.sessions_change_ratio >= -0.1
                )
            )
            target_frequency = min(
                6, max(1, round(baseline_frequency + (1 if increment else 0)))
            )
            candidates.append(
                GoalRecommendation(
                    goal_type="weekly_frequency",
                    title=f"每周训练 {target_frequency} 次",
                    target_value=float(target_frequency),
                    baseline_value=round(baseline_frequency, 2),
                    target_unit="sessions_per_week",
                    period="week",
                    start_date=self.today,
                    rationale=(
                        f"近 {profile.window.weeks} 周平均每周 {baseline_frequency:.1f} 次训练；"
                        "目标保持可持续频率，避免一次性加量过多。"
                    ),
                    evidence=[f"active_weeks={active_weeks}"],
                    confidence="medium" if active_weeks >= 4 else "low",
                    data_gaps=gaps,
                )
            )
        durations = [bucket.duration_minutes for bucket in active_buckets]
        if durations:
            baseline_duration = statistics.fmean(durations)
            target_duration = min(
                1440, max(30, round((baseline_duration * 1.05) / 5) * 5)
            )
            candidates.append(
                GoalRecommendation(
                    goal_type="weekly_duration",
                    title=f"每周训练 {target_duration} 分钟",
                    target_value=float(target_duration),
                    baseline_value=round(baseline_duration, 1),
                    target_unit="minutes_per_week",
                    period="week",
                    start_date=self.today,
                    rationale="在近期周训练时长基础上小幅增加约 5%，优先保证恢复日。",
                    evidence=[f"active_weeks={active_weeks}"],
                    confidence="medium" if active_weeks >= 4 else "low",
                    data_gaps=gaps,
                )
            )
        work_days = profile.weekly
        if work_days:
            distance_baseline_km = statistics.fmean(
                [bucket.distance_km for bucket in active_buckets if bucket.distance_km > 0]
            ) if any(bucket.distance_km > 0 for bucket in active_buckets) else 0
            if distance_baseline_km > 0:
                target_km = round(distance_baseline_km * 1.05, 1)
                dominant = self._dominant_sport(profile)
                if dominant not in {"running", "cycling", "walking"}:
                    dominant = "any"
                candidates.append(
                    GoalRecommendation(
                        goal_type="distance",
                        sport=dominant,
                        title=f"每周{self._sport_label(dominant)} {target_km:g} 公里",
                        target_value=round(target_km * 1000, 1),
                        baseline_value=round(distance_baseline_km * 1000, 1),
                        target_unit="meters",
                        period="week",
                        start_date=self.today,
                        rationale="按近期周距离小幅增加约 5%，并保留至少一天完全休息。",
                        evidence=[f"dominant_sport={dominant}"],
                        confidence="medium" if active_weeks >= 4 else "low",
                        data_gaps=gaps,
                    )
                )
        proxy = profile.best_5k_proxy
        if proxy.estimated_5k_seconds and active_weeks >= 4:
            target_seconds = round(proxy.estimated_5k_seconds * 0.98)
            source_parts: list[str] = []
            if proxy.source_distance_km is not None:
                source_parts.append(f"{proxy.source_distance_km:g} 公里")
            if proxy.source_workout_date is not None:
                source_parts.append(proxy.source_workout_date.isoformat())
            source_label = f"（{'，'.join(source_parts)}）" if source_parts else ""
            evidence = [f"best_5k_proxy={proxy.estimated_5k_seconds}"]
            if proxy.source_distance_km is not None:
                evidence.append(f"source_distance_km={proxy.source_distance_km}")
            if proxy.source_workout_date is not None:
                evidence.append(
                    f"source_workout_date={proxy.source_workout_date.isoformat()}"
                )
            candidates.append(
                GoalRecommendation(
                    goal_type="race",
                    sport="running",
                    title=f"5K 目标 {_format_seconds(target_seconds)}",
                    target_value=float(target_seconds),
                    target_time_seconds=target_seconds,
                    race_distance="5k",
                    baseline_value=float(proxy.estimated_5k_seconds),
                    target_unit="seconds",
                    period="target_date",
                    start_date=self.today,
                    target_date=self.today + timedelta(weeks=12),
                    rationale=(
                        f"基于近期跑步{source_label}的平均配速折算 5K 约 "
                        f"{_format_seconds(proxy.estimated_5k_seconds)}，目标提高约 2%；"
                        "这是训练目标，不是正式比赛成绩预测。"
                    ),
                    evidence=evidence,
                    confidence="low",
                    data_gaps=gaps + ["5K 代理值不是芯片计时 PB。"],
                )
            )
        if profile.body is not None and profile.body.measurements >= 4:
            candidates.append(
                GoalRecommendation(
                    goal_type="body_composition",
                    title="体重趋势",
                    mode="trend",
                    target_value=None,
                    baseline_value=profile.body.latest_weight_kg,
                    target_unit="kg",
                    period="rolling_28d",
                    start_date=self.today,
                    rationale="只跟踪趋势，不设极端减重目标；体重受水分和进食影响，应看多日均值。",
                    evidence=[f"body_measurements={profile.body.measurements}"],
                    confidence="low",
                    data_gaps=gaps,
                )
            )
        priority = {
            "race": 0,
            "weekly_frequency": 1,
            "weekly_duration": 2,
            "distance": 3,
            "body_composition": 4,
        }
        candidates.sort(key=lambda item: priority.get(item.goal_type, 9))
        return candidates[: max(0, limit)]

    def validate_llm_recommendation(self, candidate: Any) -> GoalCreate:
        raw = candidate.model_dump() if hasattr(candidate, "model_dump") else dict(candidate)
        self._reject_medical_language(
            " ".join(str(raw.get(key, "")) for key in ("title", "rationale"))
        )
        data = {key: value for key, value in raw.items() if key in GoalCreate.model_fields}
        data.setdefault("start_date", self.today)
        goal = GoalCreate.model_validate(data)
        self._validate_dates(goal)
        self._validate_race_time(goal)
        baseline = goal.baseline_value
        if goal.goal_type == "body_composition":
            baseline = self._baseline_for_body_goal(goal)
        elif goal.goal_type == "race" and baseline is None:
            estimate = self._race_estimate(goal)
            baseline = estimate[0] if estimate else None
        elif (
            goal.goal_type in {"weekly_frequency", "weekly_duration", "distance"}
            and baseline is None
        ):
            baseline = self._recent_metric_baseline(goal)
        return goal.model_copy(update={"baseline_value": baseline})

    # -------------------------------------------------------------- helpers

    def _validate_dates(self, goal: GoalCreate) -> None:
        if goal.target_date is not None and goal.target_date < self.today:
            raise ValueError("target_date must not be in the past")
        if goal.goal_type == "race":
            assert goal.target_date is not None
            weeks = (goal.target_date - self.today).days / 7
            if not 2 <= weeks <= 104:
                raise ValueError("race target_date must be 2-104 weeks away")
        elif goal.goal_type == "body_composition" and goal.mode == "target":
            assert goal.target_date is not None
            weeks = (goal.target_date - self.today).days / 7
            if not 4 <= weeks <= 52:
                raise ValueError("body target_date must be 4-52 weeks away")
        elif (
            goal.goal_type == "distance"
            and goal.period == "target_date"
            and (goal.target_date is None or goal.target_date < self.today)
        ):
            raise ValueError("distance target_date must be today or later")

    @staticmethod
    def _validate_race_time(goal: GoalCreate) -> None:
        if goal.goal_type != "race" or goal.race_distance is None:
            return
        if goal.target_time_seconds is None:
            raise ValueError("race requires target_time_seconds")
        low, high = RACE_TIME_BOUNDS[goal.race_distance]
        if not low <= goal.target_time_seconds <= high:
            raise ValueError(
                f"target_time_seconds for {goal.race_distance} must be {low}-{high}"
            )

    def _baseline_for_body_goal(self, goal: GoalCreate) -> float | None:
        metric = "weight_kg" if goal.target_unit == "kg" else "body_fat_pct"
        series = self._recent_body_series(metric)
        if len(series) < 4 or (series[-1][0] - series[0][0]).days < 21:
            if goal.mode == "trend":
                return series[-1][1] if series else None
            raise ValueError("body goal needs at least 4 measurements over 21 days")
        baseline = series[-1][1]
        if goal.mode == "target" and goal.target_value is not None:
            target = float(goal.target_value)
            assert goal.target_date is not None
            weeks = max(1.0, (goal.target_date - self.today).days / 7)
            if metric == "weight_kg":
                max_change = weeks * min(0.5, baseline * 0.005)
            else:
                max_change = weeks * 0.25
            if abs(target - baseline) > max_change + 0.1:
                raise ValueError(
                    "body target exceeds the conservative weekly change limit"
                )
            latest_bmi = self._latest_bmi()
            if metric == "weight_kg" and latest_bmi is not None and baseline > 0:
                target_bmi = latest_bmi * target / baseline
                if target_bmi < 18.5:
                    raise ValueError("target weight would imply BMI below 18.5")
        return baseline

    def _recent_body_series(self, metric: str) -> list[tuple[date, float]]:
        if self.query is None:
            return []
        start = self.today - timedelta(days=28)
        try:
            measurements = self.query.get_body_measurements(
                start.isoformat(), self.today.isoformat()
            )
        except Exception:
            return []
        series: list[tuple[date, float]] = []
        for measurement in measurements:
            value = _number(measurement.get(metric))
            parsed = _parse_datetime(measurement.get("timestamp"))
            if value is not None and parsed is not None:
                series.append((parsed.date(), value))
        series.sort(key=lambda pair: pair[0])
        return series

    def _body_series(self, goal: Goal, as_of: date) -> list[tuple[date, float]]:
        if self.query is None:
            return []
        metric = "weight_kg" if goal.target_unit == "kg" else "body_fat_pct"
        start = min(goal.start_date, as_of - timedelta(days=28))
        try:
            measurements = self.query.get_body_measurements(
                start.isoformat(), as_of.isoformat()
            )
        except Exception:
            return []
        series: list[tuple[date, float]] = []
        for measurement in measurements:
            value = _number(measurement.get(metric))
            parsed = _parse_datetime(measurement.get("timestamp"))
            if value is not None and parsed is not None:
                series.append((parsed.date(), value))
        series.sort(key=lambda pair: pair[0])
        return series

    def _latest_bmi(self) -> float | None:
        if self.query is None:
            return None
        try:
            measurements = self.query.get_body_measurements(
                (self.today - timedelta(days=28)).isoformat(), self.today.isoformat()
            )
        except Exception:
            return None
        for measurement in reversed(measurements):
            bmi = _number(measurement.get("bmi"))
            if bmi is not None:
                return bmi
        return None

    def _race_estimate(
        self, goal: Goal | GoalCreate, as_of: date | None = None
    ) -> tuple[float, date | None, str] | None:
        if self.query is None or goal.race_distance is None:
            return None
        as_of = as_of or self.today
        target_distance = RACE_DISTANCES_M[goal.race_distance]
        workouts = self._workouts(as_of - timedelta(days=84), as_of, goal)
        candidates: list[tuple[float, date | None, str]] = []
        for workout in workouts:
            distance_m = _number(workout.get("distance_m"))
            duration_seconds = workout_duration_seconds(workout) or 0
            pace = _number(workout.get("avg_pace_sec_per_km"))
            if not distance_m or distance_m <= 0:
                continue
            if distance_m < target_distance * 0.9:
                continue
            if duration_seconds > 0:
                estimate = duration_seconds * target_distance / distance_m
                method = "recent_distance_scaled"
            elif pace:
                estimate = pace * target_distance / 1000
                method = "average_pace_scaled"
            else:
                continue
            if 600 <= estimate <= 36_000:
                candidates.append((estimate, self._workout_date(workout), method))
        if not candidates:
            return None
        return min(candidates, key=lambda item: item[0])

    def _recent_metric_baseline(self, goal: Goal | GoalCreate) -> float | None:
        if self.query is None:
            return None
        workouts = self._workouts(
            self.today - timedelta(days=27), self.today, goal
        )
        if not workouts:
            return None
        if goal.goal_type == "weekly_frequency":
            return round(len(workouts) / 4, 2)
        if goal.goal_type == "weekly_duration":
            return round(
                sum(_number(item.get("duration_minutes")) or 0 for item in workouts) / 4,
                1,
            )
        if goal.goal_type == "distance":
            return round(
                sum(
                    _number(item.get("distance_m")) or 0
                    for item in workouts
                    if _number(item.get("distance_m")) is not None
                )
                / 4,
                1,
            )
        return None

    def _weekly_trend(self, goal: Goal, as_of: date) -> list[dict[str, Any]]:
        if self.query is None or goal.goal_type not in {
            "weekly_frequency",
            "weekly_duration",
            "distance",
        }:
            return []
        current_week_start = as_of - timedelta(days=as_of.weekday())
        start = current_week_start - timedelta(weeks=3)
        workouts = self._workouts(start, as_of, goal)
        buckets: dict[date, list[dict[str, Any]]] = {}
        for workout in workouts:
            workout_date = self._workout_date(workout)
            if workout_date is None:
                continue
            week_start = workout_date - timedelta(days=workout_date.weekday())
            buckets.setdefault(week_start, []).append(workout)
        trend: list[dict[str, Any]] = []
        for week_start in sorted(buckets):
            week_workouts = buckets[week_start]
            if goal.goal_type == "weekly_frequency":
                value = float(len(week_workouts))
            elif goal.goal_type == "weekly_duration":
                value = sum(
                    _number(item.get("duration_minutes")) or 0
                    for item in week_workouts
                )
            else:
                value = sum(
                    _number(item.get("distance_m")) or 0
                    for item in week_workouts
                    if _number(item.get("distance_m")) is not None
                )
            trend.append({"week_start": week_start.isoformat(), "value": round(value, 1)})
        return trend

    def _workouts(
        self, start: date, end: date, goal: Goal | GoalCreate
    ) -> list[dict[str, Any]]:
        if self.query is None or end < start:
            return []
        try:
            workouts = self.query.get_workouts(start.isoformat(), end.isoformat())
        except Exception:
            return []
        if goal.sport != "any":
            workouts = [
                workout
                for workout in workouts
                if normalize_activity_type(workout.get("activity_type")) == goal.sport
            ]
        return workouts

    def _quality(self, data_type: str) -> dict[str, Any]:
        if self.query is None:
            return {
                "status": "insufficient",
                "coverage": {},
                "missing_metrics": [],
                "caveats": ["Query service unavailable."],
            }
        try:
            coverage = self.query.get_data_coverage([data_type])
        except Exception:
            coverage = []
        if isinstance(coverage, dict):
            item = coverage.get(data_type, {})
        else:
            item = next(
                (
                    entry
                    for entry in coverage
                    if isinstance(entry, dict) and entry.get("data_type") == data_type
                ),
                {},
            )
        days = int(item.get("days_with_data") or 0)
        if days <= 0:
            return {
                "status": "insufficient",
                "coverage": coverage,
                "missing_metrics": [data_type],
                "caveats": [f"No {data_type} records are available."],
            }
        return {
            "status": "ok",
            "coverage": coverage,
            "missing_metrics": [],
            "caveats": ["Missing dates are not treated as zero."],
        }

    def _reject_medical_language(self, text: str) -> None:
        lowered = text.lower()
        for term in MEDICAL_CLAIM_TERMS + EXTREME_DIET_TERMS:
            if term.lower() in lowered:
                raise ValueError("recommendation contains medical or extreme-diet language")

    @staticmethod
    def _dominant_sport(profile: TrainingProfile) -> str:
        counts: dict[str, int] = {}
        for bucket in profile.weekly:
            for sport, count in bucket.by_sport.items():
                counts[sport] = counts.get(sport, 0) + count
        if not counts:
            return "any"
        return max(counts, key=lambda sport: (counts[sport], sport))

    @staticmethod
    def _sport_label(sport: str) -> str:
        return {
            "running": "跑步",
            "cycling": "骑行",
            "walking": "步行",
            "strength": "力量训练",
            "swimming": "游泳",
            "other": "运动",
            "any": "运动",
        }.get(sport, "运动")

    @staticmethod
    def _workout_date(workout: dict[str, Any]) -> date | None:
        parsed = _parse_datetime(workout.get("start_at"))
        return parsed.date() if parsed else None
