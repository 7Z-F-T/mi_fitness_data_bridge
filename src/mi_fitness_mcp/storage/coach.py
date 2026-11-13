"""Persistence for the optional coach extension.

Only goals, generated plans, and AI-run metadata live here.  The store never
stores prompts, model responses, raw health samples, credentials, or the
minimized profile payload that was sent to a provider.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime
from typing import Any

from mi_fitness_mcp.storage import Database
from mi_fitness_mcp.storage.coach_schema import create_coach_schema


class CoachNotInitializedError(RuntimeError):
    """The writable schema has not been created in this database yet."""


GOAL_COLUMNS = (
    "id",
    "user_id",
    "goal_type",
    "sport",
    "title",
    "mode",
    "target_value",
    "baseline_value",
    "target_unit",
    "period",
    "start_date",
    "target_date",
    "race_distance",
    "target_time_seconds",
    "available_days",
    "max_sessions_per_week",
    "notes",
    "status",
    "achieved_at",
    "created_at",
    "updated_at",
)

GOAL_UPDATE_FIELDS = {
    "goal_type",
    "sport",
    "title",
    "mode",
    "target_value",
    "baseline_value",
    "target_unit",
    "period",
    "start_date",
    "target_date",
    "race_distance",
    "target_time_seconds",
    "available_days",
    "max_sessions_per_week",
    "notes",
    "status",
    "achieved_at",
}

PLAN_COLUMNS = (
    "id",
    "user_id",
    "goal_id",
    "status",
    "title",
    "start_date",
    "end_date",
    "weeks",
    "generated_by",
    "provider",
    "model",
    "prompt_version",
    "schema_version",
    "ai_run_id",
    "goal_snapshot_json",
    "plan_json",
    "validation_status",
    "validation_warnings_json",
    "created_at",
    "updated_at",
    "activated_at",
    "archived_at",
)

AI_RUN_COLUMNS = (
    "id",
    "user_id",
    "goal_id",
    "plan_id",
    "kind",
    "provider",
    "model",
    "endpoint_kind",
    "prompt_version",
    "schema_version",
    "status",
    "error_code",
    "attempts",
    "fallback_used",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "estimated_cost_usd",
    "latency_ms",
    "provider_request_id",
    "created_at",
)

AI_RUN_FIELDS = frozenset(AI_RUN_COLUMNS)
MAX_AI_RUNS_PER_USER = 200
_DATE_FIELDS = {"start_date", "target_date"}


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _as_dict(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return dict(value)


def _normalize_value(key: str, value: Any) -> Any:
    if key in _DATE_FIELDS and isinstance(value, date) and not isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _json_ready(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    return value


def _json_dump(value: Any) -> str:
    return json.dumps(
        _json_ready(value if value is not None else {}),
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _json_list_dump(value: Any) -> str:
    return json.dumps(
        _json_ready(value if value is not None else []),
        ensure_ascii=False,
        separators=(",", ":"),
    )


class CoachStore:
    """Small repository around the three coach tables."""

    def __init__(self, db: Database, *, user_id: str = "local") -> None:
        self.db = db
        self.user_id = user_id
        if not db.read_only:
            self.ensure_schema()

    def ensure_schema(self) -> None:
        if self.db.read_only:
            return
        try:
            if self.schema_initialized():
                return
        except Exception:
            pass
        with self.db._get_connection() as conn:
            create_coach_schema(conn)
            conn.commit()

    def schema_initialized(self) -> bool:
        with self.db._get_connection() as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' "
                "AND name IN ('coach_goals', 'coach_training_plans', 'coach_ai_runs')"
            ).fetchall()
        return len(rows) == 3

    def _require_schema(self) -> None:
        if not self.schema_initialized():
            raise CoachNotInitializedError(
                "Coach tables are not initialized; run a writable command first."
            )

    # ------------------------------------------------------------------ goals

    def insert_goal(self, goal: Any) -> dict[str, Any]:
        self._require_schema()
        data = _as_dict(goal)
        now = _now_iso()
        values = {
            "id": data.get("id") or uuid.uuid4().hex,
            "user_id": data.get("user_id") or self.user_id,
            "goal_type": data["goal_type"],
            "sport": data.get("sport") or "any",
            "title": data["title"],
            "mode": data.get("mode") or "target",
            "target_value": data.get("target_value"),
            "baseline_value": data.get("baseline_value"),
            "target_unit": data["target_unit"],
            "period": data.get("period") or "week",
            "start_date": _normalize_value("start_date", data["start_date"]),
            "target_date": _normalize_value("target_date", data.get("target_date")),
            "race_distance": data.get("race_distance"),
            "target_time_seconds": data.get("target_time_seconds"),
            "available_days": data.get("available_days"),
            "max_sessions_per_week": data.get("max_sessions_per_week"),
            "notes": data.get("notes"),
            "status": data.get("status") or "active",
            "achieved_at": data.get("achieved_at"),
            "created_at": data.get("created_at") or now,
            "updated_at": data.get("updated_at") or now,
        }
        placeholders = ", ".join("?" for _ in GOAL_COLUMNS)
        with self.db._get_connection() as conn:
            conn.execute(
                f"INSERT INTO coach_goals ({', '.join(GOAL_COLUMNS)}) VALUES ({placeholders})",
                [values[column] for column in GOAL_COLUMNS],
            )
            conn.commit()
        result = self.get_goal(values["id"])
        assert result is not None
        return result

    def update_goal(self, goal_id: str, changes: Any) -> dict[str, Any] | None:
        self._require_schema()
        data = _as_dict(changes)
        allowed = {
            key: _normalize_value(key, value)
            for key, value in data.items()
            if key in GOAL_UPDATE_FIELDS and value is not None
        }
        if not allowed:
            return self.get_goal(goal_id)
        allowed["updated_at"] = _now_iso()
        assignments = ", ".join(f"{column} = ?" for column in allowed)
        params = [*allowed.values(), goal_id, self.user_id]
        with self.db._get_connection() as conn:
            cursor = conn.execute(
                f"UPDATE coach_goals SET {assignments} WHERE id = ? AND user_id = ?",
                params,
            )
            conn.commit()
            if cursor.rowcount == 0:
                return None
        return self.get_goal(goal_id)

    def get_goal(self, goal_id: str) -> dict[str, Any] | None:
        self._require_schema()
        with self.db._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM coach_goals WHERE id = ? AND user_id = ?",
                (goal_id, self.user_id),
            ).fetchone()
        return dict(row) if row is not None else None

    def list_goals(
        self, *, status: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        self._require_schema()
        sql = "SELECT * FROM coach_goals WHERE user_id = ?"
        params: list[Any] = [self.user_id]
        if status:
            sql += " AND status = ?"
            params.append(status)
        sql += " ORDER BY created_at DESC, id DESC LIMIT ?"
        params.append(limit)
        with self.db._get_connection() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def count_goals(self, *, status: str | None = None) -> int:
        self._require_schema()
        sql = "SELECT COUNT(*) AS n FROM coach_goals WHERE user_id = ?"
        params: list[Any] = [self.user_id]
        if status:
            sql += " AND status = ?"
            params.append(status)
        with self.db._get_connection() as conn:
            row = conn.execute(sql, params).fetchone()
        return int(row["n"]) if row is not None else 0

    # ------------------------------------------------------------------ plans

    def insert_plan(self, plan: Any) -> dict[str, Any]:
        self._require_schema()
        data = _as_dict(plan)
        now = _now_iso()
        goal_snapshot = data.get("goal_snapshot", data.get("goal_snapshot_json"))
        plan_body = data.get("plan", data.get("plan_json"))
        warnings = data.get("validation_warnings", data.get("validation_warnings_json"))
        values = {
            "id": data.get("id") or uuid.uuid4().hex,
            "user_id": data.get("user_id") or self.user_id,
            "goal_id": data["goal_id"],
            "status": data.get("status") or "draft",
            "title": data["title"],
            "start_date": _normalize_value("start_date", data["start_date"]),
            "end_date": _normalize_value("end_date", data["end_date"]),
            "weeks": int(data["weeks"]),
            "generated_by": data["generated_by"],
            "provider": data.get("provider"),
            "model": data.get("model"),
            "prompt_version": data.get("prompt_version"),
            "schema_version": data["schema_version"],
            "ai_run_id": data.get("ai_run_id"),
            "goal_snapshot_json": (
                goal_snapshot
                if isinstance(goal_snapshot, str)
                else _json_dump(goal_snapshot)
            ),
            "plan_json": (
                plan_body if isinstance(plan_body, str) else _json_dump(plan_body)
            ),
            "validation_status": data["validation_status"],
            "validation_warnings_json": (
                warnings if isinstance(warnings, str) else _json_list_dump(warnings)
            ),
            "created_at": data.get("created_at") or now,
            "updated_at": data.get("updated_at") or now,
            "activated_at": data.get("activated_at"),
            "archived_at": data.get("archived_at"),
        }
        placeholders = ", ".join("?" for _ in PLAN_COLUMNS)
        with self.db._get_connection() as conn:
            conn.execute(
                f"INSERT INTO coach_training_plans ({', '.join(PLAN_COLUMNS)}) "
                f"VALUES ({placeholders})",
                [values[column] for column in PLAN_COLUMNS],
            )
            conn.commit()
        result = self.get_plan(values["id"])
        assert result is not None
        return result

    @staticmethod
    def _plan_row(row: Any) -> dict[str, Any]:
        data = dict(row)
        for raw_key, parsed_key, default in (
            ("goal_snapshot_json", "goal_snapshot", {}),
            ("plan_json", "plan", {}),
            ("validation_warnings_json", "validation_warnings", []),
        ):
            raw = data.pop(raw_key, None)
            try:
                data[parsed_key] = json.loads(raw) if raw else default
            except (TypeError, json.JSONDecodeError):
                data[parsed_key] = default
        return data

    def get_plan(self, plan_id: str) -> dict[str, Any] | None:
        self._require_schema()
        with self.db._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM coach_training_plans WHERE id = ? AND user_id = ?",
                (plan_id, self.user_id),
            ).fetchone()
        return self._plan_row(row) if row is not None else None

    def list_plans(
        self,
        *,
        goal_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        self._require_schema()
        sql = "SELECT * FROM coach_training_plans WHERE user_id = ?"
        params: list[Any] = [self.user_id]
        if goal_id:
            sql += " AND goal_id = ?"
            params.append(goal_id)
        if status:
            sql += " AND status = ?"
            params.append(status)
        sql += " ORDER BY created_at DESC, id DESC LIMIT ?"
        params.append(limit)
        with self.db._get_connection() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._plan_row(row) for row in rows]

    def get_active_plan(self, goal_id: str) -> dict[str, Any] | None:
        self._require_schema()
        with self.db._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM coach_training_plans "
                "WHERE user_id = ? AND goal_id = ? AND status = 'active'",
                (self.user_id, goal_id),
            ).fetchone()
        return self._plan_row(row) if row is not None else None

    def activate_plan(self, plan_id: str, goal_id: str) -> dict[str, Any] | None:
        self._require_schema()
        existing = self.get_plan(plan_id)
        if existing is None or existing.get("goal_id") != goal_id:
            return None
        now = _now_iso()
        with self.db._get_connection() as conn:
            conn.execute(
                "UPDATE coach_training_plans SET status = 'superseded', updated_at = ? "
                "WHERE user_id = ? AND goal_id = ? AND status = 'active' AND id <> ?",
                (now, self.user_id, goal_id, plan_id),
            )
            cursor = conn.execute(
                "UPDATE coach_training_plans SET status = 'active', activated_at = ?, "
                "updated_at = ? WHERE id = ? AND user_id = ? AND goal_id = ?",
                (now, now, plan_id, self.user_id, goal_id),
            )
            conn.commit()
            if cursor.rowcount == 0:
                return None
        return self.get_plan(plan_id)

    def archive_plan(self, plan_id: str) -> dict[str, Any] | None:
        self._require_schema()
        now = _now_iso()
        with self.db._get_connection() as conn:
            cursor = conn.execute(
                "UPDATE coach_training_plans SET status = 'archived', archived_at = ?, "
                "updated_at = ? WHERE id = ? AND user_id = ?",
                (now, now, plan_id, self.user_id),
            )
            conn.commit()
            if cursor.rowcount == 0:
                return None
        return self.get_plan(plan_id)

    # ---------------------------------------------------------------- ai runs

    def record_ai_run(self, run: Any) -> str:
        self._require_schema()
        data = _as_dict(run)
        filtered = {key: value for key, value in data.items() if key in AI_RUN_FIELDS}
        filtered.setdefault("id", uuid.uuid4().hex)
        filtered.setdefault("user_id", self.user_id)
        filtered.setdefault("attempts", 1)
        filtered.setdefault("fallback_used", 0)
        filtered.setdefault("created_at", _now_iso())
        if isinstance(filtered.get("fallback_used"), bool):
            filtered["fallback_used"] = int(filtered["fallback_used"])
        columns = [column for column in AI_RUN_COLUMNS if column in filtered]
        placeholders = ", ".join("?" for _ in columns)
        with self.db._get_connection() as conn:
            conn.execute(
                f"INSERT INTO coach_ai_runs ({', '.join(columns)}) VALUES ({placeholders})",
                [filtered[column] for column in columns],
            )
            conn.execute(
                "DELETE FROM coach_ai_runs WHERE user_id = ? AND id NOT IN ("
                "SELECT id FROM coach_ai_runs WHERE user_id = ? "
                "ORDER BY created_at DESC, id DESC LIMIT ?)",
                (self.user_id, self.user_id, MAX_AI_RUNS_PER_USER),
            )
            conn.commit()
        return str(filtered["id"])

    def list_ai_runs(self, *, limit: int = 20) -> list[dict[str, Any]]:
        self._require_schema()
        with self.db._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM coach_ai_runs WHERE user_id = ? "
                "ORDER BY created_at DESC, id DESC LIMIT ?",
                (self.user_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def latest_ai_run(self) -> dict[str, Any] | None:
        runs = self.list_ai_runs(limit=1)
        return runs[0] if runs else None
