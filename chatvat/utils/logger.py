import sys
import logging
from rich.console import Console
from rich.theme import Theme

# colors for cli output
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
    """Prints a warning message in Yellow."""
    console.print(f"⚠️  {message}", style="warning")

def log_error(message: str, fatal: bool = False):
    """ Prints an error message in Red.
        if fatal=True it exits the whole cli"""
    console.print(f"❌ {message}", style="error")
    if fatal:
        sys.exit(1)

def setup_runtime_logging(name: str = "chatvat"):
    """setup logging for docker container"""
    log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

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