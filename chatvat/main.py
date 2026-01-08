# FILE: chatvat/main.py

import typer
import pyfiglet
import json
import requests
import os
import re
import sys
from typing import List, Dict, Optional
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.align import Align
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.table import Table

from chatvat.config_schema import ProjectConfig, DataSource
from chatvat.constants import DEFAULT_EMBEDDING_MODEL, DEFAULT_LLM_MODEL
from chatvat.utils.logger import log_info, log_error, log_success, log_warning
from chatvat.builder import build_bot

app = typer.Typer(
    name="ChatVat",
    help="🤖 Build production-ready RAG Chatbots.",
    add_completion=False
)
console = Console()

def safe_append_to_env(key: str, value: str):
    """
    Safely adds or updates key in .env file.
    - If value is EMPTY and key exists -> Keeps existing value (No overwrite).
    - If value is EMPTY and key missing -> Sets key="".
    - If value is PROVIDED -> Overwrites/Sets new value.
    """
    value = value.strip()
    env_line = f"{key}={value}\n"
    
    # Create file if missing
    if not os.path.exists(".env"):
        with open(".env", "w") as f:
            # If empty value provided for new file, write it as empty string
            f.write(f"# ChatVat Secrets\n{env_line}")
        return

    with open(".env", "r") as f:
        content = f.read()
    
    if key in content:
        # Key Exists
        if not value:
            # User gave empty input -> Preserve old value
            log_info(f"Using existing value for {key}")
            return
        else:
            # User gave new value -> Overwrite
            content = re.sub(f"^{key}=.*", f"{key}={value}", content, flags=re.MULTILINE)
            with open(".env", "w") as f:
                f.write(content)
            log_success(f"Updated {key}")
    else:
        # Key Missing -> Append whatever we have (even if empty)
        with open(".env", "a") as f:
            f.write(env_line)
        log_success(f"Set {key}")

def resolve_env_var(value: str) -> str:
    """resolves ${VAR} from .env for connection testing"""
    if value.startswith("${") and value.endswith("}"):
        var_name = value[2:-1]
        if var_name in os.environ:
            return os.environ[var_name]
        
        if os.path.exists(".env"):
            with open(".env", "r") as f:
                for line in f:
                    if line.startswith(f"{var_name}="):
                        return line.split("=", 1)[1].strip()
    return value

# --- CONNECTION TESTER ---

def test_connection(url: str, headers: Dict = None) -> bool: ##type: ignore
    """pings url to check if its accessible"""
    real_headers = {}
    if headers:
        for k, v in headers.items():
            real_headers[k] = resolve_env_var(v)

    with console.status(f"[bold cyan]Testing connection to {url}...[/bold cyan]", spinner="line"):
        try:
            # Verify=False to allow older SSL certs during dev
            response = requests.get(url, headers=real_headers, timeout=5, verify=False)
            
            if response.status_code == 200:
                console.print(f"  ✅ [green]Connected successfully! (200 OK)[/green]")
                return True
            elif response.status_code in [401, 403]:
                console.print(f"  🔒 [yellow]Auth Error ({response.status_code}). Check your keys.[/yellow]")
                return False
            else:
                console.print(f"  ❌ [red]Status: {response.status_code}[/red]")
                return False
        except Exception as e:
            console.print(f"  ❌ [red]Connection Error: {e}[/red]")
            return False

def ask_for_sources() -> List[DataSource]:
    """interactive loop for adding data sources"""
    sources = []
    while True:
        console.print("\n[bold]Add a Knowledge Source[/bold]")
        
        console.print("Types: [green]static_url[/green] (Website), [green]dynamic_json[/green] (API), [green]local_file[/green] (PDF/TXT)")
        source_type = Prompt.ask("Select Type", choices=["static_url", "dynamic_json", "local_file"], default="static_url")
        
        target = Prompt.ask("Enter Target (URL or File Path)")
        headers = {}
        
        should_add = True
        
        if source_type in ["static_url", "dynamic_json"]:
            if not target.startswith("http"):
                log_warning("URL should start with http:// or https://")
            
            success = test_connection(target)
            
            if not success:
                # Offer to fix Auth
                if Confirm.ask("⚠️  Connection failed. Do you need Auth Headers?"):
                    while True:
                        console.print("[dim]Tip: Use hyphens for headers (e.g. 'x-api-key')[/dim]")
                        key = Prompt.ask("Header Name")
                        raw_value = Prompt.ask("Header Value (Leave empty to keep existing if reusing key)", default="")
                        
                        if Confirm.ask("Is this a secret?", default=True):
                            # Default env var name: X-API-KEY -> X_API_KEY
                            default_var_name = key.upper().replace("-", "_")
                            var_name = Prompt.ask("Env Var Name", default=default_var_name)
                            
                            # Using SAFE append to handle updates/fallbacks
                            safe_append_to_env(var_name, raw_value)
                            
                            final_value = f"${{{var_name}}}"
                        else:
                            final_value = raw_value

                        headers[key] = final_value
                        if not Confirm.ask("Add another header?", default=False):
                            break
                    
                    # Retest
                    success = test_connection(target, headers=headers)

                if not success:
                    console.print("[yellow]⚠️  Source is still unreachable.[/yellow]")
                    if not Confirm.ask("Force add this source anyway? (e.g. maybe it works inside the container)", default=True):
                        should_add = False

        # File Logic
        elif source_type == "local_file":
            if not os.path.exists(target):
                log_error(f"File not found: {target}")
                if not Confirm.ask("File missing. Add anyway? (You must provide it later)", default=False):
                    should_add = False
            else:
                log_success("File verified.")

        if should_add:
            source_obj = DataSource(type=source_type, target=target, headers=headers)# type: ignore
            sources.append(source_obj)
            log_success(f"Added source: {target}")
        else:
            console.print("[dim]Skipped adding source.[/dim]")

        # Summary Table
        if sources:
            table = Table(title="Sources Configured", show_header=True)
            table.add_column("Type")
            table.add_column("Target")
            table.add_column("Auth Headers")
            for s in sources:
                table.add_row(s.type, s.target, str(s.headers))
            console.print(table)

        if not Confirm.ask("Add another source?", default=False):
            break
    
    return sources

def print_banner():
    console.clear()
    try:
        ascii_art = pyfiglet.figlet_format("ChatVat", font="slant")
        
        styled_text = Text()
        lines = ascii_art.split("\n")
        
        # Color Map: Top lines = Magenta, Middle = Cyan, Bottom = Green
        for i, line in enumerate(lines):
            if i < len(lines) // 3:
                style = "bold magenta"
            elif i < 2 * len(lines) // 3:
                style = "bold cyan"
            else:
                style = "bold spring_green1"
            
            styled_text.append(line + "\n", style=style)

    except Exception:
        styled_text = Text("ChatVat", style="bold cyan")

    console.print(Panel(
        Align.center(styled_text),
        border_style="bright_blue",
        title="[bold white]The ChatBot Factory[/bold white]",
        subtitle="[dim]v1.0.0[/dim]",
        padding=(1, 2)
    ))

# --- CLI COMMANDS ---

@app.command()
def init():
    """🧙 Run the Configuration Wizard"""
    console.print(Panel.fit("🧙 Configuration Wizard", style="bold green"))
    
    # 1. Global Secrets
    groq_key = Prompt.ask("Enter GROQ_API_KEY (Leave empty to keep existing)", password=True, default="")
    # Using SAFE append to handle updates/fallbacks
    safe_append_to_env("GROQ_API_KEY", groq_key)

    # 2. Project Config
    bot_name = Prompt.ask("🤖 Name your Bot", default="MyAssistant")
    system_prompt = Prompt.ask("🧠 System Persona", default="You are a helpful assistant.")
    
    # 3. Sources
    sources = ask_for_sources()
    
    # 4. Settings
    refresh_minutes = IntPrompt.ask("🔄 Auto-Update Interval (Minutes) [0=Disabled]", default=0)
    port = IntPrompt.ask("🌐 Deployment Port", default=8000)

    # 5. AI Configuration
    console.print("\n[bold]🧠 AI Model Configuration[/bold]")
    llm_model = Prompt.ask("Select Groq Model", default=DEFAULT_LLM_MODEL)
    embed_model = Prompt.ask("Select Embedding Model (HuggingFace)", default=DEFAULT_EMBEDDING_MODEL)
    
    try:
        config = ProjectConfig(
            bot_name=bot_name, sources=sources, system_prompt=system_prompt,
            refresh_interval_minutes=refresh_minutes, port=port,
            llm_model=llm_model, embedding_model=embed_model
        )
        with open("chatvat.config.json", "w") as f:
            f.write(config.model_dump_json(indent=4))
        log_success("✅ Configuration saved to 'chatvat.config.json'")
    except Exception as e:
        log_error(f"Save failed: {e}")

@app.command()
def build():
    """🏗️ Build the Docker Image"""
    if build_bot:
        build_bot()
    else:
        log_error("Builder module not found! Internal Error.")

@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """main menu loop"""
    if ctx.invoked_subcommand is None:
        while True:
            print_banner()
            
            has_config = os.path.exists("chatvat.config.json")
            default_choice = "build" if has_config else "init"

            console.print("[bold]Main Menu[/bold]")
            console.print("1. [cyan]init[/cyan]   - Create/Edit Configuration")
            console.print("2. [cyan]build[/cyan]  - Compile Docker Image")
            console.print("3. [red]exit[/red]   - Quit")
            
            choice = Prompt.ask(
                "\nSelect an option",
                choices=["init", "build", "exit"],
                default=default_choice
            )
            
            if choice == "init":
                init()
                if not Confirm.ask("\nGo back to menu?", default=True):
                    break

            elif choice == "build":
                if not has_config:
                    log_error("No configuration found. Run 'init' first.")
                    Prompt.ask("Press Enter to continue...")
                else:
                    build()
                    if not Confirm.ask("\nBuild finished. Back to menu?", default=True):
                        break

            elif choice == "exit":
                console.print("Goodbye! 👋")
                sys.exit(0)

if __name__ == "__main__":
    app()