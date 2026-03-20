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
    # Nuovi campi v0.8
    "tipo_investimento": "",
    "impatto_occupazionale": "",
    "sostenibilita": "",
}

TIPI_INVESTIMENTO = [
    ("beni_strumentali", "Beni strumentali / macchinari"),
    ("digitale", "Digitalizzazione / ICT"),
    ("rd", "Ricerca & Sviluppo"),
    ("formazione", "Formazione / capitale umano"),
    ("internazionalizzazione", "Internazionalizzazione / export"),
    ("efficientamento", "Efficientamento energetico"),
    ("avvio_impresa", "Avvio nuova impresa"),
    ("altro", "Altro"),
]

# Completezza checks su 3 livelli: obbligatorio, importante, opzionale
# Formato: (key, label, livello, check_fn)
COMPLETEZZA_CHECKS = [
    # ── OBBLIGATORI — senza questi il progetto e' inutilizzabile
    ("descrizione_breve", "Descrizione breve", "obbligatorio",
        lambda p: bool(p.get("descrizione_breve", "").strip())),
    ("settore", "Settore", "obbligatorio",
        lambda p: bool(p.get("settore"))),
    ("budget", "Budget previsto", "obbligatorio",
        lambda p: p.get("budget_min") is not None),
    ("tipo_investimento", "Tipo investimento", "obbligatorio",
        lambda p: bool(p.get("tipo_investimento"))),

    # ── IMPORTANTI — migliorano matching e score
    ("keywords", "Keywords (min 3)", "importante",
        lambda p: len(p.get("keywords", [])) >= 3),
    ("comuni_target", "Comuni target (min 1)", "importante",
        lambda p: len(p.get("comuni_target", [])) >= 1),
    ("descrizione_estesa", "Descrizione estesa (min 200 car.)", "importante",
        lambda p: len((p.get("descrizione_estesa") or "").strip()) >= 200),
    ("cofinanziamento", "Capacita' cofinanziamento", "importante",
        lambda p: p.get("cofinanziamento_pct") is not None),
    ("piano_lavoro", "Piano di lavoro (min 1 fase)", "importante",
        lambda p: len(p.get("piano_lavoro", [])) >= 1),
    ("kpi", "KPI definiti (min 2)", "importante",
        lambda p: len(p.get("kpi", [])) >= 2),

    # ── OPZIONALI — premiali ma non bloccanti
    ("partner", "Partner previsti", "opzionale",
        lambda p: len(p.get("partner", [])) >= 1),
    ("lettere", "Lettera d'intento (min 1)", "opzionale",
        lambda p: any(part.get("lettera_intento") for part in p.get("partner", []))),
    ("documenti", "Documento di supporto (min 1)", "opzionale",
        lambda p: len(p.get("documenti_supporto", [])) >= 1),
    ("referenze", "Referenze simili", "opzionale",
        lambda p: bool(p.get("referenze_simili", "").strip())),
    ("impatto_occup", "Impatto occupazionale", "opzionale",
        lambda p: bool(p.get("impatto_occupazionale"))),
    ("sostenibilita", "Sostenibilita'", "opzionale",
        lambda p: bool(p.get("sostenibilita"))),
]

SETTORI = [
    ("turismo_cultura", "Turismo & Cultura"),
    ("ict_digitale", "ICT & Digitale"),
    ("manifatturiero", "Manifatturiero & Artigianato"),
    ("agricoltura_agroalimentare", "Agricoltura & Agroalimentare"),
    ("commercio_servizi", "Commercio & Servizi"),
    ("energia_ambiente", "Energia & Ambiente"),
    ("sociale_terzo_settore", "Sociale & Terzo Settore"),
    ("edilizia_infrastrutture", "Edilizia & Infrastrutture"),
    ("ricerca_formazione", "Ricerca & Formazione"),
    ("trasporti_logistica", "Trasporti & Logistica"),
    ("altro", "Altro"),
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
    Items have: key, label, level (obbligatorio/importante/opzionale), ok.
    """
    items = []
    done = 0
    for key, label, level, check_fn in COMPLETEZZA_CHECKS:
        ok = check_fn(profilo)
        if ok:
            done += 1
        items.append({"key": key, "label": label, "level": level, "ok": ok})
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
