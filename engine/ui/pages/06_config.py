"""
Pagina 06 — Configurazione
Permette di gestire: portali attivi, soglia notifiche, orario scansione, log esecuzioni.
"""
import streamlit as st
import json
import psycopg2
import pandas as pd
from pathlib import Path
from datetime import datetime

from engine.config import (
    DATABASE_URL,
    SCORE_NOTIFICATION_THRESHOLD,
    URGENCY_THRESHOLD_DAYS,
    ARCHIVE_AFTER_DAYS,
)
st.title("⚙️ Configurazione")

# ─────────────────────────────────────────────
# PORTALI ATTIVI
# ─────────────────────────────────────────────

PORTALI_INFO = {
    "invitalia": {"label": "Invitalia", "url": "invitalia.it", "tipo": "Nazionale"},
    "regione_sicilia": {"label": "Regione Siciliana", "url": "regione.sicilia.it", "tipo": "Regionale"},
    "mimit": {"label": "MIMIT", "url": "mimit.gov.it", "tipo": "Ministeriale"},
    "padigitale": {"label": "PA Digitale 2026", "url": "padigitale2026.gov.it", "tipo": "Digitale / PNRR"},
    "inpa": {"label": "InPA", "url": "inpa.gov.it", "tipo": "PA"},
    "comune_palermo": {"label": "Comune di Palermo", "url": "comune.palermo.it", "tipo": "Comunale"},
    "euroinfosicilia": {"label": "EuroInfoSicilia", "url": "euroinfosicilia.it", "tipo": "Aggregatore EU"},
}

# Config file path
CONFIG_FILE = Path(__file__).parent.parent.parent / ".portali_config.json"


def load_portali_config() -> dict[str, bool]:
    """Load portal active/inactive state from config file."""
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except Exception:
            pass
    return {name: True for name in PORTALI_INFO}  # all active by default


def save_portali_config(config: dict[str, bool]) -> None:
    CONFIG_FILE.write_text(json.dumps(config, indent=2))


st.subheader("🌐 Portali attivi")
st.caption("Seleziona i portali da includere nella scansione giornaliera.")

portali_config = load_portali_config()
updated_config = {}

cols = st.columns(2)
for i, (key, info) in enumerate(PORTALI_INFO.items()):
    col = cols[i % 2]
    with col:
        active = col.toggle(
            f"**{info['label']}**",
            value=portali_config.get(key, True),
            key=f"portale_{key}",
            help=f"{info['tipo']} — {info['url']}",
        )
        updated_config[key] = active

if st.button("💾 Salva configurazione portali"):
    save_portali_config(updated_config)
    st.success("Configurazione salvata!")

st.divider()

# ─────────────────────────────────────────────
# SOGLIE E PARAMETRI
# ─────────────────────────────────────────────

st.subheader("🎯 Soglie e parametri")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "Soglia notifica Telegram",
        f"{SCORE_NOTIFICATION_THRESHOLD}/100",
        help="Bandi con score ≥ questa soglia vengono notificati su Telegram. Modifica in .env → SCORE_NOTIFICATION_THRESHOLD",
    )

with col2:
    st.metric(
        "Soglia urgenza",
        f"{URGENCY_THRESHOLD_DAYS} giorni",
        help="Bandi con meno di X giorni alla scadenza → notifica urgente. Modifica in .env → URGENCY_THRESHOLD_DAYS",
    )

with col3:
    st.metric(
        "Archivia dopo",
        f"{ARCHIVE_AFTER_DAYS} giorni",
        help="Bandi scaduti da più di X giorni vengono archiviati automaticamente. Modifica in .env → ARCHIVE_AFTER_DAYS",
    )

st.info(
    "📝 Per modificare queste soglie, edita il file `.env` nella cartella `engine/` e riavvia l'applicazione.",
    icon="ℹ️",
)

st.divider()

# ─────────────────────────────────────────────
# ORARIO SCANSIONE
# ─────────────────────────────────────────────

st.subheader("🕗 Scansione automatica")

col1, col2 = st.columns([2, 1])

with col1:
    st.markdown("""
    La scansione giornaliera è gestita da **Prefect** con cron `0 8 * * *` (ogni giorno alle 08:00).

    Per avviarla:
    ```bash
    # Avvia lo scheduler (rimane in esecuzione)
    python -m engine.pipeline.flows --serve

    # Oppure avvia una scansione singola manuale
    python -m engine.pipeline.flows
    ```

    Il dashboard Prefect è disponibile su [http://localhost:4200](http://localhost:4200)
    """)

with col2:
    st.markdown("**Prossima scansione:**")
    now = datetime.now()
    next_scan = now.replace(hour=8, minute=0, second=0, microsecond=0)
    if now.hour >= 8:
        from datetime import timedelta
        next_scan += timedelta(days=1)
    st.metric("", next_scan.strftime("%d/%m/%Y ore %H:%M"))
    st.caption("Usa il bottone **Avvia scansione** nella sidebar.")

st.divider()

# ─────────────────────────────────────────────
# LOG ULTIME ESECUZIONI
# ─────────────────────────────────────────────

st.subheader("📋 Ultime esecuzioni")
st.caption("Statistiche per portale nell'ultimo mese.")

try:
    conn = psycopg2.connect(DATABASE_URL)

    # Stats per portale
    df_portali = pd.read_sql("""
        SELECT
            portale,
            COUNT(*) AS totale_bandi,
            COUNT(CASE WHEN stato IN ('idoneo','lavorazione','pronto','inviato') THEN 1 END) AS idonei,
            COUNT(CASE WHEN stato = 'scartato' THEN 1 END) AS scartati,
            MAX(created_at) AS ultimo_trovato,
            AVG(score) AS score_medio
        FROM bandi
        WHERE created_at > NOW() - INTERVAL '30 days'
        GROUP BY portale
        ORDER BY totale_bandi DESC
    """, conn)

    if not df_portali.empty:
        df_portali["score_medio"] = pd.to_numeric(df_portali["score_medio"], errors="coerce").fillna(0).round(1)
        df_portali["ultimo_trovato"] = pd.to_datetime(df_portali["ultimo_trovato"]).dt.strftime("%d/%m/%Y %H:%M")

        # Add active status
        df_portali["attivo"] = df_portali["portale"].map(
            lambda p: "✅" if updated_config.get(p, True) else "⏸️"
        )

        df_portali.columns = ["Portale", "Tot. Bandi", "Idonei", "Scartati", "Ultimo trovato", "Score medio", "Stato"]
        st.dataframe(df_portali, use_container_width=True, hide_index=True)
    else:
        st.info("Nessun dato nell'ultimo mese. Avvia la prima scansione!")

    # Recent bandi by day
    st.subheader("📈 Bandi trovati per giorno (ultimi 7 giorni)")
    df_daily = pd.read_sql("""
        SELECT
            DATE(created_at) AS giorno,
            COUNT(*) AS nuovi
        FROM bandi
        WHERE created_at > NOW() - INTERVAL '7 days'
        GROUP BY DATE(created_at)
        ORDER BY giorno
    """, conn)

    if not df_daily.empty:
        df_daily["giorno"] = pd.to_datetime(df_daily["giorno"])
        df_daily["nuovi"] = pd.to_numeric(df_daily["nuovi"], errors="coerce").fillna(0).astype(int)
        st.bar_chart(df_daily.set_index("giorno")["nuovi"])
    else:
        st.info("Nessun dato per il grafico.")

    conn.close()

except psycopg2.OperationalError as e:
    st.warning(f"Database non raggiungibile: {e}")
    st.info("Avvia PostgreSQL con `docker compose up -d postgres` e riprova.")
except Exception as e:
    st.error(f"Errore: {e}")

st.divider()

# ─────────────────────────────────────────────
# TELEGRAM
# ─────────────────────────────────────────────

st.subheader("📱 Configurazione Telegram")

from engine.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
    st.success("✅ Telegram configurato correttamente")
    st.markdown(f"- Chat ID: `{TELEGRAM_CHAT_ID}`")
    st.markdown(f"- Token: `{TELEGRAM_BOT_TOKEN[:8]}...{TELEGRAM_BOT_TOKEN[-4:]}`")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🧪 Invia messaggio di test"):
            try:
                from engine.notifications.alerts import _send_message
                ok = _send_message("🧪 *Test notifica* — Bandi Researcher funziona correttamente!")
                if ok:
                    st.success("Messaggio inviato!")
                else:
                    st.error("Invio fallito. Controlla token e chat_id.")
            except Exception as e:
                st.error(f"Errore: {e}")

    with col2:
        if st.button("🤖 Avvia bot Telegram"):
            st.info(
                "Avvia il bot da terminale:\n```bash\npython -m engine.notifications.telegram_bot\n```",
                icon="ℹ️",
            )
else:
    st.warning("⚠️ Telegram non configurato")
    st.markdown("""
    Aggiungi queste variabili a `.env`:
    ```
    TELEGRAM_BOT_TOKEN=<il-tuo-token>
    TELEGRAM_CHAT_ID=<il-tuo-chat-id>
    ```
    Crea un bot su [@BotFather](https://t.me/BotFather) e usa [@userinfobot](https://t.me/userinfobot) per il chat_id.
    """)
