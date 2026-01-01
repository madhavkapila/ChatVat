import asyncio
import logging
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

try:
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
except ImportError:
    logger.error("Crawl4AI not installed. The bot cannot browse the web.")
    raise

class RuntimeCrawler:
    """fetches static/dynamic websites and returns markdown"""

    def __init__(self):
        # Configure the browser to run strictly in Headless mode (No GUI)
        # This is CRITICAL for Docker containers which have no screen.
        self.browser_config = BrowserConfig(
            headless=True,
            verbose=False, # Keep logs clean in production
            user_agent_mode="random" # Added here to avoid getting blocked by some sites when using default user-agent which is easily identifiable as a bot
        )

    def _is_safe_url(self, url: str) -> bool:
        """ssrf protection - blocks internal network access"""
        try:
            parsed = urlparse(url)
            hostname = parsed.hostname
            if not hostname: return False
            # Block internal Docker IPs and Localhost
            if hostname in ["localhost", "127.0.0.1", "0.0.0.0", "::1"]:
                return False
            return True
        except Exception:
            return False

    async def fetch_page(self, url: str) -> Optional[str]:
        """
        Fetches a URL and returns Markdown content.
        catches ALL errors so the Background Worker thread doesn't crash.
        """
        if not self._is_safe_url(url):
            logger.warning(f"Security: Skipped unsafe URL {url}")
            return None

        logger.info(f"Crawling: {url}")

        try:
            run_config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,  # need fresh data
                word_count_threshold=10,
                wait_for="body",
            )

            async with AsyncWebCrawler(config=self.browser_config) as crawler:
                result = await crawler.arun(url=url, config=run_config)

                if result.success:
                    logger.info(f"Successfully crawled {url} ({len(result.markdown)} chars)")
                    return result.markdown
                else:
                    logger.error(f"Failed to crawl {url}: {result.error_message}")
                    return None

        except Exception as e:
            # log and skip, ingestion loop will try next url
            logger.exception(f"Critical Crawler Error on {url}")
            return None