# FILE: chatvat/builder.py

import os
import shutil
import subprocess
import json
import sys
from chatvat.utils.logger import log_info, log_error, log_success, log_warning
from rich.prompt import Confirm

def clean_dist_folder(dist_path: str):
    """
    Removes the 'dist/' folder to ensure a fresh build context.
    """
    if os.path.exists(dist_path):
        try:
            shutil.rmtree(dist_path)
        except Exception as e:
            log_error(f"Could not clean 'dist' folder: {e}", fatal=True)
    os.makedirs(dist_path)

def copy_template_files(src_dir: str, dist_dir: str):
    """
    Copies the bot logic from the template to the build folder.
    Excludes python cache and git files to keep the build clean.
    """
    try:
        shutil.copytree(
            src_dir, 
            dist_dir, 
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.DS_Store', '.git')
        )
    except Exception as e:
        log_error(f"Failed to copy template files: {e}", fatal=True)

def inject_config(dist_dir: str):
    """
    Copies the user's 'chatvat.config.json' into the build context.
    """
    config_src = "chatvat.config.json"
    if not os.path.exists(config_src):
        log_error("Config file not found. Please run 'init' first.", fatal=True)
    
    # Destination: dist/config.json (Root of the container app)
    try:
        shutil.copy(config_src, os.path.join(dist_dir, "config.json"))
    except Exception as e:
        log_error(f"Failed to inject config: {e}", fatal=True)

def run_docker_build(bot_name: str, dist_path: str) -> bool:
    """
    Attempts to run 'docker build'.
    Returns True if successful, False if Docker is missing/failed (Soft Fail).
    """
    # Sanitize bot name for Docker tag (lowercase, no spaces)
    tag_name = bot_name.lower().replace(" ", "-")
    
    log_info(f"🐳 Attempting Docker Build for '{tag_name}'...")
    
    # Check if Docker is installed/running
    try:
        subprocess.run(
            ["docker", "--version"], 
            check=True, 
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.DEVNULL
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        log_warning("Docker is not installed or not in your PATH.")
        return False

    # Run the actual build
    try:
        cmd = ["docker", "build", "-t", tag_name, "."]
        # We allow stdout to pass through so the user sees the build steps
        result = subprocess.run(cmd, cwd=dist_path, check=True)
        return True
    
    except subprocess.CalledProcessError:
        # --- MODIFIED: Smart Retry Logic ---
        log_warning("Standard build failed. This often happens if Docker needs root permissions.")
        
        # Ask user for permission to try sudo
        if Confirm.ask("🔄 Do you want to try running with [bold red]sudo[/bold red]?", default=True):
            try:
                log_info("🔒 Requesting sudo access...")
                sudo_cmd = ["sudo"] + cmd
                subprocess.run(sudo_cmd, cwd=dist_path, check=True)
                return True
            except subprocess.CalledProcessError:
                log_error("❌ Sudo build also failed (Check output above).")
                return False
            except Exception as e:
                log_error(f"Sudo error: {e}")
                return False
        else:
            log_error("Docker build returned an error code.")
            return False
            
    except Exception as e:
        log_error(f"Unexpected error during build: {e}")
        return False

def build_bot():
    """
    Main entry point. 
    1. Generates Code.
    2. Builds Docker Image.
    3. Cleans up Code (if successful) to maintain abstraction.
    """
    # Setup Paths (Factory Mode)
    factory_dir = os.path.dirname(os.path.abspath(__file__))
    template_dir = os.path.join(factory_dir, "bot_template")
    
    user_project_dir = os.getcwd()
    dist_dir = os.path.join(user_project_dir, "dist")

    if not os.path.exists(template_dir):
        log_error(f"Corruption Error: Library template missing at {template_dir}", fatal=True)

    # Generate Intermediate Code
    log_info("📂 Preparing assembly line...")
    clean_dist_folder(dist_dir)
    copy_template_files(template_dir, dist_dir)
    inject_config(dist_dir)

    # 3. Get Bot Name
    try:
        config_path = os.path.join(user_project_dir, "chatvat.config.json")
        with open(config_path) as f:
            config = json.load(f)
            bot_name = config.get("bot_name", "chatvat-bot")
            port = config.get("port", 8000)
    except Exception:
        bot_name = "chatvat-bot"
        port = 8000

    # 4. Attempt Docker Build
    tag = bot_name.lower().replace(" ", "-")
    docker_success = run_docker_build(bot_name, dist_dir)

    if docker_success:
        log_success(f"🎉 Build Complete! Image '{tag}' is ready.")
        
        # --- ABSTRACTION ENFORCEMENT ---
        log_info("🧹 Cleaning up intermediate files...")
        try:
            shutil.rmtree(dist_dir)
            log_success("Assembly line cleared.")
        except Exception as e:
            log_warning(f"Could not delete 'dist' folder: {e}")
        # -------------------------------

        print("\n" + "="*60)
        print(f"🚀 RUN COMMAND:")
        print(f"docker run -d -p {port}:8000 --env-file .env {tag}")
        print("="*60 + "\n")
    else:
        # Fallback: Leave dist/ for the user to handle manually
        log_warning("⚠️  Docker build skipped or failed.")
        print("\n" + "="*60)
        print("✅ Your code is preserved in the 'dist/' folder.")
        print("To build manually, run:")
        print(f"cd dist && docker build -t {tag} .")
        print("="*60 + "\n")