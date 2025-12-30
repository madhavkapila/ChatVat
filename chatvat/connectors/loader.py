# FILE: chatvat/bot_template/src/connectors/loader.py

import aiohttp
import asyncio
import logging
from typing import Dict, Any, List, Optional

# Standard Logger setup
logger = logging.getLogger(__name__)

class RuntimeJsonLoader:
    """
    Fetches JSON from APIs and flattens it for embedding.
    Supports Authentication Headers (e.g., Bearer Tokens).
    """

    async def fetch_json(self, url: str, headers: Optional[Dict[str, str]] = None) -> Optional[Any]:
        """
        Async HTTP GET with robust error handling and Auth support.
        """
        try:
            # We create a session for the request
            # disable_ssl=True helps with older corporate servers, but need to be careful in high-security contexts.
            async with aiohttp.ClientSession() as session:
                
                async with session.get(url, headers=headers, timeout=30) as response: # type: ignore
                    
                    if response.status == 200:
                        return await response.json()
                    elif response.status == 401 or response.status == 403:
                        logger.error(f"🔐 Auth Error ({response.status}) accessing {url}. Check your API Keys.")
                        return None
                    else:
                        logger.warning(f"API returned status {response.status} for {url}")
                        return None
                        
        except Exception as e:
            logger.error(f"Network error fetching {url}: {str(e)}")
            return None

    def flatten_data(self, data: Any, prefix: str = "") -> List[str]:
        """
        Recursively flattens nested JSON into 'Key: Value' strings.
        (Same logic as before, just included for completeness)
        """
        chunks = []
        
        if isinstance(data, dict):
            for key, value in data.items():
                new_prefix = f"{prefix} > {key}" if prefix else key
                chunks.extend(self.flatten_data(value, new_prefix))
        
        elif isinstance(data, list):
            for i, item in enumerate(data):
                chunks.extend(self.flatten_data(item, prefix))
        
        else:
            # Base Case: It's a value (int, string, bool)
            if data is not None and str(data).strip():
                clean_value = str(data).strip()
                chunks.append(f"{prefix}: {clean_value}")
        
        return chunks

    async def load_and_transform(self, url: str, headers: Optional[Dict[str, str]] = None) -> List[str]:
        """
        Main entry point. Fetches data (using optional Auth) and flattens it.
        """
        logger.info(f"Loading JSON API: {url}")
        
        # Pass the headers down to the fetcher
        raw_data = await self.fetch_json(url, headers=headers)
        
        if not raw_data:
            return []
        
        try:
            flat_chunks = self.flatten_data(raw_data)
            logger.info(f"Flattened API data into {len(flat_chunks)} text chunks.")
            return flat_chunks
        except Exception as e:
            logger.exception(f"Error flattening data from {url}")
            return []