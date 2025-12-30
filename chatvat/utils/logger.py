import sys
import logging
from rich.console import Console
from rich.theme import Theme

# =========================================================
# EXISTING CLI LOGGING (Unchanged - Your Tools use this)
# =========================================================

# Setup Rich Theme (Standardizing our colors)
theme_map = {
    "info": "cyan",
    "warning": "yellow",
    "error": "bold red",
    "success": "bold green"
}

console = Console(theme=Theme(theme_map))

def log_info(message: str):
    """Prints an info message in Cyan."""
    console.print(f"ℹ️  {message}", style="info")

def log_success(message: str):
    """Prints a success message in Green."""
    console.print(f"✅ {message}", style="success")

def log_warning(message: str):
    """Prints a warning in Yellow."""
    console.print(f"⚠️  {message}", style="warning")

def log_error(message: str, fatal: bool = False):
    """
    Prints an error in Red. 
    If fatal=True, it exits the CLI.
    """
    console.print(f"❌ {message}", style="error")
    if fatal:
        sys.exit(1)

def setup_runtime_logging(name: str = "chatvat"):
    """
    Configures standard python logging for the Docker container.
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
            logging.StreamHandler(sys.stdout)
        ]
    )

    # Silence noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("chromadb").setLevel(logging.WARNING)

    return logging.getLogger(name)