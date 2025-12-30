# FILE: chatvat/constants.py

import os

# App Metadata
APP_NAME = "ChatVat"
APP_VERSION = "0.1.0"

# Default Model Configurations
DEFAULT_LLM_MODEL = "llama-3.1-70b-versatile"
DEFAULT_EMBEDDING_MODEL = "all-MiniLM-L6-v2"
COLLECTION_NAME = "chatvat_store"

# Paths
DEFAULT_CONFIG_FILENAME = "chatvat.config.json"
DB_PATH = "./data/chroma_db"

# Timeout settings (Resilience)
CRAWLER_TIMEOUT_SECONDS = 30
REQUEST_RETRIES = 3