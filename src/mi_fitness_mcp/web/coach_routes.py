"""Local coach HTTP routes: read-only GETs and confirmed local writes."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Request

from mi_fitness_mcp.web.coach_schemas import (
    CoachGeneratePlanRequest,
    CoachGoal,
    CoachGoalCreateRequest,
    CoachGoalUpdateRequest,
    CoachGoalWithProgress,
    CoachOverview,
    CoachPlan,
    CoachRecommendation,
    CoachRecommendRequest,
    CoachStatus,
)
from mi_fitness_mcp.web.coach_service import CoachWebService
from mi_fitness_mcp.web.exceptions import CoachConfirmationError

router = APIRouter(prefix="/coach", tags=["coach"])


def get_coach_service(request: Request) -> CoachWebService:
    return request.app.state.coach


CoachDep = Annotated[CoachWebService, Depends(get_coach_service)]


def require_coach_confirmation(request: Request) -> None:
    if request.headers.get("X-Mi-Fitness-Confirm") != "coach":
        raise CoachConfirmationError()


Confirm = Annotated[None, Depends(require_coach_confirmation)]


def _goal_with_progress(value: Any) -> CoachGoalWithProgress:
    return CoachGoalWithProgress.model_validate(value.model_dump(mode="json"))


def _goal(value: Any) -> CoachGoal:
    return CoachGoal.model_validate(value.model_dump(mode="json"))


def _public_plan_dict(value: dict[str, Any]) -> dict[str, Any]:
    result = {key: item for key, item in value.items() if key != "user_id"}
    snapshot = dict(result.get("goal_snapshot") or {})
    snapshot.pop("user_id", None)
    result["goal_snapshot"] = snapshot
    return result


def _plan(value: Any) -> CoachPlan:
    data = value.model_dump(mode="json") if hasattr(value, "model_dump") else dict(value)
    return CoachPlan.model_validate(_public_plan_dict(data))


@router.get("/status", response_model=CoachStatus, summary="Coach 配置与数据状态")
def status(service: CoachDep) -> CoachStatus:
    return CoachStatus.model_validate(service.status())


@router.get("/overview", response_model=CoachOverview, summary="Coach 总览")
def overview(
    service: CoachDep,
    weeks: int | None = Query(default=None, ge=4, le=52),
) -> CoachOverview:
    data = service.overview(weeks)
    return CoachOverview(
        status=CoachStatus.model_validate(data["status"]),
        profile=data["profile"],
        goals=[
            CoachGoalWithProgress.model_validate(item) for item in data["goals"]
        ],
        plans=[_plan(item) for item in data["plans"]],
        recommendations=[
            CoachRecommendation.model_validate(item)
            for item in data["recommendations"]
        ],
        data_quality=data["data_quality"],
    )


@router.get("/profile", summary="训练档案或 LLM payload 预览")
def profile(
    service: CoachDep,
    weeks: int | None = Query(default=None, ge=4, le=52),
    goal_id: str | None = Query(default=None, alias="goalId"),
    format_: Literal["local", "llm"] = Query(default="local", alias="format"),
) -> dict[str, Any]:
    return service.profile(weeks, goal_id, format_)


@router.get(
    "/goals",
    response_model=list[CoachGoalWithProgress],
    summary="目标列表与进度",
)
def list_goals(
    service: CoachDep,
    status: Literal["active", "achieved", "archived"] = Query(default="active"),
) -> list[CoachGoalWithProgress]:
    return [_goal_with_progress(item) for item in service.list_goals(status)]


@router.get(
    "/goals/{goal_id}",
    response_model=CoachGoalWithProgress,
    summary="目标详情与进度",
)
def get_goal(service: CoachDep, goal_id: str) -> CoachGoalWithProgress:
    return _goal_with_progress(service.get_goal(goal_id))


@router.post(
    "/goals",
    response_model=CoachGoalWithProgress,
    summary="创建目标",
    dependencies=[Depends(require_coach_confirmation)],
)
def create_goal(
    service: CoachDep, request: CoachGoalCreateRequest
) -> CoachGoalWithProgress:
    return _goal_with_progress(service.create_goal(request))


@router.post(
    "/goals/{goal_id}",
    response_model=CoachGoalWithProgress,
    summary="更新目标",
    dependencies=[Depends(require_coach_confirmation)],
)
def update_goal(
    service: CoachDep, goal_id: str, request: CoachGoalUpdateRequest
) -> CoachGoalWithProgress:
    return _goal_with_progress(service.update_goal(goal_id, request))


@router.post(
    "/goals/{goal_id}/archive",
    response_model=CoachGoal,
    summary="归档目标",
    dependencies=[Depends(require_coach_confirmation)],
)
def archive_goal(service: CoachDep, goal_id: str) -> CoachGoal:
    return _goal(service.archive_goal(goal_id))


@router.post(
    "/recommendations",
    response_model=list[CoachRecommendation],
    summary="生成目标建议",
    dependencies=[Depends(require_coach_confirmation)],
)
async def recommendations(
    service: CoachDep, request: CoachRecommendRequest
) -> list[CoachRecommendation]:
    items = await service.recommend(
        request.weeks, use_llm=request.use_llm, consent=request.consent
    )
    return [CoachRecommendation.model_validate(item.model_dump(mode="json")) for item in items]


@router.get("/plans", response_model=list[CoachPlan], summary="训练计划列表")
def list_plans(
    service: CoachDep,
    goal_id: str | None = Query(default=None, alias="goalId"),
    status: Literal["draft", "active", "superseded", "archived"] | None = Query(
        default=None
    ),
) -> list[CoachPlan]:
    return [_plan(item) for item in service.list_plans(goal_id, status)]


@router.get("/plans/{plan_id}", response_model=CoachPlan, summary="训练计划详情")
def get_plan(service: CoachDep, plan_id: str) -> CoachPlan:
    return _plan(service.get_plan(plan_id))


@router.post(
    "/plans/generate",
    response_model=CoachPlan,
    summary="生成训练计划",
    dependencies=[Depends(require_coach_confirmation)],
)
async def generate_plan(
    service: CoachDep, request: CoachGeneratePlanRequest
) -> CoachPlan:
    return _plan(await service.generate_plan(request))


@router.post(
    "/plans/{plan_id}/activate",
    response_model=CoachPlan,
    summary="激活训练计划",
    dependencies=[Depends(require_coach_confirmation)],
)
def activate_plan(service: CoachDep, plan_id: str) -> CoachPlan:
    return _plan(service.activate_plan(plan_id))


@router.post(
    "/plans/{plan_id}/archive",
    response_model=CoachPlan,
    summary="归档训练计划",
    dependencies=[Depends(require_coach_confirmation)],
)
def archive_plan(service: CoachDep, plan_id: str) -> CoachPlan:
    return _plan(service.archive_plan(plan_id))
