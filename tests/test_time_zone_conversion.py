import asyncio
from types import SimpleNamespace

from src.tools.llm_tools import convert_time_zones


class FakeLLM:
    def __init__(self, response):
        self.response = response
        self.messages = []

    async def ainvoke(self, messages):
        self.messages = messages
        return SimpleNamespace(content=self.response)


def test_convert_time_zones_builds_dated_prompt():
    llm = FakeLLM(
        "- Larnaca: 16:00\n- Moscow: 16:00\n"
        "- Berlin: 15:00\n- London: 14:00"
    )

    result = asyncio.run(
        convert_time_zones(
            text="Let's meet at 3 PM Berlin time",
            llm=llm,
            current_date="2026-07-25"
        )
    )

    assert result == (
        "Larnaca: 16:00\n"
        "Moscow:  16:00\n"
        "Berlin:  15:00\n"
        "London:  14:00"
    )
    system_prompt = llm.messages[0].content
    assert "2026-07-25" in system_prompt
    assert "Asia/Nicosia" in system_prompt
    assert "Europe/Moscow" in system_prompt
    assert "Europe/Berlin" in system_prompt
    assert "Europe/London" in system_prompt
    assert "treat the source as Larnaca" in system_prompt
    assert llm.messages[1].content == (
        "<input>Let's meet at 3 PM Berlin time</input>"
    )


def test_convert_time_zones_suppresses_non_time_response():
    llm = FakeLLM("<no_time>")

    result = asyncio.run(
        convert_time_zones(
            text="There is no schedule yet",
            llm=llm,
            current_date="2026-07-25"
        )
    )

    assert result == ""

