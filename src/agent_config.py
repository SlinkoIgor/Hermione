from typing import Literal, Optional


MODEL_CONFIGS = {
    "openai": {
        "base_model": "gpt-5.4-nano",
        "fast_model": "gpt-5.4-nano",
        "thinking_budget": None,
    },
    "litellm": {
        "base_model": "gemini-3-flash-preview",
        "fast_model": "gemini-3-flash-preview",
        "thinking_budget": None,
    }
}


def get_agent_config(
    provider: Literal["openai", "litellm"] = "openai",
    thinking_budget: Optional[int] = None,
    **overrides
):
    if provider not in MODEL_CONFIGS:
        raise ValueError(f"Unknown provider: {provider}. Available: {list(MODEL_CONFIGS.keys())}")

    config = MODEL_CONFIGS[provider].copy()

    if thinking_budget is not None:
        config["thinking_budget"] = thinking_budget

    config.update(overrides)

    return config

