import os
import openai
from langchain_openai import ChatOpenAI
import logging

logger = logging.getLogger(__name__)

LITELLM_HOST = os.getenv("LITELLM_HOST", "https://api.litellm.ai")

def get_litellm_client() -> openai.OpenAI:
    api_key = os.environ.get("LITELLM_API_KEY")
    if not api_key:
        raise ValueError("LITELLM_API_KEY environment variable is not set. Please set it to use the LLM API.")
    return openai.OpenAI(api_key=api_key, base_url=LITELLM_HOST)

def get_openai_llm(model_name: str, temperature: float = 1, thinking_budget: int = None) -> ChatOpenAI:
    kwargs = {}
    if thinking_budget is not None:
        kwargs["model_kwargs"] = {"reasoning_effort": "low"} if "gpt" in model_name.lower() else {}
    return ChatOpenAI(model=model_name, temperature=temperature, **kwargs)

def get_litellm_llm(model_name: str, temperature: float = 1, thinking_budget: int = None) -> ChatOpenAI:
    api_key = os.environ.get("LITELLM_API_KEY")
    if not api_key:
        raise ValueError("LITELLM_API_KEY environment variable is not set.")

    kwargs = {
        "model": model_name,
        "temperature": temperature,
        "openai_api_key": api_key,
        "openai_api_base": LITELLM_HOST
    }

    if thinking_budget is not None:
        model_kwargs = {}
        if "gemini" in model_name.lower():
            model_kwargs["reasoning_effort"] = "low"
        elif "gpt" in model_name.lower():
            model_kwargs["reasoning_effort"] = "low"
        if model_kwargs:
            kwargs["model_kwargs"] = model_kwargs

    return ChatOpenAI(**kwargs)

