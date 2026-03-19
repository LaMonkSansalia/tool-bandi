"""
Bandi command center with strategic decision columns.
Multi-project aware: supports project-scoped evaluations + optional live scoring.
"""
from datetime import date, timedelta

import pandas as pd
import psycopg2
import streamlit as st

from engine.config import DATABASE_URL
from engine.eligibility.configurable_scorer import score_bando_configurable
from engine.eligibility.hard_stops import check_hard_stops
from engine.eligibility.rules import get_profile
from engine.projects.manager import get_project_scoring_rules
from engine.ui.utils.decision_helpers import infer_bando_phase_key

st.title("📋 Bandi — Command Center")

pid = st.session_state.get("current_project_id", 1)
TODAY = date.today()

STATO_LABELS = {
    "idoneo": "🟢 Idoneo",
    "lavorazione": "🟡 In lavorazione",
    "pronto": "🟠 Pronto",
    "nuovo": "🔵 Nuovo",
    "analisi": "🟣 In analisi",
    "inviato": "✅ Inviato",
    "scartato": "🔻 Scartato",
    "archiviato": "⬜ Archiviato",
}

REGIONI_ITALIANE = [
    "Tutte", "Abruzzo", "Basilicata", "Calabria", "Campania",
    "Emilia-Romagna", "Friuli Venezia Giulia", "Lazio", "Liguria",
    "Lombardia", "Marche", "Molise", "Piemonte", "Puglia", "Sardegna",
    "Sicilia", "Toscana", "Trentino-Alto Adige", "Umbria",
    "Valle d'Aosta", "Veneto",
]

PHASE_LABELS = {
    "aperto": "🟢 Aperto",
    "annunciato": "📣 Annunciato",
    "chiuso": "⚫ Chiuso",
}

IDONEITA_LABELS = {
    "si": "✅ Sì",
    "no": "❌ No",
    "na": "⚪ Da valutare",
}


# ── Helpers ──────────────────────────────────────────────────────────────────
def _to_date(value):
    if value is None or pd.isna(value):
        return None
    try:
        return pd.Timestamp(value).date()
    except Exception:
        return None


def _format_currency_eur(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "—"
    value = float(value)
    if value >= 1_000_000:
        return f"€{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"€{value / 1_000:.0f}k"
    return f"€{value:,.0f}"


def stato_label(row) -> str:
    stato = row.get("stato", "")
    label = STATO_LABELS.get(stato, stato)
    scad_date = _to_date(row.get("data_scadenza"))
    if scad_date is None:
        return label
    days = (scad_date - TODAY).days
    if days < 0:
        return f"{label} ⚫"
    if days <= 7:
        return f"{label} 🔴"
    if days <= 14:
        return f"{label} 🟠"
    return label


def scadenza_badge(row) -> str:
    scad_date = _to_date(row.get("data_scadenza"))
    if scad_date is None:
        return "—"
    days = (scad_date - TODAY).days
    if days < 0:
        return f"{scad_date:%d/%m} (scaduto)"
    return f"{scad_date:%d/%m} ({days}gg)"


def regioni_badge(row) -> str:
    ra = row.get("regioni_ammesse")
    if not ra or not isinstance(ra, list):
        return "Tutte"
    if len(ra) <= 2:
        return ", ".join(ra)
    return f"{ra[0]}, {ra[1]} +{len(ra) - 2}"


def gap_badge(row) -> str:
    gaps = row.get("gap_analysis")
    if not gaps or not isinstance(gaps, list):
        return "—"
    red = sum(1 for g in gaps if isinstance(g, dict) and g.get("semaforo") == "rosso")
    yellow = sum(1 for g in gaps if isinstance(g, dict) and g.get("semaforo") == "giallo")
    if red == 0 and yellow == 0:
        return "✅"
    parts = []
    if red:
        parts.append(f"{red}🔴")
    if yellow:
        parts.append(f"{yellow}🟡")
    return " ".join(parts)


def budget_badge(row) -> str:
    budget_totale = row.get("budget_totale")
    importo_max = row.get("importo_max")
    if pd.notna(budget_totale) and budget_totale is not None:
        return f"{_format_currency_eur(budget_totale)} (totale)"
    if pd.notna(importo_max) and importo_max is not None:
        return f"{_format_currency_eur(importo_max)} (max)"
    return "—"


def budget_value(row) -> float | None:
    budget_totale = row.get("budget_totale")
    importo_max = row.get("importo_max")
    if pd.notna(budget_totale) and budget_totale is not None:
        return float(budget_totale)
    if pd.notna(importo_max) and importo_max is not None:
        return float(importo_max)
    return None


def infer_bando_phase(row) -> str:
    phase_key = infer_bando_phase_key(row, today=TODAY)
    return PHASE_LABELS.get(phase_key, PHASE_LABELS["aperto"])


def stored_idoneita(row):
    score = pd.to_numeric(row.get("score"), errors="coerce")
    stato = row.get("stato")
    if row.get("hard_stop_reason"):
        return False
    if pd.notna(score):
        return float(score) >= 40
    if stato in {"idoneo", "lavorazione", "pronto", "inviato"}:
        return True
    if stato == "scartato":
        return False
    return None


def idoneita_label(row) -> str:
    value = row.get("idoneita_current")
    if value is True:
        return IDONEITA_LABELS["si"]
    if value is False:
        return IDONEITA_LABELS["no"]
    return IDONEITA_LABELS["na"]


def apply_live_scoring(df: pd.DataFrame, project_id: int) -> pd.DataFrame:
    df = df.copy()
    profile = get_profile(project_id)
    scoring_rules = get_project_scoring_rules(project_id) or {}

    live_scores: list[float | None] = []
    live_eligibility: list[bool | None] = []
    live_hs_reason: list[str | None] = []

    for row in df.to_dict("records"):
        hs = check_hard_stops(row, profile)
        if hs.excluded:
            live_scores.append(None)
            live_eligibility.append(False)
            live_hs_reason.append(hs.reason)
            continue

        score_result = score_bando_configurable(row, profile, scoring_rules)
        live_scores.append(score_result.score)
        live_eligibility.append(score_result.score >= 40)
        live_hs_reason.append(None)

    df["score_live"] = live_scores
    df["idoneita_live"] = live_eligibility
    df["hard_stop_reason_live"] = live_hs_reason
    return df


# ── Filtri (sidebar) ─────────────────────────────────────────────────────────
with st.sidebar:
    st.subheader("Filtri Command Center")

    search_query = st.text_input("🔍 Cerca titolo / ente", placeholder="es. digitalizzazione")

    stato_filter = st.multiselect(
        "Stato pratica",
        options=list(STATO_LABELS.keys()),
        default=[],
        format_func=lambda s: STATO_LABELS.get(s, s),
        help="Vuoto = mostra tutti (esclusi archiviati)",
    )

    fase_filter = st.multiselect(
        "Status bando",
        options=["Aperto", "Annunciato", "Chiuso"],
        default=["Aperto", "Annunciato"],
    )
    idoneita_filter = st.multiselect(
        "Idoneità",
        options=["Sì", "No", "Da valutare"],
        default=["Sì", "No", "Da valutare"],
    )
    use_live_scoring = st.toggle(
        "Ricalcolo score live",
        value=True,
        help="Ricalcola score e idoneità sul profilo del progetto selezionato.",
    )

    solo_non_scaduti = st.checkbox("Nascondi scaduti", value=False)

    st.divider()

    with st.expander("💰 Finanziamento"):
        tipo_fin_options = {
            "fondo_perduto": "🟢 Fondo perduto",
            "prestito_agevolato": "🔵 Prestito agevolato",
            "mix": "🟡 Mix (FP + Prestito)",
            "contributo_conto_capitale": "🟢 Conto capitale",
            "voucher": "🟣 Voucher",
        }
        tipo_fin_filter = st.multiselect(
            "Tipo finanziamento",
            options=list(tipo_fin_options.keys()),
            format_func=lambda k: tipo_fin_options[k],
        )
        col_imp_min, col_imp_max = st.columns(2)
        with col_imp_min:
            importo_min = st.number_input("Importo min €", min_value=0, step=5000, value=0)
        with col_imp_max:
            importo_max_filter = st.number_input("Importo max €", min_value=0, step=5000, value=0)

    with st.expander("📋 Requisiti"):
        regione_filter = st.selectbox("Regione", options=REGIONI_ITALIANE)
        ateco_filter = st.text_input("Settore ATECO (prefisso)", placeholder="es. 62")
        tipo_ben_options = [
            "impresa_individuale", "srl", "spa", "societa_di_persone",
            "pmi", "micro_impresa", "startup", "associazione",
            "pro_loco", "ente_pubblico", "tutti",
        ]
        tipo_ben_filter = st.multiselect("Tipo beneficiario", options=tipo_ben_options)

    with st.expander("📊 Score & Urgenza"):
        score_range = st.slider("Score finanziabilita", 0, 100, (0, 100))
        scadenza_max_gg = st.select_slider(
            "Scadenza entro",
            options=[0, 7, 14, 30, 60, 90, 180],
            value=0,
            format_func=lambda d: "Tutti" if d == 0 else f"{d} giorni",
        )
        portale_options = [
            "invitalia", "regione_sicilia", "mimit", "padigitale",
            "inpa", "comune_palermo", "euroinfosicilia",
        ]
        portale_filter = st.multiselect("Portale", options=portale_options)

    if st.button("🔄 Reset filtri"):
        st.rerun()


# ── Query SQL ────────────────────────────────────────────────────────────────
where = ["pe.project_id = %s"]
params: list = [pid]

if stato_filter:
    where.append("pe.stato = ANY(%s)")
    params.append(stato_filter)
else:
    where.append("pe.stato != 'archiviato'")

if solo_non_scaduti:
    where.append("(b.data_scadenza IS NULL OR b.data_scadenza >= %s)")
    params.append(TODAY)

if search_query:
    where.append("(b.titolo ILIKE %s OR b.ente_erogatore ILIKE %s)")
    params += [f"%{search_query}%", f"%{search_query}%"]

if tipo_fin_filter:
    where.append("b.tipo_finanziamento = ANY(%s)")
    params.append(tipo_fin_filter)

if importo_min > 0:
    where.append("(b.importo_max >= %s OR b.importo_max IS NULL)")
    params.append(importo_min)
if importo_max_filter > 0:
    where.append("(b.importo_max <= %s OR b.importo_max IS NULL)")
    params.append(importo_max_filter)

if regione_filter != "Tutte":
    where.append(
        "(%s ILIKE ANY(b.regioni_ammesse) "
        "OR b.regioni_ammesse IS NULL "
        "OR array_length(b.regioni_ammesse, 1) IS NULL)"
    )
    params.append(regione_filter.lower())

if ateco_filter:
    where.append(
        "(EXISTS (SELECT 1 FROM unnest(b.settori_ateco) a WHERE a ILIKE %s) "
        "OR b.settori_ateco IS NULL "
        "OR array_length(b.settori_ateco, 1) IS NULL)"
    )
    params.append(f"{ateco_filter}%")

if tipo_ben_filter:
    where.append(
        "(b.tipo_beneficiario && %s::text[] "
        "OR b.tipo_beneficiario IS NULL "
        "OR array_length(b.tipo_beneficiario, 1) IS NULL)"
    )
    params.append(tipo_ben_filter)

if scadenza_max_gg > 0:
    where.append("(b.data_scadenza <= %s)")
    params.append(TODAY + timedelta(days=scadenza_max_gg))

if portale_filter:
    where.append("b.portale = ANY(%s)")
    params.append(portale_filter)

sql = f"""
    SELECT
        b.id,
        b.titolo,
        b.ente_erogatore,
        b.portale,
        b.data_pubblicazione,
        b.data_scadenza,
        b.first_seen_at,
        b.budget_totale,
        b.importo_max,
        b.tipo_finanziamento,
        b.aliquota_fondo_perduto,
        b.regioni_ammesse,
        b.tipo_beneficiario,
        b.settori_ateco,
        b.fatturato_minimo,
        b.dipendenti_minimi,
        b.anzianita_minima_anni,
        b.soa_richiesta,
        b.certificazioni_richieste,
        b.raw_text,
        b.metadata,
        pe.score,
        pe.stato,
        pe.hard_stop_reason,
        pe.gap_analysis
    FROM bandi b
    JOIN project_evaluations pe ON pe.bando_id = b.id
    WHERE {' AND '.join(where)}
    ORDER BY
        CASE pe.stato
            WHEN 'lavorazione' THEN 1
            WHEN 'pronto' THEN 2
            WHEN 'idoneo' THEN 3
            WHEN 'analisi' THEN 4
            WHEN 'nuovo' THEN 5
            ELSE 6
        END,
        b.data_scadenza ASC NULLS LAST
"""

try:
    conn = psycopg2.connect(DATABASE_URL)
    df = pd.read_sql(sql, conn, params=params)
    conn.close()
except psycopg2.OperationalError:
    st.warning("Database non raggiungibile. Avvia: `docker compose up -d postgres`")
    st.stop()
except Exception as e:
    st.error(f"Errore DB: {e}")
    st.stop()

if df.empty:
    try:
        conn_check = psycopg2.connect(DATABASE_URL)
        df_check = pd.read_sql(
            "SELECT COUNT(*) as n FROM project_evaluations WHERE project_id = %s",
            conn_check,
            params=[pid],
        )
        conn_check.close()
        total = int(df_check["n"].iloc[0]) if not df_check.empty else 0
    except Exception:
        total = 0

    if total > 0:
        st.warning(
            f"Nessun bando visibile con i filtri attuali, ma il progetto ha **{total} bandi** valutati. "
            "Prova a ridurre i filtri attivi."
        )
    else:
        st.info("Nessun bando trovato. Avvia una scansione dalla sidebar.")
    st.stop()

if use_live_scoring:
    try:
        with st.spinner("Ricalcolo score/idoneità sul progetto corrente..."):
            df = apply_live_scoring(df, pid)
        df["score_current"] = pd.to_numeric(df["score_live"], errors="coerce")
        df["idoneita_current"] = df["idoneita_live"]
        df["hard_stop_reason_current"] = df["hard_stop_reason_live"]
        st.caption("Score e idoneita' mostrati sono ricalcolati live sul progetto selezionato.")
    except Exception as e:
        st.warning(f"Ricalcolo live non disponibile ({e}). Uso score salvato.")
        df["score_current"] = pd.to_numeric(df["score"], errors="coerce")
        df["idoneita_current"] = df.apply(stored_idoneita, axis=1)
        df["hard_stop_reason_current"] = df["hard_stop_reason"]
else:
    df["score_current"] = pd.to_numeric(df["score"], errors="coerce")
    df["idoneita_current"] = df.apply(stored_idoneita, axis=1)
    df["hard_stop_reason_current"] = df["hard_stop_reason"]

df["Idoneita"] = df.apply(idoneita_label, axis=1)
df["Score Finanziabilita"] = df["score_current"].round().astype("Int64")
df["Budget"] = df.apply(budget_badge, axis=1)
df["Budget_raw"] = df.apply(budget_value, axis=1)
df["Status"] = df.apply(infer_bando_phase, axis=1)
df["Stato"] = df.apply(stato_label, axis=1)
df["Scadenza"] = df.apply(scadenza_badge, axis=1)
df["Regione"] = df.apply(regioni_badge, axis=1)
df["Gap"] = df.apply(gap_badge, axis=1)

phase_filter_labels = {
    "Aperto": PHASE_LABELS["aperto"],
    "Annunciato": PHASE_LABELS["annunciato"],
    "Chiuso": PHASE_LABELS["chiuso"],
}
if fase_filter:
    df = df[df["Status"].isin([phase_filter_labels[x] for x in fase_filter])]

idoneita_filter_labels = {
    "Sì": IDONEITA_LABELS["si"],
    "No": IDONEITA_LABELS["no"],
    "Da valutare": IDONEITA_LABELS["na"],
}
if idoneita_filter:
    df = df[df["Idoneita"].isin([idoneita_filter_labels[x] for x in idoneita_filter])]

score_min, score_max = score_range
if score_min > 0 or score_max < 100:
    df = df[
        df["Score Finanziabilita"].notna()
        & (df["Score Finanziabilita"] >= score_min)
        & (df["Score Finanziabilita"] <= score_max)
    ]

if df.empty:
    st.warning("Nessun bando corrisponde ai filtri decisionali correnti.")
    st.stop()

# ── Toolbar ──────────────────────────────────────────────────────────────────
sort_options = [
    "Priorita operativa",
    "Score finanziabilita",
    "Scadenza",
    "Budget",
    "Piu recenti",
]

col_count, col_sort, col_export = st.columns([3, 3, 1])
with col_count:
    eligible_count = int((df["idoneita_current"] == True).sum())  # noqa: E712
    open_count = int((df["Status"] == PHASE_LABELS["aperto"]).sum())
    st.write(f"**{len(df)} bandi** | **{eligible_count} idonei** | **{open_count} aperti**")
with col_sort:
    sort_key = st.selectbox("Ordina per", options=sort_options, label_visibility="collapsed")
with col_export:
    csv_data = df[
        [
            "titolo", "ente_erogatore", "portale", "data_pubblicazione", "data_scadenza",
            "Score Finanziabilita", "Idoneita", "Status", "Budget", "Stato",
        ]
    ].to_csv(index=False)
    st.download_button("⬇️ CSV", data=csv_data, file_name="bandi_command_center.csv", mime="text/csv")

if sort_key == "Score finanziabilita":
    df = df.sort_values(["score_current", "data_scadenza"], ascending=[False, True], na_position="last")
elif sort_key == "Scadenza":
    df = df.sort_values("data_scadenza", ascending=True, na_position="last")
elif sort_key == "Budget":
    df = df.sort_values("Budget_raw", ascending=False, na_position="last")
elif sort_key == "Piu recenti":
    df = df.sort_values("first_seen_at", ascending=False, na_position="last")

df = df.reset_index(drop=True)

# ── Tabella ──────────────────────────────────────────────────────────────────
st.caption("Clicca su una riga per aprire il dettaglio del bando.")

selected = st.dataframe(
    df[
        [
            "Idoneita",
            "Score Finanziabilita",
            "Budget",
            "Status",
            "Stato",
            "titolo",
            "ente_erogatore",
            "Scadenza",
            "Regione",
            "Gap",
        ]
    ],
    width="stretch",
    hide_index=True,
    on_select="rerun",
    selection_mode="single-row",
    column_config={
        "Idoneita": st.column_config.TextColumn("Idoneità", width="small"),
        "Score Finanziabilita": st.column_config.ProgressColumn(
            "Score",
            help="Score di finanziabilita 0-100",
            min_value=0,
            max_value=100,
            format="%d",
            width="small",
        ),
        "Budget": st.column_config.TextColumn("Budget", width="small"),
        "Status": st.column_config.TextColumn("Status", width="small"),
        "Stato": st.column_config.TextColumn("Stato pratica", width="small"),
        "titolo": st.column_config.TextColumn("Titolo", width="large"),
        "ente_erogatore": st.column_config.TextColumn("Ente", width="medium"),
    },
)

if selected and selected.selection.rows:
    row_idx = selected.selection.rows[0]
    bando_id = int(df.iloc[row_idx]["id"])
    st.session_state["selected_bando_id"] = bando_id
    st.session_state["bando_id"] = bando_id
    st.switch_page("pages/03_dettaglio.py")
