import pytest
import os
from src.agent import AgentBuilder
from src.agent_config import get_agent_config
from src.tools.tz_convertor import get_current_time, get_shifted_time, convert_time

@pytest.fixture(params=["openai", "litellm"])
def provider(request):
    if request.param == "litellm" and not os.environ.get("LITELLM_API_KEY"):
        pytest.skip("LITELLM_API_KEY not set, skipping LiteLLM tests")
    return request.param

@pytest.fixture
def agent(provider):
    config = get_agent_config(provider=provider)
    return AgentBuilder(
        native_language="English",
        target_language="English",
        native_currency="EUR",
        current_location="Europe/London",
        provider=provider,
        **config
    ).build()

# def test_current_time_query(agent):
#     state = agent.invoke({"messages": [{"content": "What time is it in Paris?", "type": "human"}]})
#     assert "out_tz_conversion" in state
#     assert "Current time in Paris" in state["out_tz_conversion"]
#     assert ":" in state["out_tz_conversion"]

# def test_time_shift_query(agent):
#     state = agent.invoke({"messages": [{"content": "What time will it be in Tokyo in 3 hours?", "type": "human"}]})
#     assert "out_tz_conversion" in state
#     assert "Current time in Tokyo" in state["out_tz_conversion"]
#     assert "in 3 hours" in state["out_tz_conversion"]
#     assert ":" in state["out_tz_conversion"]

# def test_multilingual_query(agent):
#     state = agent.invoke({"messages": [{"content": "Сколько времени будет в Париже через 2 часа?", "type": "human"}]})
#     assert "out_tz_conversion" in state
#     assert "в Париже" in state["out_tz_conversion"]
#     assert "часа" in state["out_tz_conversion"]
#     assert ":" in state["out_tz_conversion"]

# def test_invalid_time_format_query(agent):
#     state = agent.invoke({"messages": [{"content": "If it's 25:00 in New York, what time is it in London?", "type": "human"}]})
#     assert "out_tz_conversion" in state
#     assert "25:00 in New York" in state["out_tz_conversion"]
#     assert "in London" in state["out_tz_conversion"]
#     assert ":" in state["out_tz_conversion"]

# def test_complex_timezone_query(agent):
#     state = agent.invoke({"messages": [{"content": "What time will it be in Sydney in 5 hours if it's 9 AM in Los Angeles?", "type": "human"}]})
#     assert "out_tz_conversion" in state
#     assert "9:00 AM in Los Angeles" in state["out_tz_conversion"]
#     assert "in Sydney" in state["out_tz_conversion"]
#     assert "In 5 hours" in state["out_tz_conversion"]
#     assert ":" in state["out_tz_conversion"]

# def test_timezone_accuracy(agent):
#     state = agent.invoke({"messages": [{"content": "If it's 14:30 in Berlin, what time is it in UTC?", "type": "human"}]})
#     assert "out_tz_conversion" in state
#     result = state["out_tz_conversion"]

#     berlin_time = "14:30"
#     berlin_tz = "Europe/Berlin"
#     utc_tz = "UTC"

#     conversion_result = convert_time(berlin_time, berlin_tz, utc_tz)
#     expected_time = conversion_result["time"]

#     assert expected_time in result
