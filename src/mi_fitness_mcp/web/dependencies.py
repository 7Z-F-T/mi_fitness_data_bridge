"""FastAPI dependencies for the local web API."""

from __future__ import annotations

from fastapi import Request

from mi_fitness_mcp.web.exceptions import SyncConfirmationError
from mi_fitness_mcp.web.service import FitnessService
from mi_fitness_mcp.web.sync import SyncCoordinator


def get_service(request: Request) -> FitnessService:
    """Return the app-scoped read-only data service."""
    return request.app.state.service


def get_sync_coordinator(request: Request) -> SyncCoordinator:
    """Return the app-scoped local sync coordinator."""
    return request.app.state.sync


def require_sync_confirmation(request: Request) -> None:
    """Require an explicit header so a cross-site form cannot start a sync.

    A custom header triggers CORS preflight; the API only allows local frontend
    origins, so a random website cannot send this header to localhost.
    """
    if request.headers.get("X-Mi-Fitness-Confirm") != "sync":
        raise SyncConfirmationError()
