# FILE: chatvat/constants.py

import os

# app info
APP_NAME = "ChatVat"
APP_VERSION = "0.1.0"

# model defaults
DEFAULT_LLM_MODEL = "llama-3.3-70b-versatile"
DEFAULT_EMBEDDING_MODEL = "all-MiniLM-L6-v2"
COLLECTION_NAME = "chatvat_store"

# paths
DEFAULT_CONFIG_FILENAME = "chatvat.config.json"
DB_PATH = "./data/chroma_db"

# timeouts
CRAWLER_TIMEOUT_SECONDS = 30
REQUEST_RETRIES = 3