# FILE: chatvat/constants.py

import os
from importlib import metadata

# app info
APP_NAME = "ChatVat"
try:
    # Dynamically grabs the version from Poetry/PyPI metadata!
    APP_VERSION = metadata.version("chatvat")
except metadata.PackageNotFoundError:
    # Fallback just in case you are running it raw locally without installing
    APP_VERSION = "dev"

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