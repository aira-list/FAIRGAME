"""FastAPI app factory + static SPA mount.

Run with::

    uvicorn web_api.main:app --reload
"""

from __future__ import annotations

import re
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse, Response

from src.utils.logger import configure_logging
from web_api.routes import register
from web_api.run_history import seed_starter_runs
from web_api.storage import WEB_DIR, resolve_within

configure_logging()

_NO_CACHE = {"Cache-Control": "no-cache, no-store, must-revalidate"}
_INCLUDE_RE = re.compile(r"^\s*<!--\s*INCLUDE:\s*(\S+)\s*-->\s*$", re.MULTILINE)


def _render_index() -> str:
    """Read web/index.html and inline ``<!-- INCLUDE: partials/foo.html -->``
    markers with the contents of the named files. Read at every request so
    edits show up under ``--reload`` without restarting uvicorn."""
    shell = (WEB_DIR / "index.html").read_text()

    def _replace(match: re.Match[str]) -> str:
        rel = match.group(1)
        target = WEB_DIR / rel
        if not target.is_file():
            return f"<!-- INCLUDE: {rel} (NOT FOUND) -->"
        return target.read_text()

    return _INCLUDE_RE.sub(_replace, shell)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    # Ship-with-repo sample runs: topped up at SERVER STARTUP (never at
    # import) so tests and tooling that merely import this module don't
    # write to RUNS_DIR. Opt out with FAIRGAME_SKIP_STARTER_RUNS=1.
    seed_starter_runs()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="FAIRGAME", version="0.2.0", lifespan=_lifespan)
    register(app)

    if WEB_DIR.is_dir():
        # No StaticFiles mount: the catch-all SPA route below already serves
        # any file under WEB_DIR (with resolve_within containment checking).

        @app.get("/", include_in_schema=False)
        def root() -> HTMLResponse:
            return HTMLResponse(_render_index(), headers=_NO_CACHE)

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str) -> Response:
            # Containment-checked: a percent-decoded ``../`` must not escape
            # WEB_DIR and serve arbitrary files. ``resolve_within`` returns
            # None on any escape, in which case we fall back to the SPA shell.
            target = resolve_within(WEB_DIR, path)
            if target is not None and target.is_file():
                return FileResponse(target, headers=_NO_CACHE)
            # Unknown client-side route — fall back to the SPA shell.
            return HTMLResponse(_render_index(), headers=_NO_CACHE)
    else:

        @app.get("/", include_in_schema=False)
        def root_no_web() -> dict[str, str]:
            return {
                "message": (
                    f"FAIRGAME API is running but the static frontend ({WEB_DIR}) is missing."
                ),
            }

    return app


app = create_app()
