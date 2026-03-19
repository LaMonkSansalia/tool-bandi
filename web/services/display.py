"""
Display constants and formatting helpers.
Extracted from tool-bandi-ui/apps/bandi/views.py.
"""

# ── Stato badge ──────────────────────────────────────────────────────────────

STATO_META = {
    "nuovo":       ("Nuovo",          "bg-gray-100 text-gray-600"),
    "idoneo":      ("Idoneo",         "bg-green-100 text-green-800"),
    "lavorazione": ("In lavorazione", "bg-blue-100 text-blue-800"),
    "pronto":      ("Pronto",         "bg-purple-100 text-purple-800"),
    "inviato":     ("Inviato",        "bg-indigo-100 text-indigo-800"),
    "scartato":    ("Scartato",       "bg-red-100 text-red-800"),
    "archiviato":  ("Archiviato",     "bg-gray-100 text-gray-400"),
}

# Candidatura states (new spec)
STATO_CANDIDATURA_META = {
    "bozza":       ("Bozza",          "bg-gray-100 text-gray-600"),
    "lavorazione": ("In lavorazione", "bg-blue-100 text-blue-800"),
    "sospesa":     ("Sospesa",        "bg-yellow-100 text-yellow-800"),
    "pronta":      ("Pronta",         "bg-purple-100 text-purple-800"),
    "inviata":     ("Inviata",        "bg-indigo-100 text-indigo-800"),
    "abbandonata": ("Abbandonata",    "bg-red-100 text-red-800"),
}

# ── Tipo finanziamento badge ─────────────────────────────────────────────────

TIPO_FP_LABELS = {
    "fondo_perduto":  "Fondo Perduto",
    "prestito":       "Prestito",
    "voucher":        "Voucher",
    "misto":          "Misto",
    "conto_capitale": "Conto Capitale",
    "garanzia":       "Garanzia",
}

TIPO_FP_CSS = {
    "fondo_perduto":  "bg-emerald-100 text-emerald-800",
    "prestito":       "bg-blue-100 text-blue-800",
    "voucher":        "bg-yellow-100 text-yellow-800",
    "misto":          "bg-orange-100 text-orange-800",
    "conto_capitale": "bg-cyan-100 text-cyan-800",
    "garanzia":       "bg-violet-100 text-violet-800",
}


# ── Formatting helpers ───────────────────────────────────────────────────────

def score_meta(score) -> tuple[str, str]:
    """Return (display_string, css_classes) for a score badge."""
    if score is None:
        return "—", "text-gray-400"
    if score >= 60:
        return str(score), "bg-green-100 text-green-800"
    if score >= 40:
        return str(score), "bg-orange-100 text-orange-800"
    return str(score), "bg-red-100 text-red-800"


def format_budget(value) -> str:
    """Format budget as human-readable string."""
    if value is None:
        return "—"
    v = float(value)
    if v >= 1_000_000:
        return f"€{v / 1_000_000:.1f}M"
    if v >= 1_000:
        return f"€{v / 1_000:.0f}K"
    return f"€{v:.0f}"


def giorni_label(giorni) -> tuple[str, str]:
    """Return (label, css_classes) for deadline display."""
    if giorni is None:
        return "—", ""
    if giorni < 0:
        return "Scaduto", "text-gray-400"
    if giorni == 0:
        return "Oggi!", "text-red-600 font-bold"
    if giorni <= 14:
        return f"{giorni}gg", "text-red-600 font-semibold"
    if giorni <= 30:
        return f"{giorni}gg", "text-orange-600"
    return f"{giorni}gg", "text-gray-600"


def enrich_bando_row(row: dict) -> dict:
    """Add display metadata to a bando/evaluation row."""
    row["stato_label"], row["stato_css"] = STATO_META.get(
        row.get("stato", ""), (row.get("stato", ""), "")
    )
    row["tipo_fp_label"] = TIPO_FP_LABELS.get(
        row.get("tipo_finanziamento", ""), row.get("tipo_finanziamento") or "—"
    )
    row["tipo_fp_css"] = TIPO_FP_CSS.get(row.get("tipo_finanziamento", ""), "")
    row["score_display"], row["score_css"] = score_meta(row.get("score"))
    row["budget_label"] = format_budget(row.get("budget_display"))
    row["giorni_label"], row["giorni_css"] = giorni_label(row.get("giorni_rimasti"))
    row["urgente"] = (
        row.get("giorni_rimasti") is not None and 0 <= row["giorni_rimasti"] <= 14
    )
    return row


def as_list(val) -> list:
    """Defensive JSONB parser — always returns a list."""
    if not val:
        return []
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        import json
        try:
            parsed = json.loads(val)
            return parsed if isinstance(parsed, list) else []
        except (ValueError, TypeError):
            return []
    return []
