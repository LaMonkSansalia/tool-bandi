"""
Pydantic models for validated Claude structurer output.
These models define the expected JSON structure for parsed bandi.
"""
from __future__ import annotations
from datetime import date
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class CriterioValutazione(BaseModel):
    criterio: str
    peso: Optional[int] = None          # percentage weight if present


class BandoStructured(BaseModel):
    """
    Validated output from claude_structurer.py.
    Maps directly to the `bandi` DB table.
    """
    titolo: str
    ente_erogatore: Optional[str] = None
    portale: Optional[str] = None

    data_scadenza: Optional[date] = None
    data_pubblicazione: Optional[date] = None

    budget_totale: Optional[float] = None
    importo_max: Optional[float] = None          # max per single beneficiary

    tipo_beneficiario: list[str] = Field(default_factory=list)
    regioni_ammesse: list[str] = Field(default_factory=list)

    fatturato_minimo: Optional[float] = None
    dipendenti_minimi: Optional[int] = None
    anzianita_minima_anni: Optional[int] = None

    soa_richiesta: bool = False
    certificazioni_richieste: list[str] = Field(default_factory=list)
    settori_ateco: list[str] = Field(default_factory=list)

    criteri_valutazione: list[CriterioValutazione] = Field(default_factory=list)
    documenti_da_allegare: list[str] = Field(default_factory=list)

    @field_validator("data_scadenza", "data_pubblicazione", mode="before")
    @classmethod
    def parse_date(cls, v):
        if v is None:
            return None
        if isinstance(v, date):
            return v
        if isinstance(v, str):
            # Try common Italian date formats
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y"):
                try:
                    from datetime import datetime
                    return datetime.strptime(v.strip(), fmt).date()
                except ValueError:
                    continue
        return None  # unparseable → None, flag for review

    @field_validator("budget_totale", "importo_max", "fatturato_minimo", mode="before")
    @classmethod
    def parse_currency(cls, v):
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            # Strip currency symbols and thousand separators
            clean = v.replace("€", "").replace(".", "").replace(",", ".").strip()
            try:
                return float(clean)
            except ValueError:
                return None
        return None

    @field_validator("tipo_beneficiario", "regioni_ammesse",
                     "certificazioni_richieste", "settori_ateco",
                     "documenti_da_allegare", mode="before")
    @classmethod
    def ensure_list(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            return [v]
        return v


class BandoRequisitoRaw(BaseModel):
    """Single requirement extracted by Claude for the bando_requisiti table."""
    tipo: str                           # hard | soft | bonus
    categoria: str                      # fatturato | dipendenti | geo | giuridica | certificazione | altro
    descrizione_originale: str          # verbatim from bando
    valore_richiesto: Optional[str] = None
    soddisfatto: Optional[bool] = None  # None = unknown until checked
    semaforo: Optional[str] = None      # verde | giallo | rosso
    fonte_evidenza: Optional[str] = None
    nota: Optional[str] = None


class ClaudeStructurerOutput(BaseModel):
    """
    Complete output from claude_structurer.py.
    Contains parsed bando + list of extracted requirements.
    """
    bando: BandoStructured
    requisiti: list[BandoRequisitoRaw] = Field(default_factory=list)
    parsing_notes: Optional[str] = None    # Claude's own notes about uncertainty
    confidence: Optional[str] = None       # high | medium | low
