"""Read/write service bridge for the local coach web API."""

from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path
from typing import Any

from mi_fitness_mcp.auth import coach_llm_key_configured, load_mi_fitness_token
from mi_fitness_mcp.coach.llm.base import LLMErrorCode, LLMProviderError
from mi_fitness_mcp.coach.models import GoalCreate, GoalUpdate
from mi_fitness_mcp.coach.service import CoachDisabledError as CoachServiceDisabledError
from mi_fitness_mcp.coach.service import (
    CoachLLMUnavailableError,
    CoachService,
)
from mi_fitness_mcp.config import Config, load_config
from mi_fitness_mcp.services.query_service import QueryService
from mi_fitness_mcp.storage import Database
from mi_fitness_mcp.storage.coach import CoachNotInitializedError, CoachStore
from mi_fitness_mcp.web import exceptions
from mi_fitness_mcp.web.coach_schemas import (
    CoachGeneratePlanRequest,
    CoachGoalCreateRequest,
    CoachGoalUpdateRequest,
)


class CoachWebService:
    def __init__(self, db_path: Path | str, *, config: Config | None = None) -> None:
        self.db_path = Path(db_path)
        self.config = config or load_config()
        self._read_service: CoachService | None = None
        self._write_service: CoachService | None = None

    def _resolve_user_id(self, db: Database) -> str:
        user_id, _ = load_mi_fitness_token()
        if user_id:
            return user_id
        try:
            with db._get_connection() as conn:
                tables = {
                    row["name"]
                    for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    ).fetchall()
                }
                for table in (
                    "workouts",
                    "daily_activity",
                    "sleep_sessions",
                    "body_measurements",
                ):
                    if table not in tables:
                        continue
                    row = conn.execute(
                        f"SELECT user_id, COUNT(*) AS n FROM {table} "
                        "WHERE user_id IS NOT NULL GROUP BY user_id "
                        "ORDER BY n DESC LIMIT 1"
                    ).fetchone()
                    if row is not None and row["user_id"]:
                        return str(row["user_id"])
        except Exception:
            pass
        return "local"

    def _build(self, *, writable: bool) -> CoachService:
        try:
            db = Database(self.db_path, read_only=not writable)
        except FileNotFoundError as exc:
            raise exceptions.CoachNotInitializedError() from exc
        store = CoachStore(db)
        try:
            initialized = store.schema_initialized()
        except FileNotFoundError as exc:
            raise exceptions.CoachNotInitializedError() from exc
        if not initialized:
            raise exceptions.CoachNotInitializedError()
        service = CoachService(
            store,
            QueryService(db, self._resolve_user_id(db)),
            self.config.coach,
            timezone=self.config.timezone,
        )
        return service

    def read(self) -> CoachService:
        if self._read_service is None:
            self._read_service = self._build(writable=False)
        return self._read_service

    def write(self) -> CoachService:
        if self._write_service is None:
            self._write_service = self._build(writable=True)
        return self._write_service

    def status(self) -> dict[str, Any]:
        try:
            return self.read().status()
        except exceptions.CoachNotInitializedError:
            return self._empty_status()

    def _empty_status(self) -> dict[str, Any]:
        return {
            "enabled": self.config.coach.enabled,
            "language": self.config.coach.language,
            "profile_weeks": self.config.coach.profile_weeks,
            "default_plan_weeks": self.config.coach.default_plan_weeks,
            "allow_deterministic_fallback": (
                self.config.coach.allow_deterministic_fallback
            ),
            "provider": self.config.coach.llm.provider,
            "model": self.config.coach.llm.model,
            "base_url": self.config.coach.llm.base_url,
            "key_configured": (
                coach_llm_key_configured(self.config.coach.llm.provider)
                if self.config.coach.enabled
                else False
            ),
            "anthropic_extra_available": (
                importlib.util.find_spec("anthropic") is not None
            ),
            "remote_consent_at": self.config.coach.llm.remote_consent_at,
            "schema_initialized": False,
            "goal_count": 0,
            "plan_count": 0,
            "latest_ai_run": None,
        }

    def overview(self, weeks: int | None = None) -> dict[str, Any]:
        return self.read().overview(weeks)

    def profile(
        self, weeks: int | None, goal_id: str | None, format_: str
    ) -> dict[str, Any]:
        service = self.read()
        if format_ == "llm":
            return {"payload": service.llm_payload(weeks, goal_id)}
        return {"profile": service.profile(weeks).model_dump(mode="json")}

    def list_goals(self, status: str = "active"):
        return self.read().list_goals(status)

    def get_goal(self, goal_id: str):
        try:
            return self.read().get_goal(goal_id)
        except KeyError as exc:
            raise exceptions.CoachGoalNotFoundError() from exc

    def create_goal(self, request: CoachGoalCreateRequest):
        goal_type = request.goal_type
        mode = request.mode
        payload = request.model_dump(exclude_none=True)
        payload.pop("goal_type", None)
        payload["goal_type"] = goal_type
        payload["mode"] = mode
        payload.setdefault("sport", "running" if goal_type == "race" else "any")
        payload.setdefault("start_date", date.today())
        if not payload.get("target_unit"):
            payload["target_unit"] = _default_unit(goal_type)
        if not payload.get("period"):
            payload["period"] = _default_period(goal_type, mode)
        try:
            goal = self.write().create_goal(GoalCreate.model_validate(payload))
            return self.write().get_goal(goal.id)
        except (ValueError, TypeError) as exc:
            raise exceptions.CoachValidationError(str(exc)) from exc

    def update_goal(self, goal_id: str, request: CoachGoalUpdateRequest):
        changes = request.model_dump(exclude_unset=True, exclude_none=True)
        try:
            self.write().update_goal(goal_id, GoalUpdate.model_validate(changes))
            return self.write().get_goal(goal_id)
        except KeyError as exc:
            raise exceptions.CoachGoalNotFoundError() from exc
        except (ValueError, TypeError) as exc:
            raise exceptions.CoachValidationError(str(exc)) from exc

    def archive_goal(self, goal_id: str):
        try:
            return self.write().archive_goal(goal_id)
        except KeyError as exc:
            raise exceptions.CoachGoalNotFoundError() from exc

    async def recommend(
        self, weeks: int | None, *, use_llm: bool, consent: bool
    ) -> list[Any]:
        try:
            service = self.write() if use_llm else self.read()
            if use_llm:
                return await service.recommend_goals_ai(weeks, consent=consent)
            return service.recommend_goals(weeks)
        except Exception as exc:
            self._raise_mapped(exc)

    def list_plans(self, goal_id: str | None, status: str | None):
        return self.read().list_plans(goal_id=goal_id, status=status)

    def get_plan(self, plan_id: str) -> dict[str, Any]:
        try:
            return self.read().get_plan(plan_id)
        except KeyError as exc:
            raise exceptions.CoachPlanNotFoundError() from exc

    async def generate_plan(self, request: CoachGeneratePlanRequest):
        try:
            service = self.write()
            if request.use_llm:
                return await service.generate_plan_ai(
                    request.goal_id,
                    weeks=request.weeks,
                    days_per_week=request.days_per_week,
                    session_minutes=request.session_minutes,
                    consent=request.consent,
                    activate=request.activate,
                )
            return service.generate_plan(
                request.goal_id,
                weeks=request.weeks,
                days_per_week=request.days_per_week,
                session_minutes=request.session_minutes,
                activate=request.activate,
            )
        except Exception as exc:
            self._raise_mapped(exc)

    def activate_plan(self, plan_id: str):
        try:
            return self.write().activate_plan(plan_id)
        except KeyError as exc:
            raise exceptions.CoachPlanNotFoundError() from exc

    def archive_plan(self, plan_id: str):
        try:
            return self.write().archive_plan(plan_id)
        except KeyError as exc:
            raise exceptions.CoachPlanNotFoundError() from exc

    def _raise_mapped(self, exc: Exception) -> None:
        if isinstance(exc, exceptions.ApiError):
            raise exc
        if isinstance(exc, LLMProviderError):
            raise _llm_api_error(exc) from exc
        if isinstance(exc, CoachServiceDisabledError):
            raise exceptions.CoachDisabledError(str(exc)) from exc
        if isinstance(exc, CoachLLMUnavailableError):
            raise exceptions.CoachDisabledError(str(exc)) from exc
        if isinstance(exc, CoachNotInitializedError):
            raise exceptions.CoachNotInitializedError() from exc
        if isinstance(exc, KeyError):
            message = str(exc)
            if "Plan" in message:
                raise exceptions.CoachPlanNotFoundError() from exc
            raise exceptions.CoachGoalNotFoundError() from exc
        if isinstance(exc, (ValueError, TypeError)):
            raise exceptions.CoachValidationError(str(exc)) from exc
        raise exc


def _llm_api_error(exc: LLMProviderError) -> exceptions.ApiError:
    if exc.code == LLMErrorCode.CONSENT_REQUIRED:
        return exceptions.CoachLLMError(
            str(exc), code="LLM_CONSENT_REQUIRED", status_code=409
        )
    if exc.code == LLMErrorCode.KEY_MISSING:
        return exceptions.CoachLLMError(
            str(exc), code="LLM_NOT_CONFIGURED", status_code=409
        )
    if exc.code == LLMErrorCode.EXTRA_MISSING:
        return exceptions.CoachLLMError(
            str(exc), code="COACH_EXTRA_MISSING", status_code=409
        )
    if exc.code == LLMErrorCode.TIMEOUT:
        return exceptions.CoachLLMError(
            str(exc), code="LLM_TIMEOUT", status_code=504
        )
    if exc.code in {
        LLMErrorCode.REFUSED,
        LLMErrorCode.CONTENT_FILTERED,
        LLMErrorCode.INVALID_OUTPUT,
    }:
        return exceptions.CoachLLMError(
            str(exc), code="LLM_OUTPUT_REJECTED", status_code=502
        )
    return exceptions.CoachLLMError(str(exc), code="LLM_UNAVAILABLE", status_code=502)


def _default_unit(goal_type: str) -> str:
    return {
        "weekly_frequency": "sessions_per_week",
        "weekly_duration": "minutes_per_week",
        "race": "seconds",
        "distance": "meters",
        "body_composition": "kg",
    }.get(goal_type, "sessions_per_week")


def _default_period(goal_type: str, mode: str) -> str:
    if goal_type == "body_composition":
        return "rolling_28d" if mode == "trend" else "target_date"
    if goal_type == "race":
        return "target_date"
    return "week"
