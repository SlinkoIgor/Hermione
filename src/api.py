from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Literal
import uvicorn
from dotenv import load_dotenv
import os
import sys

# Load environment variables from .env file in the root directory
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

from agent import AgentBuilder
from agent_config import get_agent_config
import json
from langchain_core.messages import HumanMessage
import logging
import time
from datetime import datetime
import signal
import asyncio
import httpx
from contextlib import asynccontextmanager

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

# Global dictionary to track active requests
active_requests = {}
request_counter = 0
requests_lock = asyncio.Lock()

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
    provider_mode: Literal["openai_only", "litellm_only", "both"] = "litellm_only"

async def check_litellm_availability() -> bool:
    """Check if LiteLLM API is available."""
    try:
        litellm_host = os.getenv("LITELLM_HOST", "https://api.litellm.ai")
        api_key = os.environ.get("LITELLM_API_KEY")

        if not api_key:
            logger.warning("LITELLM_API_KEY not set, LiteLLM unavailable")
            return False

        async with httpx.AsyncClient(timeout=2.0) as client:
            # Simple health check if possible, or minimal model check
            # Assuming /health or root endpoint exists, otherwise fallback to models list
            try:
                # Try a lighter endpoint first if available, else stick to existing check but faster timeout
                headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
                test_payload = {
                    "model": "gemini-2.5-flash-lite",
                    "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": 1
                }
                response = await client.post(f"{litellm_host}/chat/completions", headers=headers, json=test_payload)
                is_available = 200 <= response.status_code < 300
                if not is_available:
                    logger.warning(f"LiteLLM availability check failed with status {response.status_code}")
                else:
                    logger.info("LiteLLM is available")
                return is_available
            except:
                return False
    except Exception as e:
        logger.warning(f"LiteLLM availability check failed: {str(e)}")
        return False

async def get_providers_to_run(provider_mode: str) -> list[str]:
    """Get list of providers based on provider_mode setting and availability."""
    providers = []

    if provider_mode == "openai_only":
        providers.append("openai")
    elif provider_mode == "litellm_only":
        if await check_litellm_availability():
            providers.append("litellm")
        else:
            logger.warning("LiteLLM unavailable, falling back to OpenAI")
            providers.append("openai")
    elif provider_mode == "both":
        providers.append("openai")
        if await check_litellm_availability():
            providers.append("litellm")
        else:
            logger.warning("LiteLLM unavailable, using OpenAI only")

    return providers

async def run_agent_streaming(provider: str, human_message: HumanMessage, cancellation_event: asyncio.Event):
    """Run an agent with streaming results as they complete."""
    try:
        logger.info(f"Running streaming agent with provider: {provider}")
        config = get_agent_config(provider=provider)
        agent_instance = AgentBuilder(provider=provider, **config).build()

        async for result in agent_instance.ainvoke_streaming({"messages": [human_message]}, cancellation_event=cancellation_event):
            if cancellation_event.is_set():
                logger.info(f"Request cancelled for provider {provider}")
                break

            output_key = result["output_key"]
            if output_key.startswith("out_"):
                output_key = output_key[4:]

            yield {
                "provider": provider,
                "output_key": output_key,
                "value": result["value"],
                "tag": result["tag"],
                "model": result["model"]
            }
    except asyncio.CancelledError:
        logger.info(f"Request cancelled for provider {provider}")
        raise
    except Exception as e:
        logger.error(f"Error running streaming agent with provider {provider}: {str(e)}", exc_info=True)
        if provider == "litellm":
            logger.warning(f"LiteLLM provider failed, continuing without it")
        else:
            raise

@app.post("/runs/stream")
async def run_stream(request: SimpleRequest):
    """
    Process a user message and stream results as they become available.
    Now streams individual model results as they complete.
    """
    global request_counter

    async with requests_lock:
        current_request_id = request_counter
        request_counter += 1

        for request_id, event in list(active_requests.items()):
            logger.info(f"Cancelling previous request {request_id}")
            event.set()

        active_requests.clear()

        cancellation_event = asyncio.Event()
        active_requests[current_request_id] = cancellation_event

    logger.info(f"Starting new request {current_request_id}")

    async def generate():
        try:
            logger.info(f"Processing streaming request {current_request_id} with content: {request.content[:100]}... provider_mode: {request.provider_mode}")
            user_message = request.content
            human_message = HumanMessage(content=user_message)

            providers_to_run = await get_providers_to_run(request.provider_mode)
            accumulated_output = {}
            total_results_expected = 0
            results_received = 0

            for provider in providers_to_run:
                config = get_agent_config(provider=provider)
                if isinstance(config.get("base_model"), list):
                    total_results_expected += len(config["base_model"])
                else:
                    total_results_expected += 1

            for provider in providers_to_run:
                if cancellation_event.is_set():
                    logger.info(f"Request {current_request_id} cancelled before provider {provider}")
                    break

                try:
                    async for result in run_agent_streaming(provider, human_message, cancellation_event):
                        if cancellation_event.is_set():
                            logger.info(f"Request {current_request_id} cancelled during streaming")
                            break

                        output_key = result["output_key"]
                        value = result["value"]
                        tag = result["tag"]
                        model = result["model"]

                        if output_key not in accumulated_output:
                            accumulated_output[output_key] = []

                        accumulated_output[output_key].append({
                            "value": value,
                            "tag": tag,
                            "model": model
                        })

                        results_received += 1

                        response_chunk = {
                            "output_key": output_key,
                            "value": value,
                            "tag": tag,
                            "model": model,
                            "provider": provider,
                            "all_complete": results_received >= total_results_expected
                        }
                        yield f"data: {json.dumps(response_chunk)}\n\n"

                except Exception as e:
                    logger.error(f"Error streaming from provider {provider}: {e}", exc_info=True)
                    if provider != "litellm":
                        raise

            if not cancellation_event.is_set():
                final_response = {
                    "output": accumulated_output,
                    "all_complete": True
                }
                yield f"data: {json.dumps(final_response)}\n\n"

        except asyncio.CancelledError:
            logger.info(f"Request {current_request_id} was cancelled")
        except Exception as e:
            logger.error(f"Error in stream for request {current_request_id}: {str(e)}", exc_info=True)
            error_response = {"error": str(e)}
            yield f"data: {json.dumps(error_response)}\n\n"
        finally:
            async with requests_lock:
                if current_request_id in active_requests:
                    del active_requests[current_request_id]
                    logger.info(f"Cleaned up request {current_request_id}")

    return StreamingResponse(generate(), media_type="text/event-stream")

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