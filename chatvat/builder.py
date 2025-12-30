# FILE: chatvat/builder.py

import os
import shutil
import subprocess
import json
import sys
import chatvat  
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

def copy_source_code(dist_dir: str):
    """
    [NEW LOGIC] SOURCE INJECTION
    Instead of pip installing, we copy the 'chatvat' python package directly 
    into the container. This ensures Dev/Prod parity without internet access.
    """
    # 1. Locate the actual library on the host machine
    library_path = os.path.dirname(chatvat.__file__)
    
    # 2. Destination: dist/chatvat (So 'import chatvat' works inside /app)
    destination = os.path.join(dist_dir, "chatvat")
    
    log_info(f"🧠 Injecting Core Engine from {library_path}...")
    
    try:
        # We exclude 'bot_template' to avoid recursion (we copy that separately)
        # We exclude git/cache files to keep the Docker image small.
        shutil.copytree(
            library_path, 
            destination, 
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(
                'bot_template', '__pycache__', '*.pyc', '.git', '.DS_Store'
            )
        )
    except Exception as e:
        log_error(f"Failed to inject source code: {e}", fatal=True)

def copy_template_files(template_dir: str, dist_dir: str):
    """
    Copies the bot logic (Dockerfile, src/main.py) from the template to the build folder.
    This overlays the entry points ON TOP of the injected engine.
    """
    try:
        shutil.copytree(
            template_dir, 
            dist_dir, 
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.DS_Store', '.git')
        )
    except Exception as e:
        log_error(f"Failed to copy template files: {e}", fatal=True)

def inject_config(dist_dir: str):
    """
    Copies the user's 'chatvat.config.json' and '.env' into the build context.
    """
    # [UPDATED] Use the standard config name
    config_src = "chatvat.config.json"
    
    if not os.path.exists(config_src):
        log_error("Config file not found. Please run 'init' first.", fatal=True)
    
    # Destination: dist/chatvat.config.json (Root of the container app)
    try:
        shutil.copy(config_src, os.path.join(dist_dir, "chatvat.config.json"))
        
        # [NEW] Also inject secrets if they exist
        if os.path.exists(".env"):
            shutil.copy(".env", os.path.join(dist_dir, ".env"))
            
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
        # [UPDATED] No more build args needed. The code is already in the folder.
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
    1. Prepares 'dist' folder.
    2. Injects Core Engine (Source Code).
    3. Injects Template & Configs.
    4. Builds Docker Image.
    5. Cleans up Code (if successful) to maintain abstraction.
    """
    # Setup Paths (Factory Mode)
    # [UPDATED] Dynamic Location using package path
    library_path = os.path.dirname(chatvat.__file__)
    template_dir = os.path.join(library_path, "bot_template")
    
    user_project_dir = os.getcwd()
    dist_dir = os.path.join(user_project_dir, "dist")

    if not os.path.exists(template_dir):
        log_error(f"Corruption Error: Library template missing at {template_dir}", fatal=True)

    # Generate Intermediate Code
    log_info("📂 Preparing assembly line...")
    clean_dist_folder(dist_dir)
    
    # [NEW] Step 1: Inject the Brain (The Python Package)
    copy_source_code(dist_dir)
    
    # Step 2: Inject the Body (The Dockerfile & Entrypoint)
    copy_template_files(template_dir, dist_dir)
    
    # Step 3: Inject the Soul (Configuration)
    inject_config(dist_dir)

    # 3. Get Bot Name
    try:
        # [UPDATED] Filename correction
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
        # [UPDATED] Added --env-file so it picks up the .env from CWD
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