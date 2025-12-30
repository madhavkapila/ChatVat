# FILE: chatvat/bot_template/src/core/ingestor.py

import asyncio
import logging
from typing import List, Dict, Any

# LangChain imports
from langchain_core.documents import Document

# Local Imports
from chatvat.bot_template.src.connectors.crawler import RuntimeCrawler
from chatvat.bot_template.src.connectors.loader import RuntimeJsonLoader
from chatvat.bot_template.src.core.vector import get_vector_db
from chatvat.bot_template.src.config_loader import load_runtime_config 

logger = logging.getLogger(__name__)

class IngestionEngine:
    """
    Orchestrates the data pipeline.
    Connects the Config -> Fetchers -> VectorDB.
    """

    def __init__(self):
        # Initialize tools once (reuse connections)
        self.crawler = RuntimeCrawler()
        self.loader = RuntimeJsonLoader()
        self.db = get_vector_db()

    async def _process_static_url(self, target: str) -> List[Document]:
        """Strategy for Static/JS Websites"""
        markdown = await self.crawler.fetch_page(target)
        if markdown:
            # Metadata is crucial for the chatbot to cite its sources later
            return [Document(page_content=markdown, metadata={"source": target, "type": "url"})]
        return []

    async def _process_dynamic_json(self, target: str, headers: Dict[str, Any] = None) -> List[Document]:
        """Strategy for API Endpoints (with Auth)"""
        # Call the loader with headers
        text_chunks = await self.loader.load_and_transform(target, headers=headers)
        
        documents = []
        for chunk in text_chunks:
            # Create a separate document for every chunk so retrieval is granular
            doc = Document(
                page_content=chunk, 
                metadata={"source": target, "type": "json"}
            )
            documents.append(doc)
        return documents

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
                        # We use getattr in case the field is missing in older configs
                        headers = getattr(source, 'headers', {})
                        new_docs = await self._process_dynamic_json(source.target, headers)
                    
                    if new_docs:
                        all_docs.extend(new_docs)
                        
                except Exception as e:
                    logger.error(f"❌ Error processing {source.target}: {e}")
                    # Continue to next source! Don't stop the whole bot.

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