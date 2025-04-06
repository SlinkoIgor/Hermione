from fastapi import FastAPI, HTTPException, Request
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

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('app.log')
    ]
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Hermione Agent API")

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

# Initialize the agent
agent = AgentBuilder().build()

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
        response_message = result["messages"][-1]
        logger.info(f"Request processed successfully, response: {response_message}")
        return response_message.content
    except Exception as e:
        logger.error(f"Error in run: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    logger.info("Starting Hermione Agent API server")
    uvicorn.run("api:app", host="0.0.0.0", port=8123, reload=True)