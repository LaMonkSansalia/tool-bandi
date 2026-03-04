# COSTS.md — Token & Cost Tracking

## How to update this file

**Claude Code (Gandalf):** type `/cost` in chat at end of session, paste output below
**Ollama (qwen3:14b):** free (local), token count tracked via API

---

## Sessions Log

| Date | Agent | Task | Input tokens | Output tokens | Cost (€) | Notes |
|------|-------|------|-------------|---------------|----------|-------|
| 2026-03-02 | Gandalf (Claude Sonnet 4.6) | Brainstorming + design docs | — | — | — | Session start, no /cost yet |

---

## Totals

| Agent | Total input tokens | Total output tokens | Total cost (€) |
|-------|-------------------|--------------------|--------------:|
| Gandalf (Claude Sonnet 4.6) | — | — | — |
| Mimmo (qwen3:14b) | — | — | **0.00** |

---

## How to log Ollama tokens

Ollama API returns token counts per call. To see them:
```bash
curl -s http://localhost:11434/api/generate \
  -d '{"model":"qwen3:14b","prompt":"your prompt","stream":false}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'in:{d[\"prompt_eval_count\"]} out:{d[\"eval_count\"]}')"
```

Or check COMMS.md — Mimmo should log token counts per task when using the API directly.
