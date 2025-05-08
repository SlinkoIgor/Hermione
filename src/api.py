from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Literal
import uvicorn
from agent import AgentBuilder
import json
from langchain_core.messages import HumanMessage
import logging
import time
from datetime import datetime
import sys
import os
import signal
import asyncio
from dotenv import load_dotenv
from contextlib import asynccontextmanager

# Load environment variables from .env file in the root directory
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

# Determine if we're in development mode
IS_DEV = os.getenv('NODE_ENV') == 'development'

# Determine log directory and environment
logs_dir = os.getenv('HERMIONE_LOG_DIR')

if not logs_dir:
    logs_dir = os.path.join(os.path.dirname(__file__), 'logs')
    try:
        os.makedirs(logs_dir, exist_ok=True)
    except Exception as e:
        print(f"Failed to create logs directory: {e}")
        logs_dir = os.path.dirname(__file__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(logs_dir, 'api.log'), mode='a')
    ]
)
logger = logging.getLogger(__name__)

# Log startup information
logger.info("Starting Hermione API server")
logger.info(f"Python executable: {sys.executable}")
logger.info(f"Current directory: {os.getcwd()}")
logger.info(f"Log directory: {logs_dir}")

# Global shutdown event
shutdown_event = asyncio.Event()

# Global agent variable
agent = None

# Get environment variables
DEFAULT_PORT = 8123
PORT = int(os.getenv('API_PORT', str(DEFAULT_PORT)))
HOST = '127.0.0.1'

@asynccontextmanager
async def lifespan(app: FastAPI):
    global agent
    try:
        # Startup
        logger.info("Starting up API server")
        logger.info(f"Python path: {sys.executable}")
        logger.info(f"API script path: {os.path.abspath(__file__)}")
        logger.info(f"Environment: {'development' if IS_DEV else 'production'}")
        logger.info(f"Host: {HOST}")
        logger.info(f"Port: {PORT}")

        # Setup signal handlers
        def handle_signal(signum, frame):
            logger.info(f"Received signal {signum}")
            asyncio.create_task(shutdown())

        signal.signal(signal.SIGTERM, handle_signal)
        signal.signal(signal.SIGINT, handle_signal)

        # Initialize the agent
        agent = AgentBuilder().build()
        logger.info("Agent initialized successfully")

        yield

    except Exception as e:
        logger.error(f"Error during startup: {e}")
        raise
    finally:
        # Shutdown
        logger.info("Shutting down API server")
        await shutdown()

async def shutdown():
    logger.info("Initiating graceful shutdown")
    shutdown_event.set()
    try:
        # Give time for cleanup
        await asyncio.sleep(2)
        # Force close any remaining connections
        for task in asyncio.all_tasks():
            if task is not asyncio.current_task():
                task.cancel()
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")
    finally:
        logger.info("Shutdown complete")

app = FastAPI(title="Hermione Agent API", lifespan=lifespan)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    logger.info(f"Request started: {request.method} {request.url}")
    response = await call_next(request)
    process_time = time.time() - start_time
    logger.info(f"Request completed: {request.method} {request.url} - Status: {response.status_code} - Time: {process_time:.2f}s")
    return response

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SimpleRequest(BaseModel):
    content: str

@app.post("/runs")
async def run(request: SimpleRequest):
    """
    Process a user message and return the agent's response.
    """
    try:
        logger.info(f"Processing request with content: {request.content[:100]}...")
        user_message = request.content
        human_message = HumanMessage(content=user_message)
        result = agent.invoke({"messages": [human_message]})
        tool_warning = result.get("tool_warning", False)

        output = {}
        for key, value in result.items():
            if key.startswith("out_") and value:
                output[key[4:]] = value

        response_data = {
            "tool_warning": tool_warning,
            "output": output
        }

        logger.info(f"Request processed successfully, response: {response_data}")
        return response_data
    except Exception as e:
        logger.error(f"Error in run: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def root():
    return {"status": "ok"}

if __name__ == "__main__":
    try:
        logger.info("Starting Hermione Agent API server")
        uvicorn.run(
            "api:app",
            host=HOST,
            port=PORT,
            reload=False,
            workers=1,
            log_level="info"
        )
    except Exception as e:
        logger.error(f"Error running server: {e}")
        sys.exit(1)