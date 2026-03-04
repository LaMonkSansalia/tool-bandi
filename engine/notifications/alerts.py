"""
Alerts — send Telegram messages for specific events.

All messages are in Italian (UI-facing).
Called from: pipeline/flows.py, telegram_bot.py, Streamlit pages.

Functions:
  send_new_bando_alert(item)             — new compatible bando found
  send_urgency_alert(bando)              — deadline < URGENCY_THRESHOLD_DAYS
  send_update_alert(bando, changes)      — bando updated (idoneo+)
  send_rettifica_alert(bando, original)  — amendment to a tracked bando
  send_spider_failure_alert(name, error) — spider failed
"""
from __future__ import annotations
import logging
from datetime import date
from typing import Any

import requests

from engine.config import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    URGENCY_THRESHOLD_DAYS,
)

logger = logging.getLogger(__name__)

STREAMLIT_URL = "http://localhost:8501"

# Maximum Telegram message length
TELEGRAM_MAX_LEN = 4096


def _send_message(text: str, reply_markup: dict | None = None, chat_id: str | None = None) -> bool:
    """
    Send a message to a Telegram chat.
    Falls back to the global TELEGRAM_CHAT_ID if chat_id is not provided.
    Returns True on success, False on failure (never raises).
    """
    target_chat = chat_id or TELEGRAM_CHAT_ID
    if not TELEGRAM_BOT_TOKEN or not target_chat:
        logger.warning("Telegram not configured — message not sent")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload: dict[str, Any] = {
        "chat_id": target_chat,
        "text": text[:TELEGRAM_MAX_LEN],
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    try:
        resp = requests.post(url, json=payload, timeout=10)
        if not resp.ok:
            logger.error(f"Telegram API error: {resp.status_code} — {resp.text[:200]}")
            return False
        return True
    except requests.RequestException as e:
        logger.error(f"Telegram request failed: {e}")
        return False


def _bando_keyboard(bando_id: int | None, bando_url: str | None = None) -> dict | None:
    """Build inline keyboard JSON for a bando notification."""
    if not bando_id:
        return None

    buttons = [[
        {"text": "📄 Dettagli", "callback_data": f"detail:{bando_id}"},
        {"text": "✅ Analizza", "callback_data": f"analyze:{bando_id}"},
        {"text": "❌ Ignora", "callback_data": f"ignore:{bando_id}"},
    ]]
    if bando_url:
        buttons.append([{"text": "🌐 Portale originale", "url": bando_url}])

    return {"inline_keyboard": buttons}


def _format_scadenza(data_scadenza: Any) -> str:
    """Format deadline with urgency indicator."""
    if not data_scadenza:
        return "N/D"

    if isinstance(data_scadenza, str):
        try:
            data_scadenza = date.fromisoformat(data_scadenza)
        except ValueError:
            return data_scadenza

    days_left = (data_scadenza - date.today()).days
    formatted = data_scadenza.strftime("%d/%m/%Y")

    if days_left < 0:
        return f"{formatted} ⚫ (scaduto)"
    if days_left < URGENCY_THRESHOLD_DAYS:
        return f"{formatted} 🔴 ({days_left}gg rimasti)"
    if days_left < 30:
        return f"{formatted} 🟡 ({days_left}gg rimasti)"
    return formatted


# ─────────────────────────────────────────────
# PUBLIC ALERT FUNCTIONS
# ─────────────────────────────────────────────

def send_new_bando_alert(item: dict[str, Any], project: dict | None = None) -> bool:
    """
    Alert: new bando found with score >= threshold.
    Sent when a bando enters 'idoneo' state for the first time.
    """
    prefix = f"[{project['slug'].upper()}] " if project else ""
    chat_id = (project or {}).get("telegram_chat_id")
    bando_id = item.get("id")
    titolo = item.get("titolo", "Titolo non disponibile")
    ente = item.get("ente_erogatore", "Ente non specificato")
    score = item.get("score")
    portale = item.get("portale", "")
    url = item.get("url", "")
    scadenza = _format_scadenza(item.get("data_scadenza"))
    importo = item.get("importo_max")

    score_str = f"{score}/100" if score is not None else "N/D"
    importo_str = f"€{importo:,.0f}".replace(",", ".") if importo else "N/D"

    text = (
        f"🟢 *{prefix}Nuovo bando compatibile!*\n\n"
        f"📌 *{titolo}*\n"
        f"🏛 {ente}\n"
        f"🌐 {portale.replace('_', ' ').title()}\n\n"
        f"🎯 Score: *{score_str}*\n"
        f"💶 Importo max: *{importo_str}*\n"
        f"📅 Scadenza: *{scadenza}*\n"
    )

    if url:
        text += f"\n🔗 [Vai al portale]({url})"

    return _send_message(text, reply_markup=_bando_keyboard(bando_id, url), chat_id=chat_id)


def send_urgency_alert(bando: dict[str, Any]) -> bool:
    """
    Alert: bando with < URGENCY_THRESHOLD_DAYS remaining, first detected.
    Used for retroactive bandi found on first scan.
    """
    bando_id = bando.get("id")
    titolo = bando.get("titolo", "")
    ente = bando.get("ente_erogatore", "")
    scadenza = _format_scadenza(bando.get("data_scadenza"))

    data_sc = bando.get("data_scadenza")
    if isinstance(data_sc, str):
        try:
            data_sc = date.fromisoformat(data_sc)
        except ValueError:
            data_sc = None

    days_left = (data_sc - date.today()).days if data_sc else 0

    text = (
        f"🔴 *URGENTE — Bando in scadenza!*\n\n"
        f"📌 *{titolo}*\n"
        f"🏛 {ente}\n\n"
        f"⏰ Scadenza: *{scadenza}*\n"
        f"‼️ Rimangono solo *{days_left} giorni*\n\n"
        f"Agisci subito!"
    )

    return _send_message(text, reply_markup=_bando_keyboard(bando_id, bando.get("url")))


def send_update_alert(bando: dict[str, Any], changes: dict[str, Any]) -> bool:
    """
    Alert: bando in stato idoneo+ has been updated (scadenza or importo changed).
    """
    bando_id = bando.get("id")
    titolo = bando.get("titolo", "")
    stato = bando.get("stato", "")

    change_lines = []
    if "data_scadenza" in changes:
        old, new = changes["data_scadenza"]
        change_lines.append(f"  • Scadenza: {_format_scadenza(old)} → *{_format_scadenza(new)}*")
    if "importo_max" in changes:
        old, new = changes["importo_max"]
        old_str = f"€{old:,.0f}".replace(",", ".") if old else "N/D"
        new_str = f"€{new:,.0f}".replace(",", ".") if new else "N/D"
        change_lines.append(f"  • Importo: {old_str} → *{new_str}*")
    if "titolo" in changes:
        change_lines.append(f"  • Titolo aggiornato")

    if not change_lines:
        return False  # Nothing meaningful changed

    stato_emoji = {"idoneo": "🟡", "lavorazione": "🔵", "pronto": "🟢", "inviato": "✅"}.get(stato, "⚪")

    text = (
        f"⚠️ *Bando aggiornato* {stato_emoji}\n\n"
        f"📌 *{titolo}*\n"
        f"Stato attuale: {stato}\n\n"
        f"*Modifiche rilevate:*\n"
        + "\n".join(change_lines)
    )

    return _send_message(text, reply_markup=_bando_keyboard(bando_id, bando.get("url")))


def send_rettifica_alert(rettifica: dict[str, Any], original: dict[str, Any]) -> bool:
    """
    Alert: an amendment (rettifica) was found for a tracked bando.
    """
    original_id = original.get("id")
    original_titolo = original.get("titolo", "")
    original_stato = original.get("stato", "")
    rettifica_url = rettifica.get("url", "")

    # Only alert if the original is in a relevant state
    relevant_states = {"idoneo", "lavorazione", "pronto"}
    if original_stato not in relevant_states:
        return False

    stato_emoji = {"idoneo": "🟡", "lavorazione": "🔵", "pronto": "🟢"}.get(original_stato, "⚪")

    text = (
        f"📝 *Rettifica rilevata!* {stato_emoji}\n\n"
        f"Il bando\n*{original_titolo}*\n"
        f"(stato: {original_stato}) ha ricevuto un avviso di rettifica.\n\n"
        f"⚠️ Verificare le modifiche prima di procedere con la domanda.\n"
    )
    if rettifica_url:
        text += f"\n🔗 [Leggi la rettifica]({rettifica_url})"

    return _send_message(text, reply_markup=_bando_keyboard(original_id))


def send_spider_failure_alert(spider_name: str, error: str) -> bool:
    """
    Alert: a spider failed during the daily scan.
    Monitoring alert — not a bando notification.
    """
    text = (
        f"🕷️ *Spider fallito*\n\n"
        f"Spider: `{spider_name}`\n"
        f"Errore: `{error[:200]}`\n\n"
        f"Controllare i log Prefect per dettagli."
    )
    return _send_message(text)


def send_scan_summary(summary: dict[str, Any]) -> bool:
    """
    Daily scan completion summary (optional, can be disabled).
    """
    text = (
        f"📊 *Scansione giornaliera completata*\n\n"
        f"🔍 Scraped: {summary.get('scraped', 0)}\n"
        f"🆕 Inseriti: {summary.get('inserted', 0)}\n"
        f"🔄 Aggiornati: {summary.get('updated', 0)}\n"
        f"📨 Notifiche inviate: {summary.get('notified', 0)}"
    )
    return _send_message(text)


def send_progressive_deadline_alert(bando: dict[str, Any], days_left: int) -> bool:
    """
    Progressive deadline alert for bandi in stato idoneo/lavorazione.
    Triggered at: 30, 14, 7, 3, 1 days before deadline.
    Includes document completion status.
    """
    # Only for relevant states
    stato = bando.get("stato", "")
    if stato not in {"idoneo", "lavorazione", "pronto"}:
        return False

    bando_id = bando.get("id")
    titolo = bando.get("titolo", "")
    ente = bando.get("ente_erogatore", "")
    scadenza = _format_scadenza(bando.get("data_scadenza"))

    # Urgency emoji based on days left
    if days_left <= 1:
        urgency = "🔴🔴🔴 DOMANI"
    elif days_left <= 3:
        urgency = "🔴🔴 URGENTISSIMO"
    elif days_left <= 7:
        urgency = "🔴 URGENTE"
    elif days_left <= 14:
        urgency = "🟠 ATTENZIONE"
    else:
        urgency = "🟡 PROMEMORIA"

    # Get document completion from DB
    doc_status = _get_doc_completion(bando_id)

    text = (
        f"{urgency}\n\n"
        f"📌 *{titolo}*\n"
        f"🏛 {ente} | {stato.upper()}\n\n"
        f"⏰ Scadenza: *{scadenza}*\n"
        f"📅 Rimangono: *{days_left} giorni*\n\n"
        f"📄 Documenti: {doc_status}"
    )

    return _send_message(text, reply_markup=_bando_keyboard(bando_id, bando.get("url")))


def _get_doc_completion(bando_id: int | None) -> str:
    """Get document completion status string from DB."""
    if not bando_id:
        return "non generati"
    try:
        import psycopg2
        from engine.config import DATABASE_URL
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute(
            "SELECT stato, COUNT(*) FROM bando_documenti_generati WHERE bando_id=%s GROUP BY stato",
            (bando_id,)
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        if not rows:
            return "❌ non generati"
        stati = {stato: count for stato, count in rows}
        total = sum(stati.values())
        firmati = stati.get("firmato", 0)
        approvati = stati.get("approvato", 0) + firmati
        return f"{approvati}/{total} approvati ({'✅' if approvati == total else '⏳'})"
    except Exception:
        return "stato sconosciuto"


def check_and_send_progressive_alerts(project: dict | None = None) -> int:
    """
    Check active bandi and send progressive deadline alerts.
    If project is given, only check that project's evaluations.
    Otherwise checks across all active projects.

    Returns number of alerts sent.
    """
    import psycopg2
    from engine.config import DATABASE_URL

    MILESTONES = [30, 14, 7, 3, 1]
    sent = 0

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        if project:
            cur.execute("""
                SELECT b.id, b.titolo, b.ente_erogatore, b.data_scadenza,
                       pe.stato, pe.score, b.url_fonte AS url
                FROM bandi b
                JOIN project_evaluations pe ON pe.bando_id = b.id
                WHERE pe.project_id = %s
                  AND pe.stato IN ('idoneo', 'lavorazione', 'pronto')
                  AND b.data_scadenza IS NOT NULL
                  AND b.data_scadenza >= CURRENT_DATE
                ORDER BY b.data_scadenza ASC
            """, (project["id"],))
        else:
            # Legacy: query bandi table directly
            cur.execute("""
                SELECT id, titolo, ente_erogatore, data_scadenza, stato, score,
                       url_fonte AS url
                FROM bandi
                WHERE stato IN ('idoneo', 'lavorazione', 'pronto')
                  AND data_scadenza IS NOT NULL
                  AND data_scadenza >= CURRENT_DATE
                ORDER BY data_scadenza ASC
            """)

        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]

        for row in rows:
            bando = dict(zip(cols, row))
            scad = bando["data_scadenza"]
            days_left = (scad - date.today()).days

            for milestone in MILESTONES:
                if days_left == milestone:
                    ok = send_progressive_deadline_alert(bando, days_left)
                    if ok:
                        sent += 1
                    break

        cur.close()
        conn.close()

    except Exception as e:
        logger.error(f"Progressive alerts check failed: {e}")

    return sent
