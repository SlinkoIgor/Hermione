import pytest
from langchain_core.messages import HumanMessage
from src.agent import AgentBuilder
import numpy as np

@pytest.fixture
def agent():
    return AgentBuilder(native_currency="EUR").build()

def test_math_formula_calculation(agent):
    messages = agent.invoke({"messages": [HumanMessage("log10(1000 * 66)")]})
    result = str(messages['messages'][-1].content)
    required_parts = [
        "=======<result>=======",
        "4.819543935541868",
        "=====<script>======",
        "log10(1000 * 66)"
    ]
    for part in required_parts:
        assert part in result

def test_word_explanation(agent):
    messages = agent.invoke({"messages": [HumanMessage("Photosynthesis")]})
    result = str(messages['messages'][-1].content)
    required_parts = [
        "=======<translation>=======",
        "Фотосинтез",
        "[",
        "]",
        "=======<fixed_text>=======",
        "Photosynthesis"
    ]
    for part in required_parts:
        assert part in result

def test_time_zone_conversion_russian(agent):
    messages = agent.invoke({"messages": [HumanMessage("давай встретимся в 3 дня по Барселоне")]})
    result = str(messages['messages'][-1].content)
    expected = "=======<tz_conversion>=======\n\nдавай встретимся в 16:00 по Никосии"
    assert result.strip() == expected.strip()

def test_text_translation(agent):
    messages = agent.invoke({
        "messages": [HumanMessage(
            "The issue is that LangChain's bind_tools expects a function with a valid __name__ attribute, "
            "which classes (even callables) don't naturally have. Since functools.partial and lambda also "
            "don't provide __name__, the best approach is to use a decorator-based wrapper to dynamically set __name__."
        )]
    })
    result = str(messages['messages'][-1].content)
    expected_parts = [
        "=======<translation>=======",
        "Проблема в том, что bind_tools в LangChain ожидает функцию с допустимым атрибутом __name__",
        "=======<fixed_text>=======",
        "The issue is that LangChain's bind_tools expects a function with a valid __name__ attribute"
    ]
    for part in expected_parts:
        assert part in result

def test_time_zone_conversion_english(agent):
    messages = agent.invoke({"messages": [HumanMessage("can you make it after 4 PM Berlin time?")]})
    result = str(messages['messages'][-1].content)
    expected = "=======<tz_conversion>=======\n\nдавай встретимся в 17:00 по Никосии"
    assert result.strip() == expected.strip()

def test_currency_conversion(agent):
    messages = agent.invoke({"messages": [HumanMessage("How much is 100 USD in EUR?")]})
    result = str(messages['messages'][-1].content)
    expected_format = "=======<convert_currency>=======\n\n"
    assert result.startswith(expected_format)
    assert " USD == " in result
    assert " EUR" in result

def test_sum_of_logarithms(agent):
    messages = agent.invoke({"messages": [HumanMessage("SUM(log(n)) где N = 1..10 c шагом 1")]})
    result = str(messages['messages'][-1].content)
    expected_result = sum(np.log(n) for n in range(1, 11))
    assert abs(float(result.split("=======<result>=======")[1].split("=====<script>======")[0].strip()) - expected_result) < 1e-10

def test_percentage_calculation(agent):
    messages = agent.invoke({"messages": [HumanMessage("Найдите часть от целого:\nА) 23% от 300;")]})
    result = str(messages['messages'][-1].content)
    expected_result = (23 / 100) * 300
    assert abs(float(result.split("=======<result>=======")[1].split("=====<script>======")[0].strip()) - expected_result) < 1e-10 