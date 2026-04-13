"""Tests for structural page fingerprinting (SPA crawl dedup)."""

from src.analysis.structural_fingerprint import (
    is_same_template,
    structural_fingerprint,
)


def _dom(
    *,
    landmarks=None,
    headings=None,
    inputs_unlabelled=None,
    interactive=None,
    font_sizes=None,
) -> dict:
    return {
        "html_structure": {
            "landmarks": landmarks or {},
            "headings": headings or [],
            "forms": {
                "inputs_without_labels": inputs_unlabelled or [],
                "selects_without_labels": [],
            },
        },
        "interactive_elements": interactive or [],
        "fonts": {"sizes": font_sizes or []},
    }


# ── Stability ──


def test_same_input_gives_same_fingerprint():
    dom = _dom(
        landmarks={"main": 1, "nav": 1, "header": 1, "footer": 1, "aside": 0},
        headings=[{"level": 1}, {"level": 2}, {"level": 2}, {"level": 3}],
        interactive=[{"element": "button.primary"}, {"element": "a.link"}],
        font_sizes=[{"size": "14px"}, {"size": "16px"}, {"size": "24px"}],
    )
    assert structural_fingerprint(dom) == structural_fingerprint(dom)


def test_fingerprint_is_16_chars():
    dom = _dom()
    fp = structural_fingerprint(dom)
    assert len(fp) == 16


def test_empty_dom_has_stable_fingerprint():
    fp1 = structural_fingerprint({})
    fp2 = structural_fingerprint({})
    assert fp1 == fp2


# ── Text content is ignored ──


def test_different_text_same_structure_same_fingerprint():
    dom_a = _dom(
        landmarks={"main": 1},
        headings=[{"level": 1, "text": "Program A"}, {"level": 2, "text": "Exercises"}],
        interactive=[{"element": "button.cta", "text": "Start session"}],
    )
    dom_b = _dom(
        landmarks={"main": 1},
        headings=[{"level": 1, "text": "Program B"}, {"level": 2, "text": "Sessions"}],
        interactive=[{"element": "button.cta", "text": "Begin"}],
    )
    assert structural_fingerprint(dom_a) == structural_fingerprint(dom_b)


def test_different_heading_sequence_different_fingerprint():
    dom_a = _dom(headings=[{"level": 1}, {"level": 2}, {"level": 2}])
    dom_b = _dom(headings=[{"level": 1}, {"level": 2}, {"level": 3}])
    assert structural_fingerprint(dom_a) != structural_fingerprint(dom_b)


# ── Landmark sensitivity ──


def test_missing_landmark_changes_fingerprint():
    dom_with_nav = _dom(landmarks={"main": 1, "nav": 1})
    dom_without_nav = _dom(landmarks={"main": 1, "nav": 0})
    assert structural_fingerprint(dom_with_nav) != structural_fingerprint(dom_without_nav)


def test_landmark_count_ignored_only_presence_matters():
    # One nav vs three navs: both "present" → same fingerprint.
    dom_one = _dom(landmarks={"main": 1, "nav": 1})
    dom_three = _dom(landmarks={"main": 1, "nav": 3})
    assert structural_fingerprint(dom_one) == structural_fingerprint(dom_three)


# ── Interactive bucketing ──


def test_interactive_count_bucketed():
    """5 buttons and 4 buttons should fingerprint the same (both in 1-5 bucket)."""
    dom_5 = _dom(interactive=[{"element": "button.a"}] * 5)
    dom_4 = _dom(interactive=[{"element": "button.a"}] * 4)
    assert structural_fingerprint(dom_5) == structural_fingerprint(dom_4)


def test_interactive_buckets_cross_boundary():
    """5 buttons vs 6 buttons straddles the 1-5 / 6-15 boundary."""
    dom_5 = _dom(interactive=[{"element": "button.x"}] * 5)
    dom_6 = _dom(interactive=[{"element": "button.x"}] * 6)
    assert structural_fingerprint(dom_5) != structural_fingerprint(dom_6)


def test_interactive_tag_distribution_matters():
    # Different tags → different structure.
    dom_buttons = _dom(interactive=[{"element": "button.a"}] * 3)
    dom_links = _dom(interactive=[{"element": "a.link"}] * 3)
    assert structural_fingerprint(dom_buttons) != structural_fingerprint(dom_links)


# ── Form inputs ──


def test_form_inputs_contribute():
    dom_no_form = _dom()
    dom_with_form = _dom(interactive=[
        {"element": "input.email"}, {"element": "input.password"},
    ])
    assert structural_fingerprint(dom_no_form) != structural_fingerprint(dom_with_form)


# ── Typography scale ──


def test_more_font_sizes_different_fingerprint():
    dom_narrow = _dom(font_sizes=[{"size": "14px"}, {"size": "16px"}])
    dom_wide = _dom(font_sizes=[{"size": f"{i}px"} for i in range(10, 25)])
    assert structural_fingerprint(dom_narrow) != structural_fingerprint(dom_wide)


# ── Template detection scenario ──


def test_template_detection_for_detail_pages():
    """Two 'program detail' pages should share a fingerprint."""
    def _detail_dom(title_text: str, button_text: str):
        return _dom(
            landmarks={"main": 1, "nav": 1, "header": 1},
            headings=[
                {"level": 1, "text": title_text},
                {"level": 2, "text": "Exercises"},
                {"level": 2, "text": "Sessions"},
            ],
            interactive=[
                {"element": "button.start", "text": button_text},
                {"element": "a.back", "text": "Back"},
                {"element": "button.edit", "text": "Edit"},
            ],
            font_sizes=[{"size": "14px"}, {"size": "16px"}, {"size": "24px"}],
        )

    program_a = _detail_dom("Program A", "Start session")
    program_b = _detail_dom("Program B", "Begin")
    program_c = _detail_dom("Program Z", "Resume")
    assert structural_fingerprint(program_a) == structural_fingerprint(program_b)
    assert structural_fingerprint(program_a) == structural_fingerprint(program_c)


def test_template_detection_differentiates_list_vs_detail():
    """A list page and a detail page should NOT fingerprint the same."""
    list_dom = _dom(
        landmarks={"main": 1, "nav": 1},
        headings=[{"level": 1, "text": "Programs"}],
        interactive=[{"element": "a.card"}] * 10,
    )
    detail_dom = _dom(
        landmarks={"main": 1, "nav": 1, "header": 1},
        headings=[{"level": 1}, {"level": 2}, {"level": 2}],
        interactive=[{"element": "button.cta"}, {"element": "a.back"}],
    )
    assert structural_fingerprint(list_dom) != structural_fingerprint(detail_dom)


# ── Helper ──


def test_is_same_template():
    fp_a = "abc123def456"
    fp_b = "abc123def456"
    fp_c = "xyz789"
    assert is_same_template(fp_a, fp_b)
    assert not is_same_template(fp_a, fp_c)
