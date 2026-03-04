"""
Pagina Profilo — visualizza il profilo del progetto corrente.
Multi-project aware: loads from projects.profilo JSONB.
"""
import streamlit as st
from engine.projects.manager import get_project

st.title("👤 Profilo Aziendale")

pid = st.session_state.get("current_project_id", 1)
project = get_project(pid)

if not project:
    st.error(f"Progetto {pid} non trovato.")
    st.stop()

profile = project["profilo"]
skills = project.get("skills")

st.divider()

# ── Anagrafica ────────────────────────────────────────────────────────────────
col1, col2 = st.columns(2)

with col1:
    st.subheader("Anagrafica")
    a = profile.get("anagrafica", {})
    st.markdown(f"""
    | Campo | Valore |
    |-------|--------|
    | **Denominazione** | {a.get('denominazione', '—')} |
    | **P.IVA** | {a.get('partita_iva', '—')} |
    | **Forma giuridica** | {a.get('forma_giuridica', '—')} |
    | **Regime fiscale** | {a.get('regime_fiscale', '—')} |
    | **REA** | {a.get('numero_rea', '—')} |
    """)

with col2:
    st.subheader("Sede e Localizzazione")
    s = profile.get("sede", {})
    st.markdown(f"""
    | Campo | Valore |
    |-------|--------|
    | **Indirizzo** | {s.get('indirizzo', '—')}, {s.get('cap', '')} {s.get('comune', '')} |
    | **Regione** | {s.get('regione', '—')} |
    | **Zona ZES** | {'✅ Si' if s.get('zona_zes') else '❌ No'} |
    | **Mezzogiorno** | {'✅ Si' if s.get('zona_mezzogiorno') else '❌ No'} |
    """)

# ── Attivita ──────────────────────────────────────────────────────────────────
st.subheader("Attivita")
col3, col4 = st.columns(2)

with col3:
    att = profile.get("attivita", {})
    ateco = att.get("ateco_2025", att.get("ateco", "—"))
    st.markdown(f"""
    | Campo | Valore |
    |-------|--------|
    | **ATECO** | {ateco} |
    | **Settore** | {att.get('ateco_descrizione', att.get('settore_principale', '—'))} |
    | **Attiva dal** | {att.get('data_inizio', '—')} |
    | **Anni attivita** | {att.get('anni_attivita', '—')} |
    """)

with col4:
    dim = profile.get("dimensione", {})
    fatturato = dim.get("fatturato_stimato_max", dim.get("fatturato_max", 0))
    st.markdown(f"""
    | Campo | Valore |
    |-------|--------|
    | **Dipendenti** | {dim.get('dipendenti', '—')} |
    | **Fatturato max** | {fatturato:,.0f}€ |
    | **Micro-impresa** | {'✅ Si' if dim.get('micro_impresa') else '❌ No'} |
    """)

# ── Eligibility constraints ─────────────────────────────────────────────────
constraints = profile.get("eligibility_constraints", {})

if constraints.get("HARD_STOP"):
    st.subheader("⛔ Hard Stops (esclusioni automatiche)")
    for hs in constraints["HARD_STOP"]:
        st.error(f"**{hs['constraint']}** — {hs['motivo']}")

if constraints.get("VANTAGGI"):
    st.subheader("✅ Vantaggi Competitivi")
    for v in constraints["VANTAGGI"]:
        st.success(v)

if constraints.get("YELLOW_FLAG"):
    st.subheader("🟡 Attenzione")
    for yf in constraints["YELLOW_FLAG"]:
        st.warning(f"**{yf['constraint']}** — {yf['nota']}")

# ── Scoring rules ────────────────────────────────────────────────────────────
scoring_rules = project.get("scoring_rules", {})
if scoring_rules.get("rules"):
    st.subheader("📊 Regole di Scoring")
    for rule in scoring_rules["rules"]:
        keywords = rule.get("config", {}).get("keywords", [])
        kw_str = f" — keywords: `{', '.join(keywords[:5])}`" if keywords else ""
        st.markdown(f"- **{rule['name']}** ({rule['points']}pt) — {rule.get('description', '')}{kw_str}")

# ── Skills raw ────────────────────────────────────────────────────────────────
if skills:
    with st.expander("📋 Skills Matrix (raw JSON)"):
        st.json(skills)
