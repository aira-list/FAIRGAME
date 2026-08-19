"""Route registration helper."""

from __future__ import annotations

from fastapi import FastAPI

from web_api.routes import library, run_configs, runs, system, transfer


def register(app: FastAPI) -> None:
    app.include_router(system.router)
    app.include_router(runs.router)
    app.include_router(library.router)
    app.include_router(run_configs.router)
    app.include_router(transfer.router)
