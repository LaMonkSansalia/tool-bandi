"""
Spider: Invitalia — bandi e incentivi
URL: https://www.invitalia.it/cosa-facciamo/rafforziamo-le-imprese

Extracts: titolo, url_dettaglio, data_scadenza, pdf_urls, testo_html
"""
from __future__ import annotations
import re
import logging
from datetime import date
from pathlib import Path
from urllib.parse import urljoin

import scrapy
from scrapy.http import Response

logger = logging.getLogger(__name__)

# Download PDFs here
PDF_DIR = Path(__file__).parent.parent.parent.parent / "bandi_trovati"


class InvitaliaSpider(scrapy.Spider):
    name = "invitalia"
    allowed_domains = ["invitalia.it"]

    start_urls = [
        "https://www.invitalia.it/cosa-facciamo/rafforziamo-le-imprese",
    ]

    custom_settings = {
        "DOWNLOAD_DELAY": 3,
        "ROBOTSTXT_OBEY": True,
    }

    def parse(self, response: Response):
        """Parse the main bandi listing page."""
        # Find bando cards/links — Invitalia uses various layouts; try common selectors
        bando_links = (
            response.css("article.card a::attr(href)").getall()
            or response.css(".incentivo-item a::attr(href)").getall()
            or response.css("h2 a::attr(href)").getall()
            or response.css("h3 a::attr(href)").getall()
        )

        if not bando_links:
            logger.warning(f"No bando links found on {response.url} — site structure may have changed")
            return

        seen = set()
        for href in bando_links:
            url = urljoin(response.url, href)
            if url not in seen and "invitalia.it" in url:
                seen.add(url)
                yield scrapy.Request(url, callback=self.parse_bando)

        # Pagination
        next_page = response.css("a.pagination-next::attr(href), a[rel='next']::attr(href)").get()
        if next_page:
            yield scrapy.Request(urljoin(response.url, next_page), callback=self.parse)

    def parse_bando(self, response: Response):
        """Parse individual bando detail page."""
        titolo = (
            response.css("h1::text").get()
            or response.css("h2.page-title::text").get()
            or ""
        ).strip()

        if not titolo:
            logger.warning(f"No title found at {response.url}")
            return

        # Extract all text content
        testo_html = response.css("main").get() or response.css("article").get() or response.text

        # Find PDF links
        pdf_urls = [
            urljoin(response.url, href)
            for href in response.css("a[href$='.pdf']::attr(href)").getall()
        ]

        # Try to extract deadline from text
        data_scadenza = self._extract_scadenza(response)

        # Try to extract budget/importo
        importo_max = self._extract_importo(response)

        tipo_fin, aliquota_fp = self._extract_finanziamento(response)

        item = {
            "titolo": titolo,
            "ente_erogatore": "Invitalia",
            "portale": "invitalia",
            "url": response.url,
            "url_fonte": response.url,
            "data_scadenza": data_scadenza.isoformat() if data_scadenza else None,
            "importo_max": importo_max,
            "tipo_finanziamento": tipo_fin,
            "aliquota_fondo_perduto": aliquota_fp,
            "pdf_urls": pdf_urls,
            "testo_html": testo_html[:50000],
        }

        logger.info(f"Found bando: {titolo[:60]} — {tipo_fin or '?'} — PDFs: {len(pdf_urls)}")
        yield item

    def _extract_scadenza(self, response: Response) -> date | None:
        """Try to extract deadline from page text using common patterns."""
        text = response.css("*::text").getall()
        full_text = " ".join(text)

        # Italian date patterns
        patterns = [
            r"scadenza[:\s]+(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4})",
            r"entro il\s+(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4})",
            r"(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4})",   # generic fallback
        ]

        for pattern in patterns:
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                date_str = match.group(1)
                for sep in ("/", "-", "."):
                    parts = date_str.split(sep)
                    if len(parts) == 3:
                        try:
                            d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
                            if y > 2020:   # sanity check
                                return date(y, m, d)
                        except ValueError:
                            continue
        return None

    def _extract_finanziamento(self, response: Response) -> tuple[str | None, float | None]:
        """
        Returns (tipo_finanziamento, aliquota_fondo_perduto%).
        Detects common Italian public-grant financing patterns.
        """
        text = " ".join(response.css("*::text").getall()).lower()

        # Detect fondo perduto percentage first (e.g. "50% a fondo perduto")
        aliquota = None
        fp_pct = re.search(r"(\d{1,3})\s*%\s*(?:a\s+)?fondo\s+perduto", text)
        if fp_pct:
            aliquota = float(fp_pct.group(1))

        # Classify tipo finanziamento
        has_fp    = bool(re.search(r"fondo\s+perduto|contributo\s+a\s+fondo", text))
        has_prest = bool(re.search(r"prestito\s+agevolato|finanziamento\s+agevolato|mutuo\s+agevolato", text))
        has_vouch = bool(re.search(r"voucher", text))
        has_cck   = bool(re.search(r"conto\s+capitale|in\s+conto\s+impianti|in\s+conto\s+interesse", text))

        if has_vouch:
            tipo = "voucher"
        elif has_fp and has_prest:
            tipo = "mix"
            aliquota = aliquota  # partial FP
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

    def _extract_importo(self, response: Response) -> float | None:
        """Try to extract max grant amount from page text."""
        text = " ".join(response.css("*::text").getall())
        patterns = [
            r"fino a\s+€?\s*([\d\.]+(?:\.000)?)\s*euro",
            r"massimo\s+€?\s*([\d\.]+(?:\.000)?)\s*euro",
            r"€\s*([\d\.]+(?:\.000)?)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    amount_str = match.group(1).replace(".", "")
                    return float(amount_str)
                except ValueError:
                    continue
        return None
