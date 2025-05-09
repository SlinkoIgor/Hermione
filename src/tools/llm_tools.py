from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from textwrap import dedent


def translate_text(
    text: str,
    native_language: str,
    target_language: str,
    is_native_language: bool
) -> str:
    """Translates text to the specified target language.

    Parameters:
        text: The text to be translated.
        native_language: The user's native language (e.g., "English", "Spanish", "Russian").
        target_language: The target language for translation (e.g., "English", "Spanish", "Russian").
        is_native_language: Whether the text is in the native language (True or False).
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
    Preserve the original line breaks in the text.

    If it's a word (or two words) not a text, then return 1 main translation and 2 possible translations with the following format:
    main_translation
    [possible_translation_1, possible_translation_2]""")

    llm = ChatOpenAI(model="gpt-4o", temperature=0)

    messages = [SystemMessage(system_prompt), HumanMessage(text)]

    response = llm.invoke(messages)
    return response.content


def fix_text(
    text: str,
) -> str:
    """Fixes grammar in the original text.

    Parameters:
        text: The text to be fixed.
        language: The language of the input text.
    Returns:
        The text with grammar fixes.
    """
    system_prompt = dedent(f"""You are a professional grammar editor.
    Fix any grammar, spelling, or punctuation errors in the text.
    Maintain the original meaning, tone, and style as much as possible.
    For every word where you make a change (spelling, words order, words deletion, words addition) put it in <b>tags</b>.
    If you've changed the capital letter, make only this letter in <b>tags</b>.
    If you added punctuation, make only this punctuation in <b>tags</b>.
    Preserve the original line breaks in the text.
    Only return the fixed text, no explanations or other text.""")

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

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    messages = [system_message, HumanMessage(content=word)]

    response = llm.invoke(messages)
    return response.content


def text_summarization(
    text: str,
    native_language: str
) -> str:
    """Summarizes text into a TL;DR in the native language.

    Parameters:
        text: The text to be summarized.
        native_language: The user's native language (e.g., "English", "Spanish", "Russian").
    Returns:
        A concise summary of the text in the native language.

    Examples:
        text_summarization("Long text...", "English") returns "Summary in English"
    """
    system_prompt = dedent(f"""You are a professional summarizer.
    Create a concise TL;DR summary of the given text in {native_language}.
    The summary should be no more than 2-3 (!!!!TWO or THREE!!!!) sentences and capture the main points.
    Only return the summary, no explanations or other text.""")

    llm = ChatOpenAI(model="gpt-4o", temperature=0)

    messages = [SystemMessage(system_prompt), HumanMessage(text)]

    response = llm.invoke(messages)
    return response.content


def generate_bash_command(
    text: str
) -> str:
    """Generates a bash command based on text input.

    Parameters:
        text: Either an incorrect bash command or a natural language description
             of what the user wants to do with bash.
    Returns:
        A valid one-liner bash command. If the command contains dangerous operations
        (like rm, mv), a warning about the risks will be included.

    Examples:
        generate_bash_command("list all files in current directory") returns "ls -la"
        generate_bash_command("rm -rf *") returns "rm -rf *\nWARNING: This command will permanently delete all files in the current directory without confirmation. Use with extreme caution."
    """
    system_prompt = dedent(f"""You are a bash command expert.
    Generate a valid one-liner bash command based on the input.
    The input could be either an incorrect bash command or a natural language description.
    If the command contains dangerous operations (like rm, mv, etc.),
    add a warning about the risks in the next separate line, starting with #.
    Only return the command and warning (if applicable), no explanations or other text.
    The command must be a one-liner.""")

    llm = ChatOpenAI(model="gpt-4o", temperature=0)

    messages = [SystemMessage(system_prompt), HumanMessage(text)]

    response = llm.invoke(messages)
    response_content = response.content
    if response_content.startswith("```bash"):
        response_content = response_content[len("```bash"):].strip()
    if response_content.endswith("```"):
        response_content = response_content[:-3].strip()
    response.content = response_content
    return response.content


if __name__ == "__main__":
    original = "Hello world"
    translated = translate_text(original, "Spanish", "Spanish", True)
    print(f"Original: {original}")
    print(f"Translated: {translated}")

    original_fr = "Bonjour le monde"
    translated_from_fr = translate_text(original_fr, "English", "German", False)
    print(f"Original: {original_fr}")
    print(f"Translated: {translated_from_fr}")
