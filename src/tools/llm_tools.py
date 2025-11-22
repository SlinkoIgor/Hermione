from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from textwrap import dedent


async def translate_text(
    text: str,
    native_language: str,
    target_language: str,
    is_native_language: bool,
    llm: ChatOpenAI = None
) -> str:
    """Translates text to the specified target language.

    Parameters:
        text: The text to be translated.
        native_language: The user's native language (e.g., "English", "Spanish", "Russian").
        target_language: The target language for translation (e.g., "English", "Spanish", "Russian").
        is_native_language: Whether the text is in the native language (True or False).
        llm: The LLM to use for translation. If None, creates a default ChatOpenAI instance.
    Returns:
        The translated text in the target language.

    Examples:
        translate_text("Hello world", "English", "Spanish", True) returns "Hola mundo"
        translate_text("Bonjour le monde", "English", "German", False) returns "Hello world"
    """
    target = target_language if is_native_language else native_language
    system_prompt = dedent(f"""You are a professional translator.
    Translate the given text (or word) to {target}.
    Maintain the original meaning, tone, and style as much as possible.
    Only return the translated text (or word), no explanations or other text.
    Preserve the original formatting (tabs, line breaks, spaces, paragraphs, etc.) in the text.

    If it's a word (or two words) not a text, then return 1 main translation and 4 possible translations with the following format:
    main_translation
    [possible_translation_1, possible_translation_2, possible_translation_3, possible_translation_4]""")

    messages = [SystemMessage(system_prompt), HumanMessage(text)]

    response = await llm.ainvoke(messages)
    return response.content


async def fix_text(
    text: str,
    llm: ChatOpenAI = None
) -> str:
    """Fixes grammar in the original text.

    Parameters:
        text: The text to be fixed.
        llm: The LLM to use for fixing. If None, creates a default ChatOpenAI instance.
    Returns:
        The text with grammar fixes.
    """
    system_prompt = dedent(f"""You are a professional grammar editor.
    Fix any grammar, spelling, or punctuation errors in the text.
    Maintain the original meaning, tone, and style as much as possible.
    For every word where you make a change (spelling, words order, words deletion, words addition) put it in <b>tags</b>.
    If you've changed the capital letter, make only this letter in <b>tags</b>.
    If you added punctuation, make only this punctuation in <b>tags</b>.
    Preserve the original formatting (tabs, line breaks, spaces, paragraphs, etc.) in the text.
    Make sure that you put the <b>tags</b> only around the words/punctuation that you've changed.
    Only return the fixed text, no explanations or other text.""")

    messages = [SystemMessage(system_prompt), HumanMessage(text)]

    response = await llm.ainvoke(messages)
    return response.content


async def text_summarization(
    text: str,
    native_language: str,
    llm: ChatOpenAI = None
) -> str:
    """Summarizes text into a TL;DR in the native language.

    Parameters:
        text: The text to be summarized.
        native_language: The user's native language (e.g., "English", "Spanish", "Russian").
        llm: The LLM to use for summarization. If None, creates a default ChatOpenAI instance.
    Returns:
        A concise summary of the text in the native language.

    Examples:
        text_summarization("Long text...", "English") returns "Summary in English"
    """
    system_prompt = dedent(f"""You are a professional summarizer.
    Create a concise TL;DR summary of the given text in {native_language}.
    The summary should be no more than 2-3 (!!!!TWO or THREE!!!!) sentences and capture the main points.
    Only return the summary, no explanations or other text.""")

    messages = [SystemMessage(system_prompt), HumanMessage(text)]

    response = await llm.ainvoke(messages)
    return response.content


async def text_reformulation(
    text: str,
    llm: ChatOpenAI = None
) -> str:
    """Reformulates the given text in the same language with different wording.

    Parameters:
        text: The text to be reformulated.
        llm: The LLM to use for reformulation.
    Returns:
        The reformulated text in the same language.

    Examples:
        text_reformulation("Hello, how are you?") returns "Hi, how's it going?"
    """
    system_prompt = dedent("""You are a professional writer and editor.
    Rewrite the given text using different words and sentence structures while maintaining the same meaning.
    Keep the same language as the original text.
    Make the reformulation natural and fluent.
    Preserve the original tone and style (formal/informal, professional/casual).
    Preserve the original formatting (tabs, line breaks, spaces, paragraphs, etc.) in the text.
    Only return the reformulated text, no explanations or other text.""")

    messages = [SystemMessage(system_prompt), HumanMessage(text)]

    response = await llm.ainvoke(messages)
    return response.content


async def text_enrichment(
    text: str,
    llm: ChatOpenAI = None
) -> str:
    """Enriches the text with Slack-style emoji tags.

    Parameters:
        text: The text to be enriched.
        llm: The LLM to use for enrichment.
    Returns:
        The enriched text with emoji tags.
    """
    system_prompt = dedent("""You are an expert content creator who loves using Slack emojis to make text more engaging and visual.
    Your task is to enrich the given text by adding relevant Slack-style emoji tags (shortcodes like :smile:, :rocket:, :tv:, etc.).

    Guidelines:
    1. Insert emoji tags where they add value, context, or visual appeal.
    2. Use a variety of tags appropriate for the context (tech, emotions, objects, etc.).
    3. You can place tags before headers, bullet points, or key terms. Also after if you want to emphasize something.
    4. Keep the original text content and meaning intact.
    5. Preserve the original formatting (lines, paragraphs).
    6. Do not overdo it; make it look professional yet lively.
    7. Lean towards using rare emoji tags
    8. When using emoji tags that could be absent in the user packs, put an alternative common emoji tag next to it.

    Example style:
    "Last :fri: we discussed on how to improve speed of LLM generation.

    :tv: Recording
    :noted-anime: Gemini notes
    :miro: Miro board

    What did we cover:
    :phoenix_wright_taps_paper:Grouped attention"

    Only return the enriched text, no explanations.""")

    messages = [SystemMessage(system_prompt), HumanMessage(text)]

    response = await llm.ainvoke(messages)
    return response.content


if __name__ == "__main__":
    import asyncio
    
    async def main():
        original = "Hello world"
        # Note: You'll need to initialize an LLM instance here for this to work directly
        # translated = await translate_text(original, "Spanish", "Spanish", True)
        # print(f"Original: {original}")
        # print(f"Translated: {translated}")

    asyncio.run(main())
