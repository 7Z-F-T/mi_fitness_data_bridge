"""FastAPI dependencies for the local web API."""

from __future__ import annotations

from fastapi import Request

from mi_fitness_mcp.web.service import FitnessService


def get_service(request: Request) -> FitnessService:
    """Return the app-scoped read-only data service."""
    return request.app.state.service
