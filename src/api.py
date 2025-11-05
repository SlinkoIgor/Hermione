from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Literal
import uvicorn
from agent import AgentBuilder
from agent_config import get_agent_config
import json
from langchain_core.messages import HumanMessage
import logging
import time
from datetime import datetime
import sys
import os
import signal
import asyncio
import httpx
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
    provider_mode: Literal["openai_only", "litellm_only", "both"] = "litellm_only"

async def check_litellm_availability() -> bool:
    """Check if LiteLLM API is available."""
    try:
        litellm_host = os.getenv("LITELLM_HOST", "https://api.litellm.ai")
        api_key = os.environ.get("LITELLM_API_KEY")

        if not api_key:
            logger.warning("LITELLM_API_KEY not set, LiteLLM unavailable")
            return False

        async with httpx.AsyncClient(timeout=5.0) as client:
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            test_payload = {
                "model": "gemini-2.5-flash-lite",
                "messages": [{"role": "user", "content": "test"}],
                "max_tokens": 1
            }
            response = await client.post(f"{litellm_host}/chat/completions", headers=headers, json=test_payload)
            is_available = 200 <= response.status_code < 300
            if not is_available:
                logger.warning(f"LiteLLM availability check failed with status {response.status_code}")
            else:
                logger.info("LiteLLM is available")
            return is_available
    except Exception as e:
        logger.warning(f"LiteLLM availability check failed: {e}")
        return False

async def get_providers_to_run(provider_mode: str) -> list[str]:
    """Get list of providers based on provider_mode setting and availability."""
    providers = []

    if provider_mode == "openai_only":
        providers.append("openai")
    elif provider_mode == "litellm_only":
        litellm_available = await check_litellm_availability()
        if litellm_available:
            providers.append("litellm")
        else:
            logger.warning("LiteLLM unavailable, falling back to OpenAI")
            providers.append("openai")
    elif provider_mode == "both":
        litellm_available = await check_litellm_availability()
        providers.append("openai")
        if litellm_available:
            providers.append("litellm")
        else:
            logger.warning("LiteLLM unavailable, using OpenAI only")

    return providers

async def run_agent_async(provider: str, human_message: HumanMessage) -> tuple[str, Dict[str, Any], bool]:
    """Run an agent asynchronously and return provider name, result, and tool_warning."""
    try:
        logger.info(f"Running agent with provider: {provider}")
        config = get_agent_config(provider=provider)
        agent_instance = AgentBuilder(provider=provider, **config).build()

        result = await agent_instance.ainvoke({"messages": [human_message]})
        tool_warning = result.get("tool_warning", False)

        output = {}
        for key, value in result.items():
            if key.startswith("out_") and value:
                output_key = key[4:]
                if provider == "litellm" and output_key != "text":
                    output_key = f"🚄{output_key}"
                output[output_key] = value

        return provider, output, tool_warning
    except Exception as e:
        logger.error(f"Error running agent with provider {provider}: {str(e)}", exc_info=True)
        if provider == "litellm":
            logger.warning(f"LiteLLM provider failed, continuing without it")
            return provider, {}, False
        else:
            raise

@app.post("/runs")
async def run(request: SimpleRequest):
    """
    Process a user message and return the agent's response.
    Supports running with OpenAI only, LiteLLM only, or both providers.
    Runs agents in parallel when provider_mode is "both".
    """
    try:
        logger.info(f"Processing request with content: {request.content[:100]}... provider_mode: {request.provider_mode}")
        user_message = request.content
        human_message = HumanMessage(content=user_message)

        providers_to_run = await get_providers_to_run(request.provider_mode)
        all_results = {}
        tool_warnings = []

        if len(providers_to_run) > 1:
            tasks = [run_agent_async(provider, human_message) for provider in providers_to_run]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Agent execution failed: {result}", exc_info=True)
                    continue
                provider, output, tool_warning = result
                tool_warnings.append(tool_warning)
                all_results.update(output)
        else:
            for provider in providers_to_run:
                _, output, tool_warning = await run_agent_async(provider, human_message)
                tool_warnings.append(tool_warning)
                all_results.update(output)

        response_data = {
            "tool_warning": any(tool_warnings),
            "output": all_results
        }

        logger.info(f"Request processed successfully, response: {response_data}")
        return response_data
    except Exception as e:
        logger.error(f"Error in run: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/runs/stream")
async def run_stream(request: SimpleRequest):
    """
    Process a user message and stream results as they become available.
    Supports running with OpenAI only, LiteLLM only, or both providers.
    Runs agents in parallel and sends results as they complete.
    """
    async def generate():
        try:
            logger.info(f"Processing streaming request with content: {request.content[:100]}... provider_mode: {request.provider_mode}")
            user_message = request.content
            human_message = HumanMessage(content=user_message)

            providers_to_run = await get_providers_to_run(request.provider_mode)
            all_results = {}
            tool_warnings = []
            completed_providers = set()

            if len(providers_to_run) > 1:
                tasks = {provider: asyncio.create_task(run_agent_async(provider, human_message)) for provider in providers_to_run}

                while tasks:
                    done, pending = await asyncio.wait(
                        tasks.values(),
                        return_when=asyncio.FIRST_COMPLETED
                    )

                    for task in done:
                        provider = None
                        for p, t in tasks.items():
                            if t == task:
                                provider = p
                                break
                        if provider:
                            del tasks[provider]
                            try:
                                _, output, tool_warning = await task
                                tool_warnings.append(tool_warning)
                                all_results.update(output)
                                completed_providers.add(provider)

                                response_chunk = {
                                    "provider": provider,
                                    "output": output,
                                    "tool_warning": tool_warning,
                                    "completed": True,
                                    "all_complete": len(completed_providers) == len(providers_to_run)
                                }
                                yield f"data: {json.dumps(response_chunk)}\n\n"
                            except Exception as e:
                                logger.error(f"Error in agent task for {provider}: {e}", exc_info=True)
                                if provider == "litellm":
                                    completed_providers.add(provider)
                                    response_chunk = {
                                        "provider": provider,
                                        "error": str(e),
                                        "completed": True,
                                        "all_complete": len(completed_providers) == len(providers_to_run)
                                    }
                                    yield f"data: {json.dumps(response_chunk)}\n\n"
                                else:
                                    raise

            else:
                for provider in providers_to_run:
                    _, output, tool_warning = await run_agent_async(provider, human_message)
                    tool_warnings.append(tool_warning)
                    all_results.update(output)
                    completed_providers.add(provider)

                    response_chunk = {
                        "provider": provider,
                        "output": output,
                        "tool_warning": tool_warning,
                        "completed": True,
                        "all_complete": True
                    }
                    yield f"data: {json.dumps(response_chunk)}\n\n"

            final_response = {
                "tool_warning": any(tool_warnings),
                "output": all_results,
                "all_complete": True
            }
            yield f"data: {json.dumps(final_response)}\n\n"

        except Exception as e:
            logger.error(f"Error in stream: {str(e)}", exc_info=True)
            error_response = {"error": str(e)}
            yield f"data: {json.dumps(error_response)}\n\n"

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