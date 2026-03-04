"""
Gestione Progetti — lista, creazione, modifica, onboarding wizard.
"""
import json
import streamlit as st
from engine.projects.manager import (
    get_active_projects, get_project, get_project_stats,
    create_project, update_project,
)
st.title("📂 Gestione Progetti")

# ── Scoring templates ────────────────────────────────────────────────────────
SCORING_TEMPLATES = {
    "ICT / Freelancer": {
        "version": "1.0",
        "rules": [
            {"name": "regione_ammessa", "points": 15, "type": "region_match",
             "description": "Sicilia / Sud / Mezzogiorno ammessi"},
            {"name": "ateco_ict", "points": 20, "type": "ateco_match",
             "description": "ATECO ICT prioritario PNRR"},
            {"name": "zona_zes", "points": 10, "type": "keyword_and_profile",
             "description": "Zona ZES — bonus automatico",
             "config": {"profile_field": "zona_zes",
                        "keywords": ["zes", "zona economica speciale", "mezzogiorno", "sud"]}},
            {"name": "under_36", "points": 10, "type": "profile_age_check",
             "description": "Titolare under 36",
             "config": {"keywords": ["under 35", "under 36", "giovani", "under35"]}},
            {"name": "nuova_impresa", "points": 10, "type": "company_age",
             "description": "Impresa attiva da meno di 5 anni",
             "config": {"max_years": 5, "keywords": ["nuova impresa", "startup", "nuove imprese"]}},
            {"name": "forma_giuridica_ok", "points": 5, "type": "beneficiary_match",
             "description": "Forma giuridica ammessa"},
            {"name": "no_certificazioni", "points": 5, "type": "no_certifications_required",
             "description": "Nessuna certificazione obbligatoria"},
            {"name": "micro_impresa_ok", "points": 5, "type": "beneficiary_match",
             "description": "Micro-impresa ammessa",
             "config": {"accepted_types": ["micro_impresa", "pmi", "tutti", "tutte_le_imprese"]}},
            {"name": "pnrr_digitalizzazione", "points": 10, "type": "keyword_in_title",
             "description": "Bando PNRR digitalizzazione / ICT",
             "config": {"keywords": ["pnrr", "digitalizzazione", "digitale", "ict"]}},
            {"name": "importo_adeguato", "points": 10, "type": "importo_min",
             "description": "Importo > 5.000 EUR", "config": {"min_importo": 5000}},
        ],
    },
    "Turismo / Cultura": {
        "version": "1.1",
        "rules": [
            {"name": "turismo_cultura", "points": 30, "type": "keyword_in_title",
             "description": "Focus turismo/cultura/borghi",
             "config": {"keywords": ["turismo", "cultura", "patrimonio culturale",
                        "borghi", "aree interne", "promozione territoriale",
                        "valorizzazione", "heritage", "ospitalità", "accoglienza"]}},
            {"name": "astronomia_scienza", "points": 20, "type": "keyword_in_title",
             "description": "Astronomia/scienza/divulgazione",
             "config": {"keywords": ["astronomia", "scienza", "planetario",
                        "osservatorio", "divulgazione", "stem"]}},
            {"name": "zona_rurale", "points": 15, "type": "keyword_and_profile",
             "description": "Aree interne/borghi/rurali",
             "config": {"profile_field": "zona_mezzogiorno",
                        "keywords": ["aree interne", "borghi", "rurale", "sviluppo locale"]}},
            {"name": "commercio_locale", "points": 10, "type": "keyword_in_title",
             "description": "Commercio locale/artigianato",
             "config": {"keywords": ["commercio", "artigianato", "prodotti tipici",
                        "filiera corta", "mercati"]}},
            {"name": "regione_ammessa", "points": 10, "type": "region_match",
             "description": "Sicilia / Sud ammessi"},
            {"name": "importo_adeguato", "points": 5, "type": "importo_min",
             "description": "Importo > 2.000 EUR", "config": {"min_importo": 2000}},
            {"name": "no_certificazioni", "points": 5, "type": "no_certifications_required",
             "description": "Nessuna certificazione obbligatoria"},
            {"name": "tipo_beneficiario_ok", "points": 5, "type": "beneficiary_match",
             "description": "Tipo beneficiario compatibile",
             "config": {"accepted_types": ["associazione", "ente_no_profit",
                        "pro_loco", "tutti", "tutte_le_imprese", "ente_pubblico"]}},
        ],
    },
    "E-commerce / PMI": {
        "version": "1.0",
        "rules": [
            {"name": "regione_ammessa", "points": 15, "type": "region_match",
             "description": "Regione ammessa"},
            {"name": "digitalizzazione_pmi", "points": 25, "type": "keyword_in_title",
             "description": "Digitalizzazione / e-commerce PMI",
             "config": {"keywords": ["digitalizzazione", "e-commerce", "ecommerce",
                        "commercio elettronico", "voucher digitale", "pmi digitale"]}},
            {"name": "ateco_match", "points": 15, "type": "ateco_match",
             "description": "ATECO corrispondente"},
            {"name": "forma_giuridica_ok", "points": 10, "type": "beneficiary_match",
             "description": "Forma giuridica ammessa"},
            {"name": "micro_impresa_ok", "points": 10, "type": "beneficiary_match",
             "description": "Dimensione ammessa",
             "config": {"accepted_types": ["micro_impresa", "pmi", "tutti", "tutte_le_imprese"]}},
            {"name": "no_certificazioni", "points": 5, "type": "no_certifications_required",
             "description": "Nessuna certificazione obbligatoria"},
            {"name": "importo_adeguato", "points": 10, "type": "importo_min",
             "description": "Importo > 3.000 EUR", "config": {"min_importo": 3000}},
            {"name": "innovazione", "points": 10, "type": "keyword_in_title",
             "description": "Innovazione / transizione",
             "config": {"keywords": ["innovazione", "transizione", "4.0", "5.0", "pnrr"]}},
        ],
    },
}

# ── Lista progetti ───────────────────────────────────────────────────────────
st.subheader("Progetti attivi")

projects = get_active_projects()
if not projects:
    st.info("Nessun progetto configurato.")
else:
    for p in projects:
        stats = get_project_stats(p["id"])
        with st.container(border=True):
            col_info, col_stats = st.columns([3, 2])
            with col_info:
                prefix = p.get("telegram_prefix", "")
                st.markdown(f"### {prefix} {p['nome']}")
                if p.get("descrizione_breve"):
                    st.markdown(f"**{p['descrizione_breve']}**")
                if p.get("descrizione"):
                    st.caption(p["descrizione"])
                st.markdown(f"`slug: {p['slug']}` — `id: {p['id']}`")
            with col_stats:
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Totale", stats.get("totale", 0))
                c2.metric("Idonei", stats.get("idonei", 0))
                c3.metric("Nuovi", stats.get("nuovi", 0))
                c4.metric("Score", stats.get("score_medio") or "—")

st.divider()

# ── Onboarding wizard ────────────────────────────────────────────────────────
st.subheader("➕ Nuovo Progetto")

with st.form("new_project"):
    st.markdown("### Dati identificativi")
    col_a, col_b = st.columns(2)
    with col_a:
        new_slug = st.text_input("Slug (identificativo breve)", placeholder="es. pds")
        new_nome = st.text_input("Nome completo", placeholder="es. Paese Delle Stelle")
        new_desc_breve = st.text_input("Descrizione breve", placeholder="es. Astroturismo e cultura")
        new_desc = st.text_area("Descrizione completa", placeholder="Descrizione dettagliata del progetto, obiettivi, attività...")
    with col_b:
        new_prefix = st.text_input("Prefisso Telegram", placeholder="es. [PDS]")
        new_chat_id = st.text_input("Chat ID Telegram (opzionale)", placeholder="Lascia vuoto per usare quello globale")

    st.markdown("### Profilo organizzazione")
    col_c, col_d = st.columns(2)
    with col_c:
        denominazione = st.text_input("Denominazione legale")
        forma_giuridica = st.selectbox("Forma giuridica", [
            "impresa individuale", "associazione", "pro loco", "fondazione",
            "cooperativa", "srl", "srls", "spa", "snc", "sas",
            "ente pubblico", "comune", "altro",
        ])
        partita_iva = st.text_input("P.IVA / Codice Fiscale")
        regime_fiscale = st.text_input("Regime fiscale", value="ordinario")
    with col_d:
        comune = st.text_input("Comune", placeholder="es. Roccapalumba")
        provincia = st.text_input("Provincia", placeholder="es. PA")
        regione = st.selectbox("Regione", [
            "Sicilia", "Calabria", "Campania", "Puglia", "Basilicata", "Sardegna",
            "Lazio", "Lombardia", "Piemonte", "Veneto", "Emilia-Romagna",
            "Toscana", "Liguria", "Marche", "Abruzzo", "Molise",
            "Friuli Venezia Giulia", "Trentino-Alto Adige", "Umbria", "Valle d'Aosta",
        ])
        zona_zes = st.checkbox("Zona ZES", value=True)
        zona_mezzogiorno = st.checkbox("Zona Mezzogiorno", value=True)

    st.markdown("### Attivita")
    col_e, col_f = st.columns(2)
    with col_e:
        ateco = st.text_input("Codice ATECO", placeholder="es. 79.90.20")
        settore = st.text_input("Settore principale", placeholder="es. Turismo / Promozione culturale")
        data_inizio = st.text_input("Data inizio attivita (GG/MM/AAAA)")
        anni_attivita = st.number_input("Anni attivita", min_value=0, value=0)
    with col_f:
        dipendenti = st.number_input("Dipendenti", min_value=0, value=0)
        fatturato_max = st.number_input("Fatturato max (EUR)", min_value=0, value=0)
        micro_impresa = st.checkbox("Micro-impresa", value=True)

    st.markdown("### Template scoring")
    template_choice = st.selectbox(
        "Scegli un template di scoring",
        list(SCORING_TEMPLATES.keys()),
    )

    submitted = st.form_submit_button("Crea progetto", type="primary")

    if submitted:
        if not new_slug or not new_nome:
            st.error("Slug e nome sono obbligatori.")
        else:
            profilo = {
                "anagrafica": {
                    "denominazione": denominazione,
                    "partita_iva": partita_iva,
                    "forma_giuridica": forma_giuridica,
                    "regime_fiscale": regime_fiscale,
                },
                "sede": {
                    "comune": comune,
                    "provincia": provincia,
                    "regione": regione,
                    "zona_zes": zona_zes,
                    "zona_mezzogiorno": zona_mezzogiorno,
                },
                "attivita": {
                    "ateco_2025": ateco,
                    "settore_principale": settore,
                    "data_inizio": data_inizio,
                    "anni_attivita": anni_attivita,
                },
                "dimensione": {
                    "dipendenti": dipendenti,
                    "fatturato_stimato_max": fatturato_max,
                    "micro_impresa": micro_impresa,
                },
                "certificazioni": {
                    "soa": None,
                    "iso_9001": False,
                    "iso_27001": False,
                },
                "eligibility_constraints": {
                    "HARD_STOP": [],
                    "YELLOW_FLAG": [],
                    "VANTAGGI": [],
                },
            }

            scoring_rules = SCORING_TEMPLATES[template_choice]

            try:
                project_id = create_project(
                    slug=new_slug,
                    nome=new_nome,
                    profilo=profilo,
                    scoring_rules=scoring_rules,
                    descrizione=new_desc or None,
                    descrizione_breve=new_desc_breve or None,
                    telegram_chat_id=new_chat_id or None,
                    telegram_prefix=new_prefix or None,
                )
                st.success(f"Progetto creato con successo! ID: {project_id}")
                st.rerun()
            except Exception as e:
                st.error(f"Errore nella creazione: {e}")

st.divider()

# ── Import da JSON ───────────────────────────────────────────────────────────
with st.expander("📥 Importa profilo da file JSON"):
    st.caption("Carica un file company_profile.json per creare un nuovo progetto.")
    uploaded = st.file_uploader("Seleziona file JSON", type=["json"])
    if uploaded:
        try:
            data = json.load(uploaded)
            st.json(data)
            st.info("Usa il form sopra per creare il progetto con questi dati.")
        except json.JSONDecodeError:
            st.error("File JSON non valido.")
