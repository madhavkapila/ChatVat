# FILE: chatvat/bot_template/src/main.py

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from chatvat.bot_template.src.core.engine import get_rag_engine
from chatvat.bot_template.src.core.ingestor import run_ingestion
from chatvat.bot_template.src.constants import APP_VERSION, APP_NAME
from chatvat.bot_template.src.config_loader import load_runtime_config
from chatvat.bot_template.src.utils.logger import setup_logging

# Setup Logging
logger = setup_logging()

# --- Pydantic Models for API ---
class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    message: str

# --- BACKGROUND WORKER LOGIC ---
# This is the "SatBot Logic" that prevents deployment timeouts.
async def background_ingestion_loop():
    """
    Runs ingestion based on the user's 'refresh_interval' setting.
    """
    logger.info("⏳ Background Ingestion Worker Started.")
    
    # 1. Initial Run (Wait 5s for startup)
    await asyncio.sleep(5) 
    try:
        logger.info("🏁 Triggering Initial Ingestion...")
        await run_ingestion()
    except Exception as e:
        logger.error(f"Initial ingestion failed: {e}")

    # 2. Dynamic Loop Logic
    # We load the config to see what the user wants
    config = load_runtime_config()
    
    # Default to 0 (No auto-update) if missing
    interval_minutes = getattr(config, 'refresh_interval_minutes', 0)
    
    if interval_minutes > 0:
        logger.info(f"🔄 Auto-Update enabled. Schedule: Every {interval_minutes} minutes.")
        
        while True:
            # Convert minutes to seconds
            sleep_seconds = interval_minutes * 60
            await asyncio.sleep(sleep_seconds)
            
            logger.info("⏰ Timer hit. Running scheduled ingestion...")
            try:
                await run_ingestion()
            except Exception as e:
                logger.error(f"Scheduled ingestion failed: {e}")
    else:
        logger.info("🛑 Auto-Update disabled (interval set to 0).")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI Lifespan Manager.
    Handle startup and shutdown events.
    """
    # --- STARTUP ---
    logger.info(f"🚀 {APP_NAME} v{APP_VERSION} Starting up...")
    
    # Start the background worker as a Task
    ingestion_task = asyncio.create_task(background_ingestion_loop())
    
    yield # Control returns to FastAPI here for the app's lifetime
    
    # --- SHUTDOWN ---
    logger.info("🛑 Shutting down...")
    ingestion_task.cancel()
    try:
        await ingestion_task
    except asyncio.CancelledError:
        pass

# --- API APP SETUP ---
app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    lifespan=lifespan # Attach the lifespan logic
)

# CORS (Allow frontend access)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- ROUTES ---

@app.get("/health")
async def health_check():
    """
    Simple health check for Cloud Platforms (AWS/Render).
    Returns 200 OK immediately, even if ingestion is still running.
    """
    return {"status": "healthy", "version": APP_VERSION}

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    The main Chat Interface.
    """
    try:
        # Get the engine (This is lightweight, just initializes the class)
        engine = get_rag_engine()
        
        # Generate Answer
        answer = engine.get_response(request.message)
        
        return ChatResponse(message = answer)

    except Exception as e:
        logger.error(f"API Error: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

# --- ENTRY POINT ---
# This allows running 'python src/main.py' for local testing
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)