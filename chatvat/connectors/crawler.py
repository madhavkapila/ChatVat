import asyncio
import logging
from typing import Optional
from urllib.parse import urlparse

# We use the standard logger. In Docker, this outputs to the console
# which can be viewed via 'docker logs'.
logger = logging.getLogger(__name__)

try:
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
except ImportError:
    logger.error("Crawl4AI not installed. The bot cannot browse the web.")
    raise

class RuntimeCrawler:
    """
    The 'Eyes' of the bot inside the container.
    Fetches static or dynamic (JS) websites and returns clean Markdown.
    """

    def __init__(self):
        # Configure the browser to run strictly in Headless mode (No GUI)
        # This is CRITICAL for Docker containers which have no screen.
        self.browser_config = BrowserConfig(
            headless=True,
            verbose=False, # Keep logs clean in production
            user_agent_mode="random" # Added here to avoid getting blocked by some sites when using default user-agent which is easily identifiable as a bot
        )

    def _is_safe_url(self, url: str) -> bool:
        """
        SSRF Protection: Prevents the bot from accessing internal container network.
        """
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
            # Configuring the run
            run_config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,      # Production bots need FRESH data
                word_count_threshold=10,          # Skip empty/error pages
                wait_for="body",                  # Wait until body is loaded (Basic JS wait)
                # timeout=30                      # Default timeout
            )

            # Start the browser context
            async with AsyncWebCrawler(config=self.browser_config) as crawler:
                result = await crawler.arun(url=url, config=run_config)

                if result.success:
                    logger.info(f"Successfully crawled {url} ({len(result.markdown)} chars)")
                    return result.markdown
                else:
                    logger.error(f"Failed to crawl {url}: {result.error_message}")
                    return None

        except Exception as e:
            # GRACEFUL DEGRADATION:
            # We catch the crash, log it, and return None.
            # The ingestion loop will simply skip this URL and try the next one.
            logger.exception(f"Critical Crawler Error on {url}")
            return None