"""
Tests for pure UI decision helpers.
"""
from datetime import date
from types import SimpleNamespace

from engine.ui.utils.decision_helpers import (
    infer_bando_phase_key,
    minimum_requirements,
    normalize_gap_items,
)


class TestInferBandoPhaseKey:
    def test_annunciato_from_metadata(self):
        row = {"metadata": {"stato_bando": "annunciato in gazzetta"}}
        assert infer_bando_phase_key(row, today=date(2026, 3, 4)) == "annunciato"

    def test_aperto_from_metadata(self):
        row = {"metadata": {"status": "aperto"}}
        assert infer_bando_phase_key(row, today=date(2026, 3, 4)) == "aperto"

    def test_chiuso_from_deadline(self):
        row = {"data_scadenza": "2026-03-01"}
        assert infer_bando_phase_key(row, today=date(2026, 3, 4)) == "chiuso"

    def test_annunciato_from_future_pub_date(self):
        row = {"data_pubblicazione": "2026-04-10", "data_scadenza": "2026-06-01"}
        assert infer_bando_phase_key(row, today=date(2026, 3, 4)) == "annunciato"

    def test_aperto_default(self):
        assert infer_bando_phase_key({}, today=date(2026, 3, 4)) == "aperto"


class TestMinimumRequirements:
    def test_collects_relevant_requirements(self):
        bando = {
            "regioni_ammesse": ["Sicilia", "Calabria"],
            "tipo_beneficiario": ["pmi"],
            "fatturato_minimo": 50000,
            "dipendenti_minimi": 2,
            "anzianita_minima_anni": 3,
            "certificazioni_richieste": ["ISO 9001"],
            "soa_richiesta": True,
        }
        reqs = minimum_requirements(bando)
        assert any("Regioni ammesse" in r for r in reqs)
        assert any("Beneficiari" in r for r in reqs)
        assert any("Fatturato minimo" in r for r in reqs)
        assert any("Dipendenti minimi" in r for r in reqs)
        assert any("Anzianita'" in r for r in reqs)
        assert any("Certificazioni" in r for r in reqs)
        assert any("SOA" in r for r in reqs)


class TestNormalizeGapItems:
    def test_hard_stop_returns_single_blocking_gap(self):
        gaps = normalize_gap_items(
            evaluation={},
            gap_result=None,
            hard_stop_excluded=True,
            hard_stop_reason="Fatturato minimo troppo alto",
        )
        assert len(gaps) == 1
        assert gaps[0]["semaforo"] == "rosso"
        assert "Fatturato minimo" in gaps[0]["descrizione"]

    def test_live_gap_items_sorted_and_fallback_suggestions(self):
        gap_result = SimpleNamespace(
            gaps=[
                SimpleNamespace(
                    tipo=SimpleNamespace(value="recuperabile"),
                    categoria="certificazione",
                    descrizione="Serve ISO 9001",
                    suggerimento="",
                    semaforo="giallo",
                ),
                SimpleNamespace(
                    tipo=SimpleNamespace(value="bloccante"),
                    categoria="giuridica",
                    descrizione="Forma giuridica non ammessa",
                    suggerimento="Valutare ATS",
                    semaforo="rosso",
                ),
            ]
        )
        gaps = normalize_gap_items(
            evaluation={},
            gap_result=gap_result,
            hard_stop_excluded=False,
            hard_stop_reason=None,
        )
        assert len(gaps) == 2
        assert gaps[0]["semaforo"] == "rosso"
        assert gaps[1]["semaforo"] == "giallo"
        assert gaps[1]["suggerimento"]  # fallback should be populated

    def test_uses_stored_gap_analysis_when_live_missing(self):
        evaluation = {
            "gap_analysis": [
                {
                    "tipo": "recuperabile",
                    "categoria": "fatturato",
                    "descrizione": "Fatturato borderline",
                    "suggerimento": "",
                    "semaforo": "giallo",
                }
            ]
        }
        gaps = normalize_gap_items(
            evaluation=evaluation,
            gap_result=None,
            hard_stop_excluded=False,
            hard_stop_reason=None,
        )
        assert len(gaps) == 1
        assert gaps[0]["categoria"] == "fatturato"
        assert gaps[0]["suggerimento"]  # fallback should be populated

