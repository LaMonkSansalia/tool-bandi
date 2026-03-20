"""
FastAPI application — tool-bandi web UI.
Server-rendered with Jinja2 + HTMX + Alpine.js.
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware

from engine.config import DATABASE_URL
from engine.db.pool import init_pool, close_pool

import logging

_logger = logging.getLogger(__name__)

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

# ── HTMX Layout Middleware ────────────────────────────────────────────────────
# Prevents double sidebar by detecting when a full-page layout is served
# inside an HTMX partial swap (HX-Target != body and != "").

class HTMXLayoutMiddleware(BaseHTTPMiddleware):
    """
    Generic fix for double sidebar (BUG-FIXED-015).

    When a form POST inside a tab partial gets boosted by hx-boost="true",
    HTMX follows the 303 redirect with HX-Request header but the route
    returns a full page with layout. HTMX swaps only the target element,
    injecting the full layout (including sidebar) inside the page.

    This middleware detects that case and strips the layout, returning
    only the page content (everything inside <div class="p-6">).
    """

    # Marker that identifies the content wrapper in layout.html
    _CONTENT_START = '<div class="p-6">'
    _CONTENT_END_MARKERS = ('</main>', '</div>\n\n  </div>')

    async def dispatch(self, request, call_next):
        is_htmx = request.headers.get("HX-Request") == "true"
        hx_target = request.headers.get("HX-Target", "")
        is_boosted = request.headers.get("HX-Boosted") == "true"

        # Partial = HTMX with specific target (not full-page boost)
        is_partial = is_htmx and hx_target and hx_target not in ("body", "") and not is_boosted

        request.state.is_htmx = is_htmx
        request.state.hx_target = hx_target
        request.state.is_htmx_partial = is_partial

        response = await call_next(request)

        # Only process HTML partial responses
        content_type = response.headers.get("content-type", "")
        if not (is_partial and "text/html" in content_type):
            return response

        # Read body
        body = b""
        async for chunk in response.body_iterator:
            body += chunk
        body_str = body.decode("utf-8", errors="ignore")

        # If response contains full layout, extract just the content
        if "<!DOCTYPE" in body_str or "<html" in body_str:
            extracted = self._extract_content(body_str)
            if extracted is not None:
                _logger.info(
                    "HTMX partial: stripped layout from %s (HX-Target=%s)",
                    request.url.path, hx_target,
                )
                body = extracted.encode("utf-8")

        from starlette.responses import Response as StarletteResponse
        return StarletteResponse(
            content=body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )

    def _extract_content(self, html: str) -> str | None:
        """Extract content between <div class="p-6"> and </main>."""
        start = html.find(self._CONTENT_START)
        if start == -1:
            return None
        # Skip past the opening tag
        inner_start = start + len(self._CONTENT_START)
        # Find the closing </main> or nearest structural end
        end = html.find("</main>", inner_start)
        if end == -1:
            return None
        # Find the last </div> before </main> — that's the closing of p-6
        content = html[inner_start:end]
        # Strip the trailing </div> that closes <div class="p-6">
        last_div = content.rfind("</div>")
        if last_div != -1:
            content = content[:last_div]
        return content.strip()


# Session middleware (for current_project_id + flash messages)
import os

app.add_middleware(HTMXLayoutMiddleware)

from web.auth import SimpleAuthMiddleware
app.add_middleware(SimpleAuthMiddleware)

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET", "tool-bandi-dev-secret-change-me"),
)

# Static files
app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")

# Templates
templates = Jinja2Templates(directory=WEB_DIR / "templates")

# Register custom filters for Jinja2
import re as _re
from markupsafe import Markup

from web.services.display import format_budget, giorni_label, score_meta
templates.env.filters["format_budget"] = format_budget
templates.env.filters["giorni_label"] = lambda g: giorni_label(g)[0]
templates.env.filters["giorni_css"] = lambda g: giorni_label(g)[1]
templates.env.filters["score_display"] = lambda s: score_meta(s)[0]
templates.env.filters["score_css"] = lambda s: score_meta(s)[1]


def _clean_html(text: str) -> str:
    """Strip HTML tags including <script>/<style> content, collapse whitespace."""
    if not text:
        return ""
    # Remove <script> and <style> blocks with content
    text = _re.sub(r"<(script|style)[^>]*>.*?</\1>", "", text, flags=_re.DOTALL | _re.IGNORECASE)
    # Remove HTML tags
    text = _re.sub(r"<[^>]+>", " ", text)
    # Decode common HTML entities
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&quot;", '"').replace("&#34;", '"').replace("&nbsp;", " ")
    # Collapse multiple spaces/tabs on same line
    text = _re.sub(r"[^\S\n]+", " ", text)
    # Collapse 3+ newlines into 2
    text = _re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


templates.env.filters["clean_html"] = _clean_html

# Human-readable label filters for raw DB values
from web.services.completezza import FORME_GIURIDICHE, REGIMI_FISCALI, SETTORI

_FORME_MAP = dict(FORME_GIURIDICHE)
_REGIMI_MAP = dict(REGIMI_FISCALI)
_SETTORI_MAP = dict(SETTORI)

templates.env.filters["forma_label"] = lambda v: _FORME_MAP.get(v, v.replace("_", " ").title() if v else "—")
templates.env.filters["regime_label"] = lambda v: _REGIMI_MAP.get(v, v.replace("_", " ").title() if v else "—")
templates.env.filters["settore_label"] = lambda v: _SETTORI_MAP.get(v, v.replace("_", " ").title() if v else "—")


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
