"""
State machine for project evaluations.
Extracted from tool-bandi-ui/apps/candidature/views.py

DEBITO TECNICO (D10):
La spec prevede una tabella `candidatura` separata con stati diversi:
  bozza → lavorazione → sospesa → pronta → inviata (+ abbandonata)
L'implementazione attuale usa project_evaluations.stato con stati vecchi:
  idoneo → lavorazione → pronto → inviato (+ scartato, archiviato)

STATO_CANDIDATURA_META in display.py definisce i nuovi stati ma NON e' ancora usato.
Migration 011 crea la tabella candidatura ma non e' deployata.

Piano migrazione:
1. Deploy migration 011 (tabella candidatura)
2. Data migration da project_evaluations a candidatura
3. Aggiornare route candidature per usare tabella candidatura
4. Switchare state machine ai nuovi stati
5. Mantenere project_evaluations per valutazione (non per workflow)
"""

# Current state machine (project_evaluations.stato)
# TODO(D10): Migrare a tabella candidatura con nuovi stati (vedi docstring)
TRANSITIONS = {
    "avvia_lavorazione": ("idoneo", "lavorazione"),
    "segna_pronto": ("lavorazione", "pronto"),
    "segna_inviato": ("pronto", "inviato"),
    "torna_idoneo": ("lavorazione", "idoneo"),
    "torna_lavorazione": ("pronto", "lavorazione"),
    "scarta": (None, "scartato"),      # from any scartabile state
    "archivia": (None, "archiviato"),   # from any archiviabile state
    "ripristina": (None, "idoneo"),     # from scartato/archiviato
}

STATI_SCARTABILI = {"nuovo", "idoneo", "lavorazione", "pronto"}
STATI_ARCHIVIABILI = {"scartato", "inviato"}
STATI_RIPRISTINABILI = {"scartato", "archiviato"}


def validate_transition(action: str, stato_attuale: str) -> tuple[bool, str]:
    """Validate a state transition.
    Returns (is_valid, error_message).
    """
    if action not in TRANSITIONS:
        return False, f"Azione sconosciuta: {action}"

    stato_richiesto, _ = TRANSITIONS[action]

    if action == "scarta" and stato_attuale not in STATI_SCARTABILI:
        return False, f"Non si puo' scartare dallo stato {stato_attuale}"
    if action == "archivia" and stato_attuale not in STATI_ARCHIVIABILI:
        return False, f"Non si puo' archiviare dallo stato {stato_attuale}"
    if action == "ripristina" and stato_attuale not in STATI_RIPRISTINABILI:
        return False, f"Non si puo' ripristinare dallo stato {stato_attuale}"
    if stato_richiesto and stato_attuale != stato_richiesto:
        return False, f"Transizione {action} richiede stato {stato_richiesto}, trovato {stato_attuale}"

    return True, ""


def build_initial_checklist(gap_analysis) -> list[dict]:
    """Build initial workspace checklist from gap analysis."""
    items = []
    if not gap_analysis or not isinstance(gap_analysis, list):
        return items
    for i, gap in enumerate(gap_analysis):
        if isinstance(gap, dict):
            items.append({
                "id": f"gap_{i}",
                "label": gap.get("tipo") or gap.get("categoria") or "Requisito",
                "completato": False,
                "nota": gap.get("suggerimento") or "",
                "tipo": "auto",
            })
    return items
