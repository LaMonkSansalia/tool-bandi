"""
Scrapy settings for bandi_researcher project.
"""

BOT_NAME = "bandi_researcher"
SPIDER_MODULES = ["engine.scrapers.spiders"]
NEWSPIDER_MODULE = "engine.scrapers.spiders"

# Respectful crawling
ROBOTSTXT_OBEY = True
CONCURRENT_REQUESTS = 4
CONCURRENT_REQUESTS_PER_DOMAIN = 2
DOWNLOAD_DELAY = 2          # seconds between requests to same domain
RANDOMIZE_DOWNLOAD_DELAY = True

# Retry
RETRY_ENABLED = True
RETRY_TIMES = 3
RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429]

# Timeout
DOWNLOAD_TIMEOUT = 30

# User agent rotation (polite but realistic)
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# Middlewares
DOWNLOADER_MIDDLEWARES = {
    "engine.scrapers.middlewares.RateLimitMiddleware": 543,
    "engine.scrapers.middlewares.RetryMiddleware": 550,
}

# Pipelines — order matters
ITEM_PIPELINES = {
    "engine.scrapers.pipelines.BandiPipeline": 300,
}

# Playwright (for JS-heavy portals)
DOWNLOAD_HANDLERS = {
    "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
}
PLAYWRIGHT_BROWSER_TYPE = "chromium"
PLAYWRIGHT_LAUNCH_OPTIONS = {"headless": True}

# Logging
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"

# Feed exports (for debug runs with -o output.json)
FEEDS = {}
