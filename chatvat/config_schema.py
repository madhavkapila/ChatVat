# FILE: chatvat/config_schema.py

import os
from typing import List, Optional, Literal, Dict
from pydantic import BaseModel, Field, field_validator

SourceType = Literal["static_url", "dynamic_json", "local_file"]

class DataSource(BaseModel):
    """a single knowledge source - url, api or file"""
    type: SourceType
    target: str = Field(..., description="URL or File Path")
    headers: Optional[Dict[str, str]] = Field(default_factory=dict, description="Auth headers for APIs")

    @field_validator('target')
    @classmethod
    def validate_target(cls, v: str, info):
        # We need to check the 'type' to know how to validate the 'target'
        values = info.data
        source_type = values.get('type')

        if source_type in ['static_url', 'dynamic_json']:
            if not (v.startswith("http://") or v.startswith("https://")):
                raise ValueError(f"Target '{v}' must be a valid URL starting with http/https")
        
        elif source_type == 'local_file':
            if not os.path.exists(v):
                raise ValueError(f"Local file not found: {v}")
        
        return v

class ProjectConfig(BaseModel):
    """
    The Master Blueprint.
    This is what gets saved to 'chatvat.config.json' on the user's machine.
    """
    bot_name: str = Field(..., min_length=1)
    
    # The list of knowledge sources
    sources: List[DataSource] = Field(default_factory=list)
    
    # Custom Persona (System Prompt)
    system_prompt: Optional[str] = None
    
    # Auto-Update Frequency (in minutes). 0 = Disabled.
    refresh_interval_minutes: int = Field(default=0, ge=0)

    # Deployment Port (Default 8000, but user can change it)
    port: int = Field(default=8000, ge=1024, le=65535)

    # Model Choices
    llm_model: str = Field(default="llama-3.3-70b-versatile")
    # Choice for embedding model which would be used to generate embeddings
    embedding_model: str = Field(default="all-MiniLM-L6-v2")