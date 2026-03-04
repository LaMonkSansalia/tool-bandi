"""
Dashboard — panoramica bandi, scadenze imminenti, metriche, grafici Plotly.
Multi-project aware: reads from project_evaluations.
"""
from datetime import date, timedelta
import streamlit as st
import pandas as pd
import psycopg2
import plotly.express as px
from engine.config import DATABASE_URL

st.title("📊 Dashboard")

pid = st.session_state.get("current_project_id", 1)


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


# ── Metriche principali ───────────────────────────────────────────────────────
today = date.today()
week_ago = today - timedelta(days=7)

col1, col2, col3, col4 = st.columns(4)

with col1:
    df = query_df("""
        SELECT COUNT(*) as n FROM bandi b
        JOIN project_evaluations pe ON pe.bando_id = b.id
        WHERE pe.project_id = %s AND b.first_seen_at >= %s
    """, [pid, week_ago])
    n = int(df["n"].iloc[0]) if not df.empty else 0
    st.metric("Bandi trovati (7gg)", n)

with col2:
    df = query_df("""
        SELECT COUNT(*) as n FROM project_evaluations
        WHERE project_id = %s AND stato = 'idoneo'
    """, [pid])
    n = int(df["n"].iloc[0]) if not df.empty else 0
    st.metric("Idonei in attesa", n)

with col3:
    df = query_df("""
        SELECT COUNT(*) as n FROM project_evaluations
        WHERE project_id = %s AND stato = 'lavorazione'
    """, [pid])
    n = int(df.iloc[0, 0]) if not df.empty else 0
    st.metric("In lavorazione", n)

with col4:
    df = query_df("""
        SELECT ROUND(AVG(score)) as avg FROM project_evaluations
        WHERE project_id = %s AND stato = 'idoneo' AND score IS NOT NULL
    """, [pid])
    avg = int(df["avg"].iloc[0]) if not df.empty and pd.notna(df["avg"].iloc[0]) else 0
    st.metric("Score medio (idonei)", f"{avg}/100")

st.divider()

# ── Grafici row 1 ─────────────────────────────────────────────────────────────
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("📈 Bandi trovati per settimana")
    df_weekly = query_df("""
        SELECT DATE_TRUNC('week', b.first_seen_at)::date AS settimana, COUNT(*) AS nuovi
        FROM bandi b
        JOIN project_evaluations pe ON pe.bando_id = b.id
        WHERE pe.project_id = %s AND b.first_seen_at > NOW() - INTERVAL '12 weeks'
        GROUP BY settimana ORDER BY settimana
    """, [pid])
    if not df_weekly.empty:
        fig = px.bar(
            df_weekly, x="settimana", y="nuovi",
            labels={"settimana": "Settimana", "nuovi": "Bandi trovati"},
            color_discrete_sequence=["#1a1a6e"],
        )
        fig.update_layout(showlegend=False, margin=dict(l=0, r=0, t=20, b=0), height=250)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Dati insufficienti per il grafico settimanale.")

with col_right:
    st.subheader("🎯 Distribuzione score")
    df_scores = query_df("""
        SELECT pe.score FROM project_evaluations pe
        WHERE pe.project_id = %s AND pe.score IS NOT NULL AND pe.stato != 'archiviato'
    """, [pid])
    if not df_scores.empty:
        fig = px.histogram(
            df_scores, x="score", nbins=20, range_x=[0, 100],
            color_discrete_sequence=["#2d7d2d"],
            labels={"score": "Score", "count": "N. bandi"},
        )
        fig.add_vline(x=60, line_dash="dash", line_color="red",
                      annotation_text="Notifica (60)", annotation_position="top right")
        fig.add_vline(x=40, line_dash="dash", line_color="orange",
                      annotation_text="Idoneo (40)", annotation_position="top left")
        fig.update_layout(showlegend=False, margin=dict(l=0, r=0, t=20, b=0), height=250)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Nessun dato di score disponibile.")

st.divider()

# ── Gantt scadenze ────────────────────────────────────────────────────────────
st.subheader("📅 Timeline scadenze — prossimi 60 giorni")

df_gantt = query_df("""
    SELECT b.id, b.titolo, b.ente_erogatore, b.data_scadenza,
           pe.stato, pe.score, b.first_seen_at::date AS data_inizio
    FROM bandi b
    JOIN project_evaluations pe ON pe.bando_id = b.id
    WHERE pe.project_id = %s
      AND b.data_scadenza IS NOT NULL
      AND b.data_scadenza BETWEEN NOW() AND NOW() + INTERVAL '60 days'
      AND pe.stato NOT IN ('archiviato', 'scartato', 'inviato')
    ORDER BY b.data_scadenza ASC LIMIT 15
""", [pid])

if not df_gantt.empty:
    df_gantt["data_scadenza"] = pd.to_datetime(df_gantt["data_scadenza"])
    df_gantt["data_inizio"] = pd.to_datetime(df_gantt["data_inizio"])
    df_gantt["titolo_short"] = df_gantt["titolo"].str[:48] + "…"
    stato_color_map = {
        "nuovo": "#4e89e8", "analisi": "#9c27b0", "idoneo": "#2e7d32",
        "lavorazione": "#f57c00", "pronto": "#1b5e20",
    }
    fig = px.timeline(
        df_gantt,
        x_start="data_inizio", x_end="data_scadenza", y="titolo_short",
        color="stato", color_discrete_map=stato_color_map,
        hover_data={"ente_erogatore": True, "score": True, "titolo_short": False},
    )
    fig.add_vline(
        x=pd.Timestamp(today), line_dash="dot", line_color="#cc0000", annotation_text="Oggi",
    )
    fig.update_layout(
        height=max(260, 38 * len(df_gantt)),
        margin=dict(l=0, r=0, t=10, b=0),
        yaxis={"categoryorder": "total ascending"},
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Nessun bando attivo con scadenza nei prossimi 60 giorni.")

st.divider()

# ── Scadenze imminenti (7 giorni) ─────────────────────────────────────────────
st.subheader("⏰ Scadenze imminenti (prossimi 7 giorni)")

df_scad = query_df("""
    SELECT b.titolo, b.ente_erogatore, b.data_scadenza, pe.stato, pe.score
    FROM bandi b
    JOIN project_evaluations pe ON pe.bando_id = b.id
    WHERE pe.project_id = %s
      AND b.data_scadenza BETWEEN %s AND %s
      AND pe.stato NOT IN ('archiviato', 'inviato', 'scartato')
    ORDER BY b.data_scadenza ASC
""", [pid, today, today + timedelta(days=7)])

if df_scad.empty:
    st.success("Nessuna scadenza urgente nei prossimi 7 giorni.")
else:
    df_scad["Gg"] = (pd.to_datetime(df_scad["data_scadenza"]) - pd.Timestamp(today)).dt.days
    df_scad["⚠"] = df_scad["Gg"].apply(lambda d: "🔴" if d <= 3 else "🟡")
    df_scad["Score"] = df_scad["score"].apply(lambda s: f"{int(s)}/100" if pd.notna(s) else "—")
    st.dataframe(
        df_scad[["⚠", "titolo", "ente_erogatore", "data_scadenza", "Gg", "stato", "Score"]],
        use_container_width=True, hide_index=True,
    )

st.divider()

# ── Distribuzione per portale e stato ────────────────────────────────────────
col_a, col_b = st.columns(2)

with col_a:
    st.subheader("🌐 Bandi per portale")
    df_portale = query_df("""
        SELECT b.portale, COUNT(*) AS totale,
               COUNT(CASE WHEN pe.stato IN ('idoneo','lavorazione','pronto') THEN 1 END) AS idonei
        FROM bandi b
        JOIN project_evaluations pe ON pe.bando_id = b.id
        WHERE pe.project_id = %s AND pe.stato != 'archiviato'
        GROUP BY b.portale ORDER BY totale DESC
    """, [pid])
    if not df_portale.empty:
        fig = px.bar(
            df_portale, x="portale", y=["totale", "idonei"], barmode="group",
            color_discrete_sequence=["#1a1a6e", "#2d7d2d"],
            labels={"value": "N. bandi", "portale": "Portale", "variable": ""},
        )
        fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=270)
        st.plotly_chart(fig, use_container_width=True)

with col_b:
    st.subheader("📊 Bandi per stato")
    df_stato = query_df("""
        SELECT pe.stato, COUNT(*) as n FROM project_evaluations pe
        WHERE pe.project_id = %s
        GROUP BY pe.stato ORDER BY n DESC
    """, [pid])
    if not df_stato.empty:
        fig = px.pie(
            df_stato, names="stato", values="n", color="stato",
            color_discrete_map={
                "nuovo": "#4e89e8", "analisi": "#9c27b0", "idoneo": "#2e7d32",
                "lavorazione": "#f57c00", "pronto": "#1b5e20", "inviato": "#00897b",
                "scartato": "#c62828", "archiviato": "#aaa",
            },
            hole=0.4,
        )
        fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=270)
        st.plotly_chart(fig, use_container_width=True)

st.divider()

# ── Ultimi bandi trovati ──────────────────────────────────────────────────────
st.subheader("🆕 Ultimi bandi trovati")

df_new = query_df("""
    SELECT b.titolo, b.ente_erogatore, b.portale, b.data_scadenza,
           pe.score, pe.stato, b.first_seen_at::date AS trovato
    FROM bandi b
    JOIN project_evaluations pe ON pe.bando_id = b.id
    WHERE pe.project_id = %s
    ORDER BY b.first_seen_at DESC LIMIT 10
""", [pid])

if df_new.empty:
    st.info("Nessun bando nel database. Avvia la scansione dalla pagina **Configurazione**.")
else:
    STATO_COLORS = {
        "nuovo": "🔵", "analisi": "🟣", "idoneo": "🟢",
        "lavorazione": "🟡", "pronto": "🟠", "inviato": "✅",
        "scartato": "❌", "archiviato": "⬜",
    }
    df_new["🚦"] = df_new["stato"].map(STATO_COLORS).fillna("⬜")
    df_new["Score"] = df_new["score"].apply(lambda s: f"{int(s)}/100" if pd.notna(s) else "—")
    st.dataframe(
        df_new[["🚦", "titolo", "ente_erogatore", "portale", "data_scadenza", "Score", "trovato"]],
        use_container_width=True, hide_index=True,
    )
