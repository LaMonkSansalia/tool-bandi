"""
Spider: EuroInfoSicilia
URL: https://www.euroinfosicilia.it/por-fesr-sicilia/bandi/

Aggregates EU-funded bandi for Sicilian businesses.
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


class EuroInfoSiciliaSpider(scrapy.Spider):
    name = "euroinfosicilia"
    allowed_domains = ["euroinfosicilia.it"]

    start_urls = [
        "https://www.euroinfosicilia.it/por-fesr-sicilia/bandi/",
        "https://www.euroinfosicilia.it/bandi-e-avvisi/",
    ]

    custom_settings = {
        "DOWNLOAD_DELAY": 2,
        "ROBOTSTXT_OBEY": True,
        "DOWNLOAD_TIMEOUT": 30,
    }

    def parse(self, response: Response):
        """Parse bandi listing pages."""
        bando_links = (
            response.css("article.post h2 a::attr(href)").getall()
            or response.css(".entry-title a::attr(href)").getall()
            or response.css(".bando-item a::attr(href)").getall()
            or response.css("h2 a::attr(href), h3 a::attr(href)").getall()
        )

        if not bando_links:
            logger.warning(f"No links at {response.url}")
            # WordPress-style fallback
            bando_links = response.css("a[href*='/bandi/'], a[href*='/avvisi/']::attr(href)").getall()

        seen = set()
        for href in bando_links:
            url = urljoin(response.url, href)
            if "euroinfosicilia.it" not in url:
                continue
            # Skip category/tag pages
            if any(skip in url for skip in ["/category/", "/tag/", "/page/", "?page"]):
                continue
            if url not in seen:
                seen.add(url)
                yield scrapy.Request(url, callback=self.parse_bando)

        # WordPress pagination
        next_page = (
            response.css("a.next.page-numbers::attr(href)").get()
            or response.css("link[rel='next']::attr(href)").get()
        )
        if next_page:
            yield scrapy.Request(urljoin(response.url, next_page), callback=self.parse)

    def parse_bando(self, response: Response):
        """Parse single bando post."""
        titolo = (
            response.css("h1.entry-title::text").get()
            or response.css("h1::text").get()
            or response.css(".post-title::text").get()
            or ""
        ).strip()

        if not titolo:
            logger.warning(f"No title at {response.url}")
            return

        testo_html = (
            response.css("div.entry-content").get()
            or response.css("article.post").get()
            or response.css("main").get()
            or response.text
        )

        pdf_urls = [
            urljoin(response.url, href)
            for href in response.css("a[href$='.pdf']::attr(href)").getall()
        ]

        # EuroInfoSicilia often links to external portals (Regione, EU)
        external_links = []
        for a in response.css("a"):
            href = a.attrib.get("href", "")
            text = a.css("::text").get("").lower()
            if href and any(kw in text for kw in ["scarica", "download", "bando", "avviso", "decreto"]):
                if href.endswith(".pdf") and href not in pdf_urls:
                    pdf_urls.append(href)
                elif not href.startswith("#"):
                    external_links.append(href)

        data_scadenza = self._extract_scadenza(response)
        importo_max = self._extract_importo(response)

        # Try to determine ente from content
        ente = self._detect_ente(response)

        item = {
            "titolo": titolo,
            "ente_erogatore": ente,
            "portale": "euroinfosicilia",
            "url": response.url,
            "data_scadenza": data_scadenza.isoformat() if data_scadenza else None,
            "importo_max": importo_max,
            "pdf_urls": pdf_urls,
            "testo_html": testo_html[:50000] if testo_html else "",
            "is_rettifica": "rettifica" in titolo.lower(),
        }

        logger.info(f"Found bando EuroInfo: {titolo[:60]} | ente: {ente} | scadenza: {data_scadenza}")
        yield item

    def _detect_ente(self, response: Response) -> str:
        """Try to detect the actual issuing entity from content."""
        text = " ".join(response.css("*::text").getall())
        ente_map = {
            "Regione Siciliana": ["regione siciliana", "regione sicilia"],
            "MIMIT": ["mimit", "ministero delle imprese", "mise"],
            "Invitalia": ["invitalia"],
            "FESR Sicilia": ["por fesr", "fesr"],
            "PNRR": ["pnrr", "piano nazionale"],
            "EU / Horizon": ["horizon europe", "horizon 2020"],
        }
        text_lower = text[:2000].lower()
        for ente, keywords in ente_map.items():
            if any(kw in text_lower for kw in keywords):
                return ente
        return "EuroInfoSicilia / Vario"

    def _extract_scadenza(self, response: Response) -> date | None:
        text = " ".join(response.css("*::text").getall())

        patterns = [
            r"scaden[za]{0,2}[:\s]+(?:il\s+)?(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4})",
            r"entro[:\s]+(?:il\s+)?(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4})",
            r"chiusura[:\s]+(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4})",
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
            r"dotazione.*?€?\s*([\d\.,]+(?:\s*(?:milioni|mln|mld))?)",
            r"fino a\s+€?\s*([\d\.,]+)",
            r"contributo.*?(?:massimo|fino a)\s+€?\s*([\d\.,]+)",
            r"€\s*([\d\.,]+(?:\.000)?)",
        ]
        for pattern in patterns:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                try:
                    s = m.group(1).strip()
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
