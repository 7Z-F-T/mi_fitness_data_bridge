"""Read-only service layer backing the local web API."""

from __future__ import annotations

import logging
import os
import sqlite3
from collections.abc import Callable
from datetime import date, timedelta
from functools import wraps
from pathlib import Path
from typing import Any, TypeVar

from mi_fitness_mcp.services.query_service import QueryService
from mi_fitness_mcp.storage import Database
from mi_fitness_mcp.web.exceptions import (
    AmbiguousUserError,
    DatabaseLockedError,
    DatabaseUnavailableError,
    NoDataError,
    QueryError,
    WorkoutNotFoundError,
)
from mi_fitness_mcp.web.mappers import (
    activity_from_summary,
    bucket_keys,
    gps_from_row,
    heart_rate_from_row,
    normalize_activity_type,
    range_bounds,
    sample_from_row,
    sleep_from_payload,
    weighted_avg_heart_rate,
    workout_bucket_key,
    workout_from_payload,
)
from mi_fitness_mcp.web.schemas import (
    DailyActivity,
    Goal,
    HealthResponse,
    HomeSummary,
    SummaryRange,
    Workout,
    WorkoutDetail,
    WorkoutSummary,
    WorkoutSummaryBucket,
    WorkoutTotals,
    WorkoutTypeSummary,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")

HEALTH_TABLES = (
    "daily_activity",
    "sleep_sessions",
    "workouts",
    "workout_detail_samples",
    "workout_gps_points",
    "body_measurements",
    "heart_rate_samples",
    "spo2_samples",
    "stress_samples",
    "abnormal_heart_beat_events",
)


def translate_db_errors(func: Callable[..., T]) -> Callable[..., T]:
    """Translate low-level SQLite errors into friendly API exceptions."""

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> T:
        try:
            return func(*args, **kwargs)
        except FileNotFoundError as exc:
            raise DatabaseUnavailableError() from exc
        except sqlite3.OperationalError as exc:
            message = str(exc).lower()
            if "locked" in message or "busy" in message:
                raise DatabaseLockedError() from exc
            if "no such table" in message:
                raise DatabaseUnavailableError(
                    "本地数据库结构过旧或不完整，请先运行 `mi-fitness-bridge sync` 初始化或升级数据库。"
                ) from exc
            logger.exception("SQLite query failed")
            raise QueryError() from exc
        except sqlite3.DatabaseError as exc:
            logger.exception("SQLite database error")
            raise DatabaseUnavailableError() from exc

    return wrapper


class FitnessService:
    """Lazily-open the cache read-only and expose dashboard-shaped data."""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self._db: Database | None = None
        self._query: QueryService | None = None

    def invalidate(self) -> None:
        """Drop cached read state after a sync writes new data."""
        self._db = None
        self._query = None

    @property
    def db(self) -> Database:
        self._load()
        if self._db is None:  # pragma: no cover - defensive
            raise DatabaseUnavailableError()
        return self._db

    @translate_db_errors
    def _load(self) -> QueryService:
        if self._query is not None:
            return self._query
        path = self.db_path.expanduser()
        if not path.is_file():
            raise DatabaseUnavailableError()
        database = Database(path, read_only=True)
        user_id = self._discover_user_id(database)
        self._db = database
        self._query = QueryService(database, user_id)
        return self._query

    @staticmethod
    def _discover_user_id(database: Database) -> str:
        with database._get_connection() as conn:
            existing = {
                row["name"]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
            available = [table for table in HEALTH_TABLES if table in existing]
            if not available:
                raise NoDataError()
            union_sql = " UNION ALL ".join(
                f"SELECT user_id FROM {table}" for table in available
            )
            rows = conn.execute(
                f"SELECT user_id, COUNT(*) AS n FROM ({union_sql}) AS users "
                "GROUP BY user_id ORDER BY n DESC"
            ).fetchall()

        users = [str(row["user_id"]) for row in rows if row["user_id"] is not None]
        if not users:
            raise NoDataError()

        configured = os.environ.get("MI_FITNESS_WEB_USER_ID", "").strip()
        if configured:
            if configured not in users:
                raise NoDataError(
                    "MI_FITNESS_WEB_USER_ID 指定的账号在数据库中没有数据。"
                )
            return configured
        if len(users) > 1:
            raise AmbiguousUserError()
        return users[0]

    @staticmethod
    def _activity_for(query: QueryService, date_str: str) -> DailyActivity:
        summaries = query.get_daily_summaries(date_str, date_str)
        return activity_from_summary(summaries[0] if summaries else None, date_str)

    @translate_db_errors
    def home(self, day: date | None = None) -> HomeSummary:
        query = self._load()
        target = day or date.today()
        target_str = target.isoformat()

        activity = self._activity_for(query, target_str)

        sleep_summary = query.get_sleep_summary(target_str, target_str)
        main_sessions = sleep_summary.get("main_sessions") or []
        sleep = sleep_from_payload(main_sessions[0]) if main_sessions else None

        hr_rows = query.get_heart_rate_samples(target_str, target_str, limit=5000)
        hr_samples = [heart_rate_from_row(row) for row in hr_rows]
        resting_samples = [
            sample for sample in hr_samples if sample.sample_type == "resting"
        ]
        resting_heart_rate = (
            round(
                sum(sample.bpm for sample in resting_samples)
                / len(resting_samples)
            )
            if resting_samples
            else None
        )
        latest_heart_rate = hr_samples[-1].bpm if hr_samples else None

        weekly_activity = [
            self._activity_for(
                query, (target - timedelta(days=offset)).isoformat()
            )
            for offset in range(6, -1, -1)
        ]

        recent_payloads = query.get_workouts("1970-01-01", target_str)
        recent_workouts = sorted(
            (workout_from_payload(payload) for payload in recent_payloads),
            key=lambda workout: workout.start_at,
            reverse=True,
        )[:4]

        return HomeSummary(
            date=target_str,
            activity=activity,
            sleep=sleep,
            resting_heart_rate=resting_heart_rate,
            latest_heart_rate=latest_heart_rate,
            hr_samples=hr_samples,
            weekly_activity=weekly_activity,
            recent_workouts=recent_workouts,
        )

    @translate_db_errors
    def workouts(self, limit: int = 20) -> list[Workout]:
        query = self._load()
        payloads = query.get_workouts("1970-01-01", "9999-12-31")
        workouts = sorted(
            (workout_from_payload(payload) for payload in payloads),
            key=lambda workout: workout.start_at,
            reverse=True,
        )
        return workouts[:limit]

    @translate_db_errors
    def workout_detail(self, workout_id: str) -> WorkoutDetail:
        query = self._load()
        payload = query.get_workout(workout_id)
        if payload is None:
            raise WorkoutNotFoundError()
        workout = workout_from_payload(payload)

        try:
            sample_rows = self.db.query_workout_detail_samples(
                query.user_id, workout_id
            )
            gps_rows = self.db.query_workout_gps_points(query.user_id, workout_id)
        except sqlite3.OperationalError as exc:
            if "no such table" in str(exc).lower():
                sample_rows, gps_rows = [], []
            else:
                raise

        return WorkoutDetail(
            workout=workout,
            samples=[sample_from_row(row) for row in sample_rows],
            gps=[gps_from_row(row) for row in gps_rows],
        )

    @translate_db_errors
    def workout_summary(
        self, range_: SummaryRange, anchor: date
    ) -> WorkoutSummary:
        query = self._load()
        start, end = range_bounds(range_, anchor)
        payloads = query.get_workouts(start.isoformat(), end.isoformat())
        workouts = sorted(
            (workout_from_payload(payload) for payload in payloads),
            key=lambda workout: workout.start_at,
            reverse=True,
        )

        buckets: dict[str, dict[str, Any]] = {
            key: {
                "key": key,
                "workouts": 0,
                "duration_minutes": 0,
                "distance_m": 0.0,
                "calories_kcal": 0.0,
            }
            for key in bucket_keys(range_, start, end)
        }
        types: dict[str, dict[str, Any]] = {}

        for workout in workouts:
            bucket = buckets.get(workout_bucket_key(workout, range_))
            if bucket is not None:
                bucket["workouts"] += 1
                bucket["duration_minutes"] += workout.duration_minutes
                bucket["distance_m"] += workout.distance_m or 0
                bucket["calories_kcal"] += workout.calories_kcal or 0

            type_key = normalize_activity_type(workout.activity_type)
            item = types.setdefault(
                type_key,
                {
                    "type": type_key,
                    "workouts": 0,
                    "duration_minutes": 0,
                    "distance_m": 0.0,
                },
            )
            item["workouts"] += 1
            item["duration_minutes"] += workout.duration_minutes
            item["distance_m"] += workout.distance_m or 0

        return WorkoutSummary(
            range=range_,
            anchor=anchor.isoformat(),
            buckets=[WorkoutSummaryBucket(**bucket) for bucket in buckets.values()],
            totals=WorkoutTotals(
                workouts=len(workouts),
                duration_minutes=sum(
                    workout.duration_minutes for workout in workouts
                ),
                distance_m=sum(workout.distance_m or 0 for workout in workouts),
                calories_kcal=sum(
                    workout.calories_kcal or 0 for workout in workouts
                ),
                avg_heart_rate_bpm=weighted_avg_heart_rate(workouts),
            ),
            by_type=[
                WorkoutTypeSummary(**item)
                for item in sorted(
                    types.values(),
                    key=lambda item: (-item["workouts"], item["type"]),
                )
            ],
            workouts=workouts,
        )

    def goals(self) -> list[Goal]:
        # Goals are not persisted yet; this page should work even before a sync.
        return []

    @translate_db_errors
    def health(self) -> HealthResponse:
        path = self.db_path.expanduser()
        if not path.is_file():
            raise DatabaseUnavailableError()
        Database(path, read_only=True).ping()
        return HealthResponse()
