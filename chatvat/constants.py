# FILE: chatvat/constants.py

import os

# app info
APP_NAME = "ChatVat"
APP_VERSION = "0.2.5"

# model defaults
DEFAULT_LLM_MODEL = "llama-3.3-70b-versatile"
DEFAULT_EMBEDDING_MODEL = "all-MiniLM-L6-v2"
DEFAULT_RETRIEVER_K = 5  # Number of top relevant chunks to fetch from vector DB
MAX_TOKENS = 400  # Max tokens for LLM response
COLLECTION_NAME = "chatvat_store"

# paths
DEFAULT_CONFIG_FILENAME = "chatvat.config.json"
DB_PATH = "./data/chroma_db"

# timeouts
CRAWLER_TIMEOUT_SECONDS = 30
REQUEST_RETRIES = 3