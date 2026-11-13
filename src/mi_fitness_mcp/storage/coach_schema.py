"""Additive SQLite schema for the optional coach extension.

These tables are created by writable :class:`mi_fitness_mcp.storage.Database`
instances.  They stay empty and have no behavioural effect unless the user
explicitly enables the optional coach module.  Read-only web connections never
run this migration; callers get an actionable "not initialized" error instead.
"""

from __future__ import annotations

import sqlite3


def create_coach_schema(conn: sqlite3.Connection) -> None:
    """Create coach goals, plans, and AI-run metadata tables if missing."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS coach_goals (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL DEFAULT 'local',
            goal_type TEXT NOT NULL CHECK (
                goal_type IN (
                    'weekly_frequency', 'weekly_duration', 'race',
                    'distance', 'body_composition'
                )
            ),
            sport TEXT NOT NULL DEFAULT 'any' CHECK (
                sport IN (
                    'any', 'running', 'cycling', 'walking', 'strength',
                    'swimming', 'other'
                )
            ),
            title TEXT NOT NULL,
            mode TEXT NOT NULL DEFAULT 'target' CHECK (mode IN ('target', 'trend')),
            target_value REAL,
            baseline_value REAL,
            target_unit TEXT NOT NULL CHECK (
                target_unit IN (
                    'sessions_per_week', 'minutes_per_week', 'meters',
                    'kg', 'percent', 'seconds'
                )
            ),
            period TEXT NOT NULL DEFAULT 'week' CHECK (
                period IN ('week', 'month', 'target_date', 'rolling_28d')
            ),
            start_date TEXT NOT NULL,
            target_date TEXT,
            race_distance TEXT CHECK (
                race_distance IS NULL
                OR race_distance IN ('5k', '10k', 'half', 'full')
            ),
            target_time_seconds INTEGER,
            available_days INTEGER,
            max_sessions_per_week INTEGER,
            notes TEXT,
            status TEXT NOT NULL DEFAULT 'active' CHECK (
                status IN ('active', 'achieved', 'archived')
            ),
            achieved_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            CHECK (target_value IS NULL OR target_value > 0),
            CHECK (target_time_seconds IS NULL OR target_time_seconds > 0),
            CHECK (available_days IS NULL OR (available_days BETWEEN 2 AND 7)),
            CHECK (
                max_sessions_per_week IS NULL
                OR (max_sessions_per_week BETWEEN 1 AND 7)
            )
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_coach_goals_user_status
        ON coach_goals(user_id, status)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_coach_goals_user_type
        ON coach_goals(user_id, goal_type)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_coach_goals_user_target_date
        ON coach_goals(user_id, target_date)
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS coach_training_plans (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL DEFAULT 'local',
            goal_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'draft' CHECK (
                status IN ('draft', 'active', 'superseded', 'archived')
            ),
            title TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            weeks INTEGER NOT NULL CHECK (weeks BETWEEN 1 AND 52),
            generated_by TEXT NOT NULL CHECK (
                generated_by IN ('llm', 'fallback', 'manual')
            ),
            provider TEXT,
            model TEXT,
            prompt_version TEXT,
            schema_version TEXT NOT NULL,
            ai_run_id TEXT,
            goal_snapshot_json TEXT NOT NULL,
            plan_json TEXT NOT NULL,
            validation_status TEXT NOT NULL CHECK (
                validation_status IN ('passed', 'warnings', 'failed')
            ),
            validation_warnings_json TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            activated_at TEXT,
            archived_at TEXT
        )
    """)
    conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_coach_plans_one_active
        ON coach_training_plans(goal_id)
        WHERE status = 'active'
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_coach_plans_user_goal_status
        ON coach_training_plans(user_id, goal_id, status)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_coach_plans_user_created
        ON coach_training_plans(user_id, created_at)
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS coach_ai_runs (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL DEFAULT 'local',
            goal_id TEXT,
            plan_id TEXT,
            kind TEXT NOT NULL CHECK (
                kind IN ('goal_recommendation', 'plan_generation')
            ),
            provider TEXT NOT NULL,
            model TEXT NOT NULL,
            endpoint_kind TEXT NOT NULL CHECK (
                endpoint_kind IN ('local', 'remote')
            ),
            prompt_version TEXT NOT NULL,
            schema_version TEXT NOT NULL,
            status TEXT NOT NULL CHECK (
                status IN ('ok', 'refused', 'invalid_output', 'error', 'fallback')
            ),
            error_code TEXT,
            attempts INTEGER NOT NULL DEFAULT 1,
            fallback_used INTEGER NOT NULL DEFAULT 0,
            input_tokens INTEGER,
            output_tokens INTEGER,
            total_tokens INTEGER,
            estimated_cost_usd REAL,
            latency_ms INTEGER,
            provider_request_id TEXT,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_coach_ai_runs_user_created
        ON coach_ai_runs(user_id, created_at)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_coach_ai_runs_goal_created
        ON coach_ai_runs(goal_id, created_at)
    """)
