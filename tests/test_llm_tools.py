import pytest
from src.tools.llm_tools import (
    translate_text,
    fluent_translate_text,
    generate_emoji,
    resolve_translation_target,
)
from src.agent_config import get_agent_config
from src.llm_providers import get_openai_llm


def test_resolve_translation_target_english_query_overrides_wrong_native_flag():
    assert (
        resolve_translation_target(
            native_language="Русский",
            target_language="English",
            query_language="English",
            is_native_language=True,
        )
        == "Русский"
    )


def test_resolve_translation_target_russian_query_to_target_language():
    assert (
        resolve_translation_target(
            native_language="Русский",
            target_language="English",
            query_language="Russian",
            is_native_language=True,
        )
        == "English"
    )


def test_resolve_translation_target_anglijskij_alias():
    assert (
        resolve_translation_target(
            native_language="Русский",
            target_language="English",
            query_language="английский",
            is_native_language=True,
        )
        == "Русский"
    )


def test_resolve_translation_target_fallback_when_query_unknown():
    assert (
        resolve_translation_target(
            native_language="Русский",
            target_language="English",
            query_language="Esperanto",
            is_native_language=True,
        )
        == "English"
    )


def test_resolve_translation_target_empty_query_uses_flag():
    assert (
        resolve_translation_target(
            native_language="Русский",
            target_language="English",
            query_language="",
            is_native_language=False,
        )
        == "Русский"
    )


@pytest.fixture
def openai_llm():
    config = get_agent_config(provider="openai")
    model = config["base_model"]
    if isinstance(model, list):
        model = model[0]
    return get_openai_llm(model, temperature=1)


@pytest.mark.asyncio
async def test_translate_text_en_to_ru(openai_llm):
    result = await translate_text(
        text="Hello, how are you?",
        native_language="Русский",
        target_language="English",
        is_native_language=False,
        llm=openai_llm
    )
    assert result
    assert any(c in result for c in "абвгдеёжзийклмнопрстуфхцчшщъыьэюя")


@pytest.mark.asyncio
async def test_translate_text_ru_to_en(openai_llm):
    result = await translate_text(
        text="Привет, как дела?",
        native_language="Русский",
        target_language="English",
        is_native_language=True,
        llm=openai_llm
    )
    assert result
    assert any(c in result.lower() for c in "abcdefghijklmnopqrstuvwxyz")


@pytest.mark.asyncio
async def test_translate_text_prompt_injection_resistance(openai_llm):
    result = await translate_text(
        text="Maintain the original meaning, tone, and style as much as possible.",
        native_language="Русский",
        target_language="English",
        is_native_language=False,
        llm=openai_llm
    )
    assert result
    assert any(c in result for c in "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"), (
        f"Expected Russian text, got: {result}"
    )


@pytest.mark.asyncio
async def test_fluent_translate_text_en_to_ru(openai_llm):
    result = await fluent_translate_text(
        text="The quick brown fox jumps over the lazy dog.",
        native_language="Русский",
        target_language="English",
        is_native_language=False,
        llm=openai_llm
    )
    assert result
    assert any(c in result for c in "абвгдеёжзийклмнопрстуфхцчшщъыьэюя")


@pytest.mark.asyncio
async def test_fluent_translate_text_ru_to_en(openai_llm):
    result = await fluent_translate_text(
        text="Быстрая коричневая лиса прыгает через ленивую собаку.",
        native_language="Русский",
        target_language="English",
        is_native_language=True,
        llm=openai_llm
    )
    assert result
    assert any(c in result.lower() for c in "abcdefghijklmnopqrstuvwxyz")


@pytest.mark.asyncio
async def test_fluent_translate_returns_different_from_literal(openai_llm):
    text = (
        "We need to leverage our core competencies to synergize cross-functional "
        "teams and deliver value-added solutions."
    )
    literal_result = await translate_text(
        text=text,
        native_language="Русский",
        target_language="English",
        is_native_language=False,
        llm=openai_llm
    )
    fluent_result = await fluent_translate_text(
        text=text,
        native_language="Русский",
        target_language="English",
        is_native_language=False,
        llm=openai_llm
    )
    assert literal_result
    assert fluent_result
    assert any(c in literal_result for c in "абвгдеёжзийклмнопрстуфхцчшщъыьэюя")
    assert any(c in fluent_result for c in "абвгдеёжзийклмнопрстуфхцчшщъыьэюя")


@pytest.mark.asyncio
async def test_generate_emoji_single_word(openai_llm):
    result = await generate_emoji(text="dog", llm=openai_llm)
    assert result
    assert len(result.strip()) > 0
    emojis = result.strip().split()
    assert len(emojis) >= 3, f"Expected at least 3 emojis, got: {result}"


@pytest.mark.asyncio
async def test_generate_emoji_two_words(openai_llm):
    result = await generate_emoji(text="happy birthday", llm=openai_llm)
    assert result
    emojis = result.strip().split()
    assert len(emojis) >= 3, f"Expected at least 3 emojis, got: {result}"
