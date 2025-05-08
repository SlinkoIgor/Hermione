import pytest
from langchain_core.messages import HumanMessage
from src.agent import AgentBuilder
import numpy as np
import re

@pytest.fixture
def agent():
    return AgentBuilder(native_currency="EUR").build()

def test_math_formula_calculation(agent):
    messages = agent.invoke({"messages": [HumanMessage("log10(1000 * 66)")]})
    result = messages.get("out_math_result", "")
    assert "4.819543935541868" in result or "4.82" in result

def test_word_explanation(agent):
    messages = agent.invoke({"messages": [HumanMessage("Photosynthesis")]})
    assert "out_translation" in messages
    assert "out_fixed" in messages
    fixed_text = re.sub(r'<[^>]+>', '', messages["out_fixed"])
    assert "Photosynthesis" in fixed_text

def test_time_zone_conversion_russian(agent):
    messages = agent.invoke({"messages": [HumanMessage("давай встретимся в 3 дня по Барселоне")]})
    result = messages.get("out_tz_conversion", "")
    assert any(time in result for time in ["16:00", "17:00", "4 PM", "5 PM"])

def test_text_translation(agent):
    messages = agent.invoke({
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
    assert "bind_tools" in fixed_text

def test_time_zone_conversion_english(agent):
    messages = agent.invoke({"messages": [HumanMessage("can you make it after 4 PM Berlin time?")]})
    result = messages.get("out_tz_conversion", "")
    assert any(time in result for time in ["16:00", "17:00", "4 PM", "5 PM"])

def test_currency_conversion(agent):
    messages = agent.invoke({"messages": [HumanMessage("How much is 100 USD in EUR?")]})
    result = messages.get("out_currency_conversion", "")
    if "Error" in result:
        assert "EXCHANGE_RATE_API_KEY" in result
    else:
        assert "100" in result
        assert "USD" in result
        assert "EUR" in result

def test_sum_of_logarithms(agent):
    messages = agent.invoke({"messages": [HumanMessage("SUM(log(n)) где N = 1..10 c шагом 1")]})
    result = messages.get("out_math_result", "")
    expected_result = sum(np.log(n) for n in range(1, 11))
    try:
        result_value = float(result.strip())
        assert abs(result_value - expected_result) < 1e-10
    except ValueError:
        assert str(expected_result)[:5] in result

def test_percentage_calculation(agent):
    messages = agent.invoke({"messages": [HumanMessage("Найдите часть от целого:\nА) 23% от 300;")]})
    result = messages.get("out_math_result", "")
    expected_result = (23 / 100) * 300
    try:
        result_value = float(result.strip())
        assert abs(result_value - expected_result) < 1e-10
    except ValueError:
        assert str(expected_result)[:5] in result

def test_generate_bash_command(agent):
    messages = agent.invoke({"messages": [HumanMessage("list all files in current directory")]})
    result = messages.get("out_bash_command", "")
    assert "ls" in result.lower(), f"Expected 'ls' command, but got: {result}"
    assert any(flag in result for flag in ["-l", "-a", "-la", "-l -a", "-al", "--all", "--list", "-1"]), f"Expected command to contain one of the flags [-l, -a, -la, -l -a, -al, --all, --list, -1], but got command: {result}"
