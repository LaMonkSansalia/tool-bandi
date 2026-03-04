"""
Spider: InPA — Istituto Nazionale per la Pubblica Amministrazione
URL: https://www.inpa.gov.it/bandi/

Monitors: avvisi pubblici, bandi di finanziamento per enti PA.
Note: InPA primarily covers PA roles and training — filter for funding bandi.

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

# Keywords that indicate this is a relevant bando (not just job posting)
RELEVANT_KEYWORDS = [
    "finanziamento", "incentivo", "contributo", "agevolazione",
    "avviso pubblico", "bando", "fondo", "misura", "voucher",
]


class InpaSpider(scrapy.Spider):
    name = "inpa"
    allowed_domains = ["inpa.gov.it"]

    start_urls = [
        "https://www.inpa.gov.it/bandi/",
    ]

    custom_settings = {
        "DOWNLOAD_DELAY": 3,
        "ROBOTSTXT_OBEY": True,
        "DOWNLOAD_TIMEOUT": 30,
    }

    def parse(self, response: Response):
        """Parse InPA bandi listing."""
        bando_links = (
            response.css(".bando-item a::attr(href)").getall()
            or response.css(".views-row a::attr(href)").getall()
            or response.css("article h2 a::attr(href), article h3 a::attr(href)").getall()
            or response.css("table.view-content td a::attr(href)").getall()
        )

        if not bando_links:
            logger.warning(f"No links at {response.url}")
            return

        seen = set()
        for href in bando_links:
            url = urljoin(response.url, href)
            if "inpa.gov.it" not in url:
                continue
            if url not in seen:
                seen.add(url)
                yield scrapy.Request(url, callback=self.parse_bando)

        # Pagination
        next_page = response.css("li.pager-next a::attr(href), a.pager__link--next::attr(href)").get()
        if next_page:
            yield scrapy.Request(urljoin(response.url, next_page), callback=self.parse)

    def parse_bando(self, response: Response):
        """Parse single InPA bando page."""
        titolo = (
            response.css("h1::text").get()
            or response.css(".node-title::text").get()
            or ""
        ).strip()

        if not titolo:
            logger.warning(f"No title at {response.url}")
            return

        # Check relevance — skip pure job postings
        titolo_lower = titolo.lower()
        full_text = " ".join(response.css("*::text").getall()).lower()

        is_relevant = any(kw in titolo_lower or kw in full_text[:500] for kw in RELEVANT_KEYWORDS)
        if not is_relevant:
            logger.debug(f"Skipping non-funding bando: {titolo[:60]}")
            return

        testo_html = (
            response.css(".node__content").get()
            or response.css("article").get()
            or response.css("main").get()
            or response.text
        )

        pdf_urls = [
            urljoin(response.url, href)
            for href in response.css("a[href$='.pdf']::attr(href)").getall()
        ]

        data_scadenza = self._extract_scadenza(response)
        importo_max = self._extract_importo(response)

        item = {
            "titolo": titolo,
            "ente_erogatore": "InPA",
            "portale": "inpa",
            "url": response.url,
            "data_scadenza": data_scadenza.isoformat() if data_scadenza else None,
            "importo_max": importo_max,
            "pdf_urls": pdf_urls,
            "testo_html": testo_html[:50000] if testo_html else "",
            "is_rettifica": "rettifica" in titolo_lower,
        }

        logger.info(f"Found bando InPA: {titolo[:60]} | scadenza: {data_scadenza}")
        yield item

    def _extract_scadenza(self, response: Response) -> date | None:
        text = " ".join(response.css("*::text").getall())

        patterns = [
            r"scaden[za]{0,2}[:\s]+(?:il\s+)?(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4})",
            r"termine.*?presentazione.*?(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4})",
            r"entro[:\s]+(?:il\s+)?(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4})",
            r"(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4})",
        ]
        for pattern in patterns:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                date_str = m.group(1)
                for sep in ("/", "-", "."):
                    parts = date_str.split(sep)
                    if len(parts) == 3:
                        try:
                            d, mo, y = int(parts[0]), int(parts[1]), int(parts[2])
                            if 2020 < y < 2035 and 1 <= mo <= 12:
                                return date(y, mo, d)
                        except ValueError:
                            continue

        m = re.search(
            r"(\d{1,2})\s+(gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)\s+(\d{4})",
            text, re.IGNORECASE
        )
        if m:
            try:
                return date(int(m.group(3)), MONTHS_IT[m.group(2).lower()], int(m.group(1)))
            except (ValueError, KeyError):
                pass
        return None

    def _extract_importo(self, response: Response) -> float | None:
        text = " ".join(response.css("*::text").getall())
        patterns = [
            r"dotazione.*?€?\s*([\d\.,]+(?:\s*(?:milioni|mln))?)",
            r"fino a\s+€?\s*([\d\.,]+)",
            r"€\s*([\d\.,]+(?:\.000)?)",
        ]
        for pattern in patterns:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                try:
                    s = m.group(1).strip()
                    multiplier = 1_000_000 if re.search(r"milion", s, re.I) else 1
                    return float(re.sub(r"[^\d]", "", s.split()[0])) * multiplier
                except (ValueError, IndexError):
                    continue
        return None
