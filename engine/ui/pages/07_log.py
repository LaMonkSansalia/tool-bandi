"""
Pagina 07 — Log & Monitoraggio
Storico esecuzioni pipeline, errori spider, statistiche.
"""
import pandas as pd
import plotly.express as px
import psycopg2
import streamlit as st

from engine.config import DATABASE_URL

st.title("📜 Log & Monitoraggio")


def query_df(sql: str, params=None) -> pd.DataFrame:
    try:
        conn = psycopg2.connect(DATABASE_URL)
        df = pd.read_sql(sql, conn, params=params)
        conn.close()
        return df
    except psycopg2.OperationalError:
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Errore DB: {e}")
        return pd.DataFrame()


# ── Ultima scansione ──────────────────────────────────────────────────────────
st.subheader("🔄 Ultima scansione")

try:
    from engine.pipeline.monitor import get_last_run_summary
    last_run = get_last_run_summary()
    if last_run:
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("Data", last_run.get("started_at", "N/D"))
        with col2:
            st.metric("Durata", f"{last_run.get('duration_seconds', '?')}s")
        with col3:
            st.metric("Scraped", last_run.get("scraped", 0))
        with col4:
            st.metric("Inseriti", last_run.get("inserted", 0))
        with col5:
            failures = last_run.get("spider_failures", 0)
            st.metric("Spider falliti", failures, delta=None if failures == 0 else f"⚠️ {failures}")

        if last_run.get("errors"):
            st.error(f"Errori: {last_run['errors']}")
    else:
        st.info("Nessuna scansione registrata. Avvia la prima scansione dalla pagina Configurazione.")
except ImportError:
    st.warning("Monitor non disponibile.")

st.divider()

# ── Storico scansioni ─────────────────────────────────────────────────────────
st.subheader("📊 Storico scansioni (ultime 30)")

df_runs = query_df("""
    SELECT
        started_at::date AS data,
        started_at::time AS ora,
        duration_seconds AS durata_s,
        scraped, inserted, updated, notified,
        spider_failures AS falliti,
        CASE WHEN errors IS NOT NULL THEN '❌' ELSE '✅' END AS esito
    FROM pipeline_runs
    ORDER BY started_at DESC
    LIMIT 30
""")

if not df_runs.empty:
    # Chart: bandi inseriti per giorno
    df_chart = df_runs.copy()
    df_chart["data"] = pd.to_datetime(df_chart["data"])
    fig = px.bar(
        df_chart.sort_values("data"),
        x="data", y="inserted",
        labels={"data": "Data", "inserted": "Bandi inseriti"},
        color_discrete_sequence=["#1a1a6e"],
        title="Bandi inseriti per scansione",
    )
    fig.update_layout(height=230, margin=dict(l=0, r=0, t=30, b=0))
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(df_runs, use_container_width=True, hide_index=True)
else:
    st.info("Nessuna scansione nel database. La tabella verrà creata automaticamente alla prima esecuzione.")

st.divider()

# ── Spider health ─────────────────────────────────────────────────────────────
st.subheader("🕷️ Salute spider (ultimi 7 giorni)")

df_spider = query_df("""
    SELECT
        portale,
        COUNT(*) AS bandi_trovati,
        MAX(first_seen_at)::date AS ultimo_trovato,
        MIN(first_seen_at)::date AS primo_trovato
    FROM bandi
    WHERE first_seen_at > NOW() - INTERVAL '7 days'
    GROUP BY portale
    ORDER BY bandi_trovati DESC
""")

PORTALI_ATTESI = [
    "invitalia", "regione_sicilia", "mimit", "padigitale",
    "inpa", "comune_palermo", "euroinfosicilia",
]

if not df_spider.empty:
    portali_attivi = set(df_spider["portale"].tolist())
    portali_silenziosi = [p for p in PORTALI_ATTESI if p not in portali_attivi]

    if portali_silenziosi:
        st.warning(
            f"⚠️ Spider silenziosi (nessun bando negli ultimi 7gg): "
            f"`{'`, `'.join(portali_silenziosi)}`\n\n"
            "Potrebbe indicare un cambio di struttura del portale."
        )

    df_spider["🚦"] = df_spider["portale"].apply(
        lambda p: "🟢" if p in portali_attivi else "🔴"
    )
    st.dataframe(
        df_spider[["🚦", "portale", "bandi_trovati", "ultimo_trovato", "primo_trovato"]],
        use_container_width=True, hide_index=True,
    )
else:
    st.info("Nessun dato spider disponibile.")
    for portale in PORTALI_ATTESI:
        st.markdown(f"⚪ `{portale}` — nessun dato")

st.divider()

# ── Trend bandi ───────────────────────────────────────────────────────────────
st.subheader("📈 Trend bandi (ultimi 30 giorni)")

df_trend = query_df("""
    SELECT
        DATE(first_seen_at) AS giorno,
        COUNT(*) AS nuovi,
        COUNT(CASE WHEN stato IN ('idoneo','lavorazione','pronto') THEN 1 END) AS idonei
    FROM bandi
    WHERE first_seen_at > NOW() - INTERVAL '30 days'
    GROUP BY DATE(first_seen_at)
    ORDER BY giorno
""")

if not df_trend.empty:
    df_trend["giorno"] = pd.to_datetime(df_trend["giorno"])
    fig = px.line(
        df_trend, x="giorno", y=["nuovi", "idonei"],
        labels={"value": "N. bandi", "giorno": "Giorno", "variable": ""},
        color_discrete_sequence=["#1a1a6e", "#2d7d2d"],
    )
    fig.update_layout(height=250, margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Dati insufficienti per il trend.")

st.divider()

# ── Log file ──────────────────────────────────────────────────────────────────
st.subheader("📄 File di log")

from pathlib import Path
log_dir = Path(__file__).parent.parent.parent.parent / "logs"
if log_dir.exists():
    log_files = sorted(log_dir.glob("*.jsonl"), reverse=True)
    if log_files:
        selected_log = st.selectbox("File", [f.name for f in log_files])
        log_path = log_dir / selected_log
        with st.expander(f"Contenuto: {selected_log}", expanded=False):
            try:
                content = log_path.read_text(encoding="utf-8")
                lines = content.strip().split("\n")[-50:]  # Last 50 lines
                st.code("\n".join(lines), language="json")
            except Exception as e:
                st.error(f"Errore lettura: {e}")
    else:
        st.info("Nessun file di log trovato.")
else:
    st.info("Directory log non ancora creata. Verrà creata alla prima esecuzione.")
