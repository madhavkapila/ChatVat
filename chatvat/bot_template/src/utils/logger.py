# FILE: chatvat/bot_template/src/utils/logger.py

import logging
import sys

def setup_logging():
    """
    Configures the root logger for the Docker container.
    Format: [Time] [Level] [Module]: Message
    """
    # Create the format string
    log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Configure the root logger
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        datefmt=date_format,
        handlers=[
            # Output to stdout (Standard Output) so 'docker logs' catches it
            logging.StreamHandler(sys.stdout)
        ]
    )

    # Optional: Silence noisy libraries (like detailed HTTP logs from aiohttp/urllib3)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("chromadb").setLevel(logging.WARNING)

    return logging.getLogger("chatvat")