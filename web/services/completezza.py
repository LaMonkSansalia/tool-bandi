"""
Completezza checks and project profile constants.
Extracted from tool-bandi-ui/apps/progetti/views.py
"""

PROFILO_DEFAULT = {
    "descrizione_breve": "",
    "descrizione_estesa": "",
    "settore": "",
    "keywords": [],
    "comuni_target": [],
    "zone_speciali": [],
    "costituita": True,
    "budget_min": None,
    "budget_max": None,
    "cofinanziamento_pct": None,
    "cofinanziamento_fonte": "",
    "partner": [],
    "piano_lavoro": [],
    "kpi": [],
    "punti_di_forza": {"innovativita": "", "impatto_sociale": "", "sostenibilita": ""},
    "referenze_simili": "",
    "documenti_supporto": [],
    "avvio_previsto": "",
    "durata_mesi": 24,
}

COMPLETEZZA_CHECKS = [
    ("descrizione_breve", "Descrizione breve",
        lambda p: bool(p.get("descrizione_breve", "").strip())),
    ("settore_keywords", "Settore + keywords (min 3)",
        lambda p: bool(p.get("settore")) and len(p.get("keywords", [])) >= 3),
    ("comuni_target", "Comuni target (min 1)",
        lambda p: len(p.get("comuni_target", [])) >= 1),
    ("descrizione_estesa", "Descrizione estesa (min 500 parole)",
        lambda p: len((p.get("descrizione_estesa") or "").split()) >= 500),
    ("budget", "Budget previsto",
        lambda p: p.get("budget_min") is not None),
    ("cofinanziamento", "Capacita' cofinanziamento",
        lambda p: p.get("cofinanziamento_pct") is not None),
    ("partner", "Almeno 1 partner",
        lambda p: len(p.get("partner", [])) >= 1),
    ("lettere", "Lettera d'intento (min 1)",
        lambda p: any(part.get("lettera_intento") for part in p.get("partner", []))),
    ("piano_lavoro", "Piano di lavoro (min 2 fasi)",
        lambda p: len(p.get("piano_lavoro", [])) >= 2),
    ("kpi", "KPI definiti (min 2)",
        lambda p: len(p.get("kpi", [])) >= 2),
    ("documenti", "Documento di supporto (min 1)",
        lambda p: len(p.get("documenti_supporto", [])) >= 1),
    ("referenze", "Referenze simili",
        lambda p: bool(p.get("referenze_simili", "").strip())),
]

SETTORI = [
    ("turismo_astronomia", "Turismo / Astronomia"),
    ("turismo_cultura", "Turismo / Cultura / Borghi"),
    ("ict_freelancer", "ICT / Freelancer / Digitale"),
    ("ecommerce_pmi", "E-commerce / PMI"),
    ("artigianato", "Artigianato / Manifattura"),
    ("agricoltura", "Agricoltura / Agroalimentare"),
    ("innovazione", "Innovazione / R&D"),
    ("sociale", "Welfare / Sociale"),
]

COFINANZIAMENTO_FONTI = [
    ("autofinanziamento", "Autofinanziamento"),
    ("partner_privato", "Partner privato"),
    ("comune", "Comune / PA"),
    ("banca", "Banca / Finanza"),
    ("eu", "Fondi EU"),
]

ZONE_SPECIALI_OPTIONS = [
    ("ZES", "ZES (Zona Economica Speciale)"),
    ("area_interna", "Area Interna"),
    ("borgo_meno_5000", "Borgo < 5000 abitanti"),
    ("montagna", "Area Montana"),
]


def check_completezza(profilo: dict) -> tuple[list[dict], int, int]:
    """Check completezza of a project profile.
    Returns (items, done_count, percentage).
    """
    items = []
    done = 0
    for key, label, check_fn in COMPLETEZZA_CHECKS:
        ok = check_fn(profilo)
        if ok:
            done += 1
        items.append({"key": key, "label": label, "ok": ok})
    pct = int(done / len(COMPLETEZZA_CHECKS) * 100)
    return items, done, pct


def normalize_profilo(raw: dict | None) -> dict:
    """Merge raw profilo with defaults."""
    if not raw:
        return dict(PROFILO_DEFAULT)
    if isinstance(raw, str):
        import json
        raw = json.loads(raw)
    return {**PROFILO_DEFAULT, **{k: raw[k] for k in PROFILO_DEFAULT if k in raw}}


def parse_int_or_none(val) -> int | None:
    if val is None or str(val).strip() == "":
        return None
    try:
        return int(float(str(val).strip()))
    except (ValueError, TypeError):
        return None
