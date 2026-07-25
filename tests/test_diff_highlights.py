from src.tools.llm_tools import _apply_diff_highlights


def test_replaced_word_includes_original_wording():
    result = _apply_diff_highlights(
        "I has a dog",
        "I have a dog"
    )

    assert result == (
        'I <span class="original-wording"><s>has</s> </span>'
        '<b>have</b> a dog'
    )


def test_consecutive_replaced_words_use_one_annotation():
    result = _apply_diff_highlights(
        "This is very bad",
        "This is quite good"
    )

    assert result == (
        'This is <span class="original-wording">'
        '<s>very bad</s> </span><b>quite good</b>'
    )


def test_added_punctuation_has_no_original_annotation():
    result = _apply_diff_highlights(
        "Hello world",
        "Hello, world."
    )

    assert result == "Hello<b>,</b> world."
    assert "original-wording" not in result


def test_removed_punctuation_has_no_original_annotation():
    result = _apply_diff_highlights(
        "Hello, world!",
        "Hello world"
    )

    assert result == "Hello world"
    assert "original-wording" not in result

