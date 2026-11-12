"""Command-line entry point for the local read-only web API."""

from __future__ import annotations

from pathlib import Path

LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def run_web(
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    db_path: Path | None = None,
) -> None:
    """Run the FastAPI app with uvicorn."""
    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover - depends on optional extra
        raise SystemExit(
            "Web 依赖未安装。请运行：pip install -e '.[web]'"
        ) from exc

    if host not in LOOPBACK_HOSTS:
        print("⚠️  警告：Web API 包含敏感健康数据，建议只监听 127.0.0.1。")

    from mi_fitness_mcp.web.app import create_app

    app = create_app(db_path=db_path)
    uvicorn.run(app, host=host, port=port, log_level="info")
