"""
Spider: PA Digitale 2026
URL: https://padigitale2026.gov.it/misure

Focused on avvisi pubblici per comuni e PA locali — aggregated catalog.
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


class PaDigitaleSpider(scrapy.Spider):
    name = "padigitale"
    allowed_domains = ["padigitale2026.gov.it"]

    start_urls = [
        "https://padigitale2026.gov.it/misure",
    ]

    custom_settings = {
        "DOWNLOAD_DELAY": 2,
        "ROBOTSTXT_OBEY": True,
        "DOWNLOAD_TIMEOUT": 30,
    }

    def parse(self, response: Response):
        """Parse misure/avvisi catalog."""
        # PA Digitale has card-based layouts
        bando_links = (
            response.css(".misura-card a::attr(href)").getall()
            or response.css(".avviso-item a::attr(href)").getall()
            or response.css("article a::attr(href)").getall()
            or response.css(".card a::attr(href)").getall()
        )

        if not bando_links:
            logger.warning(f"No links at {response.url} — may require JS rendering")
            # Attempt to find any content links
            bando_links = response.css("a[href*='/misure/']::attr(href), a[href*='/avvisi/']::attr(href)").getall()

        seen = set()
        for href in bando_links:
            url = urljoin(response.url, href)
            if "padigitale2026.gov.it" not in url:
                continue
            if url not in seen:
                seen.add(url)
                yield scrapy.Request(url, callback=self.parse_bando)

    def parse_bando(self, response: Response):
        """Parse single misura/avviso page."""
        titolo = (
            response.css("h1::text").get()
            or response.css(".misura-title::text").get()
            or response.css(".page-title::text").get()
            or ""
        ).strip()

        if not titolo:
            logger.warning(f"No title at {response.url}")
            return

        testo_html = (
            response.css(".misura-content").get()
            or response.css("main article").get()
            or response.css("main").get()
            or response.text
        )

        pdf_urls = [
            urljoin(response.url, href)
            for href in response.css("a[href$='.pdf']::attr(href)").getall()
        ]

        # Also grab attached documents (often .zip with PDF inside)
        doc_urls = response.css("a[href*='allegat']::attr(href)").getall()
        for href in doc_urls:
            url = urljoin(response.url, href)
            if url not in pdf_urls:
                pdf_urls.append(url)

        data_scadenza = self._extract_scadenza(response)
        importo_max = self._extract_importo(response)

        item = {
            "titolo": titolo,
            "ente_erogatore": "PA Digitale 2026 / AgID",
            "portale": "padigitale",
            "url": response.url,
            "data_scadenza": data_scadenza.isoformat() if data_scadenza else None,
            "importo_max": importo_max,
            "pdf_urls": pdf_urls,
            "testo_html": testo_html[:50000] if testo_html else "",
            "is_rettifica": "rettifica" in titolo.lower(),
        }

        logger.info(f"Found misura: {titolo[:60]} | scadenza: {data_scadenza}")
        yield item

    def _extract_scadenza(self, response: Response) -> date | None:
        text = " ".join(response.css("*::text").getall())

        # PA Digitale often shows dates in structured fields
        patterns = [
            r"scadenza.*?(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4})",
            r"apertura candidature.*?(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4})",
            r"entro.*?(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4})",
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
            r"dotazione.*?€?\s*([\d\.,]+(?:\s*(?:mila|milioni|mln))?)",
            r"risorse.*?€?\s*([\d\.,]+(?:\s*(?:mila|milioni|mln))?)",
            r"fino a\s+€?\s*([\d\.,]+)",
            r"€\s*([\d\.,]+(?:\.000)?)",
        ]
        for pattern in patterns:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                try:
                    s = m.group(1).strip()
                    multiplier = 1
                    if re.search(r"milion", s, re.I):
                        multiplier = 1_000_000
                    elif "mila" in s:
                        multiplier = 1_000
                    clean = float(re.sub(r"[^\d]", "", s.split()[0]))
                    return clean * multiplier
                except (ValueError, IndexError):
                    continue
        return None
