# # FILE: chatvat/core/metadata.py

import logging
import trafilatura
from typing import Optional, Dict
from urllib.parse import urlparse
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Tags that are never part of the "main content" — universal boilerplate.
_BOILERPLATE_TAGS = ["nav", "header", "footer", "aside", "script", "style", "noscript", "iframe"]


class MetadataExtractor:
    """
    Visual Dominance Metadata Extractor.

    Determines a page's true identity by reading it like a human:
    1. Extract the metadata title (from <title>, og:title, etc.)
    2. Extract the visual header — the first prominent heading a user
       would actually see in the content area.
    3. A caller (the Ingestor) decides which signal to trust, using
       cross-page frequency analysis to detect site-wide generic titles.

    This logic is source-agnostic: it relies on universal HTML structure
    (headings, semantic containers), not on specific keywords or domains.
    """

    # ── Public API ──────────────────────────────────────────────────

    def extract_signals(self, html: str, url: str) -> Dict[str, Optional[str]]:
        """
        Extract all identity signals from a single page.
        Returns: {
            "meta_title":    str,          # from <title> / og:title / trafilatura
            "visual_header": str | None,   # first prominent heading in content area
            "url_slug":      str           # cleaned last path segment
        }
        """
        meta_title = self._extract_meta_title(html) if html else ""
        visual_header = self._extract_visual_header(html) if html else None
        url_slug = self._extract_url_slug(url)
        return {
            "meta_title": meta_title,
            "visual_header": visual_header,
            "url_slug": url_slug,
        }

    def resolve_subject(
        self,
        signals: Dict[str, Optional[str]],
        title_is_sitewide: bool = False,
    ) -> str:
        """
        Final decision: pick the best identity from the extracted signals.

        The Visual Header is the PRIMARY signal — it is what a human
        actually reads as the page subject.  On well-built sites the
        meta title and visual header converge, so either works; on
        poorly-built sites (Thapar, etc.) they diverge, and the visual
        header is the one that's correct.

        Priority (source-agnostic, language-agnostic):
          1. visual_header  — first prominent heading in the content area
          2. meta_title     — only if no visual header was found AND
                              the title is not repeated site-wide noise
          3. url_slug       — last resort
          4. "Webpage Content" — absolute fallback
        """
        meta   = (signals.get("meta_title") or "").strip()
        visual = (signals.get("visual_header") or "").strip()
        slug   = (signals.get("url_slug") or "").strip()

        # Primary: Visual header — what a human reads
        if visual:
            return visual

        # Secondary: Meta title — only when visual extraction found nothing
        if meta and not title_is_sitewide:
            return meta

        # Tertiary: URL slug
        return slug or "Webpage Content"

    def get_page_subject(
        self, html: str, url: str, title_is_sitewide: bool = False
    ) -> str:
        """
        Backward-compatible convenience wrapper.
        Extracts signals and resolves in one call.
        """
        signals = self.extract_signals(html, url)
        return self.resolve_subject(signals, title_is_sitewide)

    # ── Private helpers ─────────────────────────────────────────────

    def _extract_meta_title(self, html: str) -> str:
        """
        Best-effort metadata title via trafilatura.
        Checks <title>, og:title, twitter:title, etc.
        """
        try:
            metadata = trafilatura.extract_metadata(html)
            if metadata and metadata.title:
                return metadata.title.strip()
        except Exception:
            pass
        return ""

    def _extract_visual_header(self, html: str) -> Optional[str]:
        """
        The 'Visual Dominance' heuristic.

        Finds the first prominent heading a human would see in the
        main content area — using universal HTML structure, not keywords.

        Priority:
          1. <h1> → <h2> → <h3>  inside a semantic container
             (<main>, <article>, <div role="main">)
          2. Same search over entire <body> (minus boilerplate tags)
          3. First <strong> / <b> text that looks like a title
             (< 80 chars, doesn't end with ':' or '?')
        """
        try:
            soup = BeautifulSoup(html, "html.parser")
        except Exception:
            return None

        # Strip boilerplate tags so they never pollute the search
        for tag_name in _BOILERPLATE_TAGS:
            for tag in soup.find_all(tag_name):
                tag.decompose()

        # --- Step 1: Look for headings inside semantic containers ---
        content_root = (
            soup.find("main")
            or soup.find("article")
            or soup.find("div", attrs={"role": "main"})
        )

        search_areas = [content_root, soup.body] if content_root else [soup.body]

        for area in search_areas:
            if not area:
                continue
            for level in ["h1", "h2", "h3"]:
                heading = area.find(level)
                if heading:
                    text = heading.get_text(strip=True)
                    if text and len(text) < 150:
                        return text

        # --- Step 2: Fallback to first <strong> / <b> ---
        # Many poorly-built sites (e.g. Thapar faculty pages) render
        # the page identity as bold text rather than a heading tag.
        body = soup.body if soup.body else soup
        for bold_tag in body.find_all(["strong", "b"]):
            text = bold_tag.get_text(strip=True)
            if not text:
                continue
            # Sanity filters (source-agnostic):
            #  • Must be short enough to be a title, not a paragraph
            #  • Must not be a field label like "Email:" or "Specialization:"
            if len(text) < 80 and not text.endswith(":") and not text.endswith("?"):
                return text

        return None

    def _extract_url_slug(self, url: str) -> str:
        """Last-resort identity from the URL path."""
        path = urlparse(url).path
        if path in ["", "/"]:
            return "Webpage Content"
        slug = path.split("/")[-1].replace("-", " ").replace("_", " ")
        if len(slug) < 4 or slug.isdigit():
            return "Webpage Content"
        return slug.title()