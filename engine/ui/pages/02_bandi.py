"""
Lista bandi — colonne smart compatte, filtri avanzati con expander, ordinamento configurabile.
Multi-project aware: reads from project_evaluations.
"""
from datetime import date, timedelta

import streamlit as st
import pandas as pd
import psycopg2
from engine.config import DATABASE_URL

st.title("📋 Bandi")

pid = st.session_state.get("current_project_id", 1)

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

TIPO_FIN_SHORT = {
    "fondo_perduto":             "FP",
    "prestito_agevolato":        "Prest.",
    "mix":                       "Mix",
    "contributo_conto_capitale": "C.Cap.",
    "voucher":                   "Vouch.",
    "altro":                     "Altro",
}

REGIONI_ITALIANE = [
    "Tutte", "Abruzzo", "Basilicata", "Calabria", "Campania",
    "Emilia-Romagna", "Friuli Venezia Giulia", "Lazio", "Liguria",
    "Lombardia", "Marche", "Molise", "Piemonte", "Puglia", "Sardegna",
    "Sicilia", "Toscana", "Trentino-Alto Adige", "Umbria",
    "Valle d'Aosta", "Veneto",
]


# ── Helpers ──────────────────────────────────────────────────────────────────

def stato_label(row) -> str:
    """Readable stato label with urgency indicator."""
    stato = row.get("stato", "")
    label = STATO_LABELS.get(stato, stato)
    scad = row.get("data_scadenza")
    if scad is None:
        return label
    try:
        days = (pd.Timestamp(scad).date() - date.today()).days
        if days < 0:
            return f"{label} ⚫"
        if days <= 7:
            return f"{label} 🔴"
        if days <= 14:
            return f"{label} 🟠"
        return label
    except Exception:
        return label


def importo_badge(row) -> str:
    """Compact importo + tipo finanziamento + aliquota."""
    imp = row.get("importo_max")
    if pd.isna(imp) or imp is None:
        return "—"
    # Format importo compatto: 50.000 → 50k, 1.500.000 → 1.5M
    if imp >= 1_000_000:
        imp_str = f"{imp/1_000_000:.1f}M"
    elif imp >= 1_000:
        imp_str = f"{imp/1_000:.0f}k"
    else:
        imp_str = f"{imp:,.0f}"

    tipo = row.get("tipo_finanziamento")
    aliq = row.get("aliquota_fondo_perduto")

    parts = [f"€{imp_str}"]
    if pd.notna(tipo) and tipo:
        parts.append(TIPO_FIN_SHORT.get(tipo, tipo[:5]))
    if pd.notna(aliq) and aliq is not None:
        parts.append(f"{int(aliq)}%")
    return " ".join(parts)


def scadenza_badge(row) -> str:
    """Scadenza with days left."""
    scad = row.get("data_scadenza")
    if scad is None:
        return "—"
    try:
        scad_date = pd.Timestamp(scad).date()
        days = (scad_date - date.today()).days
        formatted = scad_date.strftime("%d/%m")
        if days < 0:
            return f"{formatted} (scaduto)"
        return f"{formatted} ({days}gg)"
    except Exception:
        return str(scad)


def regioni_badge(row) -> str:
    """First 2 regions or 'Tutte'."""
    ra = row.get("regioni_ammesse")
    if not ra or not isinstance(ra, list) or len(ra) == 0:
        return "Tutte"
    if len(ra) <= 2:
        return ", ".join(ra)
    return f"{ra[0]}, {ra[1]} +{len(ra)-2}"


def gap_badge(row) -> str:
    """Count red/yellow gaps from gap_analysis JSONB."""
    gaps = row.get("gap_analysis")
    if not gaps or not isinstance(gaps, list):
        return "—"
    rossi = sum(1 for g in gaps if isinstance(g, dict) and g.get("semaforo") == "rosso")
    gialli = sum(1 for g in gaps if isinstance(g, dict) and g.get("semaforo") == "giallo")
    if rossi == 0 and gialli == 0:
        return "✅"
    parts = []
    if rossi:
        parts.append(f"{rossi}🔴")
    if gialli:
        parts.append(f"{gialli}🟡")
    return " ".join(parts)


# ── Filtri (sidebar) ─────────────────────────────────────────────────────────
with st.sidebar:
    st.subheader("Filtri")

    # -- Filtri rapidi (sempre visibili)
    search_query = st.text_input("🔍 Cerca titolo / ente", placeholder="es. digitalizzazione")

    stato_filter = st.multiselect(
        "Stato",
        options=list(STATO_LABELS.keys()),
        default=[],
        format_func=lambda s: STATO_LABELS.get(s, s),
        help="Vuoto = mostra tutti (esclusi archiviati)",
    )

    solo_non_scaduti = st.checkbox("Nascondi scaduti", value=False)

    st.divider()

    # -- Finanziamento (expander)
    with st.expander("💰 Finanziamento"):
        tipo_fin_options = {
            "fondo_perduto": "🟢 Fondo perduto",
            "prestito_agevolato": "🔵 Prestito agevolato",
            "mix": "🟡 Mix (FP + Prestito)",
            "contributo_conto_capitale": "🟢 Conto capitale",
            "voucher": "🟣 Voucher",
        }
        tipo_fin_filter = st.multiselect(
            "Tipo finanziamento", options=list(tipo_fin_options.keys()),
            format_func=lambda k: tipo_fin_options[k],
        )
        col_imp_min, col_imp_max = st.columns(2)
        with col_imp_min:
            importo_min = st.number_input("Importo min €", min_value=0, step=5000, value=0)
        with col_imp_max:
            importo_max_filter = st.number_input("Importo max €", min_value=0, step=5000, value=0)

    # -- Requisiti (expander)
    with st.expander("📋 Requisiti"):
        regione_filter = st.selectbox("Regione", options=REGIONI_ITALIANE)
        ateco_filter = st.text_input("Settore ATECO (prefisso)", placeholder="es. 62")
        tipo_ben_options = [
            "impresa_individuale", "srl", "spa", "societa_di_persone",
            "pmi", "micro_impresa", "startup", "associazione",
            "pro_loco", "ente_pubblico", "tutti",
        ]
        tipo_ben_filter = st.multiselect("Tipo beneficiario", options=tipo_ben_options)

    # -- Score & Urgenza (expander)
    with st.expander("📊 Score & Urgenza"):
        score_min = st.slider("Score minimo", 0, 100, 0)
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

# Stato filter: if empty → show all except archiviato
if stato_filter:
    where.append("pe.stato = ANY(%s)")
    params.append(stato_filter)
else:
    where.append("pe.stato != 'archiviato'")

# Score
if score_min > 0:
    where.append("(pe.score >= %s OR pe.score IS NULL)")
    params.append(score_min)

# Nascondi scaduti
if solo_non_scaduti:
    where.append("(b.data_scadenza IS NULL OR b.data_scadenza >= %s)")
    params.append(date.today())

# Ricerca testo
if search_query:
    where.append("(b.titolo ILIKE %s OR b.ente_erogatore ILIKE %s)")
    params += [f"%{search_query}%", f"%{search_query}%"]

# Tipo finanziamento
if tipo_fin_filter:
    where.append("b.tipo_finanziamento = ANY(%s)")
    params.append(tipo_fin_filter)

# Importo range
if importo_min > 0:
    where.append("(b.importo_max >= %s OR b.importo_max IS NULL)")
    params.append(importo_min)
if importo_max_filter > 0:
    where.append("(b.importo_max <= %s OR b.importo_max IS NULL)")
    params.append(importo_max_filter)

# Regione
if regione_filter != "Tutte":
    where.append("(%s ILIKE ANY(b.regioni_ammesse) OR b.regioni_ammesse IS NULL OR array_length(b.regioni_ammesse, 1) IS NULL)")
    params.append(regione_filter.lower())

# ATECO prefix
if ateco_filter:
    where.append("(EXISTS (SELECT 1 FROM unnest(b.settori_ateco) a WHERE a ILIKE %s) OR b.settori_ateco IS NULL OR array_length(b.settori_ateco, 1) IS NULL)")
    params.append(f"{ateco_filter}%")

# Tipo beneficiario
if tipo_ben_filter:
    where.append("(b.tipo_beneficiario && %s::text[] OR b.tipo_beneficiario IS NULL OR array_length(b.tipo_beneficiario, 1) IS NULL)")
    params.append(tipo_ben_filter)

# Scadenza entro N giorni
if scadenza_max_gg > 0:
    where.append("(b.data_scadenza <= %s)")
    params.append(date.today() + timedelta(days=scadenza_max_gg))

# Portale
if portale_filter:
    where.append("b.portale = ANY(%s)")
    params.append(portale_filter)

# ── Ordinamento ──────────────────────────────────────────────────────────────
sort_options = {
    "Rilevanza (stato + scadenza)": """
        CASE pe.stato
            WHEN 'lavorazione' THEN 1 WHEN 'pronto' THEN 2
            WHEN 'idoneo' THEN 3 WHEN 'analisi' THEN 4
            WHEN 'nuovo' THEN 5 ELSE 6
        END, b.data_scadenza ASC NULLS LAST""",
    "Score decrescente": "pe.score DESC NULLS LAST",
    "Scadenza crescente": "b.data_scadenza ASC NULLS LAST",
    "Importo decrescente": "b.importo_max DESC NULLS LAST",
    "Piu' recenti": "b.first_seen_at DESC NULLS LAST",
}

sql = f"""
    SELECT b.id, b.titolo, b.ente_erogatore, b.portale, b.data_scadenza,
           pe.score, pe.stato, b.first_seen_at,
           b.importo_max, b.tipo_finanziamento, b.aliquota_fondo_perduto,
           b.regioni_ammesse, b.tipo_beneficiario,
           pe.gap_analysis
    FROM bandi b
    JOIN project_evaluations pe ON pe.bando_id = b.id
    WHERE {' AND '.join(where)}
    ORDER BY
        CASE pe.stato
            WHEN 'lavorazione' THEN 1
            WHEN 'pronto'      THEN 2
            WHEN 'idoneo'      THEN 3
            WHEN 'analisi'     THEN 4
            WHEN 'nuovo'       THEN 5
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
    # Check if there ARE bandi but filters hide them
    try:
        conn_check = psycopg2.connect(DATABASE_URL)
        df_check = pd.read_sql(
            "SELECT COUNT(*) as n FROM project_evaluations WHERE project_id = %s",
            conn_check, params=[pid],
        )
        conn_check.close()
        total = int(df_check["n"].iloc[0]) if not df_check.empty else 0
    except Exception:
        total = 0

    if total > 0:
        st.warning(
            f"Nessun bando visibile con i filtri attuali, ma il progetto ha **{total} bandi** valutati. "
            "Prova a deselezionare **Nascondi scaduti** o a cambiare i filtri di stato."
        )
    else:
        st.info("Nessun bando trovato. Avvia una scansione dalla sidebar.")
    st.stop()

# ── Colonne smart ────────────────────────────────────────────────────────────
df["Stato"] = df.apply(stato_label, axis=1)
df["Importo"] = df.apply(importo_badge, axis=1)
df["Score"] = df["score"].apply(lambda s: f"{int(s)}/100" if pd.notna(s) else "—")
df["Scadenza"] = df.apply(scadenza_badge, axis=1)
df["Regione"] = df.apply(regioni_badge, axis=1)
df["Gap"] = df.apply(gap_badge, axis=1)

# ── Toolbar ──────────────────────────────────────────────────────────────────
col_count, col_sort, col_export = st.columns([3, 3, 1])
with col_count:
    st.write(f"**{len(df)} bandi** trovati")
with col_sort:
    sort_key = st.selectbox("Ordina per", options=list(sort_options.keys()), label_visibility="collapsed")
with col_export:
    csv_data = df[["titolo", "ente_erogatore", "portale", "data_scadenza", "score", "stato",
                   "importo_max", "tipo_finanziamento"]].to_csv(index=False)
    st.download_button(
        "⬇️ CSV", data=csv_data, file_name="bandi_export.csv", mime="text/csv",
    )

# Apply sorting (re-query would be better but for now sort the dataframe)
if sort_key == "Score decrescente":
    df = df.sort_values("score", ascending=False, na_position="last")
elif sort_key == "Scadenza crescente":
    df = df.sort_values("data_scadenza", ascending=True, na_position="last")
elif sort_key == "Importo decrescente":
    df = df.sort_values("importo_max", ascending=False, na_position="last")
elif sort_key == "Piu' recenti":
    df = df.sort_values("first_seen_at", ascending=False, na_position="last")
# Default "Rilevanza" keeps the SQL ORDER BY

# Reset index after sorting so iloc matches visual position
df = df.reset_index(drop=True)

# ── Tabella ──────────────────────────────────────────────────────────────────
st.caption("Clicca su una riga per aprire il dettaglio del bando.")

selected = st.dataframe(
    df[["Stato", "titolo", "ente_erogatore", "Importo", "Score", "Scadenza", "Regione", "Gap"]],
    use_container_width=True,
    hide_index=True,
    on_select="rerun",
    selection_mode="single-row",
    column_config={
        "Stato": st.column_config.TextColumn("Stato", width="small"),
        "titolo": st.column_config.TextColumn("Titolo", width="large"),
        "ente_erogatore": st.column_config.TextColumn("Ente", width="medium"),
    },
)

# Navigazione al dettaglio
if selected and selected.selection.rows:
    row_idx = selected.selection.rows[0]
    bando_id = int(df.iloc[row_idx]["id"])
    st.session_state["selected_bando_id"] = bando_id
    st.session_state["bando_id"] = bando_id
    st.switch_page("pages/03_dettaglio.py")
