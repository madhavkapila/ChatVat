# FILE: chatvat/bot_template/src/core/vector.py

import logging
import threading
from typing import List, Optional

import chromadb
from chromadb.config import Settings
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document


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
            # Setup Embedding Function (HuggingFace)
            self.embedding_fn = HuggingFaceEmbeddings(model_name=DEFAULT_EMBEDDING_MODEL)
            
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
                count_initial = len(documents)
                
                unique_map = {}
                for doc in documents:
                    # Generate ID based on content hash
                    doc_id = str(hash(doc.page_content))
                    
                    # Only keep the first occurrence of this ID
                    if doc_id not in unique_map:
                        unique_map[doc_id] = doc
                
                # Extract clean lists
                ids = list(unique_map.keys())
                clean_docs = list(unique_map.values())
                count_final = len(clean_docs)
                
                if count_initial != count_final:
                    logger.warning(f"⚠️ Dropped {count_initial - count_final} duplicate documents.")

                if clean_docs:
                    logger.info(f"🔒 Lock Acquired. Upserting {count_final} unique documents...")
                    self.vector_store.add_documents(documents=clean_docs, ids=ids)
                    logger.info(f"🔓 Upsert Complete. Lock Released.")
                else:
                    logger.warning("⚠️ No unique documents to upload.")
                    
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