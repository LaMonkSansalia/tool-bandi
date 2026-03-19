"""
Shared sidebar component — scan button + app info.
Called from app.py ONLY. Project selector is in app.py top-bar.
Navigation managed by st.navigation().
"""
import streamlit as st


def render_sidebar() -> None:
    """Render scan button and app info in sidebar."""
    st.sidebar.title("🎯 Bandi Researcher")
    current_project = st.session_state.get("current_project")
    if current_project:
        prefix = current_project.get("telegram_prefix", "")
        name = current_project.get("nome", "")
        st.sidebar.caption(f"Progetto attivo: {prefix} {name}".strip())

    st.sidebar.markdown("---")

    # ── Scan button (prominent) ─────────────────────────────────────────────
    if st.sidebar.button(
        "▶️ Avvia scansione",
        type="primary",
        use_container_width=True,
    ):
        _run_scan()

    st.sidebar.markdown("---")


def _run_scan() -> None:
    """Execute daily_scan and show results in sidebar."""
    with st.sidebar:
        with st.spinner("Scansione in corso..."):
            try:
                from engine.pipeline.flows import daily_scan
                result = daily_scan()
                st.success(
                    f"Completata! "
                    f"Trovati: {result.get('scraped', 0)} | "
                    f"Inseriti: {result.get('inserted', 0)}"
                )
            except Exception as e:
                st.error(f"Errore: {e}")
