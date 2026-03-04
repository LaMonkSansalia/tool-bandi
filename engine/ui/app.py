"""
Streamlit entry point — bandi_researcher UI.
Uses st.navigation() for unified routing (no duplicate nav).
Run: PYTHONPATH=. venv/bin/streamlit run engine/ui/app.py
"""
import streamlit as st

st.set_page_config(
    page_title="Bandi Researcher",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

from engine.ui.components.sidebar import render_sidebar
from engine.projects.manager import get_active_projects, get_project_stats
from engine.config import DEFAULT_PROJECT_ID

# ── Pages ─────────────────────────────────────────────────────────────────────
pages = {
    "Bandi": [
        st.Page("pages/02_bandi.py",     title="Bandi",     icon="📋", default=True),
        st.Page("pages/03_dettaglio.py", title="Dettaglio", icon="📄"),
    ],
    "Panoramica": [
        st.Page("pages/01_dashboard.py", title="Dashboard",  icon="📊"),
        st.Page("pages/04_documenti.py", title="Documenti",  icon="📑"),
    ],
    "Impostazioni": [
        st.Page("pages/08_progetti.py",  title="Progetti",       icon="📂"),
        st.Page("pages/05_profilo.py",   title="Profilo",        icon="👤"),
        st.Page("pages/06_config.py",    title="Configurazione", icon="⚙️"),
        st.Page("pages/07_log.py",       title="Log",            icon="📜"),
    ],
}

# ── Project selector (compact top-bar) ────────────────────────────────────────
try:
    _projects = get_active_projects()
except Exception:
    _projects = []

if _projects:
    _current_id = st.session_state.get("current_project_id", DEFAULT_PROJECT_ID)
    _default_idx = 0
    for _i, _p in enumerate(_projects):
        if _p["id"] == _current_id:
            _default_idx = _i
            break

    col_proj, col_desc, col_stats = st.columns([2, 4, 4])

    with col_proj:
        _selected = st.selectbox(
            "📂 Progetto",
            _projects,
            index=_default_idx,
            format_func=lambda p: f"{p.get('telegram_prefix', '')} {p['nome']}".strip(),
            label_visibility="collapsed",
        )
        st.session_state["current_project_id"] = _selected["id"]
        st.session_state["current_project"] = _selected

    with col_desc:
        _desc_breve = _selected.get("descrizione_breve") or _selected.get("descrizione") or ""
        if _desc_breve:
            st.caption(_desc_breve)

    with col_stats:
        try:
            _stats = get_project_stats(_selected["id"])
            _c1, _c2, _c3 = st.columns(3)
            _c1.metric("Idonei", _stats.get("idonei", 0))
            _c2.metric("Lav.", _stats.get("in_lavorazione", 0))
            _c3.metric("Score", _stats.get("score_medio") or "—")
        except Exception:
            pass
else:
    st.session_state["current_project_id"] = DEFAULT_PROJECT_ID
    st.info("Nessun progetto configurato. Vai a **Progetti** per crearne uno.")

render_sidebar()

pg = st.navigation(pages)
pg.run()
