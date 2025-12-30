# FILE: chatvat/utils/logger.py

import sys
from rich.console import Console
from rich.theme import Theme

# Setup Rich Theme (Standardizing our colors)
theme_map = {
    "info": "cyan",
    "warning": "yellow",
    "error": "bold red",
    "success": "bold green"
}

console = Console(theme=Theme(theme_map))

# Define Helper Functions (Used by main.py and builder.py)

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