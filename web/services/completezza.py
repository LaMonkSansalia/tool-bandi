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
    ("mezzi_propri", "Mezzi propri / autofinanziamento"),
    ("prestito_bancario", "Prestito bancario (mutuo, fido)"),
    ("prestito_agevolato", "Prestito agevolato (Simest, Microcredito)"),
    ("leasing", "Leasing / locazione finanziaria"),
    ("equity_crowdfunding", "Equity crowdfunding"),
    ("venture_capital", "Venture Capital / Business Angel"),
    ("altro_bando", "Contributo da altro bando (cumulo)"),
    ("altro", "Altro"),
]

ZONE_SPECIALI_OPTIONS = [
    ("zes_unica", "ZES Unica Mezzogiorno"),
    ("zls", "Zona Logistica Semplificata (ZLS)"),
    ("area_interna", "Area interna SNAI (intermedia/periferica/ultra-periferica)"),
    ("borgo_5000", "Comune < 5.000 abitanti"),
    ("isola_minore", "Isola minore"),
    ("cratere_sismico", "Cratere sismico / area emergenza"),
]

# ── Costanti soggetto ─────────────────────────────────────────────────────────

FORME_GIURIDICHE = [
    # Imprese individuali
    ("impresa_individuale", "Impresa individuale / Ditta individuale"),
    ("libero_professionista", "Libero professionista con P.IVA"),
    # Societa' di persone
    ("snc", "SNC — Societa' in Nome Collettivo"),
    ("sas", "SAS — Societa' in Accomandita Semplice"),
    # Societa' di capitali
    ("srl", "SRL — Societa' a Responsabilita' Limitata"),
    ("srls", "SRLS — SRL Semplificata"),
    ("spa", "SPA — Societa' per Azioni"),
    ("sapa", "SAPA — Societa' in Accomandita per Azioni"),
    # Cooperative
    ("cooperativa", "Societa' cooperativa"),
    ("cooperativa_sociale", "Cooperativa sociale"),
    # Terzo settore
    ("associazione", "Associazione"),
    ("fondazione", "Fondazione"),
    ("aps", "APS — Associazione di Promozione Sociale"),
    ("odv", "ODV — Organizzazione di Volontariato"),
    # Reti e consorzi
    ("consorzio", "Consorzio"),
    ("rete_impresa", "Rete d'impresa"),
]

REGIMI_FISCALI = [
    ("ordinario", "Regime ordinario"),
    ("semplificato", "Regime semplificato"),
    ("forfettario", "Regime forfettario"),
    ("agricolo", "Regime speciale agricoltura"),
    ("non_profit", "Ente non commerciale"),
]

QUALIFICHE_SOGGETTO = [
    ("startup_innovativa", "Startup innovativa (sez. speciale CCIAA)"),
    ("pmi_innovativa", "PMI innovativa"),
    ("impresa_sociale", "Impresa sociale (D.Lgs. 155/2006)"),
    ("societa_benefit", "Societa' benefit"),
    ("impresa_femminile", "Impresa femminile (>= 2/3 quote + organi)"),
    ("impresa_giovanile", "Impresa giovanile (titolare/soci under 35)"),
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
