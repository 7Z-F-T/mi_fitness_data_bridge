"""Persistence and activation for generated training plans."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from mi_fitness_mcp.coach.models import (
    Goal,
    PlanValidationResult,
    TrainingPlan,
    TrainingPlanContent,
)
from mi_fitness_mcp.storage.coach import CoachStore

SCHEMA_VERSION = "coach-plan-schema-v1"


class TrainingPlanService:
    def __init__(self, store: CoachStore) -> None:
        self.store = store

    def create_draft(
        self,
        goal: Goal,
        content: TrainingPlanContent,
        validation: PlanValidationResult,
        *,
        generated_by: str,
        provider: str | None = None,
        model: str | None = None,
        prompt_version: str | None = None,
        ai_run_id: str | None = None,
        activate: bool = False,
    ) -> TrainingPlan:
        start_date = content.weeks[0].start_date
        end_date = content.weeks[-1].start_date + timedelta(days=6)
        warnings = [
            f"{issue.code}: {issue.message}" for issue in validation.issues
        ]
        goal_snapshot = goal.model_dump(mode="json")
        goal_snapshot.pop("user_id", None)
        stored = self.store.insert_plan(
            {
                "goal_id": goal.id,
                "title": content.title,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "weeks": len(content.weeks),
                "generated_by": generated_by,
                "provider": provider,
                "model": model,
                "prompt_version": prompt_version,
                "schema_version": SCHEMA_VERSION,
                "ai_run_id": ai_run_id,
                "goal_snapshot": goal_snapshot,
                "plan": content.model_dump(mode="json"),
                "validation_status": validation.status,
                "validation_warnings": warnings,
            }
        )
        if activate:
            activated = self.store.activate_plan(stored["id"], goal.id)
            if activated is not None:
                stored = activated
        return TrainingPlan.model_validate(stored)

    def get(self, plan_id: str) -> TrainingPlan:
        row = self.store.get_plan(plan_id)
        if row is None:
            raise KeyError(f"Plan not found: {plan_id}")
        return TrainingPlan.model_validate(row)

    def list(
        self, *, goal_id: str | None = None, status: str | None = None
    ) -> list[TrainingPlan]:
        return [
            TrainingPlan.model_validate(row)
            for row in self.store.list_plans(goal_id=goal_id, status=status)
        ]

    def activate(self, plan_id: str) -> TrainingPlan:
        plan = self.get(plan_id)
        stored = self.store.activate_plan(plan_id, plan.goal_id)
        if stored is None:
            raise KeyError(f"Plan not found: {plan_id}")
        return TrainingPlan.model_validate(stored)

    def archive(self, plan_id: str) -> TrainingPlan:
        stored = self.store.archive_plan(plan_id)
        if stored is None:
            raise KeyError(f"Plan not found: {plan_id}")
        return TrainingPlan.model_validate(stored)

    def active_for_goal(self, goal_id: str) -> TrainingPlan | None:
        row = self.store.get_active_plan(goal_id)
        return TrainingPlan.model_validate(row) if row is not None else None

    @staticmethod
    def warnings_text(plan: TrainingPlan) -> list[str]:
        return list(plan.validation_warnings)

    @staticmethod
    def snapshot(plan: TrainingPlan) -> dict[str, Any]:
        return plan.goal_snapshot
