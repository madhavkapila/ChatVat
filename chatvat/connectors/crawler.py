# FILE: chatvat/connectors/crawler.py

import asyncio
import logging
from typing import Optional, List, Set, Tuple, Dict
from urllib.parse import urlparse, urljoin

logger = logging.getLogger(__name__)

try:
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
    from crawl4ai.content_filter_strategy import PruningContentFilter
    from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
    from bs4 import BeautifulSoup
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
        # Visited set to prevent cyclic crawling (A -> B -> A)
        self.visited: Set[str] = set()

    def _surgical_cleanup(self, html: str) -> str:
        """
        The 'High-Level Only' Cleaner.
        Removes specific tags known to contain noise (menus, forms, scripts).
        Leaves the Content Structure (divs, tables, headers) 100% intact.
        """
        if not html: return ""
        
        try:
            soup = BeautifulSoup(html, 'html.parser')

            # The "Kill List" - Tags that are NEVER content
            NOISE_TAGS = [
                'nav', 'footer', 'header', 'aside', 
                'script', 'style', 'noscript', 'iframe',
                'form', 'select', 'button', 'input', 'textarea'
            ]

            for tag_name in NOISE_TAGS:
                for tag in soup.find_all(tag_name):
                    tag.decompose()

            return str(soup)

        except Exception as e:
            logger.warning(f"Surgical cleanup failed: {e}. Returning raw HTML.")
            return html

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

    def _normalize_url(self, url: str) -> str:
        """Strips fragments but KEEPS query params for pagination"""
        parsed = urlparse(url)
        # only strip the fragment (hash)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{parsed.query}"

    def _should_crawl(self, current_url: str, base_url: str, scope: str) -> bool:
        """
        Determines if we should follow this link based on user scope.
        """
        current_parsed = urlparse(current_url)
        base_parsed = urlparse(base_url)

        # 1. External Domain Check (Always block external links)
        if current_parsed.netloc != base_parsed.netloc:
            return False

        # 2. Scope Check
        if scope == "domain":
            return True # Same domain is allowed
        elif scope == "restrictive":
            # Must start with the base path
            # e.g. Base: /faculty, Link: /faculty/profile/1 (Allowed)
            # e.g. Base: /faculty, Link: /home (Blocked)
            return current_url.startswith(base_url)
        
        return False

    async def crawl_recursive(self, start_url: str, max_depth: int, scope: str) -> List[Dict[str, str]]:
        """
        Performs Breadth-First Search (BFS) Crawl.
        Returns a list of Markdown strings (one per page).
        Returns: [{'content': 'Clean Markdown', 'html_title': 'Page Title', 'url': '...'}, ...]
        """
        # Queue stores tuples: (url, current_depth)
        queue: List[Tuple[str, int]] = [(start_url, 1)]
        
        # Reset visited for this run, but add start_url normalized
        self.visited = {self._normalize_url(start_url)}
        
        results_data = []

        logger.info(f"🕷️ Starting Recursive Crawl: {start_url} (Depth: {max_depth}, Scope: {scope})")

        # Context Manager handles the Browser Session
        async with AsyncWebCrawler(config=self.browser_config) as crawler:
            
            while queue:
                # Pop the next URL to visit
                current_url, depth = queue.pop(0)
                
                logger.info(f"🕸️ Crawling [Depth {depth}/{max_depth}]: {current_url}")

                try:
                    md_generator = DefaultMarkdownGenerator()

                    # excluded_tags: Crawl4AI strips these HTML-spec tags BEFORE
                    # markdown conversion.  Removes structural noise (navs, footers,
                    # forms, dropdowns) while preserving content structure (headings,
                    # tables, lists, bold text).
                    # This does NOT affect result.html — raw HTML stays intact for
                    # metadata extraction in metadata.py.
                    # Every tag listed is an HTML standard element — source-agnostic.
                    run_config = CrawlerRunConfig(
                        cache_mode=CacheMode.BYPASS,
                        markdown_generator=md_generator,
                        excluded_tags=[
                            "nav", "footer", "header", "aside",
                            "noscript", "iframe",
                            "form", "select", "option",
                            "button", "input", "textarea",
                        ],
                        remove_forms=True,
                    )

                    # Fetch Page
                    result = await crawler.arun(url=current_url, config=run_config)

                    if result.success:
                        # Get Clean Content (Pruned Markdown)
                        # We clean the HTML immediately so both Markdown and Links are clean.
                        clean_html = self._surgical_cleanup(result.html)

                        clean_content = result.markdown.fit_markdown or result.markdown.raw_markdown

                        # Add the content to our results
                        results_data.append({
                            "content": clean_content,
                            # "html_title": page_title,
                            "url": current_url,
                            "html": result.html,          # Raw HTML for metadata extraction (trafilatura needs <head>, <meta>, etc.)
                            "clean_html": clean_html       # Cleaned HTML for link discovery and visual header extraction
                        })

                        # If we can go deeper, look for links
                        if depth < max_depth:
                            # We parse 'clean_html' so we don't find links in the footer/nav
                            soup = BeautifulSoup(clean_html, 'html.parser')

                            # Find all links
                            links_found = 0
                            for link in soup.find_all('a', href=True):
                                raw_href = link['href']
                                
                                # Convert relative (/profile) to absolute (https://...)
                                abs_link = urljoin(current_url, raw_href)
                                norm_link = self._normalize_url(abs_link)

                                # Validation Chain
                                if (norm_link not in self.visited 
                                    and self._is_safe_url(abs_link)
                                    and self._should_crawl(abs_link, start_url, scope)):
                                    
                                    self.visited.add(norm_link)
                                    queue.append((abs_link, depth + 1))
                                    links_found += 1
                            
                            logger.info(f"   ↳ Found {links_found} valid sub-links to queue.")

                    else:
                        logger.warning(f"Failed to crawl {current_url}: {result.error_message}")

                except Exception as e:
                    logger.error(f"Critical error on {current_url}: {e}")
                    # Continue to next item in queue, don't crash

        logger.info(f"✅ Recursive Crawl Complete. Pages fetched: {len(results_data)}")
        return results_data

    # Wrapper for single page (backward compatibility)
    async def fetch_page(self, url: str) -> Optional[str]:
        results = await self.crawl_recursive(url, max_depth=1, scope="restrictive")
        if results:
            return results[0].get('html') or results[0].get('content')
        return None