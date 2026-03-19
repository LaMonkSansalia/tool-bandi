"""
Gestione Progetti — lista, creazione, modifica, onboarding wizard.
"""
import json
import re
import streamlit as st
from engine.projects.manager import (
    get_active_projects, get_project_stats, create_project,
)
from engine.ui.utils.project_form import seed_from_profile_json, validate_project_form
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

if "project_seed" not in st.session_state:
    st.session_state["project_seed"] = {}

FORMA_GIURIDICA_OPTIONS = [
    "impresa individuale", "associazione", "pro loco", "fondazione",
    "cooperativa", "srl", "srls", "spa", "snc", "sas",
    "ente pubblico", "comune", "altro",
]
REGIONE_OPTIONS = [
    "Sicilia", "Calabria", "Campania", "Puglia", "Basilicata", "Sardegna",
    "Lazio", "Lombardia", "Piemonte", "Veneto", "Emilia-Romagna",
    "Toscana", "Liguria", "Marche", "Abruzzo", "Molise",
    "Friuli Venezia Giulia", "Trentino-Alto Adige", "Umbria", "Valle d'Aosta",
]

WIZARD_STEPS = [
    "Dati identificativi",
    "Profilo organizzazione",
    "Attivita, ATECO e dimensione",
    "Skills e template",
    "Revisione finale",
]
FORM_KEY_PREFIX = "project_form_"
BOOL_FIELDS = {"zona_zes", "zona_mezzogiorno", "micro_impresa", "iso_9001", "iso_27001", "soa"}
INT_FIELDS = {"anni_attivita", "dipendenti", "fatturato_max"}
FORM_DEFAULTS = {
    "new_slug": "",
    "new_nome": "",
    "new_desc_breve": "",
    "new_desc": "",
    "new_prefix": "",
    "new_chat_id": "",
    "denominazione": "",
    "forma_giuridica": FORMA_GIURIDICA_OPTIONS[0],
    "partita_iva": "",
    "regime_fiscale": "ordinario",
    "comune": "",
    "provincia": "",
    "regione": REGIONE_OPTIONS[0],
    "zona_zes": True,
    "zona_mezzogiorno": True,
    "ateco": "",
    "ateco_secondari_text": "",
    "settore": "",
    "data_inizio": "",
    "anni_attivita": 0,
    "dipendenti": 0,
    "fatturato_max": 0,
    "micro_impresa": True,
    "iso_9001": False,
    "iso_27001": False,
    "soa": False,
    "skills_text": "",
    "template_choice": next(iter(SCORING_TEMPLATES.keys())),
}


def _field_key(name: str) -> str:
    return f"{FORM_KEY_PREFIX}{name}"


def _normalize_value(name: str, value):
    if name in BOOL_FIELDS:
        return bool(value)
    if name in INT_FIELDS:
        try:
            return int(value or 0)
        except Exception:
            return 0
    if name == "template_choice" and value not in SCORING_TEMPLATES:
        return FORM_DEFAULTS["template_choice"]
    return value


def _initialize_form_state(seed_data: dict | None = None, reset: bool = False):
    seed_data = seed_data or {}
    for name, default in FORM_DEFAULTS.items():
        key = _field_key(name)
        if reset or key not in st.session_state:
            value = seed_data.get(name, default)
            st.session_state[key] = _normalize_value(name, value)


def _get_form_data() -> dict:
    data: dict = {}
    for name, default in FORM_DEFAULTS.items():
        data[name] = _normalize_value(name, st.session_state.get(_field_key(name), default))
    return data


def _parse_ateco_secondari(text: str) -> tuple[list[str], list[str]]:
    items = [x.strip() for x in text.splitlines() if x.strip()]
    invalid = [x for x in items if not re.fullmatch(r"\d{2}(?:\.\d{2}){0,2}", x)]
    return items, invalid


def _validate_step(step_idx: int, data: dict) -> list[str]:
    errors: list[str] = []
    if step_idx == 0:
        slug = str(data["new_slug"]).strip()
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,30}[a-z0-9]", slug):
            errors.append("Slug non valido: usa solo minuscole, numeri e trattini (3-32 caratteri).")
        if not str(data["new_nome"]).strip():
            errors.append("Nome progetto obbligatorio.")
    elif step_idx == 1:
        if not str(data["denominazione"]).strip():
            errors.append("Denominazione legale obbligatoria.")
        piva = str(data["partita_iva"]).strip().upper()
        if piva and not re.fullmatch(r"(?:\d{11}|[A-Z0-9]{16})", piva):
            errors.append("P.IVA/Codice Fiscale non valido.")
    elif step_idx == 2:
        ateco = str(data["ateco"]).strip()
        if ateco and not re.fullmatch(r"\d{2}(?:\.\d{2}){0,2}", ateco):
            errors.append("ATECO principale non valido (esempio corretto: 62.01.00).")
        data_inizio = str(data["data_inizio"]).strip()
        if data_inizio and not re.fullmatch(r"\d{2}/\d{2}/\d{4}", data_inizio):
            errors.append("Data inizio non valida (usa formato GG/MM/AAAA).")
        _, invalid_ateco_secondary = _parse_ateco_secondari(str(data["ateco_secondari_text"]))
        if invalid_ateco_secondary:
            errors.append("ATECO secondari non validi: " + ", ".join(invalid_ateco_secondary))
    return errors


def _validate_final(data: dict) -> list[str]:
    payload = {
        "new_slug": data["new_slug"],
        "new_nome": data["new_nome"],
        "denominazione": data["denominazione"],
        "ateco": data["ateco"],
        "partita_iva": data["partita_iva"],
        "data_inizio": data["data_inizio"],
    }
    errors = validate_project_form(payload)
    _, invalid_ateco_secondary = _parse_ateco_secondari(str(data["ateco_secondari_text"]))
    if invalid_ateco_secondary:
        errors.append("ATECO secondari non validi: " + ", ".join(invalid_ateco_secondary))
    return errors


if "project_wizard_step" not in st.session_state:
    st.session_state["project_wizard_step"] = 0

_initialize_form_state(st.session_state.get("project_seed", {}))

with st.expander("📥 Importa profilo JSON (prefill automatico)"):
    st.caption("Carica un `company_profile.json`: i campi del wizard verranno precompilati.")
    uploaded = st.file_uploader("Seleziona file JSON", type=["json"], key="project_profile_upload")
    if uploaded is not None:
        st.caption(f"File selezionato: `{uploaded.name}`")
        if st.button("Applica prefill", key="apply_project_seed", type="primary"):
            try:
                data = json.load(uploaded)
                seed = seed_from_profile_json(data)
                st.session_state["project_seed"] = seed
                _initialize_form_state(seed, reset=True)
                st.session_state["project_wizard_step"] = 0
                st.success("Prefill caricato: controlla i dati e prosegui step-by-step.")
                st.rerun()
            except json.JSONDecodeError:
                st.error("File JSON non valido.")
            except Exception as e:
                st.error(f"Errore durante l'import: {e}")

    if st.button("Pulisci prefill", key="clear_project_seed"):
        st.session_state["project_seed"] = {}
        _initialize_form_state({}, reset=True)
        st.session_state["project_wizard_step"] = 0
        st.rerun()

step_idx = int(st.session_state.get("project_wizard_step", 0))
step_idx = max(0, min(step_idx, len(WIZARD_STEPS) - 1))
st.session_state["project_wizard_step"] = step_idx
step_title = WIZARD_STEPS[step_idx]

st.progress((step_idx + 1) / len(WIZARD_STEPS), text=f"Step {step_idx + 1}/{len(WIZARD_STEPS)} — {step_title}")

form_data = _get_form_data()

if step_idx == 0:
    st.markdown("### 1) Dati identificativi")
    col_a, col_b = st.columns(2)
    with col_a:
        st.text_input(
            "Slug (identificativo breve)",
            key=_field_key("new_slug"),
            placeholder="es. pds",
            help="Solo lettere minuscole, numeri e trattini.",
        )
        st.text_input("Nome completo", key=_field_key("new_nome"), placeholder="es. Paese Delle Stelle")
        st.text_input(
            "Descrizione breve",
            key=_field_key("new_desc_breve"),
            placeholder="es. Astroturismo e cultura",
        )
        st.text_area(
            "Descrizione completa",
            key=_field_key("new_desc"),
            placeholder="Descrizione dettagliata del progetto, obiettivi, attività...",
        )
    with col_b:
        st.text_input("Prefisso Telegram", key=_field_key("new_prefix"), placeholder="es. [PDS]")
        st.text_input(
            "Chat ID Telegram (opzionale)",
            key=_field_key("new_chat_id"),
            placeholder="Lascia vuoto per usare quello globale",
        )

elif step_idx == 1:
    st.markdown("### 2) Profilo organizzazione")
    col_c, col_d = st.columns(2)
    with col_c:
        st.text_input("Denominazione legale", key=_field_key("denominazione"))
        forma_current = form_data["forma_giuridica"]
        if forma_current not in FORMA_GIURIDICA_OPTIONS:
            forma_current = FORMA_GIURIDICA_OPTIONS[0]
        st.selectbox(
            "Forma giuridica",
            FORMA_GIURIDICA_OPTIONS,
            index=FORMA_GIURIDICA_OPTIONS.index(forma_current),
            key=_field_key("forma_giuridica"),
        )
        st.text_input("P.IVA / Codice Fiscale", key=_field_key("partita_iva"))
        st.text_input("Regime fiscale", key=_field_key("regime_fiscale"))
    with col_d:
        st.text_input("Comune", key=_field_key("comune"), placeholder="es. Roccapalumba")
        st.text_input("Provincia", key=_field_key("provincia"), placeholder="es. PA")
        regione_current = form_data["regione"]
        if regione_current not in REGIONE_OPTIONS:
            regione_current = REGIONE_OPTIONS[0]
        st.selectbox(
            "Regione",
            REGIONE_OPTIONS,
            index=REGIONE_OPTIONS.index(regione_current),
            key=_field_key("regione"),
        )
        st.checkbox("Zona ZES", key=_field_key("zona_zes"))
        st.checkbox("Zona Mezzogiorno", key=_field_key("zona_mezzogiorno"))

elif step_idx == 2:
    st.markdown("### 3) Attivita, ATECO e dimensione")
    col_e, col_f = st.columns(2)
    with col_e:
        st.text_input(
            "Codice ATECO principale",
            key=_field_key("ateco"),
            placeholder="es. 79.90.20",
        )
        st.text_area(
            "ATECO secondari (uno per riga)",
            key=_field_key("ateco_secondari_text"),
            placeholder="62.01.00\n63.11.20",
        )
        st.text_input(
            "Settore principale",
            key=_field_key("settore"),
            placeholder="es. Turismo / Promozione culturale",
        )
        st.text_input("Data inizio attivita (GG/MM/AAAA)", key=_field_key("data_inizio"))
        st.number_input("Anni attivita", min_value=0, key=_field_key("anni_attivita"))
    with col_f:
        st.number_input("Dipendenti", min_value=0, key=_field_key("dipendenti"))
        st.number_input("Fatturato max (EUR)", min_value=0, key=_field_key("fatturato_max"))
        st.checkbox("Micro-impresa", key=_field_key("micro_impresa"))
        st.markdown("**Certificazioni possedute**")
        st.checkbox("ISO 9001", key=_field_key("iso_9001"))
        st.checkbox("ISO 27001", key=_field_key("iso_27001"))
        st.checkbox("SOA", key=_field_key("soa"))

elif step_idx == 3:
    st.markdown("### 4) Skills e template")
    st.text_area(
        "Competenze (una per riga)",
        key=_field_key("skills_text"),
        placeholder="Project management\nRendicontazione\nPartnership territoriali",
        height=180,
    )
    template_current = form_data["template_choice"]
    if template_current not in SCORING_TEMPLATES:
        template_current = next(iter(SCORING_TEMPLATES.keys()))
    st.selectbox(
        "Scegli un template di scoring",
        list(SCORING_TEMPLATES.keys()),
        index=list(SCORING_TEMPLATES.keys()).index(template_current),
        key=_field_key("template_choice"),
    )
    with st.expander("Anteprima template selezionato"):
        st.json(SCORING_TEMPLATES[st.session_state[_field_key("template_choice")]])

else:
    st.markdown("### 5) Revisione finale")
    col_r1, col_r2 = st.columns(2)
    with col_r1:
        st.markdown(f"**Slug:** `{form_data['new_slug']}`")
        st.markdown(f"**Nome:** {form_data['new_nome'] or '—'}")
        st.markdown(f"**Denominazione:** {form_data['denominazione'] or '—'}")
        st.markdown(f"**ATECO:** {form_data['ateco'] or '—'}")
        st.markdown(f"**Regione:** {form_data['regione'] or '—'}")
        st.markdown(f"**Template:** {form_data['template_choice']}")
    with col_r2:
        secondary_codes, invalid_secondary = _parse_ateco_secondari(str(form_data["ateco_secondari_text"]))
        st.markdown(f"**ATECO secondari:** {', '.join(secondary_codes) if secondary_codes else '—'}")
        st.markdown(f"**Competenze:** {len([x for x in str(form_data['skills_text']).splitlines() if x.strip()])}")
        if invalid_secondary:
            st.warning("ATECO secondari da correggere: " + ", ".join(invalid_secondary))

    if st.button("✅ Crea progetto", type="primary", use_container_width=True):
        form_data = _get_form_data()
        errors = _validate_final(form_data)
        if errors:
            for err in errors:
                st.error(err)
        else:
            ateco_secondari, _ = _parse_ateco_secondari(str(form_data["ateco_secondari_text"]))
            skills_keywords = [x.strip() for x in str(form_data["skills_text"]).splitlines() if x.strip()]
            skills_payload = {"keywords": skills_keywords} if skills_keywords else None

            profilo = {
                "anagrafica": {
                    "denominazione": form_data["denominazione"],
                    "partita_iva": form_data["partita_iva"],
                    "forma_giuridica": form_data["forma_giuridica"],
                    "regime_fiscale": form_data["regime_fiscale"],
                },
                "sede": {
                    "comune": form_data["comune"],
                    "provincia": form_data["provincia"],
                    "regione": form_data["regione"],
                    "zona_zes": form_data["zona_zes"],
                    "zona_mezzogiorno": form_data["zona_mezzogiorno"],
                },
                "attivita": {
                    "ateco_2025": form_data["ateco"],
                    "ateco_secondari": ateco_secondari,
                    "settore_principale": form_data["settore"],
                    "data_inizio": form_data["data_inizio"],
                    "anni_attivita": form_data["anni_attivita"],
                },
                "dimensione": {
                    "dipendenti": form_data["dipendenti"],
                    "fatturato_stimato_max": form_data["fatturato_max"],
                    "micro_impresa": form_data["micro_impresa"],
                },
                "certificazioni": {
                    # Keep None for missing SOA due to downstream boolean conversion logic.
                    "soa": "present" if form_data["soa"] else None,
                    "iso_9001": form_data["iso_9001"],
                    "iso_27001": form_data["iso_27001"],
                },
                "eligibility_constraints": {
                    "HARD_STOP": [],
                    "YELLOW_FLAG": [],
                    "VANTAGGI": [],
                },
            }

            scoring_rules = SCORING_TEMPLATES[form_data["template_choice"]]
            try:
                project_id = create_project(
                    slug=str(form_data["new_slug"]).strip(),
                    nome=str(form_data["new_nome"]).strip(),
                    profilo=profilo,
                    scoring_rules=scoring_rules,
                    descrizione=str(form_data["new_desc"]).strip() or None,
                    descrizione_breve=str(form_data["new_desc_breve"]).strip() or None,
                    skills=skills_payload,
                    telegram_chat_id=str(form_data["new_chat_id"]).strip() or None,
                    telegram_prefix=str(form_data["new_prefix"]).strip() or None,
                )
                st.success(f"Progetto creato con successo! ID: {project_id}")
                st.session_state["project_seed"] = {}
                _initialize_form_state({}, reset=True)
                st.session_state["project_wizard_step"] = 0
                st.rerun()
            except Exception as e:
                st.error(f"Errore nella creazione: {e}")

st.divider()
col_prev, col_next, col_reset = st.columns([1, 1, 2])
with col_prev:
    if st.button("← Indietro", disabled=step_idx == 0, use_container_width=True):
        st.session_state["project_wizard_step"] = max(0, step_idx - 1)
        st.rerun()
with col_next:
    if st.button("Avanti →", type="primary", disabled=step_idx >= len(WIZARD_STEPS) - 1, use_container_width=True):
        current_data = _get_form_data()
        step_errors = _validate_step(step_idx, current_data)
        if step_errors:
            for err in step_errors:
                st.error(err)
        else:
            st.session_state["project_wizard_step"] = min(len(WIZARD_STEPS) - 1, step_idx + 1)
            st.rerun()
with col_reset:
    if st.button("♻️ Reset wizard", use_container_width=True):
        st.session_state["project_seed"] = {}
        _initialize_form_state({}, reset=True)
        st.session_state["project_wizard_step"] = 0
        st.rerun()
