"""
Spider: Comune di Palermo — Albo Pretorio + Bandi
URLs:
  - https://www.comune.palermo.it/albopretorio (avvisi ufficiali)
  - https://www.comune.palermo.it/ufficio.php?id=... (specific offices)

Focus: bandi per imprese, incentivi, contributi comunali.
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

RELEVANT_KEYWORDS = [
    "bando", "avviso", "contributo", "finanziamento", "incentivo",
    "agevolazione", "voucher", "fondo", "sussidio", "misura",
    "impresa", "attività produttiva", "commercio",
]


class ComunePalermoSpider(scrapy.Spider):
    name = "comune_palermo"
    allowed_domains = ["comune.palermo.it"]

    start_urls = [
        "https://www.comune.palermo.it/albopretorio",
    ]

    custom_settings = {
        "DOWNLOAD_DELAY": 3,
        "ROBOTSTXT_OBEY": True,
        "DOWNLOAD_TIMEOUT": 30,
    }

    def parse(self, response: Response):
        """Parse Albo Pretorio listing."""
        # Albo Pretorio typically uses table rows
        rows = response.css("table tr, .albo-row, .atti-row")

        if not rows:
            logger.warning(f"No rows at {response.url}")
            # Try generic link extraction
            links = response.css("a[href*='atto'], a[href*='bando'], a[href*='avviso']")
            for link in links:
                href = link.attrib.get("href", "")
                url = urljoin(response.url, href)
                if "comune.palermo.it" in url:
                    yield scrapy.Request(url, callback=self.parse_bando)
            return

        for row in rows:
            title_text = " ".join(row.css("::text").getall()).lower()
            # Filter for relevant bandi
            if not any(kw in title_text for kw in RELEVANT_KEYWORDS):
                continue

            link = row.css("a::attr(href)").get()
            if link:
                url = urljoin(response.url, link)
                if "comune.palermo.it" in url:
                    yield scrapy.Request(url, callback=self.parse_bando)

        # Pagination
        next_page = response.css("a.next::attr(href), li.next a::attr(href), a[title='Pagina successiva']::attr(href)").get()
        if next_page:
            yield scrapy.Request(urljoin(response.url, next_page), callback=self.parse)

    def parse_bando(self, response: Response):
        """Parse single atto/bando page."""
        titolo = (
            response.css("h1::text").get()
            or response.css(".oggetto::text").get()
            or response.css(".titolo-atto::text").get()
            or response.css("h2::text").get()
            or ""
        ).strip()

        if not titolo:
            logger.warning(f"No title at {response.url}")
            return

        full_text = " ".join(response.css("*::text").getall()).lower()

        # Final relevance check
        if not any(kw in titolo.lower() or kw in full_text[:1000] for kw in RELEVANT_KEYWORDS):
            logger.debug(f"Skipping irrelevant atto: {titolo[:60]}")
            return

        testo_html = (
            response.css(".contenuto-atto").get()
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
            "ente_erogatore": "Comune di Palermo",
            "portale": "comune_palermo",
            "url": response.url,
            "data_scadenza": data_scadenza.isoformat() if data_scadenza else None,
            "importo_max": importo_max,
            "pdf_urls": pdf_urls,
            "testo_html": testo_html[:50000] if testo_html else "",
            "is_rettifica": "rettifica" in titolo.lower(),
        }

        logger.info(f"Found bando Palermo: {titolo[:60]} | scadenza: {data_scadenza}")
        yield item

    def _extract_scadenza(self, response: Response) -> date | None:
        text = " ".join(response.css("*::text").getall())

        patterns = [
            r"scaden[za]{0,2}[:\s]+(?:il\s+)?(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4})",
            r"termine.*?(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4})",
            r"entro[:\s]+(?:il\s+)?(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4})",
            r"presentare.*?entro.*?(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4})",
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
            r"contributo.*?(?:massimo|fino a)\s+€?\s*([\d\.,]+)",
            r"dotazione.*?€?\s*([\d\.,]+)",
            r"fino a\s+€?\s*([\d\.,]+)",
            r"€\s*([\d\.,]+(?:\.000)?)",
        ]
        for pattern in patterns:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                try:
                    s = m.group(1).replace(".", "").replace(",", ".")
                    return float(re.sub(r"[^\d.]", "", s))
                except ValueError:
                    continue
        return None
