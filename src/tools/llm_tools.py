from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from textwrap import dedent


def translate_text(
    text: str,
    native_language: str,
    target_language: str,
    fix_grammar: bool = False
) -> str:
    """Translates text to the specified target language.

    Parameters:
        text: The text to be translated.
        native_language: The user's native language (e.g., "English", "Spanish", "Russian").
        target_language: The target language for translation (e.g., "English", "Spanish", "Russian").
        fix_grammar: Whether to fix the grammar of the text.
    Returns:
        The translated text in the target language.

    Examples:
        translate_text("Hello world", "English", "Spanish") returns "Hola mundo"
        translate_text("Bonjour le monde", "English", "German") returns "Hello world"
    """
    system_prompt = dedent(f"""You are a professional translator.
    First, determine if the text is in {native_language} or not.
    If the text is in {native_language}, translate it to {target_language}.
    If the text is NOT in {native_language}, translate it to {native_language}.
    Maintain the original meaning, tone, and style as much as possible.""")

    if fix_grammar:
        system_prompt += dedent(f"""
            If the text is NOT in {native_language}, then additionally to translation, fix the grammar of the text.
            FORMAT:
            =======<translated_text>=======
            [translated_text]
            =======<fixed_text>=======
            [fixed_text]
            IF the text is in {native_language}, then only return the translated text, no explanations or other text.
            Only return the translated text (and fixed text, if applicable), no explanations or other text.""")
    else:
        system_prompt += "Only return the translated text, no explanations or other text."

    llm = ChatOpenAI(model="gpt-4o", temperature=0)

    messages = [SystemMessage(system_prompt), HumanMessage(text)]

    response = llm.invoke(messages)
    return response.content


def explain_word(
    word: str,
    native_language: str
) -> str:
    """Explains a word in the user's native language.

    Parameters:
        word: The word to be explained (can be in any language).
        native_language: The user's native language (e.g., "Spanish", "Russian").

    Returns:
        An explanation of the word in the user's native language.

    Examples:
        explain_word("algorithm", "Spanish") returns an explanation of "algorithm" in Spanish
        explain_word("récursion", "French") returns an explanation of "récursion" in French
    """
    system_message = SystemMessage(dedent(f"""You are a language teacher and word expert.
        Your task is to explain the meaning of the given word in {native_language}.
        Provide a clear definition, usage examples, and any relevant context.
        The explanation should be in {native_language} to help the user understand.
        The word could be from any language, so identify the language and explain accordingly.
        The exaplanation should have no more than 100 words,
        and start with the query word/phrase in that {native_language}."""))

    llm = ChatOpenAI(model="gpt-4o", temperature=0)

    messages = [system_message, HumanMessage(content=word)]

    response = llm.invoke(messages)
    return response.content

if __name__ == "__main__":
    original = "Hello world"
    translated = translate_text(original, "Spanish")
    print(f"Original: {original}")
    print(f"Translated: {translated}")

    original_fr = "Bonjour le monde"
    translated_from_fr = translate_text(original_fr, "English")
    print(f"Original: {original_fr}")
    print(f"Translated: {translated_from_fr}")
