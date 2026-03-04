"""
Spider: Regione Sicilia — bandi e finanziamenti
URL: https://www.regione.sicilia.it/istituzioni/regione/strutture-regionali/presidenza-regione/attivita-produttive-imprese
Also: https://www.regione.sicilia.it/temi/economia-e-lavoro/attivita-produttive/bandi-avvisi

Extracts: titolo, url_dettaglio, data_scadenza, pdf_urls, testo_html
"""
from __future__ import annotations
import re
import logging
from datetime import date
from urllib.parse import urljoin

import scrapy
from scrapy.http import Response

logger = logging.getLogger(__name__)

MONTHS_IT = {
    "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4,
    "maggio": 5, "giugno": 6, "luglio": 7, "agosto": 8,
    "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12,
}


class RegioneSiciliaSpider(scrapy.Spider):
    name = "regione_sicilia"
    allowed_domains = ["regione.sicilia.it"]

    start_urls = [
        "https://www.regione.sicilia.it/temi/economia-e-lavoro/attivita-produttive/bandi-avvisi",
        "https://www.regione.sicilia.it/istituzioni/regione/strutture-regionali/presidenza-regione/attivita-produttive-imprese",
    ]

    custom_settings = {
        "DOWNLOAD_DELAY": 3,
        "ROBOTSTXT_OBEY": True,
        "DOWNLOAD_TIMEOUT": 30,
    }

    def parse(self, response: Response):
        """Parse listing page of bandi/avvisi."""
        bando_links = (
            response.css("article h2 a::attr(href)").getall()
            or response.css(".field-content a::attr(href)").getall()
            or response.css("td.views-field-title a::attr(href)").getall()
            or response.css("li a::attr(href)").getall()
        )

        if not bando_links:
            logger.warning(f"No links found on {response.url} — structure may have changed")
            return

        seen = set()
        for href in bando_links:
            url = urljoin(response.url, href)
            # Skip external and non-content links
            if "regione.sicilia.it" not in url:
                continue
            if any(skip in url for skip in ["/login", "/user", "/search", "/sitemap"]):
                continue
            if url not in seen:
                seen.add(url)
                yield scrapy.Request(url, callback=self.parse_bando)

        # Pagination (Drupal-style)
        next_page = response.css("li.pager-next a::attr(href), a.page-link[aria-label='Successivo']::attr(href)").get()
        if next_page:
            yield scrapy.Request(urljoin(response.url, next_page), callback=self.parse)

    def parse_bando(self, response: Response):
        """Parse individual bando page."""
        titolo = (
            response.css("h1.page-header::text").get()
            or response.css("h1::text").get()
            or response.css(".field-name-title::text").get()
            or ""
        ).strip()

        if not titolo:
            logger.warning(f"No title at {response.url}")
            return

        # Skip non-bando pages
        if any(skip in titolo.lower() for skip in ["privacy", "cookie", "accessibilità"]):
            return

        testo_html = (
            response.css(".field-name-body").get()
            or response.css("article.node").get()
            or response.css("main").get()
            or response.text
        )

        pdf_urls = [
            urljoin(response.url, href)
            for href in response.css("a[href$='.pdf']::attr(href)").getall()
        ]

        data_scadenza = self._extract_scadenza(response)
        importo_max = self._extract_importo(response)

        # Check for rettifica
        is_rettifica = "rettifica" in titolo.lower() or "avviso di rettifica" in titolo.lower()

        item = {
            "titolo": titolo,
            "ente_erogatore": "Regione Siciliana",
            "portale": "regione_sicilia",
            "url": response.url,
            "data_scadenza": data_scadenza.isoformat() if data_scadenza else None,
            "importo_max": importo_max,
            "pdf_urls": pdf_urls,
            "testo_html": testo_html[:50000] if testo_html else "",
            "is_rettifica": is_rettifica,
        }

        logger.info(f"Found bando: {titolo[:60]} | scadenza: {data_scadenza} | PDFs: {len(pdf_urls)}")
        yield item

    def _extract_scadenza(self, response: Response) -> date | None:
        text = " ".join(response.css("*::text").getall())

        # Try numeric patterns first
        numeric_patterns = [
            r"scaden[za]{0,2}[:\s]+(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4})",
            r"entro[:\s]+(?:il\s+)?(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4})",
            r"entro e non oltre[:\s]+(?:il\s+)?(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4})",
            r"(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4})",
        ]
        for pattern in numeric_patterns:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                date_str = m.group(1)
                for sep in ("/", "-", "."):
                    parts = date_str.split(sep)
                    if len(parts) == 3:
                        try:
                            d, mo, y = int(parts[0]), int(parts[1]), int(parts[2])
                            if 2020 < y < 2035 and 1 <= mo <= 12 and 1 <= d <= 31:
                                return date(y, mo, d)
                        except ValueError:
                            continue

        # Try Italian text date (e.g., "15 marzo 2025")
        text_pattern = r"(\d{1,2})\s+(gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)\s+(\d{4})"
        m = re.search(text_pattern, text, re.IGNORECASE)
        if m:
            try:
                d = int(m.group(1))
                mo = MONTHS_IT[m.group(2).lower()]
                y = int(m.group(3))
                return date(y, mo, d)
            except (ValueError, KeyError):
                pass

        return None

    def _extract_importo(self, response: Response) -> float | None:
        text = " ".join(response.css("*::text").getall())
        patterns = [
            r"dotazione[:\s]+(?:finanziaria[:\s]+)?€?\s*([\d\.,]+(?:\s*(?:mila|milioni|mln))?)",
            r"fino a\s+€?\s*([\d\.,]+(?:\.000)?)\s*euro",
            r"massimo\s+€?\s*([\d\.,]+(?:\.000)?)",
            r"€\s*([\d\.,]+(?:\.000)?)",
        ]
        for pattern in patterns:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                try:
                    amount_str = m.group(1).replace(".", "").replace(",", ".")
                    if "milioni" in amount_str or "mln" in amount_str:
                        return float(re.sub(r"[^\d.]", "", amount_str)) * 1_000_000
                    if "mila" in amount_str:
                        return float(re.sub(r"[^\d.]", "", amount_str)) * 1_000
                    return float(re.sub(r"[^\d.]", "", amount_str))
                except ValueError:
                    continue
        return None
