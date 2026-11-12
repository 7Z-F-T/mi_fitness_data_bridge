"""Local read-only HTTP API for the Mi Fitness SQLite cache."""

from mi_fitness_mcp.web.app import create_app

__all__ = ["create_app"]
