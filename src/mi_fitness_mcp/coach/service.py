"""Orchestration for the optional local coach extension."""

from __future__ import annotations

import contextlib
import importlib.util
from datetime import date, timedelta
from typing import Any

from mi_fitness_mcp.auth import coach_llm_key_configured
from mi_fitness_mcp.coach.goals import GoalService
from mi_fitness_mcp.coach.llm.base import LLMErrorCode, LLMProviderError, LLMRequest
from mi_fitness_mcp.coach.llm.factory import (
    ProviderFactory,
    build_provider,
    endpoint_kind,
    require_egress_allowed,
)
from mi_fitness_mcp.coach.llm.runner import LLMRunner
from mi_fitness_mcp.coach.llm.schemas import (
    GoalRecommendationBatch,
    TrainingPlanDraft,
    materialize_plan,
    to_provider_schema,
)
from mi_fitness_mcp.coach.models import (
    Goal,
    GoalCreate,
    GoalRecommendation,
    GoalUpdate,
    GoalWithProgress,
    PlanGenerationConstraints,
    PlanValidationIssue,
    PlanValidationResult,
    TrainingPlan,
    TrainingProfile,
)
from mi_fitness_mcp.coach.plans import TrainingPlanService
from mi_fitness_mcp.coach.profile import TrainingProfileBuilder
from mi_fitness_mcp.coach.prompts import (
    GOAL_SCHEMA_NAME,
    PAYLOAD_VERSION,
    PLAN_SCHEMA_NAME,
    PROMPT_VERSION_GOALS,
    PROMPT_VERSION_PLAN,
    build_goal_user_prompt,
    build_plan_user_prompt,
    build_repair_prompt,
    goal_system_prompt,
    plan_system_prompt,
)
from mi_fitness_mcp.coach.templates import build_template_plan
from mi_fitness_mcp.coach.validation import PlanValidator
from mi_fitness_mcp.config import CoachConfig
from mi_fitness_mcp.services.query_service import QueryService
from mi_fitness_mcp.storage.coach import CoachStore


class CoachDisabledError(RuntimeError):
    """AI generation is disabled or not configured."""


class CoachLLMUnavailableError(RuntimeError):
    """The provider layer is not available in this installation."""


class CoachService:
    """Coordinates deterministic profile/goal features and optional LLM calls."""

    def __init__(
        self,
        store: CoachStore,
        query: QueryService | None,
        config: CoachConfig,
        *,
        timezone: str = "UTC",
        today: date | None = None,
        user_id: str = "local",
        provider_factory: ProviderFactory | None = None,
    ) -> None:
        self.store = store
        self.query = query
        self.config = config
        self.timezone = timezone
        self.today = today
        self.user_id = user_id
        self.provider_factory = provider_factory
        self.goals = GoalService(
            store,
            query,
            timezone,
            today=today,
            language=config.language,
        )
        self.profile_builder = TrainingProfileBuilder(
            query, timezone=timezone, today=today
        ) if query is not None else None
        self.plans = TrainingPlanService(store)

    def status(self) -> dict[str, Any]:
        provider = self.config.llm.provider
        base_url = self.config.llm.base_url
        latest_run = None
        try:
            latest_run = self.store.latest_ai_run()
        except Exception:
            latest_run = None
        return {
            "enabled": self.config.enabled,
            "language": self.config.language,
            "profile_weeks": self.config.profile_weeks,
            "default_plan_weeks": self.config.default_plan_weeks,
            "allow_deterministic_fallback": self.config.allow_deterministic_fallback,
            "provider": provider,
            "model": self.config.llm.model,
            "base_url": base_url,
            "key_configured": (
                coach_llm_key_configured(provider) if self.config.enabled else False
            ),
            "anthropic_extra_available": (
                importlib.util.find_spec("anthropic") is not None
            ),
            "remote_consent_at": self.config.llm.remote_consent_at,
            "schema_initialized": self.store.schema_initialized(),
            "goal_count": self.store.count_goals(),
            "plan_count": len(self.store.list_plans(limit=500)),
            "latest_ai_run": latest_run,
        }

    def profile(self, weeks: int | None = None) -> TrainingProfile:
        if self.profile_builder is None:
            raise CoachLLMUnavailableError("Query service is not available")
        return self.profile_builder.build(weeks or self.config.profile_weeks)

    def llm_payload(
        self,
        weeks: int | None = None,
        goal_id: str | None = None,
        language: str | None = None,
    ) -> dict[str, Any]:
        if self.profile_builder is None:
            raise CoachLLMUnavailableError("Query service is not available")
        goal = self.goals.get(goal_id).goal if goal_id else None
        profile = self.profile(weeks)
        return self.profile_builder.build_llm_payload(
            profile,
            goal=goal,
            language=language or self.config.language,
            include_body_context=(
                goal is not None and goal.goal_type == "body_composition"
            ),
        )

    # ------------------------------------------------------------------ goals

    def list_goals(self, status: str = "active") -> list[GoalWithProgress]:
        return self.goals.list(status)

    def get_goal(self, goal_id: str) -> GoalWithProgress:
        return self.goals.get(goal_id)

    def create_goal(self, data: GoalCreate | dict[str, Any]) -> Goal:
        return self.goals.create(data)

    def update_goal(self, goal_id: str, changes: GoalUpdate | dict[str, Any]) -> Goal:
        return self.goals.update(goal_id, changes)

    def archive_goal(self, goal_id: str) -> Goal:
        return self.goals.archive(goal_id)

    def recommend_goals(
        self,
        weeks: int | None = None,
        *,
        use_llm: bool = False,
        consent: bool = False,
    ) -> list[GoalRecommendation]:
        if use_llm:
            raise CoachLLMUnavailableError(
                "Use recommend_goals_ai() for a model call."
            )
        profile = self.profile(weeks)
        return self.goals.recommend(profile)

    async def recommend_goals_ai(
        self,
        weeks: int | None = None,
        *,
        consent: bool = True,
    ) -> list[GoalRecommendation]:
        self.ensure_llm_ready(consent=consent)
        profile = self.profile(weeks)
        candidates = self.goals.recommend(profile)
        if profile.data_quality.status == "insufficient" or not profile.weekly:
            return candidates
        assert self.profile_builder is not None
        payload = self.profile_builder.build_llm_payload(
            profile, language=self.config.language
        )
        provider = build_provider(
            self.config.llm, provider_factory=self.provider_factory
        )
        runner = LLMRunner(self.store, self.config)
        request = LLMRequest(
            system=goal_system_prompt(self.config.language),
            user=build_goal_user_prompt(
                payload, candidates, language=self.config.language
            ),
            schema_name=GOAL_SCHEMA_NAME,
            schema=to_provider_schema(GoalRecommendationBatch),
            max_output_tokens=self.config.llm.max_output_tokens,
            temperature=self.config.llm.temperature,
        )
        try:
            result = await runner.run(
                provider,
                request,
                kind="goal_recommendation",
                prompt_version=PROMPT_VERSION_GOALS,
                schema_version=PAYLOAD_VERSION,
            )
        except LLMProviderError:
            if self.config.allow_deterministic_fallback:
                return candidates
            raise
        finally:
            await _close_provider(provider)
        if result.refused:
            return candidates
        try:
            batch = GoalRecommendationBatch.model_validate(result.data)
        except ValueError:
            runner.record_semantic_failure(
                result,
                provider=provider,
                kind="goal_recommendation",
                prompt_version=PROMPT_VERSION_GOALS,
                schema_version=PAYLOAD_VERSION,
            )
            return candidates
        recommendations: list[GoalRecommendation] = []
        for draft in batch.recommendations[:3]:
            try:
                recommendations.append(
                    self._goal_recommendation_from_draft(draft, profile)
                )
            except (ValueError, TypeError):
                continue
        if not recommendations:
            runner.record_semantic_failure(
                result,
                provider=provider,
                kind="goal_recommendation",
                prompt_version=PROMPT_VERSION_GOALS,
                schema_version=PAYLOAD_VERSION,
            )
            return candidates
        return recommendations

    def _goal_recommendation_from_draft(
        self, draft: Any, profile: TrainingProfile
    ) -> GoalRecommendation:
        target_date = None
        needs_target_date = draft.goal_type == "race" or (
            draft.goal_type == "body_composition" and draft.mode == "target"
        ) or (draft.goal_type == "distance" and draft.period == "target_date")
        if needs_target_date:
            weeks_until = draft.weeks_until_target or 12
            target_date = self.goals.today + timedelta(weeks=weeks_until)
        candidate = {
            "goal_type": draft.goal_type,
            "sport": draft.sport,
            "title": draft.title,
            "mode": draft.mode,
            "target_value": draft.target_value,
            "target_unit": draft.target_unit,
            "period": draft.period,
            "start_date": self.goals.today,
            "target_date": target_date,
            "race_distance": draft.race_distance,
            "target_time_seconds": draft.target_time_seconds,
            "rationale": draft.rationale,
            "evidence": draft.evidence,
            "confidence": draft.confidence,
        }
        validated = self.goals.validate_llm_recommendation(candidate)
        return GoalRecommendation(
            goal_type=validated.goal_type,
            sport=validated.sport,
            title=validated.title,
            mode=validated.mode,
            target_value=validated.target_value,
            target_unit=validated.target_unit,
            period=validated.period,
            start_date=validated.start_date,
            target_date=validated.target_date,
            race_distance=validated.race_distance,
            target_time_seconds=validated.target_time_seconds,
            baseline_value=validated.baseline_value,
            rationale=draft.rationale,
            evidence=list(draft.evidence),
            confidence=draft.confidence,
            data_gaps=list(dict.fromkeys([*draft.data_gaps, *profile.data_quality.caveats])),
            source="ai_recommended",
        )

    def ensure_llm_ready(self, *, consent: bool) -> None:
        if not self.config.enabled:
            raise CoachDisabledError(
                "Coach AI is disabled; run `mi-fitness-bridge coach setup` first."
            )
        if not consent:
            raise LLMProviderError(
                LLMErrorCode.CONSENT_REQUIRED,
                "Explicit consent is required for an AI call.",
            )
        require_egress_allowed(self.config.llm, per_call_consent=True)
        if endpoint_kind(self.config.llm) == "remote" and not coach_llm_key_configured(
            self.config.llm.provider
        ):
            raise CoachDisabledError(
                "Coach LLM API key is not configured; run `mi-fitness-bridge coach setup`."
            )

    # ------------------------------------------------------------------ plans

    def list_plans(
        self, *, goal_id: str | None = None, status: str | None = None
    ) -> list[dict[str, Any]]:
        return self.store.list_plans(goal_id=goal_id, status=status)

    def get_plan(self, plan_id: str) -> dict[str, Any]:
        plan = self.store.get_plan(plan_id)
        if plan is None:
            raise KeyError(f"Plan not found: {plan_id}")
        return plan

    def generate_plan(
        self,
        goal_id: str,
        *,
        weeks: int | None = None,
        days_per_week: int | None = None,
        session_minutes: int | None = None,
        start_date: date | None = None,
        use_llm: bool = False,
        consent: bool = False,
        activate: bool = False,
    ) -> TrainingPlan:
        if use_llm:
            raise CoachLLMUnavailableError(
                "Use generate_plan_ai() for a model call."
            )
        goal, profile, constraints = self._plan_inputs(
            goal_id,
            weeks=weeks,
            days_per_week=days_per_week,
            session_minutes=session_minutes,
            start_date=start_date,
            activate=activate,
        )
        return self._save_template_plan(goal, profile, constraints)

    async def generate_plan_ai(
        self,
        goal_id: str,
        *,
        weeks: int | None = None,
        days_per_week: int | None = None,
        session_minutes: int | None = None,
        start_date: date | None = None,
        consent: bool = True,
        activate: bool = False,
    ) -> TrainingPlan:
        self.ensure_llm_ready(consent=consent)
        goal, profile, constraints = self._plan_inputs(
            goal_id,
            weeks=weeks,
            days_per_week=days_per_week,
            session_minutes=session_minutes,
            start_date=start_date,
            activate=activate,
        )
        if profile.data_quality.status == "insufficient":
            return self._fallback_plan(
                goal, profile, constraints, "训练数据不足，已使用本地安全模板。"
            )
        assert self.profile_builder is not None
        payload = self.profile_builder.build_llm_payload(
            profile,
            goal=goal,
            language=self.config.language,
            include_body_context=goal.goal_type == "body_composition",
        )
        user_prompt = build_plan_user_prompt(
            payload,
            goal,
            today=self.goals.today,
            weeks=constraints.weeks,
            days_per_week=constraints.days_per_week,
            session_minutes=constraints.session_minutes,
            language=self.config.language,
        )
        provider = build_provider(
            self.config.llm, provider_factory=self.provider_factory
        )
        runner = LLMRunner(self.store, self.config)
        request = LLMRequest(
            system=plan_system_prompt(self.config.language),
            user=user_prompt,
            schema_name=PLAN_SCHEMA_NAME,
            schema=to_provider_schema(TrainingPlanDraft),
            max_output_tokens=self.config.llm.max_output_tokens,
            temperature=self.config.llm.temperature,
        )
        try:
            try:
                result = await runner.run(
                    provider,
                    request,
                    kind="plan_generation",
                    prompt_version=PROMPT_VERSION_PLAN,
                    schema_version=PAYLOAD_VERSION,
                    goal_id=goal.id,
                )
            except LLMProviderError as exc:
                if self.config.allow_deterministic_fallback:
                    runner.record_fallback(
                        provider=provider,
                        kind="plan_generation",
                        prompt_version=PROMPT_VERSION_PLAN,
                        schema_version=PAYLOAD_VERSION,
                        goal_id=goal.id,
                    )
                    return self._fallback_plan(
                        goal,
                        profile,
                        constraints,
                        f"AI 调用失败（{exc.code.value}），已使用本地安全模板。",
                    )
                raise
            if result.refused:
                return self._fallback_plan(
                    goal, profile, constraints, "AI 拒绝了请求，已使用本地安全模板。"
                )
            try:
                content, validation = self._materialize_and_validate(
                    result, goal, profile, constraints
                )
            except ValueError as exc:
                runner.record_semantic_failure(
                    result,
                    provider=provider,
                    kind="plan_generation",
                    prompt_version=PROMPT_VERSION_PLAN,
                    schema_version=PAYLOAD_VERSION,
                    goal_id=goal.id,
                )
                return self._fallback_plan(
                    goal,
                    profile,
                    constraints,
                    f"AI 输出无法解析（{type(exc).__name__}），已使用本地安全模板。",
                )
            if validation.status == "failed":
                issues = [
                    f"{issue.code}: {issue.message}" for issue in validation.errors
                ]
                repair = LLMRequest(
                    system=request.system,
                    user=build_repair_prompt(
                        user_prompt, issues, self.config.language
                    ),
                    schema_name=request.schema_name,
                    schema=request.schema,
                    max_output_tokens=request.max_output_tokens,
                    temperature=request.temperature,
                )
                try:
                    result = await runner.run(
                        provider,
                        repair,
                        kind="plan_generation",
                        prompt_version=PROMPT_VERSION_PLAN,
                        schema_version=PAYLOAD_VERSION,
                        goal_id=goal.id,
                    )
                except LLMProviderError:
                    return self._fallback_plan(
                        goal,
                        profile,
                        constraints,
                        "AI 修复请求失败，已使用本地安全模板。",
                    )
                try:
                    content, validation = self._materialize_and_validate(
                        result, goal, profile, constraints
                    )
                except ValueError:
                    runner.record_semantic_failure(
                        result,
                        provider=provider,
                        kind="plan_generation",
                        prompt_version=PROMPT_VERSION_PLAN,
                        schema_version=PAYLOAD_VERSION,
                        goal_id=goal.id,
                    )
                    return self._fallback_plan(
                        goal,
                        profile,
                        constraints,
                        "AI 修复输出无法解析，已使用本地安全模板。",
                    )
            if validation.status == "failed":
                runner.record_semantic_failure(
                    result,
                    provider=provider,
                    kind="plan_generation",
                    prompt_version=PROMPT_VERSION_PLAN,
                    schema_version=PAYLOAD_VERSION,
                    goal_id=goal.id,
                )
                return self._fallback_plan(
                    goal,
                    profile,
                    constraints,
                    "AI 计划未通过安全校验，已使用本地安全模板。",
                )
            return self.plans.create_draft(
                goal,
                content,
                validation,
                generated_by="llm",
                provider=provider.name,
                model=getattr(provider, "model", self.config.llm.model),
                prompt_version=PROMPT_VERSION_PLAN,
                ai_run_id=result.run_id,
                activate=activate,
            )
        finally:
            await _close_provider(provider)

    def _plan_inputs(
        self,
        goal_id: str,
        *,
        weeks: int | None,
        days_per_week: int | None,
        session_minutes: int | None,
        start_date: date | None,
        activate: bool,
    ) -> tuple[Goal, TrainingProfile, PlanGenerationConstraints]:
        goal = self.goals.get(goal_id).goal
        profile = self.profile(
            12 if goal.goal_type == "race" else self.config.profile_weeks
        )
        if weeks is None:
            if goal.goal_type == "race" and goal.target_date is not None:
                weeks = max(
                    4,
                    min(
                        24,
                        (goal.target_date - self.goals.today).days // 7 + 1,
                    ),
                )
            else:
                weeks = self.config.default_plan_weeks
        if days_per_week is None:
            if goal.max_sessions_per_week:
                days_per_week = goal.max_sessions_per_week
            elif goal.goal_type == "weekly_frequency" and goal.target_value:
                days_per_week = round(goal.target_value)
            else:
                days_per_week = round(profile.observed_frequency.mean_per_week) or 3
        if goal.goal_type == "weekly_duration" and goal.target_value:
            needed_days = (int(goal.target_value) + 239) // 240
            days_per_week = max(int(days_per_week), min(6, needed_days))
        if session_minutes is None:
            session_minutes = {
                "5k": 60,
                "10k": 90,
                "half": 120,
                "full": 180,
            }.get(goal.race_distance or "", 60)
        if goal.goal_type == "weekly_duration" and goal.target_value and days_per_week:
            per_session = (int(goal.target_value) + int(days_per_week) - 1) // int(
                days_per_week
            )
            session_minutes = max(int(session_minutes), per_session)
        if start_date is None:
            today = self.goals.today
            start_date = today + timedelta(days=(7 - today.weekday()) % 7 or 7)
        constraints = PlanGenerationConstraints(
            weeks=max(4, min(24, int(weeks))),
            days_per_week=max(2, min(6, int(days_per_week))),
            session_minutes=max(20, min(180, int(session_minutes))),
            start_date=start_date,
            activate=activate,
        )
        return goal, profile, constraints

    def _save_template_plan(
        self,
        goal: Goal,
        profile: TrainingProfile,
        constraints: PlanGenerationConstraints,
        *,
        reason: str | None = None,
    ) -> TrainingPlan:
        content = build_template_plan(
            goal, profile, constraints, today=self.goals.today
        )
        validation = PlanValidator().validate(
            content,
            goal,
            profile,
            max_session_minutes=constraints.session_minutes,
        )
        if validation.status == "failed":
            details = "; ".join(
                f"{issue.code}: {issue.message}" for issue in validation.errors
            )
            raise ValueError(f"Generated plan failed safety validation: {details}")
        if reason:
            validation = PlanValidationResult(
                status="warnings",
                issues=[
                    *validation.issues,
                    PlanValidationIssue(
                        code="AI_FALLBACK",
                        message=reason,
                        severity="warning",
                    ),
                ],
            )
        return self.plans.create_draft(
            goal,
            content,
            validation,
            generated_by="fallback",
            activate=constraints.activate,
        )

    def _fallback_plan(
        self,
        goal: Goal,
        profile: TrainingProfile,
        constraints: PlanGenerationConstraints,
        reason: str,
    ) -> TrainingPlan:
        return self._save_template_plan(goal, profile, constraints, reason=reason)

    def _materialize_and_validate(
        self,
        result: Any,
        goal: Goal,
        profile: TrainingProfile,
        constraints: PlanGenerationConstraints,
    ) -> tuple[Any, PlanValidationResult]:
        draft = TrainingPlanDraft.model_validate(result.data)
        content = materialize_plan(draft, constraints.start_date or self.goals.today)
        validation = PlanValidator().validate(
            content,
            goal,
            profile,
            max_session_minutes=constraints.session_minutes,
        )
        return content, validation

    def activate_plan(self, plan_id: str) -> TrainingPlan:
        return self.plans.activate(plan_id)

    def archive_plan(self, plan_id: str) -> TrainingPlan:
        return self.plans.archive(plan_id)

    def overview(self, weeks: int | None = None) -> dict[str, Any]:
        profile = self.profile(weeks)
        goals = self.list_goals("active")
        plans = self.list_plans(status="active")
        return {
            "status": self.status(),
            "profile": profile.model_dump(mode="json"),
            "goals": [item.model_dump(mode="json") for item in goals],
            "plans": plans,
            "recommendations": [
                item.model_dump(mode="json") for item in self.goals.recommend(profile)
            ],
            "data_quality": profile.data_quality.model_dump(mode="json"),
        }


async def _close_provider(provider: Any) -> None:
    close = getattr(provider, "aclose", None)
    if close is None:
        return
    with contextlib.suppress(Exception):
        await close()
