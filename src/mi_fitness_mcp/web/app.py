"""FastAPI application for the local dashboard and optional coach API.

The API is intended for ``127.0.0.1`` only. Queries read the SQLite cache; the
explicit sync action and confirmed coach mutations write only their local
tables. The API never accepts credentials. Responses are JSON; errors use one
stable envelope:

    {"error": {"code": "...", "message": "...", "requestId": "...",
               "details": ...}}
"""

from __future__ import annotations

import logging
import os
import sqlite3
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from mi_fitness_mcp import __version__
from mi_fitness_mcp.config import load_config, resolve_database_path
from mi_fitness_mcp.web.coach_routes import router as coach_router
from mi_fitness_mcp.web.coach_service import CoachWebService
from mi_fitness_mcp.web.exceptions import ApiError, DatabaseLockedError
from mi_fitness_mcp.web.routes import router
from mi_fitness_mcp.web.service import FitnessService
from mi_fitness_mcp.web.sync import SyncCoordinator

logger = logging.getLogger(__name__)

DEFAULT_CORS_ORIGINS = (
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://127.0.0.1:4173",
    "http://localhost:4173",
)


def _cors_origins() -> list[str]:
    raw = os.environ.get("MI_FITNESS_WEB_CORS_ORIGINS", "")
    configured = [item.strip() for item in raw.split(",") if item.strip()]
    return configured or list(DEFAULT_CORS_ORIGINS)


def _error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    details: Any | None = None,
) -> JSONResponse:
    error: dict[str, Any] = {"code": code, "message": message}
    request_id = getattr(request.state, "request_id", None)
    if request_id:
        error["requestId"] = request_id
    if details:
        error["details"] = details
    return JSONResponse(status_code=status_code, content={"error": error})


def _validation_message(error: dict[str, Any]) -> str:
    """Turn common Pydantic validation errors into short Chinese guidance."""
    error_type = str(error.get("type", ""))
    context = error.get("ctx") or {}
    if "date" in error_type or "datetime" in error_type:
        return "日期格式不正确，请使用 YYYY-MM-DD。"
    if error_type == "missing":
        return "缺少必填参数。"
    if error_type == "literal_error":
        return "取值不在允许范围内。"
    if error_type == "greater_than_equal":
        return f"数值不能小于 {context.get('ge')}。"
    if error_type == "less_than_equal":
        return f"数值不能大于 {context.get('le')}。"
    return str(error.get("msg", "参数不合法。"))


def create_app(db_path: Path | str | None = None) -> FastAPI:
    """Create the FastAPI app with lazy read-only database access."""
    resolved_path = (
        Path(db_path)
        if db_path is not None
        else (resolve_database_path(None) or load_config().database_path)
    )

    fitness_service = FitnessService(resolved_path)
    sync_coordinator = SyncCoordinator(
        resolved_path, on_complete=fitness_service.invalidate
    )
    coach_service = CoachWebService(resolved_path)

    async def lifespan(_: FastAPI):
        yield
        await sync_coordinator.shutdown()

    app = FastAPI(
        title="Mi Fitness Data API",
        version=__version__,
        description=(
            "Local-only HTTP API over the SQLite cache created by "
            "mi-fitness-data-bridge. Query endpoints are read-only; the explicit "
            "local sync action writes the cache using credentials already stored "
            "in the OS keyring. Optional coach goal/plan mutations write only local "
            "coach tables after an explicit confirmation header; AI calls require "
            "separate consent. The API never accepts credentials. Bind it to "
            "127.0.0.1 only."
        ),
        docs_url="/docs",
        redoc_url=None,
        openapi_url="/openapi.json",
        lifespan=lifespan,
        openapi_tags=[
            {"name": "dashboard", "description": "首页聚合数据"},
            {"name": "workouts", "description": "运动列表、汇总与明细"},
            {"name": "sync", "description": "本地同步入口与分类同步状态"},
            {"name": "goals", "description": "旧版运动目标占位接口"},
            {"name": "coach", "description": "可选本地教练：目标、训练档案与计划"},
            {"name": "system", "description": "健康检查"},
        ],
    )
    app.state.service = fitness_service
    app.state.sync = sync_coordinator
    app.state.coach = coach_service

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=[
            "Accept",
            "Content-Type",
            "X-Request-ID",
            "X-Mi-Fitness-Confirm",
        ],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(GZipMiddleware, minimum_size=1024)

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid4().hex
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    app.include_router(router, prefix="/api")
    app.include_router(coach_router, prefix="/api")

    @app.get("/", include_in_schema=False)
    def root() -> dict[str, str]:
        return {
            "name": "Mi Fitness Data API",
            "version": __version__,
            "docs": "/docs",
            "api": "/api",
        }

    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
        response = _error_response(
            request,
            exc.status_code,
            exc.code,
            exc.message,
            exc.details,
        )
        if isinstance(exc, DatabaseLockedError):
            response.headers["Retry-After"] = "5"
        return response

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        details = [
            {
                "field": ".".join(str(part) for part in error.get("loc", ())),
                "message": _validation_message(error),
            }
            for error in exc.errors()
        ]
        return _error_response(
            request,
            422,
            "VALIDATION_ERROR",
            "请求参数不正确，请检查后重试。",
            details,
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        if exc.status_code == 404:
            return _error_response(
                request, 404, "ROUTE_NOT_FOUND", "请求的接口不存在。"
            )
        if exc.status_code == 405:
            return _error_response(
                request, 405, "METHOD_NOT_ALLOWED", "该接口不支持此请求方法。"
            )
        return _error_response(
            request,
            exc.status_code,
            "HTTP_ERROR",
            str(exc.detail),
        )

    @app.exception_handler(sqlite3.Error)
    async def handle_sqlite_error(
        request: Request, exc: sqlite3.Error
    ) -> JSONResponse:
        logger.exception("Unhandled SQLite error")
        return _error_response(
            request,
            503,
            "DATABASE_ERROR",
            "读取本地数据库失败，请稍后重试。",
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.exception("Unexpected web API error")
        return _error_response(
            request,
            500,
            "INTERNAL_ERROR",
            "服务器内部错误，请稍后重试。",
        )

    return app


app = create_app()
