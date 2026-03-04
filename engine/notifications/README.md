# Notifications — Telegram Bot

Notifiche via Telegram con inline buttons interattivi.

## Struttura

```
notifications/
├── telegram_bot.py   ← bot + handlers + inline buttons (Sprint 2-4)
└── alerts.py         ← logica alert: nuovo bando + scadenze (Sprint 2)
```

## Messaggi

### Nuovo bando compatibile (score > soglia)
```
🎯 NUOVO BANDO COMPATIBILE

📋 {titolo}
🏛️ {ente_erogatore}
💰 Fino a {importo_max}€
📅 Scadenza: {data_scadenza}

✅ Score: {score}/100
⚠️ {n_yellow_flags} yellow flag(s)

[📄 Dettagli] [✅ Analizza] [❌ Ignora]
```

### Scadenza imminente
```
⏰ SCADENZA TRA {giorni} GIORNI

📋 {titolo}
📅 {data_scadenza}
📊 Stato: {stato} ({percentuale_completamento}%)

[📂 Apri Streamlit]
```

### Errore spider
```
⚠️ SPIDER FALLITO

🕷️ Spider: {nome_spider}
❌ Errore: {messaggio}
🕐 {timestamp}

[🔍 Logs Prefect]
```

## Comandi Bot

| Comando | Descrizione |
|---------|-------------|
| `/bandi` | Lista bandi attivi con score |
| `/scadenze` | Bandi in scadenza entro 7 giorni |
| `/status` | Stato ultimo run pipeline |
| `/help` | Lista comandi |

## Setup

```bash
# In .env
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=your_chat_id  # personal chat ID
```
