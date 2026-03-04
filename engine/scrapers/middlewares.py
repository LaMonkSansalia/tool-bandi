"""
Custom Scrapy middlewares — rate limiting and retry logic.
"""
from __future__ import annotations
import logging
import time
from scrapy import signals
from scrapy.exceptions import NotConfigured

logger = logging.getLogger(__name__)


class RateLimitMiddleware:
    """Per-domain rate limiting with jitter."""

    def __init__(self, delay: float = 2.0):
        self.delay = delay
        self._last_request: dict[str, float] = {}

    @classmethod
    def from_crawler(cls, crawler):
        delay = crawler.settings.getfloat("DOWNLOAD_DELAY", 2.0)
        return cls(delay=delay)

    def process_request(self, request, spider):
        domain = request.url.split("/")[2]
        last = self._last_request.get(domain, 0)
        elapsed = time.time() - last
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self._last_request[domain] = time.time()
        return None


class RetryMiddleware:
    """Log retries with context."""

    def process_response(self, request, response, spider):
        if response.status in (429, 503):
            logger.warning(
                f"Rate limited ({response.status}) on {request.url} — will retry"
            )
        return response

    def process_exception(self, request, exception, spider):
        logger.error(f"Request failed: {request.url} — {type(exception).__name__}: {exception}")
        return None
