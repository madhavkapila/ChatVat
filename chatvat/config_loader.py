# FILE: chatvat/config_loader.py

import json
import os
import logging
from typing import List, Optional, Literal, Dict
from pydantic import BaseModel, Field
import re

from chatvat.constants import DEFAULT_LLM_MODEL, DEFAULT_EMBEDDING_MODEL

logger = logging.getLogger(__name__)

# In Docker, WORKDIR is /app, so this resolves to /app/chatvat.config.json
# On Local Dev, this resolves to the user's project folder.
CONFIG_FILENAME = "chatvat.config.json"
CONFIG_PATH = os.path.join(os.getcwd(), CONFIG_FILENAME)

# duplicate schemas here so runtime doesnt need cli deps
class DataSource(BaseModel):
    type: Literal["static_url", "dynamic_json", "local_file"]
    target: str
    headers: Optional[Dict[str, str]] = {}

class RuntimeConfig(BaseModel):
    bot_name: str
    sources: List[DataSource] = Field(default_factory=list)
    system_prompt: Optional[str] = None
    refresh_interval_minutes: int = 0
    port: int = 8000
    llm_model: str = DEFAULT_LLM_MODEL
    embedding_model: str = DEFAULT_EMBEDDING_MODEL

# --- Loader Logic ---

def _expand_env_vars(data: dict) -> dict:
    """replaces ${VAR_NAME} with actual env value"""
    json_str = json.dumps(data)
    
    pattern = re.compile(r'\$\{(\w+)\}')
    
    def replacer(match):
        var_name = match.group(1)
        return os.environ.get(var_name, match.group(0))  # keep original if not found
    
    new_json_str = pattern.sub(replacer, json_str)
    return json.loads(new_json_str)

def load_runtime_config() -> Optional[RuntimeConfig]:
    """loads config from current working dir"""
    # Debug print to confirm where it is looking (Visible in Docker Logs)
    logger.info(f"🔍 Loading config from: {CONFIG_PATH}")
    
    if not os.path.exists(CONFIG_PATH):
        logger.error(f"Config file missing at {CONFIG_PATH}")
        return None

    try:
        with open(CONFIG_PATH, 'r') as f:
            data = json.load(f)
        return RuntimeConfig(**data)
    except Exception as e:
        logger.error(f"Failed to parse runtime config: {e}")
        return None