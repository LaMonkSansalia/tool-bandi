"""
FastAPI application — tool-bandi web UI.
Server-rendered with Jinja2 + HTMX + Alpine.js.
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from engine.config import DATABASE_URL
from engine.db.pool import init_pool, close_pool

WEB_DIR = Path(__file__).parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown: manage DB pool."""
    init_pool(minconn=2, maxconn=10)
    yield
    close_pool()


app = FastAPI(
    title="Tool Bandi",
    docs_url=None,
    redoc_url=None,
    lifespan=lifespan,
)

# Session middleware (for current_project_id + flash messages)
import os
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET", "tool-bandi-dev-secret-change-me"),
)

# Static files
app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")

# Templates
templates = Jinja2Templates(directory=WEB_DIR / "templates")

# Register custom filters for Jinja2
from web.services.display import format_budget, giorni_label, score_meta
templates.env.filters["format_budget"] = format_budget
templates.env.filters["giorni_label"] = lambda g: giorni_label(g)[0]
templates.env.filters["giorni_css"] = lambda g: giorni_label(g)[1]
templates.env.filters["score_display"] = lambda s: score_meta(s)[0]
templates.env.filters["score_css"] = lambda s: score_meta(s)[1]


# ── Include routers ──────────────────────────────────────────────────────────

from web.routes.dashboard import router as dashboard_router
from web.routes.soggetti import router as soggetti_router
from web.routes.progetti import router as progetti_router
from web.routes.bandi import router as bandi_router
from web.routes.candidature import router as candidature_router
from web.routes.documenti import router as documenti_router
from web.routes.pipeline import router as pipeline_router

app.include_router(dashboard_router)
app.include_router(soggetti_router)
app.include_router(progetti_router)
app.include_router(bandi_router)
app.include_router(candidature_router)
app.include_router(documenti_router)
app.include_router(pipeline_router)
