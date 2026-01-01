# FILE: chatvat/bot_template/src/core/ingestor.py

import asyncio
import logging
import os
import json
from typing import List, Dict, Any

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from chatvat.connectors.crawler import RuntimeCrawler
from chatvat.connectors.loader import RuntimeJsonLoader
from chatvat.core.vector import get_vector_db
from chatvat.config_loader import load_runtime_config 
from langchain_community.document_loaders import PyPDFLoader, TextLoader

logger = logging.getLogger(__name__)

class IngestionEngine:
    """orchestrates data pipeline - config -> fetchers -> vectordb"""

    def __init__(self):
        self.crawler = RuntimeCrawler()
        self.loader = RuntimeJsonLoader()
        self.db = get_vector_db()

        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=100,
            add_start_index=True
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

    async def _process_static_url(self, target: str) -> List[Document]:
        """handles static/js websites"""
        markdown = await self.crawler.fetch_page(target)
        if markdown:
            # Create the raw giant document
            raw_doc = Document(page_content=markdown, metadata={"source": target, "type": "url"})
            # Split into chunks for better embedding
            chunks = self.splitter.split_documents([raw_doc])
            logger.info(f"🔪 Split {target} into {len(chunks)} chunks.")
            return chunks
            
        return []

    async def _process_dynamic_json(self, target: str, headers: Dict[str, Any] = None) -> List[Document]: #type: ignore
        """handles api endpoints with auth"""
        text_chunks = await self.loader.load_and_transform(target, headers=headers)
        
        documents = []
        for chunk in text_chunks:
            doc = Document(
                page_content=chunk, 
                metadata={"source": target, "type": "json"}
            )
            documents.append(doc)
        return documents
    
    async def _process_local_file(self, target: str) -> List[Document]:
        """handles local pdf/txt files"""
        if not os.path.exists(target):
            return []
        
        try:
            raw_docs = []
            if target.endswith(".pdf"):
                loader = PyPDFLoader(target)
                raw_docs = loader.load()
            else:
                loader = TextLoader(target, encoding="utf-8")
                raw_docs = loader.load()
            
            # --- Split Local Files too ---
            if raw_docs:
                chunks = self.splitter.split_documents(raw_docs)
                logger.info(f"🔪 Split file {target} into {len(chunks)} chunks.")
                return chunks
                
        except Exception as e:
            logger.error(f"Failed to load {target}: {e}")
            
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
                        new_docs = await self._process_static_url(source.target)
                    
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