from hypothesis import given, settings
from hypothesis import strategies as st

from backend.app.ai.content_fitter import ContentFitter
from backend.app.models.generation import DocumentPlan, DocumentSection


@settings(max_examples=40, deadline=None)
@given(st.lists(st.integers(min_value=20, max_value=30), min_size=8, max_size=8))
def test_sentence_fitting_preserves_text_and_only_splits_at_sentence_boundaries(
    sentence_lengths: list[int],
) -> None:
    sentences = [
        " ".join(f"word{sentence_index}_{word_index}" for word_index in range(length)) + "."
        for sentence_index, length in enumerate(sentence_lengths)
    ]
    paragraph = " ".join(sentences)

    chunks = ContentFitter._split_paragraph_at_sentences(paragraph)

    assert "".join(chunks) == paragraph
    assert all(chunk.rstrip().endswith(".") for chunk in chunks[:-1])


def test_overlong_single_sentence_uses_clause_boundaries_and_warns() -> None:
    words = [f"term{index}" for index in range(360)]
    for index in (39, 79, 119, 159, 199, 239, 279, 319):
        words[index] += ","
    words[-1] += "."
    paragraph = " ".join(words)
    plan = DocumentPlan(
        title="Long sentence",
        sections=[DocumentSection(title="Details", paragraphs=[paragraph])],
    )

    fitted = ContentFitter.fit_document_plan(plan)

    chunks = fitted.sections[0].paragraphs
    assert "".join(chunks) == paragraph
    assert all(chunk.rstrip().endswith(",") for chunk in chunks[:-1])
    assert "long_sentence_split_at_clause_boundary" in fitted.warnings


def test_unbreakable_long_sentence_is_preserved_and_warned() -> None:
    paragraph = " ".join(f"term{index}" for index in range(310)) + "."
    plan = DocumentPlan(
        title="Long sentence",
        sections=[DocumentSection(title="Details", paragraphs=[paragraph])],
    )

    fitted = ContentFitter.fit_document_plan(plan)

    chunks = fitted.sections[0].paragraphs
    assert "".join(chunks) == paragraph
    assert "long_sentence_split_at_word_boundary" in fitted.warnings
