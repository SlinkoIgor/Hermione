import pytest
import os
from langchain_core.messages import HumanMessage
from src.agent import AgentBuilder
from src.agent_config import get_agent_config
import numpy as np
import re
import asyncio

@pytest.fixture(params=["openai", "litellm"])
def provider(request):
    if request.param == "litellm" and not os.environ.get("LITELLM_API_KEY"):
        pytest.skip("LITELLM_API_KEY not set, skipping LiteLLM tests")
    return request.param

@pytest.fixture
def agent(provider):
    config = get_agent_config(provider=provider, thinking_budget=1000)
    return AgentBuilder(
        native_currency="EUR",
        provider=provider,
        **config
    ).build()

@pytest.mark.asyncio
async def test_math_formula_calculation(agent):
    messages = await agent.ainvoke({"messages": [HumanMessage("log10(1000 * 66)")]})
    result = messages.get("out_math_result", "")
    assert "4.819543935541868" in result or "4.82" in result

@pytest.mark.asyncio
async def test_word_explanation(agent):
    messages = await agent.ainvoke({"messages": [HumanMessage("Photosynthesis")]})
    assert "out_translation" in messages
    assert "out_fixed" in messages
    fixed_text = re.sub(r'<[^>]+>', '', messages["out_fixed"])
    assert "Photosynthesis" in fixed_text, fixed_text

# def test_time_zone_conversion_russian(agent):
#     messages = agent.invoke({"messages": [HumanMessage("давай встретимся в 3 дня по Барселоне")]})
#     result = messages.get("out_tz_conversion", "")
#     assert "Барселоне" in result
#     assert any(time in result for time in ["15:00", "16:00", "3 PM", "4 PM"])

@pytest.mark.asyncio
async def test_text_translation(agent):
    messages = await agent.ainvoke({
        "messages": [HumanMessage(
            "The issue is that LangChain's bind_tools expects a function with a valid __name__ attribute, "
            "which classes (even callables) don't naturally have. Since functools.partial and lambda also "
            "don't provide __name__, the best approach is to use a decorator-based wrapper to dynamically set __name__."
        )]
    })
    assert "out_translation" in messages
    assert "out_fixed" in messages
    fixed_text = re.sub(r'<[^>]+>', '', messages["out_fixed"])
    assert "LangChain" in fixed_text
    assert "bind_tools" in fixed_text.lower()

# def test_time_zone_conversion_english(agent):
#     messages = agent.invoke({"messages": [HumanMessage("can you make it after 4 PM Berlin time?")]})
#     result = messages.get("out_tz_conversion", "")
#     assert "Berlin" in result
#     assert any(time in result for time in ["15:00", "16:00", "3 PM", "4 PM"])

# def test_currency_conversion(agent):
#     messages = agent.invoke({"messages": [HumanMessage("How much is 100 USD in EUR?")]})
#     result = messages.get("out_currency_conversion", "")
#     if "Error" in result:
#         assert "EXCHANGE_RATE_API_KEY" in result
#     else:
#         assert "100" in result
#         assert "USD" in result
#         assert "EUR" in result

@pytest.mark.asyncio
async def test_sum_of_logarithms(agent):
    messages = await agent.ainvoke({"messages": [HumanMessage("SUM(log(n)) где N = 1..10 c шагом 1")]})
    result = messages.get("out_math_result", "")
    expected_result = sum(np.log(n) for n in range(1, 11))
    try:
        result_value = float(result.strip())
        assert abs(result_value - expected_result) < 1e-10
    except ValueError:
        assert str(expected_result)[:5] in result

@pytest.mark.asyncio
async def test_percentage_calculation(agent):
    messages = await agent.ainvoke({"messages": [HumanMessage("Найдите часть от целого:\nА) 23% от 300;")]})
    result = messages.get("out_math_result", "")
    expected_result = (23 / 100) * 300
    try:
        result_value = float(result.strip())
        assert abs(result_value - expected_result) < 1e-10
    except ValueError:
        assert str(expected_result)[:5] in result

# def test_generate_bash_command(agent):
#     messages = agent.invoke({"messages": [HumanMessage("list all files in current directory")]})
#     result = messages.get("out_bash_command", "")
#     assert "ls" in result.lower(), f"Expected 'ls' command, but got: {result}"
#     assert any(flag in result for flag in ["-l", "-a", "-la", "-l -a", "-al", "--all", "--list", "-1"]), f"Expected command to contain one of the flags [-l, -a, -la, -l -a, -al, --all, --list, -1], but got command: {result}"
