# FILE: chatvat/bot_template/src/core/vector.py

import logging
import threading
from typing import List, Optional

import chromadb
from chromadb.config import Settings
from chatvat.config_loader import load_runtime_config
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document
import hashlib


from chatvat.constants import (
    DB_PATH,               
    COLLECTION_NAME,                                
    DEFAULT_EMBEDDING_MODEL                       
)

logger = logging.getLogger(__name__)

class VectorManager:
    """
    Singleton Wrapper for ChromaDB.
    Ensures thread safety between the Background Crawler and the API.
    """
    
    _instance = None
    _init_lock = threading.Lock() # Lock for creating the instance

    def __new__(cls):
        """
        Magic method to ensure only ONE instance of this class ever exists.
        """
        if cls._instance is None:
            with cls._init_lock:
                if cls._instance is None:
                    cls._instance = super(VectorManager, cls).__new__(cls)
                    cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """
        The Setup Logic for ChromaDB.
        """
        logger.info(f"🔌 Connecting to Vector DB at {DB_PATH}...")
        
        try:
            config = load_runtime_config()
            embed_name = config.embedding_model if config else DEFAULT_EMBEDDING_MODEL
            
            # Setup Embedding Function (HuggingFace)
            self.embedding_fn = HuggingFaceEmbeddings(model_name=embed_name)
            
            # Setup Persistent Client
            self.client = chromadb.PersistentClient(
                path=DB_PATH,
                settings=Settings(allow_reset=True, anonymized_telemetry=False)
            )
            
            # Create/Get Collection
            self.collection = self.client.get_or_create_collection(
                name=COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"} # Force Cosine Similarity
            )
            
            # LangChain Wrapper (For RAG)
            self.vector_store = Chroma(
                client=self.client,
                collection_name=COLLECTION_NAME,
                embedding_function=self.embedding_fn,
            )
            
            # The Write Lock (Crucial for Thread Safety)
            self.write_lock = threading.Lock()
            logger.info("✅ Vector DB Connected Successfully.")
            
        except Exception as e:
            logger.critical(f"❌ Failed to initialize Vector DB: {e}")
            raise

    def upsert_documents(self, documents: List[Document]):
        """
        Thread-safe write operation with DEDUPLICATION.
        """
        if not documents:
            return

        with self.write_lock:
            try:
                # count_initial = len(documents)
                
                unique_map = {}
                for doc in documents:
                    # Generate a STABLE ID based on content
                    doc_id = hashlib.md5(doc.page_content.encode()).hexdigest()
                    unique_map[doc_id] = doc
                
                # Extract clean lists
                ids = list(unique_map.keys())
                clean_docs = list(unique_map.values())
                # count_final = len(clean_docs)
                
                # Extract texts and metadatas for the raw Chroma upsert
                texts = [d.page_content for d in clean_docs]
                metadatas = [d.metadata for d in clean_docs]

                logger.info(f"🔒 Upserting {len(ids)} documents to Chroma...")
                self.collection.upsert(
                    ids=ids,
                    documents=texts,
                    metadatas=metadatas
                )
                logger.info("🔓 Upsert Complete.")
            except Exception as e:
                logger.error(f"Error during upsert: {e}")

    def as_retriever(self, k: int = 5):
        """
        Returns the LangChain retriever for the RAG Engine.
        """
        return self.vector_store.as_retriever(search_kwargs={"k": k})

# Helper function for easy access
def get_vector_db():
    return VectorManager()