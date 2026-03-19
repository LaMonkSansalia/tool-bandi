"""
Tests for project onboarding form helpers.
"""
from engine.ui.utils.project_form import (
    seed_from_profile_json,
    validate_project_form,
)


class TestValidateProjectForm:
    def test_accepts_valid_payload(self):
        payload = {
            "new_slug": "pds-progetto",
            "new_nome": "Paese Delle Stelle",
            "denominazione": "Associazione PDS",
            "ateco": "62.01.00",
            "partita_iva": "07104590828",
            "data_inizio": "26/01/2023",
        }
        assert validate_project_form(payload) == []

    def test_rejects_invalid_slug(self):
        payload = {
            "new_slug": "AA",
            "new_nome": "Nome",
            "denominazione": "Den",
        }
        errors = validate_project_form(payload)
        assert any("Slug non valido" in e for e in errors)

    def test_rejects_invalid_ateco(self):
        payload = {
            "new_slug": "slug-ok",
            "new_nome": "Nome",
            "denominazione": "Den",
            "ateco": "abc",
        }
        errors = validate_project_form(payload)
        assert any("ATECO principale non valido" in e for e in errors)

    def test_rejects_invalid_piva(self):
        payload = {
            "new_slug": "slug-ok",
            "new_nome": "Nome",
            "denominazione": "Den",
            "partita_iva": "123",
        }
        errors = validate_project_form(payload)
        assert any("P.IVA/Codice Fiscale non valido" in e for e in errors)

    def test_rejects_invalid_date_format(self):
        payload = {
            "new_slug": "slug-ok",
            "new_nome": "Nome",
            "denominazione": "Den",
            "data_inizio": "2026-01-01",
        }
        errors = validate_project_form(payload)
        assert any("Data inizio non valida" in e for e in errors)


class TestSeedFromProfileJson:
    def test_generates_seed_values(self):
        data = {
            "anagrafica": {
                "denominazione": "LA MONICA LUCIANO",
                "forma_giuridica": "impresa individuale",
                "partita_iva": "07104590828",
                "regime_fiscale": "forfettario",
            },
            "sede": {
                "comune": "Palermo",
                "provincia": "PA",
                "regione": "Sicilia",
                "zona_zes": True,
                "zona_mezzogiorno": True,
            },
            "attivita": {
                "ateco_2025": "62.20.10",
                "ateco_secondari": ["62.01.00", "63.11.20"],
                "settore_principale": "ICT",
                "data_inizio": "26/01/2023",
                "anni_attivita": 3,
            },
            "dimensione": {
                "dipendenti": 0,
                "fatturato_stimato_max": 85000,
                "micro_impresa": True,
            },
            "certificazioni": {
                "iso_9001": False,
                "iso_27001": False,
                "soa": None,
            },
            "skills": {"keywords": ["ICT", "PNRR"]},
        }
        seed = seed_from_profile_json(data)
        assert seed["new_slug"] == "la-monica-luciano"
        assert seed["new_nome"] == "LA MONICA LUCIANO"
        assert seed["ateco"] == "62.20.10"
        assert "62.01.00" in seed["ateco_secondari_text"]
        assert "ICT" in seed["skills_text"]
        assert seed["fatturato_max"] == 85000

