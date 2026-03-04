"""
Telegram Bot — bandi researcher
Handles incoming commands and callback queries from inline buttons.

Commands:
  /start     — welcome message
  /bandi     — list latest compatible bandi
  /scadenze  — bandi with deadline in next 7 days
  /stats     — quick stats from DB
  /status    — status of last pipeline run
  /scan      — manually trigger daily_scan flow
  /help      — command list

Callback actions (from inline buttons on alert messages):
  analyze:<bando_id>  — starts parse+eligibility in background
  ignore:<bando_id>   — marks bando as scartato
  detail:<bando_id>   — sends detail link to Streamlit
"""
from __future__ import annotations
import asyncio
import logging
from typing import Any

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    BotCommand,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from engine.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger(__name__)

STREAMLIT_URL = "http://localhost:8501"


def _build_bando_keyboard(bando_id: int, bando_url: str | None = None) -> InlineKeyboardMarkup:
    """Build inline keyboard for a bando notification."""
    buttons = [
        [
            InlineKeyboardButton("📄 Dettagli", callback_data=f"detail:{bando_id}"),
            InlineKeyboardButton("✅ Analizza", callback_data=f"analyze:{bando_id}"),
        ],
        [
            InlineKeyboardButton("📂 Genera Docs", callback_data=f"genera_docs:{bando_id}"),
            InlineKeyboardButton("❌ Ignora", callback_data=f"ignore:{bando_id}"),
        ],
    ]
    if bando_url:
        buttons.append([InlineKeyboardButton("🌐 Portale", url=bando_url)])
    return InlineKeyboardMarkup(buttons)


# ─────────────────────────────────────────────
# COMMAND HANDLERS
# ─────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Welcome message."""
    await update.message.reply_text(
        "👋 *Bandi Researcher* attivo!\n\n"
        "Riceverai notifiche automatiche ogni mattina con i nuovi bandi compatibili.\n\n"
        "Comandi:\n"
        "• /bandi — ultimi bandi idonei\n"
        "• /scadenze — scadenze nei prossimi 7 giorni\n"
        "• /stats — statistiche rapide\n"
        "• /status — stato ultima scansione\n"
        "• /scan — avvia scansione manuale\n"
        "• /help — lista comandi",
        parse_mode="Markdown",
    )


async def cmd_scadenze(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Bandi with deadline in next 7 days."""
    try:
        import psycopg2
        from datetime import date, timedelta
        from engine.config import DATABASE_URL

        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        today = date.today()
        cur.execute("""
            SELECT id, titolo, ente_erogatore, data_scadenza, stato, score
            FROM bandi
            WHERE data_scadenza BETWEEN %s AND %s
              AND stato NOT IN ('archiviato', 'inviato', 'scartato')
            ORDER BY data_scadenza ASC
        """, (today, today + timedelta(days=7)))
        rows = cur.fetchall()
        cur.close()
        conn.close()

        if not rows:
            await update.message.reply_text("✅ Nessuna scadenza urgente nei prossimi 7 giorni.")
            return

        lines = ["⏰ *Scadenze prossimi 7 giorni:*\n"]
        for bando_id, titolo, ente, scad, stato, score in rows:
            days_left = (scad - today).days if scad else "?"
            urgency = "🔴" if isinstance(days_left, int) and days_left <= 3 else "🟡"
            scad_str = scad.strftime("%d/%m/%Y") if scad else "N/D"
            lines.append(
                f"{urgency} *{titolo[:45]}*\n"
                f"   {ente} | Scade: {scad_str} ({days_left}gg) | {stato}\n"
                f"   /dettaglio_{bando_id}"
            )

        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"Errore: {e}")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Status of last pipeline run from monitor log."""
    try:
        from engine.pipeline.monitor import get_last_run_summary
        summary = get_last_run_summary()
        if not summary:
            await update.message.reply_text("ℹ️ Nessuna scansione registrata.")
            return
        await update.message.reply_text(
            f"📊 *Ultima scansione*\n\n"
            f"Data: {summary.get('started_at', 'N/D')}\n"
            f"Durata: {summary.get('duration_seconds', '?')}s\n"
            f"Scraped: {summary.get('scraped', 0)}\n"
            f"Inseriti: {summary.get('inserted', 0)}\n"
            f"Notifiche: {summary.get('notified', 0)}\n"
            f"Errori spider: {summary.get('spider_failures', 0)}",
            parse_mode="Markdown",
        )
    except Exception as e:
        await update.message.reply_text(f"Errore: {e}")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Command list."""
    await update.message.reply_text(
        "*Comandi disponibili:*\n\n"
        "/start — messaggio di benvenuto\n"
        "/bandi — ultimi bandi idonei (max 10)\n"
        "/scadenze — bandi con scadenza entro 7 giorni\n"
        "/stats — statistiche database\n"
        "/status — stato dell'ultima scansione\n"
        "/scan — avvia scansione manuale immediata\n"
        "/help — questo messaggio\n\n"
        "*Bottoni inline:*\n"
        "📄 Dettagli — link Streamlit\n"
        "✅ Analizza — avvia analisi idoneità\n"
        "❌ Ignora — segna come scartato\n"
        "📂 Genera Docs — avvia generatore documenti",
        parse_mode="Markdown",
    )


async def cmd_bandi(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List latest compatible bandi from DB."""
    try:
        import psycopg2
        from engine.config import DATABASE_URL

        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("""
            SELECT id, titolo, ente_erogatore, score, data_scadenza, stato
            FROM bandi
            WHERE stato IN ('idoneo', 'lavorazione', 'pronto')
            ORDER BY score DESC NULLS LAST, created_at DESC
            LIMIT 10
        """)
        rows = cur.fetchall()
        cur.close()
        conn.close()

        if not rows:
            await update.message.reply_text("Nessun bando idoneo trovato.")
            return

        lines = ["*Bandi idonei:*\n"]
        for bando_id, titolo, ente, score, scadenza, stato in rows:
            scad_str = scadenza.strftime("%d/%m/%Y") if scadenza else "N/D"
            stato_emoji = {"idoneo": "🟡", "lavorazione": "🔵", "pronto": "🟢"}.get(stato, "⚪")
            lines.append(
                f"{stato_emoji} *{titolo[:50]}*\n"
                f"   {ente} | Score: {score or 'N/D'} | Scade: {scad_str}\n"
                f"   /dettaglio_{bando_id}"
            )

        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    except Exception as e:
        logger.error(f"cmd_bandi error: {e}")
        await update.message.reply_text(f"Errore DB: {e}")


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Quick stats from DB."""
    try:
        import psycopg2
        from engine.config import DATABASE_URL

        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("""
            SELECT stato, COUNT(*) FROM bandi GROUP BY stato ORDER BY COUNT(*) DESC
        """)
        rows = cur.fetchall()
        cur.execute("SELECT COUNT(*) FROM bandi WHERE created_at > NOW() - INTERVAL '7 days'")
        week_count = cur.fetchone()[0]
        cur.execute("SELECT AVG(score) FROM bandi WHERE score IS NOT NULL")
        avg_score = cur.fetchone()[0]
        cur.close()
        conn.close()

        stato_lines = "\n".join(f"  • {stato}: {count}" for stato, count in rows)
        await update.message.reply_text(
            f"📊 *Statistiche Bandi*\n\n"
            f"*Per stato:*\n{stato_lines}\n\n"
            f"*Nuovi (7gg):* {week_count}\n"
            f"*Score medio:* {round(avg_score, 1) if avg_score else 'N/D'}",
            parse_mode="Markdown",
        )

    except Exception as e:
        logger.error(f"cmd_stats error: {e}")
        await update.message.reply_text(f"Errore: {e}")


async def cmd_scan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Trigger manual scan."""
    await update.message.reply_text("⏳ Avvio scansione manuale...")
    try:
        from engine.pipeline.flows import daily_scan
        # Run in background thread
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, daily_scan)
        await update.message.reply_text(
            f"✅ Scansione completata!\n"
            f"Trovati: {result.get('scraped', 0)} | "
            f"Inseriti: {result.get('inserted', 0)} | "
            f"Notifiche: {result.get('notified', 0)}"
        )
    except Exception as e:
        logger.error(f"cmd_scan error: {e}")
        await update.message.reply_text(f"❌ Errore scansione: {e}")


# ─────────────────────────────────────────────
# CALLBACK QUERY HANDLERS
# ─────────────────────────────────────────────

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline button callbacks."""
    query = update.callback_query
    await query.answer()

    data = query.data
    if not data or ":" not in data:
        return

    action, bando_id_str = data.split(":", 1)
    try:
        bando_id = int(bando_id_str)
    except ValueError:
        await query.edit_message_text("ID bando non valido.")
        return

    if action == "detail":
        url = f"{STREAMLIT_URL}/Dettaglio?id={bando_id}"
        await query.edit_message_text(
            f"📄 *Dettaglio bando*\n\n"
            f"Apri Streamlit per vedere tutti i dettagli:\n{url}",
            parse_mode="Markdown",
        )

    elif action == "analyze":
        await query.edit_message_text(f"⏳ Avvio analisi per bando #{bando_id}...")
        try:
            await _run_eligibility_for_bando(bando_id)
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=f"✅ Analisi completata per bando #{bando_id}\nControlla Streamlit per i risultati.",
            )
        except Exception as e:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=f"❌ Errore analisi: {e}",
            )

    elif action == "ignore":
        try:
            await _mark_bando_scartato(bando_id)
            await query.edit_message_text(f"🚫 Bando #{bando_id} marcato come *scartato*.", parse_mode="Markdown")
        except Exception as e:
            await query.edit_message_text(f"❌ Errore: {e}")

    elif action == "genera_docs":
        await query.edit_message_text(f"⏳ Avvio generazione documenti per bando #{bando_id}...")
        try:
            loop = asyncio.get_event_loop()
            pkg_path = await loop.run_in_executor(
                None,
                lambda: __import__(
                    "engine.generators.package_builder", fromlist=["build_package"]
                ).build_package(bando_id, is_draft=True)
            )
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=(
                    f"📂 *Documenti generati!*\n\n"
                    f"Bando #{bando_id}\n"
                    f"Cartella: `{pkg_path.name}`\n\n"
                    f"Apri Streamlit → Documenti per revisionare e approvare."
                ),
                parse_mode="Markdown",
            )
        except Exception as e:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=f"❌ Errore generazione documenti: {e}",
            )


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

async def _run_eligibility_for_bando(bando_id: int) -> None:
    """Run eligibility analysis for a bando and update DB."""
    import psycopg2
    from engine.config import DATABASE_URL
    from engine.eligibility.hard_stops import check_hard_stops
    from engine.eligibility.scorer import score_bando
    from engine.eligibility.rules import get_profile

    profile = get_profile()

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    cur.execute("SELECT * FROM bandi WHERE id = %s", (bando_id,))
    row = cur.fetchone()
    if not row:
        raise ValueError(f"Bando #{bando_id} not found")

    cols = [desc[0] for desc in cur.description]
    bando = dict(zip(cols, row))

    hard_stop = check_hard_stops(bando, profile)
    if hard_stop.excluded:
        stato = "scartato"
        score = 0
    else:
        score_result = score_bando(bando, profile)
        stato = "idoneo" if score_result.score >= 40 else "scartato"
        score = score_result.score

    cur.execute(
        "UPDATE bandi SET stato=%s, score=%s, updated_at=NOW() WHERE id=%s",
        (stato, score, bando_id)
    )
    conn.commit()
    cur.close()
    conn.close()


async def _mark_bando_scartato(bando_id: int) -> None:
    """Mark a bando as scartato in DB."""
    import psycopg2
    from engine.config import DATABASE_URL

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute(
        "UPDATE bandi SET stato='scartato', updated_at=NOW() WHERE id=%s",
        (bando_id,)
    )
    conn.commit()
    cur.close()
    conn.close()


# ─────────────────────────────────────────────
# BOT SETUP & RUN
# ─────────────────────────────────────────────

def build_application() -> Application:
    """Build and configure the Telegram bot application."""
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN not set in .env")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("bandi", cmd_bandi))
    app.add_handler(CommandHandler("scadenze", cmd_scadenze))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("scan", cmd_scan))
    app.add_handler(CommandHandler("help", cmd_help))

    # Callbacks
    app.add_handler(CallbackQueryHandler(handle_callback))

    return app


async def set_bot_commands(app: Application) -> None:
    """Register commands in Telegram UI."""
    await app.bot.set_my_commands([
        BotCommand("start", "Messaggio di benvenuto"),
        BotCommand("bandi", "Ultimi bandi idonei"),
        BotCommand("scadenze", "Scadenze prossimi 7 giorni"),
        BotCommand("stats", "Statistiche database"),
        BotCommand("status", "Stato ultima scansione"),
        BotCommand("scan", "Avvia scansione manuale"),
        BotCommand("help", "Lista comandi"),
    ])


def run_bot() -> None:
    """Start the Telegram bot (blocking)."""
    app = build_application()
    asyncio.get_event_loop().run_until_complete(set_bot_commands(app))
    logger.info("Telegram bot starting...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_bot()
