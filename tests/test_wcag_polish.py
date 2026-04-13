"""Tests for recent WCAG-checker polish:

- Label-method breakdown surfaces in the details line
- Pass details include the breakdown when available
"""

from src.analysis.wcag_checker import check_form_labels


def _dom_with_labels(
    unlabelled_inputs: list = None,
    breakdown: dict = None,
    interactive_has_inputs: bool = True,
) -> dict:
    return {
        "html_structure": {
            "forms": {
                "inputs_without_labels": unlabelled_inputs or [],
                "selects_without_labels": [],
                "label_breakdown": breakdown or {},
            },
        },
        "interactive_elements": (
            [{"element": "input.x"}] if interactive_has_inputs else []
        ),
    }


def test_pass_shows_labelling_breakdown():
    dom = _dom_with_labels(
        breakdown={
            "with_label_element": 10,
            "with_aria_label": 3,
            "with_aria_labelledby": 0,
            "with_title": 0,
            "unlabelled": 0,
        },
    )
    result = check_form_labels(dom)
    assert result.status == "pass"
    assert "10 use <label>" in result.details
    assert "3 use aria-label" in result.details


def test_fail_shows_labelling_breakdown():
    dom = _dom_with_labels(
        unlabelled_inputs=[
            {"selector": "input.a", "type": "text", "placeholder": "email"},
            {"selector": "input.b", "type": "text", "placeholder": "pw"},
        ],
        breakdown={
            "with_label_element": 4,
            "with_aria_label": 2,
            "with_aria_labelledby": 0,
            "with_title": 0,
            "unlabelled": 2,
        },
    )
    result = check_form_labels(dom)
    assert result.status == "fail"
    assert "4 use <label>" in result.details
    assert "2 use aria-label" in result.details
    assert "2 unlabelled" in result.details


def test_title_attr_flagged_as_weak():
    dom = _dom_with_labels(
        breakdown={
            "with_label_element": 0,
            "with_aria_label": 0,
            "with_aria_labelledby": 0,
            "with_title": 5,
            "unlabelled": 0,
        },
    )
    result = check_form_labels(dom)
    # Not a violation (title IS a label), but the breakdown notes it's weak.
    assert result.status == "pass"
    assert "5 use title attr (weak)" in result.details


def test_pass_without_breakdown_keeps_clean_message():
    """Breakdown empty → original message unchanged."""
    dom = _dom_with_labels(breakdown={})
    result = check_form_labels(dom)
    assert result.status == "pass"
    assert "All form inputs have programmatic labels" in result.details
    assert "(" not in result.details.split("labels")[-1]


def test_na_when_no_inputs():
    dom = _dom_with_labels(interactive_has_inputs=False)
    result = check_form_labels(dom)
    assert result.status == "na"
