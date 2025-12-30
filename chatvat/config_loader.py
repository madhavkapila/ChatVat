# FILE: chatvat/bot_template/src/config_loader.py

import json
import os
import logging
from typing import List, Optional, Literal, Dict
from pydantic import BaseModel
import re

logger = logging.getLogger(__name__)

CONFIG_PATH = os.getenv("CONFIG_PATH", "/app/config.json")

# --- Duplicate Schema Definitions ---
# We duplicate these here so the runtime is independent of the CLI code.
# This ensures the Docker image is self-contained.

class DataSource(BaseModel):
    type: Literal["static_url", "dynamic_json", "local_file"]
    target: str
    headers: Optional[Dict[str, str]] = {}

class RuntimeConfig(BaseModel):
    bot_name: str
    sources: List[DataSource]
    system_prompt: Optional[str] = None
    refresh_interval_minutes: int = 0  # Default 0 means "Never"

# --- Loader Logic ---

def _expand_env_vars(data: dict) -> dict:
    """
    Recursively replaces strings like '${VAR_NAME}' with the value from os.environ.
    """
    # Convert dict to string for global replacement
    json_str = json.dumps(data)
    
    # Regex to find ${VAR_NAME}
    pattern = re.compile(r'\$\{(\w+)\}')
    
    def replacer(match):
        var_name = match.group(1)
        # Get from ENV, or return empty string if missing (or keep original?)
        # Returning match.group(0) keeps it as ${VAR} if missing, which is safer for debugging
        return os.environ.get(var_name, match.group(0))
    
    new_json_str = pattern.sub(replacer, json_str)
    return json.loads(new_json_str)

def load_runtime_config() -> Optional[RuntimeConfig]:
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