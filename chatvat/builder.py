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
    """removes dist/ folder for fresh build"""
    if os.path.exists(dist_path):
        try:
            shutil.rmtree(dist_path)
        except Exception as e:
            log_error(f"Could not clean 'dist' folder: {e}", fatal=True)
    os.makedirs(dist_path)

def copy_source_code(dist_dir: str):
    """copies chatvat package into container instead of pip installing"""
    library_path = os.path.dirname(chatvat.__file__)
    destination = os.path.join(dist_dir, "chatvat")
    
    log_info(f"🧠 Injecting Core Engine from {library_path}...")
    
    try:
        # exclude bot_template (copy separately) and cache files
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
    """copies bot logic (Dockerfile, src/main.py) to build folder"""
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
    """copies chatvat.config.json into build context"""
    config_src = "chatvat.config.json"
    
    if not os.path.exists(config_src):
        log_error("Config file not found. Please run 'init' first.", fatal=True)
    
    try:
        shutil.copy(config_src, os.path.join(dist_dir, "chatvat.config.json"))
        # if os.path.exists(".env"):
        #     shutil.copy(".env", os.path.join(dist_dir, ".env"))
    except Exception as e:
        log_error(f"Failed to inject config: {e}", fatal=True)

def inject_local_files(dist_dir: str, config_path: str):
    """finds local_file sources in config and copies them to build"""
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        sources = config.get("sources", [])
        for source in sources:
            if source.get("type") == "local_file":
                target = source.get("target")
                if os.path.exists(target):
                    dest_path = os.path.join(dist_dir, target)
                    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                    shutil.copy(target, dest_path)
                    log_info(f"📂 Injected local file: {target}")
    except Exception as e:
        log_warning(f"Could not inject local files: {e}")

def run_docker_build(bot_name: str, dist_path: str) -> bool:
    """runs docker build, returns True if success"""
    tag_name = bot_name.lower().replace(" ", "-")
    
    log_info(f"🐳 Attempting Docker Build for '{tag_name}'...")
    
    # check if docker is installed
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

    try:
        cmd = ["docker", "build", "-t", tag_name, "."]
        result = subprocess.run(cmd, cwd=dist_path, check=True)
        return True
    
    except subprocess.CalledProcessError:
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
    
    # Inject the Brain (The Python Package)
    copy_source_code(dist_dir)
    
    # Inject the Body (The Dockerfile & Entrypoint)
    copy_template_files(template_dir, dist_dir)
    
    # Inject the Soul (Configuration)
    inject_config(dist_dir)

    # Inject Local Files if any
    config_path = os.path.join(user_project_dir, "chatvat.config.json")
    inject_local_files(dist_dir, config_path)

    # Get Bot Name
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

    # Attempt Docker Build
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
        print(f"docker run -d --ipc=host -p {port}:8000 --name {tag}_chatvat --env-file .env {tag}")
        print("="*60 + "\n")
    else:
        # Fallback: Leave dist/ for the user to handle manually
        log_warning("⚠️  Docker build skipped or failed.")
        print("\n" + "="*60)
        print("✅ Your code is preserved in the 'dist/' folder.")
        print("To build manually, run:")
        print(f"cd dist && docker build -t {tag} .")
        print("="*60 + "\n")