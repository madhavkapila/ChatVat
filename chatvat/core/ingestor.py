# FILE: chatvat/bot_template/src/core/ingestor.py

import asyncio
import logging
import os
import json
from collections import Counter
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from chatvat.connectors.crawler import RuntimeCrawler
from chatvat.connectors.loader import RuntimeJsonLoader
from chatvat.core.vector import get_vector_db
from chatvat.config_loader import load_runtime_config 
from langchain_community.document_loaders import TextLoader
from chatvat.core.metadata import MetadataExtractor

logger = logging.getLogger(__name__)

class IngestionEngine:
    """orchestrates data pipeline - config -> fetchers -> vectordb"""

    def __init__(self):
        self.crawler = RuntimeCrawler()
        self.loader = RuntimeJsonLoader()
        self.db = get_vector_db()
        self.metadata_extractor = MetadataExtractor()

        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            add_start_index=True,
            separators=["\n\n", "\n", " ", ""] # Standard hierarchy
        )

    def _resolve_headers(self, headers: Dict[str, Any]) -> Dict[str, str]:
        """resolves environment variables in headers"""
        resolved = {}
        for k, v in headers.items():
            if isinstance(v, str):
                resolved[k] = os.path.expandvars(v)
            else:
                resolved[k] = v
        return resolved
    
    def _stamp_chunks(self, chunks: List[Document], subject: str, source_type: str) -> List[Document]:
        """
        The Universal Stamper.
        Injects the 'Subject' (Page Title, Filename, or API Name) 
        at the top of every chunk to fix 'Lost in the Middle' problems.
        """
        stamped_chunks = []
        for chunk in chunks:
            # We standardize the header format for the LLM
            # Using Markdown H1 (#) tells the LLM "This is the main topic"
            stamp = f"# Context: {subject}\n"
            
            # Additional metadata for clarity (optional, but helpful)
            if source_type == "csv":
                stamp += f"Type: Tabular Data (Row)\n\n"
            elif source_type == "json":
                stamp += f"Type: API Response\n\n"
            else:
                stamp += "\n"

            # Prepend only if not already present (idempotency)
            if not chunk.page_content.startswith(f"# Context: {subject}"):
                chunk.page_content = f"{stamp}{chunk.page_content}"
            
            # Ensure metadata is synced
            chunk.metadata["subject"] = subject
            
            stamped_chunks.append(chunk)
        return stamped_chunks
    
    async def _process_static_url(self, source_config) -> List[Document]:
        """
        Handles static/JS websites with Visual Dominance identity resolution.

        Two-pass processing:
          Pass 1 — Extract identity signals from every crawled page.
          Frequency Analysis — Detect site-wide generic meta titles.
          Pass 2 — Resolve each page's true identity, split, and stamp chunks.

        This is source-agnostic: uses universal HTML structure (headings,
        semantic containers, cross-page frequency) — no keyword blacklists.
        """
        target = source_config.target
        max_depth = getattr(source_config, "max_depth", 1)
        scope = getattr(source_config, "recursion_scope", "restrictive")

        # Crawl (returns markdown + raw HTML per page)
        crawled_pages = await self.crawler.crawl_recursive(target, max_depth, scope)
        if not crawled_pages:
            return []

        # ── Pass 1: Signal Extraction ───────────────────────────────
        page_signals = []          # [(page_data, signals_dict), ...]
        title_counter = Counter()  # meta_title → count across pages

        for i, page_data in enumerate(crawled_pages):
            raw_html = page_data.get('html', '')       # Raw HTML for meta title extraction
            url  = page_data.get("url", "")
            signals = self.metadata_extractor.extract_signals(raw_html, url)
            page_signals.append((page_data, signals))

            if signals["meta_title"]:
                    title_counter[signals["meta_title"]] += 1

        # ── Frequency Analysis ──────────────────────────────────────
        # A meta title is "site-wide noise" if it appears on MORE THAN
        # ONE page AND on ≥30% of all crawled pages.
        # This is a purely structural check — no hardcoded keywords.
        total_pages = len(crawled_pages)
        sitewide_titles: set = set()

        for title, count in title_counter.items():
            if count > 1 and (count / total_pages) >= 0.30:
                sitewide_titles.add(title)
                logger.info(
                    f"📊 Site-wide title detected: '{title}' "
                    f"(appears on {count}/{total_pages} pages — "
                    f"{count * 100 // total_pages}%%)"
                )

        # ── Pass 2: Identity Resolution + Chunking ──────────────────
        all_chunks = []

        for i, (page_data, signals) in enumerate(page_signals):
            meta_title = (signals.get("meta_title") or "").strip()
            is_sitewide = meta_title in sitewide_titles

            # Resolve the true page identity
            page_subject = self.metadata_extractor.resolve_subject(
                signals, title_is_sitewide=is_sitewide
            )

            # Logging: show which signal won and why
            if is_sitewide and signals.get("visual_header"):
                logger.info(
                    f"🏷️  Visual Override: '{page_subject}' "
                    f"(meta title '{meta_title}' is site-wide) "
                    f"URL: {page_data.get('url', '')}"
                )
            else:
                logger.info(
                    f"🏷️  Trusted Title: '{page_subject}' "
                    f"URL: {page_data.get('url', '')}"
                )

            # Build the raw Document
            raw_doc = Document(
                page_content=page_data["content"],
                metadata={
                    "source": page_data["url"],
                    "type": "url_graph",
                    "subject": page_subject,
                    "depth_index": i,
                },
            )

            # Split into chunks
            initial_chunks = self.splitter.split_documents([raw_doc])

            # Stamp every chunk with the resolved identity
            for chunk in initial_chunks:
                stamp = f"# Context: {page_subject}\n\n"
                if not chunk.page_content.startswith(stamp):
                    chunk.page_content = f"{stamp}{chunk.page_content}"
                all_chunks.append(chunk)

        logger.info(
            f"🔪 Processed {len(crawled_pages)} pages into "
            f"{len(all_chunks)} chunks."
        )
        return all_chunks

    async def _process_dynamic_json(self, target: str, headers: Dict[str, Any] = None) -> List[Document]: #type: ignore
        """handles api endpoints with auth"""
        text_chunks = await self.loader.load_and_transform(target, headers=headers)

        # Determine Subject from URL (e.g., https://api.com/users -> Users)
        path = urlparse(target).path
        subject_name = path.split('/')[-1] if path else "API Response"
        if not subject_name: subject_name = "API Root"
        subject_name = subject_name.replace('_', ' ').title()
        
        documents = []
        for chunk in text_chunks:
            doc = Document(
                page_content=chunk, 
                metadata={"source": target, "type": "json"}
            )
            documents.append(doc)

        # Stamp JSON chunks
        return self._stamp_chunks(documents, subject_name, "json")
    
    ### Separate file methods for better error handling and future extensibility (e.g. add .docx support later) ###
    
    def _load_pdf(self, file_path: str) -> List[Document]:
        """
        Converts PDF to Markdown using PyMuPDF4LLM.
        This preserves layout, tables, and headers for the LLM.
        """
        try:
            import pymupdf4llm
        except ImportError:
            logger.error("pymupdf4llm is missing. Cannot process PDF.")
            return []
        
        logger.info(f"📄 Converting PDF to Markdown (SOTA): {file_path}")

        # Convert entire PDF to a single Markdown string.
        # This ensures tables spanning pages aren't broken awkwardly.
        md_text = pymupdf4llm.to_markdown(file_path)

        # Create a Document object
        return [Document(
            page_content=md_text,
            metadata={"source": file_path, "type": "pdf_markdown"}
        )]
    
    def _load_csv_rows(self, file_path: str) -> List[Document]:
        """
        Generic CSV Handler.
        Reads the header row of ANY csv and formats each row as:
        'Header1: Value1\nHeader2: Value2...'
        """
        try:
            from langchain_community.document_loaders import CSVLoader
        except ImportError:
            logger.error("langchain_community is missing. Cannot process CSV.")
            return []

        logger.info(f"📊 Loading CSV rows as documents: {file_path}")
        
        try:
            # Loader automatically creates "Key: Value" strings for each row
            loader = CSVLoader(file_path=file_path)
            docs = loader.load()
            
            logger.info(f"   - Extracted {len(docs)} rows from CSV.")
            return docs
            
        except Exception as e:
            logger.error(f"Error parsing CSV {file_path}: {e}")
            return []
    
    def _load_plain_text(self, file_path: str) -> List[Document]:
        """Fallback for .txt or .md files"""
        loader = TextLoader(file_path, encoding="utf-8")
        return loader.load()
    

    async def _process_local_file(self, target: str) -> List[Document]:
        """
        The Dispatcher: Identifies file type and delegates to the specialist.
        """
        if not os.path.exists(target):
            logger.warning(f"File not found: {target}")
            return []
        
        # Identify Subject (Filename)
        # e.g. "Archive/Data/Salary_Report_2024.pdf" -> "Salary Report 2024"
        filename = os.path.basename(target)
        subject_name = os.path.splitext(filename)[0].replace('_', ' ').replace('-', ' ').title()
        
        # Identify File Extension
        ext = os.path.splitext(target)[1].lower()
        raw_docs = []

        try:
            # Dispatch to Handler
            if ext == ".pdf":
                raw_docs = self._load_pdf(target)
            
            elif ext == ".csv":
                raw_docs = self._load_csv_rows(target)
            
            elif ext in [".txt", ".md"]:
                raw_docs = self._load_plain_text(target)
            
            else:
                logger.warning(f"Unsupported file type '{ext}' for {target}")
                return []

            # Split (If needed) & Stamp with Subject
            # Note: CSV rows are usually small enough, but we split anyway to be safe.
            if raw_docs:
                chunks = self.splitter.split_documents(raw_docs)
                # Apply Universal Stamping
                final_chunks = self._stamp_chunks(chunks, subject_name, ext.replace('.', ''))
                logger.info(f"🔪 Processed {target} into {len(final_chunks)} searchable chunks.")
                return final_chunks

        except Exception as e:
            logger.error(f"❌ Failed to process file {target}: {e}")
        
        return []

    async def run_pipeline(self):
        """
        The Main Loop: Loads config, fetches all data, and updates the DB.
        """
        logger.info("🚀 Starting Ingestion Pipeline...")
        
        try:
            # 1. Load Configuration
            config = load_runtime_config()
            if not config or not config.sources:
                logger.warning("No sources defined in config. Skipping ingestion.")
                return

            all_docs = []

            # 2. Process Sources Sequentially
            # We iterate through the list of sources defined in config.json
            for source in config.sources:
                logger.info(f"Processing source: {source.target} ({source.type})")
                
                new_docs = []
                try:
                    if source.type == 'static_url':
                        # PASS THE WHOLE SOURCE OBJECT, NOT JUST TARGET
                        new_docs = await self._process_static_url(source)
                    
                    elif source.type == 'dynamic_json':
                        # Extract optional headers (Auth Keys) if they exist
                        raw_headers = getattr(source, 'headers', {})
                        # Resolve env vars (e.g. ${API_KEY})
                        headers = self._resolve_headers(raw_headers)
                        new_docs = await self._process_dynamic_json(source.target, headers)

                    elif source.type == 'local_file':
                        new_docs = await self._process_local_file(source.target)
                    
                    if new_docs:
                        all_docs.extend(new_docs)
                        
                except Exception as e:
                    logger.error(f"❌ Error processing {source.target}: {e}")
                    # continue to next source, dont stop the whole bot

            # 3. Batch Upsert to Database
            if all_docs:
                logger.info(f"💾 Upserting {len(all_docs)} documents to Vector DB...")
                # The lock is handled inside this method
                self.db.upsert_documents(all_docs)
                logger.info("✅ Ingestion Complete.")
            else:
                logger.info("Total documents fetched: 0. Database unchanged.")

        except Exception as e:
            logger.exception("CRITICAL: Ingestion Pipeline Failed")

# Helper to run the pipeline manually (e.g., from startup script)
async def run_ingestion():
    engine = IngestionEngine()
    await engine.run_pipeline()