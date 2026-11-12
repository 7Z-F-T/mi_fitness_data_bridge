"""GET-only read endpoints for the local dashboard API."""

from __future__ import annotations

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from mi_fitness_mcp.web.dependencies import get_service
from mi_fitness_mcp.web.schemas import (
    ApiErrorResponse,
    Goal,
    HealthResponse,
    HomeSummary,
    SummaryRange,
    Workout,
    WorkoutDetail,
    WorkoutSummary,
)
from mi_fitness_mcp.web.service import FitnessService

COMMON_RESPONSES = {
    404: {
        "model": ApiErrorResponse,
        "description": "资源不存在，或数据库中没有可展示的数据",
    },
    405: {
        "model": ApiErrorResponse,
        "description": "请求方法不允许；读接口只接受 GET",
    },
    409: {
        "model": ApiErrorResponse,
        "description": "数据库包含多个账号，需要设置 MI_FITNESS_WEB_USER_ID",
    },
    422: {
        "model": ApiErrorResponse,
        "description": "请求参数校验失败",
    },
    500: {
        "model": ApiErrorResponse,
        "description": "服务器内部错误",
    },
    503: {
        "model": ApiErrorResponse,
        "description": "数据库不存在、不可用或正被同步进程占用",
    },
}

ServiceDep = Annotated[FitnessService, Depends(get_service)]

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="健康检查",
    description="确认 API 进程和本地 SQLite 缓存均可读取。",
    tags=["system"],
    responses=COMMON_RESPONSES,
)
def health(service: ServiceDep) -> HealthResponse:
    return service.health()


@router.get(
    "/home",
    response_model=HomeSummary,
    summary="首页今日概览",
    description=(
        "返回指定日期的活动、主睡眠、心率样本、近 7 天活动和最近 4 场运动。"
        "日期使用 YYYY-MM-DD；省略时使用服务器本地日期。"
    ),
    tags=["dashboard"],
    responses=COMMON_RESPONSES,
)
def home(
    service: ServiceDep,
    date_: Annotated[
        dt.date | None,
        Query(
            alias="date",
            description="本地日期，YYYY-MM-DD；默认今天",
            examples=["2026-11-12"],
        ),
    ] = None,
) -> HomeSummary:
    return service.home(date_)


@router.get(
    "/workouts",
    response_model=list[Workout],
    summary="最近运动列表",
    description="按开始时间倒序返回运动汇总，不含秒级明细和 GPS 轨迹。",
    tags=["workouts"],
    responses=COMMON_RESPONSES,
)
def workouts(
    service: ServiceDep,
    limit: Annotated[int, Query(ge=1, le=200, description="返回数量，1-200")] = 20,
) -> list[Workout]:
    return service.workouts(limit)


@router.get(
    "/workouts/summary",
    response_model=WorkoutSummary,
    summary="运动汇总",
    description=(
        "按日/周/月/年聚合运动次数、时长、距离、消耗和类型分布。"
        "anchor 使用 YYYY-MM-DD；周从周一开始，月按自然日，年按自然月分桶。"
    ),
    tags=["workouts"],
    responses=COMMON_RESPONSES,
)
def workout_summary(
    service: ServiceDep,
    anchor: Annotated[
        dt.date,
        Query(
            description="统计锚点日期，YYYY-MM-DD",
            examples=["2026-11-12"],
        ),
    ],
    range_: Annotated[
        SummaryRange,
        Query(alias="range", description="day、week、month 或 year"),
    ] = "month",
) -> WorkoutSummary:
    return service.workout_summary(range_, anchor)


@router.get(
    "/workouts/{workout_id}",
    response_model=WorkoutDetail,
    summary="单场运动详情",
    description=(
        "返回单场运动汇总、秒级样本和 GPS 轨迹。"
        "未同步 workout_detail 的运动仍返回 200，但 samples/gps 为空。"
    ),
    tags=["workouts"],
    responses=COMMON_RESPONSES,
)
def workout_detail(
    service: ServiceDep,
    workout_id: Annotated[
        str,
        Path(
            min_length=1,
            max_length=200,
            description="提供方 workout_id",
        ),
    ],
) -> WorkoutDetail:
    return service.workout_detail(workout_id)


@router.get(
    "/goals",
    response_model=list[Goal],
    summary="运动目标",
    description="目标功能尚在规划中，当前返回空列表。",
    tags=["goals"],
    responses=COMMON_RESPONSES,
)
def goals(service: ServiceDep) -> list[Goal]:
    return service.goals()
