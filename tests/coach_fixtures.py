"""Synthetic multi-week histories for coach tests.

No real account, credential, database, export, or network request is used.
All values are invented and deterministic.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

from mi_fitness_mcp.storage import Database

SYNTHETIC_USER = "synthetic-coach-user"
TZ = "Asia/Shanghai"
BASE_START = date(2026, 1, 5)  # Monday


def _iso(day: date, clock: time) -> str:
    return datetime.combine(day, clock).replace(tzinfo=None).isoformat() + "+08:00"


def _insert_workout(
    conn: Any,
    *,
    user_id: str,
    workout_id: str,
    activity_type: str,
    day: date,
    clock: time,
    duration_minutes: int,
    distance_km: float,
    calories: float,
    avg_hr: int,
    max_hr: int,
    pace_sec_per_km: float,
    train_effect: float,
    anaerobic_effect: float,
    training_load: int,
) -> None:
    start_at = _iso(day, clock)
    end_at = (
        datetime.combine(day, clock) + timedelta(minutes=duration_minutes)
    ).replace(tzinfo=None).isoformat() + "+08:00"
    conn.execute(
        """
        INSERT INTO workouts (
            id, provider, source_type, source_record_id, user_id, device_id,
            timezone, workout_id, activity_type, start_at, end_at,
            duration_minutes, distance_m, calories_kcal, avg_heart_rate_bpm,
            max_heart_rate_bpm, avg_pace_sec_per_km, train_effect,
            anaerobic_train_effect, training_load
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            uuid.uuid4().hex,
            "mi_fitness",
            "cloud_session",
            workout_id,
            user_id,
            "synthetic-watch",
            TZ,
            workout_id,
            activity_type,
            start_at,
            end_at,
            duration_minutes,
            distance_km * 1000,
            calories,
            avg_hr,
            max_hr,
            pace_sec_per_km,
            train_effect,
            anaerobic_effect,
            training_load,
        ),
    )


def _insert_sleep(
    conn: Any, *, user_id: str, sleep_id: str, day: date, score: int
) -> None:
    start = datetime.combine(day - timedelta(days=1), time(23, 0)).replace(tzinfo=None)
    end = datetime.combine(day, time(7, 0)).replace(tzinfo=None)
    conn.execute(
        """
        INSERT INTO sleep_sessions (
            id, provider, source_type, source_record_id, user_id, device_id,
            timezone, sleep_id, start_at, end_at, duration_minutes,
            time_asleep_minutes, time_awake_minutes, sleep_score, is_nap,
            stages, sleep_score_source
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            uuid.uuid4().hex,
            "mi_fitness",
            "cloud_session",
            sleep_id,
            user_id,
            "synthetic-watch",
            TZ,
            sleep_id,
            start.isoformat() + "+08:00",
            end.isoformat() + "+08:00",
            480,
            450,
            30,
            score,
            False,
            "[]",
            "sleep_record",
        ),
    )


def _insert_body(conn: Any, *, user_id: str, day: date, weight: float, body_fat: float) -> None:
    timestamp = f"{day.isoformat()}T07:30:00+08:00"
    conn.execute(
        """
        INSERT INTO body_measurements (
            id, provider, source_type, source_record_id, user_id, device_id,
            timezone, timestamp, weight_kg, bmi, body_fat_pct
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            uuid.uuid4().hex,
            "mi_fitness",
            "cloud_session",
            f"body-{day.isoformat()}",
            user_id,
            "synthetic-scale",
            TZ,
            timestamp,
            weight,
            round(weight / (1.75**2), 1),
            body_fat,
        ),
    )


def _insert_daily(conn: Any, *, user_id: str, day: date, steps: int) -> None:
    conn.execute(
        """
        INSERT INTO daily_activity (
            id, provider, source_type, source_record_id, user_id, device_id,
            timezone, date, steps, distance_m, active_kcal
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            uuid.uuid4().hex,
            "mi_fitness",
            "cloud_session",
            f"daily-{day.isoformat()}",
            user_id,
            "synthetic-watch",
            TZ,
            day.isoformat(),
            steps,
            steps * 0.72,
            steps * 0.04,
        ),
    )


def seed_coach_history(
    db_path: Path | str,
    *,
    weeks: int = 12,
    user_id: str = SYNTHETIC_USER,
    start: date = BASE_START,
) -> tuple[Path, str, date]:
    """Seed a deterministic running/cycling/strength history.

    Returns ``(db_path, user_id, today)`` where ``today`` is the last Sunday
    in the window, suitable for ``TrainingProfileBuilder(today=...)``.
    """
    path = Path(db_path)
    db = Database(path)
    end_date = start + timedelta(weeks=weeks) - timedelta(days=1)
    workout_number = 0
    with db._get_connection() as conn:
        for week in range(weeks):
            week_start = start + timedelta(weeks=week)
            if week in {4, 9}:
                continue
            long_minutes = 55 + week * 4
            long_km = 8.0 + week * 0.5
            sessions: list[dict[str, Any]] = [
                {
                    "day_offset": 1,
                    "activity_type": "outdoor_running",
                    "clock": time(18, 30),
                    "duration": 35,
                    "km": 5.5,
                    "kcal": 330,
                    "avg_hr": 138,
                    "max_hr": 155,
                    "pace": (35 * 60) / 5.5,
                    "effect": 2.4,
                    "anaerobic": 0.4,
                    "load": 120,
                },
                {
                    "day_offset": 3,
                    "activity_type": "outdoor_cycling",
                    "clock": time(17, 30),
                    "duration": 50,
                    "km": 20.0,
                    "kcal": 380,
                    "avg_hr": 132,
                    "max_hr": 150,
                    "pace": 150,
                    "effect": 2.8,
                    "anaerobic": 0.8,
                    "load": 180,
                },
                {
                    "day_offset": 5,
                    "activity_type": "outdoor_running",
                    "clock": time(7, 0),
                    "duration": long_minutes,
                    "km": long_km,
                    "kcal": long_km * 62,
                    "avg_hr": 148,
                    "max_hr": 168,
                    "pace": (long_minutes * 60) / long_km,
                    "effect": 3.6,
                    "anaerobic": 1.2,
                    "load": 240,
                },
            ]
            if week % 2 == 0:
                sessions.append(
                    {
                        "day_offset": 6,
                        "activity_type": "strength_training",
                        "clock": time(20, 0),
                        "duration": 30,
                        "km": 0.0,
                        "kcal": 160,
                        "avg_hr": 118,
                        "max_hr": 138,
                        "pace": 0,
                        "effect": 2.0,
                        "anaerobic": 0.2,
                        "load": 70,
                    }
                )
            if week == 6:
                sessions.append(
                    {
                        "day_offset": 4,
                        "activity_type": "outdoor_running",
                        "clock": time(18, 0),
                        "duration": 24,
                        "km": 5.0,
                        "kcal": 320,
                        "avg_hr": 166,
                        "max_hr": 181,
                        "pace": 288,
                        "effect": 4.5,
                        "anaerobic": 3.0,
                        "load": 310,
                    }
                )
            for session in sessions:
                workout_number += 1
                _insert_workout(
                    conn,
                    user_id=user_id,
                    workout_id=f"synthetic-workout-{workout_number}",
                    activity_type=str(session["activity_type"]),
                    day=week_start + timedelta(days=int(session["day_offset"])),
                    clock=session["clock"],
                    duration_minutes=int(session["duration"]),
                    distance_km=float(session["km"]),
                    calories=float(session["kcal"]),
                    avg_hr=int(session["avg_hr"]),
                    max_hr=int(session["max_hr"]),
                    pace_sec_per_km=float(session["pace"]),
                    train_effect=float(session["effect"]),
                    anaerobic_effect=float(session["anaerobic"]),
                    training_load=int(session["load"]),
                )
        for offset in range(weeks * 7):
            day = start + timedelta(days=offset)
            _insert_daily(conn, user_id=user_id, day=day, steps=7000 + (offset % 5) * 900)
            if offset % 5 != 0:
                _insert_sleep(
                    conn,
                    user_id=user_id,
                    sleep_id=f"synthetic-sleep-{day.isoformat()}",
                    day=day,
                    score=78 + (offset % 10),
                )
            if offset % 7 == 6 and offset // 7 not in {3, 7}:
                week = offset // 7
                _insert_body(
                    conn,
                    user_id=user_id,
                    day=day,
                    weight=76.0 - week * 0.22,
                    body_fat=22.5 - week * 0.12,
                )
        conn.commit()
    return path, user_id, end_date


def seed_minimal_coach_history(
    db_path: Path | str,
    *,
    user_id: str = SYNTHETIC_USER,
    start: date = BASE_START,
) -> tuple[Path, str, date]:
    """Two sessions in 14 days, used to exercise insufficient-data paths."""
    path = Path(db_path)
    db = Database(path)
    with db._get_connection() as conn:
        _insert_workout(
            conn,
            user_id=user_id,
            workout_id="synthetic-minimal-1",
            activity_type="outdoor_running",
            day=start,
            clock=time(7, 0),
            duration_minutes=30,
            distance_km=4.5,
            calories=260,
            avg_hr=140,
            max_hr=160,
            pace_sec_per_km=400,
            train_effect=2.5,
            anaerobic_effect=0.2,
            training_load=100,
        )
        _insert_workout(
            conn,
            user_id=user_id,
            workout_id="synthetic-minimal-2",
            activity_type="outdoor_running",
            day=start + timedelta(days=10),
            clock=time(7, 0),
            duration_minutes=32,
            distance_km=4.8,
            calories=270,
            avg_hr=142,
            max_hr=162,
            pace_sec_per_km=400,
            train_effect=2.6,
            anaerobic_effect=0.2,
            training_load=105,
        )
        conn.commit()
    return path, user_id, start + timedelta(days=13)


def seed_coach_db(
    tmp_path: Path, *, weeks: int = 12
) -> tuple[Path, str, date]:
    return seed_coach_history(tmp_path / "coach.db", weeks=weeks)
