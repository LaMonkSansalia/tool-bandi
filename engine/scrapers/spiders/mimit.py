"""
Spider: MIMIT — Ministero delle Imprese e del Made in Italy
URL: https://www.mimit.gov.it/it/incentivi
Also: https://www.mimit.gov.it/it/comunicati-stampa (bandi/avvisi)

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


class MimitSpider(scrapy.Spider):
    name = "mimit"
    allowed_domains = ["mimit.gov.it"]

    start_urls = [
        "https://www.mimit.gov.it/it/incentivi",
    ]

    custom_settings = {
        "DOWNLOAD_DELAY": 3,
        "ROBOTSTXT_OBEY": True,
        "DOWNLOAD_TIMEOUT": 30,
    }

    def parse(self, response: Response):
        """Parse MIMIT incentivi listing."""
        # MIMIT uses a Bootstrap-based layout with cards
        bando_links = (
            response.css(".card a::attr(href)").getall()
            or response.css(".incentivi-item a::attr(href)").getall()
            or response.css("h2 a::attr(href), h3 a::attr(href)").getall()
            or response.css("table td a::attr(href)").getall()
        )

        if not bando_links:
            logger.warning(f"No links at {response.url}")
            return

        seen = set()
        for href in bando_links:
            url = urljoin(response.url, href)
            if "mimit.gov.it" not in url:
                continue
            if url not in seen:
                seen.add(url)
                yield scrapy.Request(url, callback=self.parse_bando)

        # Pagination
        next_page = response.css("a.next::attr(href), li.next a::attr(href), a[rel='next']::attr(href)").get()
        if next_page:
            yield scrapy.Request(urljoin(response.url, next_page), callback=self.parse)

    def parse_bando(self, response: Response):
        """Parse MIMIT bando detail page."""
        titolo = (
            response.css("h1::text").get()
            or response.css(".page-title::text").get()
            or response.css("header h1::text").get()
            or ""
        ).strip()

        if not titolo:
            logger.warning(f"No title at {response.url}")
            return

        testo_html = (
            response.css(".jumbotron").get()
            or response.css("article").get()
            or response.css("main .container").get()
            or response.text
        )

        pdf_urls = [
            urljoin(response.url, href)
            for href in response.css("a[href$='.pdf']::attr(href)").getall()
        ]
        # MIMIT often uses download links
        pdf_urls += [
            urljoin(response.url, href)
            for href in response.css("a.download::attr(href), a[href*='download']::attr(href)").getall()
            if href not in pdf_urls
        ]

        data_scadenza = self._extract_scadenza(response)
        importo_max = self._extract_importo(response)
        is_rettifica = "rettifica" in titolo.lower()

        item = {
            "titolo": titolo,
            "ente_erogatore": "MIMIT",
            "portale": "mimit",
            "url": response.url,
            "data_scadenza": data_scadenza.isoformat() if data_scadenza else None,
            "importo_max": importo_max,
            "pdf_urls": list(set(pdf_urls)),
            "testo_html": testo_html[:50000] if testo_html else "",
            "is_rettifica": is_rettifica,
        }

        logger.info(f"Found bando: {titolo[:60]} | scadenza: {data_scadenza}")
        yield item

    def _extract_scadenza(self, response: Response) -> date | None:
        text = " ".join(response.css("*::text").getall())

        patterns = [
            r"scaden[za]{0,2}[:\s]+(?:il\s+)?(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4})",
            r"presentazione.*?entro[:\s]+(?:il\s+)?(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4})",
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

        # Italian text date
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
            r"risorse[:\s]+(?:disponibili[:\s]+)?€?\s*([\d\.,]+(?:\s*(?:mila|milioni|mln|mld))?)",
            r"dotazione[:\s]+€?\s*([\d\.,]+)",
            r"fino a\s+€?\s*([\d\.,]+(?:\.000)?)\s*(?:euro)?",
            r"€\s*([\d\.,]+(?:\.000)?)",
        ]
        for pattern in patterns:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                try:
                    s = m.group(1)
                    multiplier = 1
                    if re.search(r"miliard", s, re.I):
                        multiplier = 1_000_000_000
                    elif re.search(r"milion", s, re.I):
                        multiplier = 1_000_000
                    elif "mila" in s:
                        multiplier = 1_000
                    clean = float(re.sub(r"[^\d]", "", s.split()[0]))
                    return clean * multiplier
                except (ValueError, IndexError):
                    continue
        return None
