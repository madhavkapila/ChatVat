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
from langchain_community.document_loaders import TextLoader

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

            # Split (If needed)
            # Note: CSV rows are usually small enough, but we split anyway to be safe.
            if raw_docs:
                chunks = self.splitter.split_documents(raw_docs)
                logger.info(f"🔪 Processed {target} into {len(chunks)} searchable chunks.")
                return chunks

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