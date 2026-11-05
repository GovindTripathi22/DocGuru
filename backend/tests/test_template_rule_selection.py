import pytest
from pydantic import ValidationError

from backend.app.jobs.manager import select_enabled_template_rules
from backend.app.models.generation import GenerationRequest
from backend.app.models.template_spec import TemplateSpecification


def test_selected_template_rules_are_resolved_from_server_template_and_do_not_mutate_it():
    spec = TemplateSpecification(
        filename="template.docx",
        document_type="docx",
        extracted_rules=[
            "Use numbered references.",
            "Include a glossary.",
            "Use neutral language.",
        ],
    )

    selected = select_enabled_template_rules(spec, [0, 2])

    assert selected.extracted_rules == ["Use numbered references.", "Use neutral language."]
    assert spec.extracted_rules == [
        "Use numbered references.",
        "Include a glossary.",
        "Use neutral language.",
    ]


def test_empty_selection_disables_template_rules_but_omission_is_legacy_compatible():
    spec = TemplateSpecification(
        filename="template.docx", document_type="docx", extracted_rules=["Use numbered references."]
    )

    assert select_enabled_template_rules(spec, []).extracted_rules == []
    assert select_enabled_template_rules(spec, None) is spec


@pytest.mark.parametrize("indexes", [[0, 0], [-1], [12], list(range(13))])
def test_request_rejects_duplicate_out_of_range_or_excessive_rule_indexes(indexes):
    with pytest.raises(ValidationError):
        GenerationRequest(
            template_id="a" * 32,
            prompt="topic",
            enabled_rule_indices=indexes,
        )
