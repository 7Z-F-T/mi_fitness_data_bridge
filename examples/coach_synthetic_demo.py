"""Offline coach demo: synthetic data only, no account, keyring, or network.

Run from the repository root:

    python examples/coach_synthetic_demo.py

It creates a temporary SQLite database, a deterministic 8-week training
history, a local goal, and a validated local template plan.
"""

from __future__ import annotations

import tempfile
import uuid
from datetime import date, datetime, time, timedelta
from pathlib import Path

from mi_fitness_mcp.coach.models import GoalCreate
from mi_fitness_mcp.coach.service import CoachService
from mi_fitness_mcp.config import CoachConfig
from mi_fitness_mcp.services.query_service import QueryService
from mi_fitness_mcp.storage import Database
from mi_fitness_mcp.storage.coach import CoachStore

USER_ID = "synthetic-demo-user"


def _seed(db: Database) -> None:
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    with db._get_connection() as conn:
        for week in range(8):
            week_start = monday - timedelta(weeks=7) + timedelta(weeks=week)
            for offset, activity_type, minutes, km, avg_hr, max_hr, effect in (
                (1, "outdoor_running", 35, 5.5, 138, 155, 2.4),
                (3, "outdoor_cycling", 50, 20.0, 132, 150, 2.8),
                (5, "outdoor_running", 55 + week * 3, 8.0 + week * 0.4, 148, 168, 3.6),
            ):
                day = week_start + timedelta(days=offset)
                start = datetime.combine(day, time(7, 0)).replace(tzinfo=None)
                end = start + timedelta(minutes=minutes)
                conn.execute(
                    """
                    INSERT INTO workouts (
                        id, provider, source_type, user_id, timezone, workout_id,
                        activity_type, start_at, end_at, duration_minutes,
                        distance_m, calories_kcal, avg_heart_rate_bpm,
                        max_heart_rate_bpm, avg_pace_sec_per_km, train_effect
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        uuid.uuid4().hex,
                        "mi_fitness",
                        "cloud_session",
                        USER_ID,
                        "UTC",
                        f"demo-workout-{week}-{offset}",
                        activity_type,
                        start.isoformat(),
                        end.isoformat(),
                        minutes,
                        km * 1000,
                        minutes * 7,
                        avg_hr,
                        max_hr,
                        (minutes * 60) / km,
                        effect,
                    ),
                )
        conn.commit()


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "coach-demo.db"
        db = Database(path)
        _seed(db)
        store = CoachStore(db)
        service = CoachService(
            store,
            QueryService(db, USER_ID),
            CoachConfig(enabled=False, profile_weeks=8, default_plan_weeks=8),
            timezone="UTC",
        )
        profile = service.profile(8)
        print("Synthetic coach demo")
        print("=" * 40)
        print(
            f"profile: {profile.data_quality.status}, "
            f"weeks={profile.window.weeks}, "
            f"active={profile.observed_frequency.active_weeks}, "
            f"missing={profile.window.weeks_without_records}"
        )
        recommendations = service.recommend_goals(weeks=8)
        print(f"rule suggestions: {len(recommendations)}")
        goal = service.create_goal(
            GoalCreate(
                goal_type="weekly_frequency",
                title="每周训练 3 次",
                target_value=3,
                target_unit="sessions_per_week",
                period="week",
                start_date=date.today(),
            )
        )
        print(f"goal: {goal.title} ({goal.id})")
        plan = service.generate_plan(goal.id, weeks=8, activate=True)
        print(
            f"plan: {plan.title} ({plan.weeks} weeks), "
            f"status={plan.status}, validation={plan.validation_status}"
        )
        first_week = plan.plan.weeks[0]
        print(f"first week ({first_week.start_date}):")
        for session in first_week.sessions:
            print(
                f"  {session.date} {session.session_type} "
                f"{session.duration_minutes} min"
            )
        print("No account, keyring, model provider, or network was used.")


if __name__ == "__main__":
    main()
