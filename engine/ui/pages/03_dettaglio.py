"""
Dettaglio bando — scheda completa con 3 tabs, ri-valuta, tutte le info.
Multi-project aware: uses project-specific profile for evaluation.
"""
import json
import re
from datetime import date

import streamlit as st
import pandas as pd
import psycopg2
import requests
from engine.config import DATABASE_URL
from engine.eligibility.hard_stops import check_hard_stops
from engine.eligibility.gap_analyzer import analyze_gaps
from engine.eligibility.configurable_scorer import score_bando_configurable
from engine.eligibility.rules import get_profile
from engine.projects.manager import (
    get_project_scoring_rules, update_evaluation_stato, upsert_evaluation,
)
from engine.ui.utils.decision_helpers import minimum_requirements, normalize_gap_items


def _extract_importo(text: str) -> float | None:
    """Estrae importo massimo dal testo della pagina."""
    for pattern in [
        r"fino a\s+€?\s*([\d\.]+(?:\.000)?)\s*euro",
        r"massimo\s+€?\s*([\d\.]+(?:\.000)?)\s*euro",
        r"€\s*([\d\.]+(?:\.000)?)",
    ]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            try:
                return float(m.group(1).replace(".", ""))
            except ValueError:
                continue
    return None


def _extract_finanziamento(text: str) -> tuple[str | None, float | None]:
    """Estrae tipo finanziamento e aliquota fondo perduto dal testo."""
    t = text.lower()
    aliquota = None
    fp_pct = re.search(r"(\d{1,3})\s*%\s*(?:a\s+)?fondo\s+perduto", t)
    if fp_pct:
        aliquota = float(fp_pct.group(1))
    has_fp    = bool(re.search(r"fondo\s+perduto|contributo\s+a\s+fondo", t))
    has_prest = bool(re.search(r"prestito\s+agevolato|finanziamento\s+agevolato|mutuo\s+agevolato", t))
    has_vouch = bool(re.search(r"voucher", t))
    has_cck   = bool(re.search(r"conto\s+capitale|in\s+conto\s+impianti|in\s+conto\s+interesse", t))

    if has_vouch:
        tipo = "voucher"
    elif has_fp and has_prest:
        tipo = "mix"
    elif has_fp:
        tipo = "fondo_perduto"
        aliquota = aliquota or 100.0
    elif has_cck:
        tipo = "contributo_conto_capitale"
    elif has_prest:
        tipo = "prestito_agevolato"
        aliquota = 0.0
    else:
        tipo = None
    return tipo, aliquota


def _days_left(scad) -> int | None:
    """Calculate days until deadline."""
    if scad is None:
        return None
    if hasattr(scad, "date"):
        scad = scad.date()
    try:
        return (scad - date.today()).days
    except Exception:
        return None


def _render_gap_message(gap: dict):
    sem = gap.get("semaforo")
    categoria = str(gap.get("categoria", "gap")).upper()
    descrizione = gap.get("descrizione", "")
    suggerimento = gap.get("suggerimento", "")
    message = f"**{categoria}** — {descrizione}"
    if suggerimento:
        message += f"\n\n💡 {suggerimento}"

    if sem == "rosso":
        st.error(message)
    elif sem == "giallo":
        st.warning(message)
    else:
        st.info(message)


SEMAFORO = {"verde": "🟢", "giallo": "🟡", "rosso": "🔴", None: "⚪"}
_TIPO_LABEL = {
    "fondo_perduto":             "🟢 Fondo perduto",
    "prestito_agevolato":        "🔵 Prestito agevolato",
    "mix":                       "🟡 Mix (FP + Prestito)",
    "contributo_conto_capitale": "🟢 Contributo conto capitale",
    "voucher":                   "🟣 Voucher",
    "altro":                     "⚪ Altro",
}

pid = st.session_state.get("current_project_id", 1)


# ── Recupera bando ────────────────────────────────────────────────────────────
bando_id = st.session_state.get("selected_bando_id")

if not bando_id:
    st.warning("Nessun bando selezionato. Torna alla lista bandi.")
    if st.button("← Lista bandi"):
        st.switch_page("pages/02_bandi.py")
    st.stop()

try:
    conn = psycopg2.connect(DATABASE_URL)
    df = pd.read_sql("SELECT * FROM bandi WHERE id = %s", conn, params=[bando_id])
    df_req = pd.read_sql(
        "SELECT * FROM bando_requisiti WHERE bando_id = %s AND (project_id = %s OR project_id IS NULL) ORDER BY tipo",
        conn, params=[bando_id, pid]
    )
    df_eval = pd.read_sql(
        "SELECT * FROM project_evaluations WHERE bando_id = %s AND project_id = %s",
        conn, params=[bando_id, pid]
    )
    conn.close()
except psycopg2.OperationalError:
    st.warning("Database non raggiungibile. Avvia: `docker compose up -d postgres`")
    st.stop()
except Exception as e:
    st.error(f"Errore DB: {e}")
    st.stop()

if df.empty:
    st.error(f"Bando {bando_id} non trovato.")
    st.stop()

bando = df.iloc[0].to_dict()
evaluation = df_eval.iloc[0].to_dict() if not df_eval.empty else {}

profile = get_profile(pid)
scoring_rules = get_project_scoring_rules(pid) or {}

_hs = check_hard_stops(bando, profile)
_score_result = score_bando_configurable(bando, profile, scoring_rules) if not _hs.excluded else None
_gap_result = analyze_gaps(bando, profile) if not _hs.excluded else None
gap_items = normalize_gap_items(evaluation, _gap_result, _hs.excluded, _hs.reason)

score = evaluation.get("score")
score_live = _score_result.score if _score_result else None
stato = evaluation.get("stato", bando.get("stato", "nuovo"))
tipo_fin = bando.get("tipo_finanziamento")
aliquota = bando.get("aliquota_fondo_perduto")
scad = bando.get("data_scadenza")
delta = _days_left(scad)
requirements = minimum_requirements(bando)


# ── Header ────────────────────────────────────────────────────────────────────
col_back, col_title = st.columns([1, 8])
with col_back:
    if st.button("← Lista"):
        st.switch_page("pages/02_bandi.py")

with col_title:
    st.title(bando["titolo"])
    st.caption(
        f"{bando.get('ente_erogatore', '—')} — {bando.get('portale', '—')} — "
        f"Scadenza: {bando.get('data_scadenza', '—')}"
    )

# ── Decision strip (above the fold) ──────────────────────────────────────────
col1, col2, col3, col4, col5, col6 = st.columns(6)
with col1:
    if _hs.excluded:
        st.metric("Idoneita'", "NO", "Hard stop")
    elif score_live is not None:
        st.metric("Idoneita'", "SI" if score_live >= 40 else "NO")
    else:
        st.metric("Idoneita'", "—")

with col2:
    if score_live is not None:
        delta_score = None
        if score is not None:
            try:
                delta_score = int(score_live) - int(score)
            except (TypeError, ValueError):
                delta_score = None
        st.metric("Score live", f"{score_live}/100", delta_score if delta_score else None)
    else:
        st.metric("Score live", "—")

with col3:
    if scad:
        st.metric("Scadenza", str(scad), f"{delta} giorni" if delta is not None else None)
    else:
        st.metric("Scadenza", "—")

with col4:
    if aliquota is not None:
        st.metric("Intensita' aiuto", f"{float(aliquota):.0f}% FP")
    elif tipo_fin:
        st.metric("Intensita' aiuto", _TIPO_LABEL.get(tipo_fin, tipo_fin))
    else:
        st.metric("Intensita' aiuto", "—")

with col5:
    st.metric("Req. minimi", len(requirements))

with col6:
    if bando.get("url_fonte"):
        st.link_button("🔗 Portale", bando["url_fonte"], use_container_width=True)
    else:
        st.metric("Fonte", "n/d")

if requirements:
    with st.expander("✅ Requisiti minimi in 20 secondi"):
        for req in requirements:
            st.markdown(f"- {req}")

st.divider()

# ── Sintesi — Partecipo o no? ─────────────────────────────────────────────────
st.subheader("🧭 Decisione in 60 secondi")

col_valut, col_info = st.columns([3, 2])

with col_valut:
    if _hs.excluded:
        st.error(f"⛔ **NON IDONEO — Hard Stop**\n\n{_hs.reason}")
    else:
        s = _score_result.score
        if s >= 60:
            st.success(
                f"✅ **PARTECIPA** — Score {s}/100\n\n"
                f"Il bando supera la soglia di notifica. I requisiti sono compatibili con il profilo."
            )
        elif s >= 40:
            st.warning(
                f"🟡 **VALUTA** — Score {s}/100\n\n"
                f"Compatibilita' parziale. Controlla i flag gialli prima di decidere."
            )
        else:
            st.error(
                f"🔴 **SCARSO INTERESSE** — Score {s}/100\n\n"
                f"Il bando ha bassa compatibilita' con il profilo."
            )

        pro = [r.description for r in _score_result.breakdown if r.matched]
        contro = [r.description for r in _score_result.breakdown if not r.matched]
        flags_gialli = [g for g in _gap_result.gaps if g.semaforo == "giallo"] if _gap_result else []
        flags_rossi  = [g for g in _gap_result.gaps if g.semaforo == "rosso"]  if _gap_result else []

        if pro:
            st.markdown("**Punti a favore:**")
            for p in pro:
                st.markdown(f"- ✅ {p}")
        if flags_rossi:
            st.markdown("**Criticita':**")
            for g in flags_rossi:
                st.markdown(f"- 🔴 {g.descrizione}")
        if flags_gialli:
            st.markdown("**Attenzione:**")
            for g in flags_gialli:
                st.markdown(f"- 🟡 {g.descrizione}")
        if contro and not flags_rossi:
            st.markdown("**Requisiti non soddisfatti:**")
            for c in contro[:3]:
                st.markdown(f"- ❌ {c}")

with col_info:
    st.markdown("**Scheda rapida**")
    if bando.get("ente_erogatore"):
        st.markdown(f"🏛️ {bando['ente_erogatore']}")

    if scad:
        urgenza = f" 🔴 **scade in {delta} giorni**" if delta is not None and 0 <= delta < 14 else ""
        st.markdown(f"📅 Scadenza: **{scad}**{urgenza}")

    if tipo_fin:
        label = _TIPO_LABEL.get(tipo_fin, f"⚪ {tipo_fin}")
        if aliquota is not None:
            label += f" — {float(aliquota):.0f}% a fondo perduto"
        st.markdown(f"💎 Tipo: {label}")
    else:
        st.markdown("💎 Tipo: ⚪ *non rilevato*")

    if bando.get("importo_max"):
        st.markdown(f"💰 Fino a **{bando['importo_max']:,.0f}€**")
    else:
        st.markdown("💰 Importo: *non disponibile*")
    if bando.get("budget_totale"):
        st.markdown(f"🏦 Budget totale: {bando['budget_totale']:,.0f}€")

    # Full lists (not truncated)
    if bando.get("tipo_beneficiario"):
        tb = bando["tipo_beneficiario"]
        if isinstance(tb, list):
            st.markdown(f"👤 Beneficiari: {', '.join(tb)}")
    if bando.get("regioni_ammesse"):
        ra = bando["regioni_ammesse"]
        if isinstance(ra, list):
            st.markdown(f"📍 Regioni: {', '.join(ra)}")
    if bando.get("settori_ateco"):
        sa = bando["settori_ateco"]
        if isinstance(sa, list):
            st.markdown(f"🏭 ATECO: {', '.join(sa)}")

st.divider()

# ── Gap suggestions first-class ──────────────────────────────────────────────
st.subheader("🛠️ Cosa ti manca per vincere?")

actionable_gaps = [g for g in gap_items if g.get("semaforo") in {"rosso", "giallo"}]
if actionable_gaps:
    for gap in actionable_gaps[:6]:
        _render_gap_message(gap)
else:
    st.success("Nessun gap critico: il profilo risulta allineato ai requisiti principali.")

informative_gaps = [g for g in gap_items if g.get("semaforo") == "verde"]
if informative_gaps:
    with st.expander("Note informative"):
        for gap in informative_gaps:
            _render_gap_message(gap)

st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# ── TABS ─────────────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

tab1, tab2, tab3 = st.tabs(["📋 Dettaglio Bando", "📊 Valutazione", "📄 Documenti & Testo"])

# ── Tab 1: Dettaglio Bando ───────────────────────────────────────────────────
with tab1:
    col_fin, col_req = st.columns(2)

    with col_fin:
        st.markdown("#### 💰 Finanziamento")
        st.markdown(f"""
| Campo | Valore |
|-------|--------|
| **Tipo** | {_TIPO_LABEL.get(tipo_fin, '—') if tipo_fin else '—'} |
| **Aliquota FP** | {f'{float(aliquota):.0f}%' if aliquota is not None else '—'} |
| **Importo max** | {f'{bando["importo_max"]:,.0f}€' if bando.get("importo_max") else '—'} |
| **Budget totale** | {f'{bando["budget_totale"]:,.0f}€' if bando.get("budget_totale") else '—'} |
""")

        st.markdown("#### 📅 Date")
        pub = bando.get("data_pubblicazione")
        scad_display = bando.get("data_scadenza")
        found = bando.get("first_seen_at")
        delta_str = f" ({delta} giorni)" if delta is not None else ""
        st.markdown(f"""
| Campo | Valore |
|-------|--------|
| **Pubblicazione** | {pub if pub else '—'} |
| **Scadenza** | {f'{scad_display}{delta_str}' if scad_display else '—'} |
| **Trovato il** | {found.strftime('%d/%m/%Y') if hasattr(found, 'strftime') else (found or '—')} |
""")

    with col_req:
        st.markdown("#### 🎯 Chi puo' partecipare")

        # Tipo beneficiario
        tb = bando.get("tipo_beneficiario")
        tb_str = ", ".join(tb) if isinstance(tb, list) and tb else "—"

        # Regioni
        ra = bando.get("regioni_ammesse")
        ra_str = ", ".join(ra) if isinstance(ra, list) and ra else "Tutte (nessuna restrizione)"

        # ATECO
        sa = bando.get("settori_ateco")
        sa_str = ", ".join(sa) if isinstance(sa, list) and sa else "Tutti"

        # Certificazioni
        cert = bando.get("certificazioni_richieste")
        cert_str = ", ".join(cert) if isinstance(cert, list) and cert else "Nessuna"

        fatt = bando.get("fatturato_minimo")
        dip = bando.get("dipendenti_minimi")
        anz = bando.get("anzianita_minima_anni")
        soa = bando.get("soa_richiesta")

        st.markdown(f"""
| Requisito | Valore |
|-----------|--------|
| **Beneficiari** | {tb_str} |
| **Regioni** | {ra_str} |
| **Settori ATECO** | {sa_str} |
| **Certificazioni** | {cert_str} |
| **SOA** | {'⛔ Richiesta' if soa else '✅ Non richiesta'} |
| **Fatturato minimo** | {f'{fatt:,.0f}€' if fatt else '—'} |
| **Dipendenti minimi** | {int(dip) if dip else '—'} |
| **Anzianita' minima** | {f'{int(anz)} anni' if anz else '—'} |
""")


# ── Tab 2: Valutazione ──────────────────────────────────────────────────────
with tab2:
    col_score_tab, col_gap_tab = st.columns(2)

    with col_score_tab:
        st.markdown("#### 📊 Score Breakdown")

        # Try stored JSONB first, fall back to live calculation
        stored_breakdown = evaluation.get("score_breakdown")
        if stored_breakdown and isinstance(stored_breakdown, list):
            for rule in stored_breakdown:
                matched = rule.get("matched", False)
                icon = "✅" if matched else "❌"
                pts = rule.get("points", 0)
                desc = rule.get("description", rule.get("rule", ""))
                st.markdown(f"{icon} **+{pts if matched else 0}pt** — {desc}")
        elif _score_result:
            for rule in _score_result.breakdown:
                icon = "✅" if rule.matched else "❌"
                st.markdown(f"{icon} **+{rule.points if rule.matched else 0}pt** — {rule.description}")
        else:
            st.info("Score non disponibile (hard stop attivo)")

        if _score_result:
            st.markdown(f"---\n**TOTALE: {_score_result.score}/100**")

    with col_gap_tab:
        st.markdown("#### 🔍 Gap Analysis")
        if gap_items:
            for gap in gap_items:
                sem = SEMAFORO.get(gap.get("semaforo"), "⚪")
                tipo = str(gap.get("tipo", "")).lower()
                categoria = gap.get("categoria", "")
                descrizione = gap.get("descrizione", "")
                suggerimento = gap.get("suggerimento", "")

                if "bloccante" in tipo or "blocking" in tipo or gap.get("semaforo") == "rosso":
                    st.error(f"{sem} **{categoria}** — {descrizione}")
                elif "recuperabile" in tipo or "recoverable" in tipo or gap.get("semaforo") == "giallo":
                    st.warning(f"{sem} **{categoria}** — {descrizione}")
                else:
                    st.info(f"{sem} {descrizione}")

                if suggerimento:
                    st.caption(f"💡 {suggerimento}")
        else:
            st.info("Gap analysis non disponibile")

    # Yellow flags
    yellow_flags = evaluation.get("yellow_flags")
    if yellow_flags and isinstance(yellow_flags, list):
        st.markdown("#### 🟡 Yellow Flags")
        for yf in yellow_flags:
            if isinstance(yf, str):
                st.warning(f"🟡 {yf}")
            elif isinstance(yf, dict):
                st.warning(f"🟡 {yf.get('descrizione', yf.get('message', str(yf)))}")

    # Checklist Requisiti (from bando_requisiti table)
    if not df_req.empty:
        st.markdown("#### 📋 Checklist Requisiti (da parsing)")
        for _, req in df_req.iterrows():
            sem = SEMAFORO.get(req.get("semaforo"), "⚪")
            label = f"{sem} **[{req['tipo'].upper()}]** {req['descrizione_originale']}"
            if req.get("valore_richiesto"):
                label += f" — richiesto: `{req['valore_richiesto']}`"
            if req.get("nota"):
                label += f"\n\n> {req['nota']}"
            st.markdown(label)


# ── Tab 3: Documenti & Testo ────────────────────────────────────────────────
with tab3:
    # Criteri di valutazione
    st.markdown("#### 📐 Criteri di valutazione")
    criteri = bando.get("criteri_valutazione")
    if criteri and isinstance(criteri, list):
        criteri_md = "| Criterio | Peso |\n|----------|------|\n"
        for c in criteri:
            if isinstance(c, dict):
                nome = c.get("criterio", "—")
                peso = c.get("peso")
                criteri_md += f"| {nome} | {f'{peso}%' if peso else '—'} |\n"
        st.markdown(criteri_md)
    else:
        st.caption("Criteri non disponibili — aggiorna la scheda per estrarli.")

    st.markdown("---")

    # Documenti da allegare
    st.markdown("#### 📎 Documenti da allegare")
    docs = bando.get("documenti_da_allegare")
    if docs and isinstance(docs, list):
        for doc in docs:
            st.markdown(f"- ☐ {doc}")
    else:
        st.caption("Lista documenti non disponibile.")

    st.markdown("---")

    # Note parsing
    confidence = bando.get("parsing_confidence")
    notes = bando.get("parsing_notes")
    if confidence or notes:
        st.markdown("#### 🤖 Note di parsing")
        if confidence:
            conf_icon = {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(confidence, "⚪")
            st.markdown(f"Confidenza: {conf_icon} **{confidence}**")
        if notes:
            st.markdown(f"> {notes}")
        st.markdown("---")

    # Raw text
    raw = bando.get("raw_text")
    if raw:
        with st.expander("📝 Testo completo del bando"):
            st.text(raw[:10000])
            if len(raw) > 10000:
                st.caption(f"(troncato a 10.000 caratteri su {len(raw):,} totali)")

    # Metadata JSON
    meta = bando.get("metadata")
    if meta:
        with st.expander("🔧 Metadata (JSON)"):
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except Exception:
                    pass
            st.json(meta)


# ══════════════════════════════════════════════════════════════════════════════
# ── AZIONI ───────────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

st.divider()
st.subheader("Azioni")

col_a, col_b, col_c, col_d = st.columns(4)

with col_a:
    if stato == "idoneo":
        if st.button("✅ Avvia lavorazione", type="primary"):
            update_evaluation_stato(pid, bando_id, "lavorazione")
            st.success("Stato aggiornato a LAVORAZIONE")
            st.rerun()

with col_b:
    if stato in ("idoneo", "nuovo", "analisi"):
        if st.button("❌ Ignora (scarta)"):
            motivo = st.text_input("Motivo (opzionale)")
            update_evaluation_stato(pid, bando_id, "scartato", motivo or "scartato manualmente")
            st.warning("Bando scartato")
            st.rerun()

with col_c:
    if stato in ("lavorazione", "pronto"):
        if st.button("📄 Vai a Documenti"):
            st.switch_page("pages/04_documenti.py")

with col_d:
    if st.button("🔄 Ri-valuta score"):
        with st.spinner("Ricalcolo in corso..."):
            hs = check_hard_stops(bando, profile)
            if hs.excluded:
                update_evaluation_stato(pid, bando_id, "scartato", hs.reason)
                st.error(f"Hard stop: {hs.reason}")
            else:
                result = score_bando_configurable(bando, profile, scoring_rules)
                gaps = analyze_gaps(bando, profile)

                # Serialize breakdown and gaps for JSONB storage
                breakdown_json = [
                    {"rule": r.rule, "points": r.points,
                     "description": r.description, "matched": r.matched}
                    for r in result.breakdown
                ]
                gaps_json = [
                    {"tipo": g.tipo.value if hasattr(g.tipo, 'value') else str(g.tipo),
                     "categoria": g.categoria, "descrizione": g.descrizione,
                     "suggerimento": g.suggerimento, "semaforo": g.semaforo}
                    for g in gaps.gaps
                ] if gaps else []

                new_stato = "idoneo" if result.score >= 40 else "scartato"
                upsert_evaluation(
                    pid, bando_id,
                    score=result.score,
                    stato=new_stato,
                    score_breakdown=breakdown_json,
                    gap_analysis=gaps_json,
                    yellow_flags=hs.yellow_flags if hs.yellow_flags else None,
                )
                st.success(f"Score aggiornato: **{result.score}/100** → {new_stato.upper()}")
            st.rerun()

st.divider()

# ── Aggiorna scheda finanziamento ────────────────────────────────────────────
with st.expander("🔄 Aggiorna scheda finanziamento"):
    st.caption("Ri-scarica la pagina del bando per aggiornare importo e tipo finanziamento.")
    url_fonte = bando.get("url_fonte")
    if not url_fonte:
        st.warning("Nessun URL disponibile per questo bando.")
    elif st.button("🔄 Aggiorna ora", key="btn_refresh"):
        with st.spinner("Scaricando la pagina..."):
            try:
                resp = requests.get(
                    url_fonte, timeout=15,
                    headers={"User-Agent": "Mozilla/5.0 (compatible; BandiResearcher/1.0)"}
                )
                resp.raise_for_status()
                page_text = resp.text

                new_importo  = _extract_importo(page_text)
                new_tipo, new_aliquota = _extract_finanziamento(page_text)

                upd_conn = psycopg2.connect(DATABASE_URL)
                with upd_conn.cursor() as cur:
                    cur.execute("""
                        UPDATE bandi SET
                            importo_max              = COALESCE(%(importo)s,    importo_max),
                            tipo_finanziamento       = COALESCE(%(tipo)s,       tipo_finanziamento),
                            aliquota_fondo_perduto   = COALESCE(%(aliquota)s,   aliquota_fondo_perduto),
                            updated_at               = NOW()
                        WHERE id = %(id)s
                    """, {
                        "importo":  new_importo,
                        "tipo":     new_tipo,
                        "aliquota": new_aliquota,
                        "id": bando_id,
                    })
                    upd_conn.commit()
                upd_conn.close()

                parts = []
                if new_importo:
                    parts.append(f"💰 Importo: **{new_importo:,.0f}€**")
                if new_tipo:
                    parts.append(f"💎 Tipo: **{new_tipo}**")
                if new_aliquota is not None:
                    parts.append(f"📊 Aliquota FP: **{new_aliquota:.0f}%**")

                if parts:
                    st.success("Scheda aggiornata!\n\n" + "  |  ".join(parts))
                else:
                    st.info("Nessun dato finanziario rilevato nella pagina. La scheda rimane invariata.")

                st.rerun()
            except requests.RequestException as e:
                st.error(f"Errore durante il download: {e}")
