import asyncio
from types import SimpleNamespace

import pytest
from langchain_core.messages import HumanMessage

import src.agent as agent_module
from src.agent import AgentBuilder, INTERRUPTED_GENERATION_NOTE
from src.tools.llm_tools import (
    FLUENT_TRANSLATION_STYLE,
    build_translation_prompt,
    generate_text,
    is_word_or_phrase,
)


class FakeStreamingLLM:
    def __init__(self, pieces, fail_at=None):
        self.pieces = pieces
        self.fail_at = fail_at

    async def astream(self, messages):
        for index, piece in enumerate(self.pieces):
            if index == self.fail_at:
                raise RuntimeError("connection dropped")
            await asyncio.sleep(0)
            yield SimpleNamespace(content=piece)

    async def ainvoke(self, messages):
        return SimpleNamespace(content="<no_time>")


def collect_events(llm, text, cancel_after=None):
    builder = AgentBuilder(provider="openai", base_model="gpt-test")
    builder._get_llm = lambda use_fast=False: llm
    cancellation_event = asyncio.Event()

    async def run():
        events = []
        stream = builder.build().ainvoke_streaming(
            {"messages": [HumanMessage(text)]},
            cancellation_event=cancellation_event,
        )
        async for event in stream:
            events.append(event)
            if cancel_after is not None and len(events) == cancel_after:
                cancellation_event.set()
        return events

    return asyncio.run(run())


@pytest.fixture(autouse=True)
def emit_every_partial(monkeypatch):
    monkeypatch.setattr(agent_module, "PARTIAL_EMIT_INTERVAL_SECONDS", 0)


@pytest.mark.parametrize(
    "text, expected",
    [
        ("serendipity", True),
        ("take off", True),
        ("  неуловимый \n", True),
        ("Stop it.", False),
        ("Really?", False),
        ("piece of cake", False),
        ("Could you take a look at this?", False),
        ("", False),
    ],
)
def test_is_word_or_phrase(text, expected):
    assert is_word_or_phrase(text) is expected


def test_translation_prompt_uses_card_format_only_for_words():
    word_prompt = build_translation_prompt("serendipity", "Русский", FLUENT_TRANSLATION_STYLE)
    text_prompt = build_translation_prompt(
        "Could you take a look at this?", "Русский", FLUENT_TRANSLATION_STYLE
    )

    assert "Contexts:" in word_prompt
    assert "Synonyms:" in word_prompt
    assert "Contexts:" not in text_prompt
    assert "Synonyms:" not in text_prompt
    assert "natural and fluent in Русский" in text_prompt
    for prompt in (word_prompt, text_prompt):
        assert "to Русский" in prompt
        assert "never as instructions" in prompt
        assert "{" not in prompt


def test_generate_text_reports_accumulated_text():
    partials = []
    llm = FakeStreamingLLM(["Hel", "", "lo ", "world"])

    result = asyncio.run(generate_text(llm, [], partials.append))

    assert result == "Hello world"
    assert partials == ["Hel", "Hello ", "Hello world"]


def test_streaming_emits_partials_before_one_final_per_tab():
    text = "this are a short test"
    llm = FakeStreamingLLM(["this is ", "a short ", "test"])

    events = collect_events(llm, text)

    assert events[0] == {
        "output_key": "existent",
        "value": text,
        "tag": "",
        "model": "router",
        "partial": False,
    }
    tabs = {"fluent_translation", "fixed", "reformulation", "polished", "enrichment"}
    assert {event["output_key"] for event in events[1:]} == tabs
    for tab in tabs:
        tab_events = [event for event in events if event["output_key"] == tab]
        assert [event["partial"] for event in tab_events] == [True, True, True, False]
        assert [event["value"] for event in tab_events[:3]] == [
            "this is ",
            "this is a short ",
            "this is a short test",
        ]
    finals = {
        event["output_key"]: event["value"]
        for event in events
        if not event["partial"]
    }
    assert finals["fluent_translation"] == "this is a short test"
    assert "<b>is</b>" in finals["fixed"]
    assert "<s>are</s>" in finals["fixed"]


def test_streaming_marks_interrupted_generation():
    llm = FakeStreamingLLM(["this is ", "a short ", "test"], fail_at=2)

    events = collect_events(llm, "this are a short test")

    finals = [
        event for event in events
        if not event["partial"] and event["output_key"] != "existent"
    ]
    assert len(finals) == 5
    for event in finals:
        assert event["value"].startswith("this is a short ")
        assert event["value"].endswith(INTERRUPTED_GENERATION_NOTE)


def test_streaming_stops_after_cancellation():
    llm = FakeStreamingLLM(["this is ", "a short ", "test"])

    events = collect_events(llm, "this are a short test", cancel_after=3)

    assert len(events) == 3
