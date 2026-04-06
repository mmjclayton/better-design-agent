"""Tests for the opinionated UI review analyser."""

import json


from src.analysis.ui_review import (  # noqa: F401
    WEIGHTS,
    CategoryScore,
    ResponsiveReport,
    TokenAudit,
    UIReviewReport,
    _check_modular_scale,
    _cluster_colors,
    _grid_adherence,
    _parse_px,
    _score_color,
    _score_copy,
    _score_hierarchy,
    _score_interactive,
    _score_patterns,
    _score_spacing,
    _score_typography,
    audit_tokens,
    get_llm_suggestions,
    run_ui_review,
)


# ── Test helpers ──


def _dom(
    *,
    fonts_families=None,
    fonts_sizes=None,
    colors_text=None,
    colors_bg=None,
    spacing_values=None,
    interactive_elements=None,
    state_tests=None,
    headings=None,
    landmarks=None,
    layout=None,
):
    return {
        "fonts": {
            "families": fonts_families or [],
            "sizes": fonts_sizes or [],
        },
        "colors": {
            "text": colors_text or [],
            "background": colors_bg or [],
        },
        "spacing_values": spacing_values or [],
        "interactive_elements": interactive_elements or [],
        "state_tests": state_tests or [],
        "html_structure": {
            "headings": headings or [],
            "landmarks": landmarks or {"main": 1, "nav": 1, "header": 1, "footer": 1},
        },
        "layout": layout or {
            "viewport_width": 1440,
            "viewport_height": 900,
            "body_font_size": "16px",
            "body_line_height": "24px",
            "body_font_family": "Inter",
            "body_bg": "#ffffff",
        },
    }


# ── parse_px ──


def test_parse_px_basic():
    assert _parse_px("16px") == 16.0
    assert _parse_px("14.5px") == 14.5


def test_parse_px_invalid():
    assert _parse_px("") is None
    assert _parse_px("1rem") is None
    assert _parse_px(None) is None


# ── modular scale ──


def test_modular_scale_perfect_1_25():
    # 16 * 1.25^n = 16, 20, 25, 31.25
    sizes = [16, 20, 25, 31.25]
    ratio, count = _check_modular_scale(sizes)
    assert ratio == 1.25
    assert count == 4


def test_modular_scale_too_few():
    ratio, count = _check_modular_scale([16, 20])
    assert ratio is None


def test_modular_scale_random():
    sizes = [11, 17, 23, 37, 41]
    ratio, count = _check_modular_scale(sizes)
    # Few should be on any scale
    assert count < len(sizes)


# ── grid adherence ──


def test_grid_adherence_perfect_8px():
    values = [8, 16, 24, 32, 48]
    assert _grid_adherence(values, 8) == 1.0


def test_grid_adherence_mixed():
    values = [8, 16, 15, 24, 13]
    adherence = _grid_adherence(values, 8)
    assert 0.3 < adherence < 0.7


def test_grid_adherence_empty():
    assert _grid_adherence([], 4) == 1.0


# ── Typography scoring ──


def test_typography_clean_scores_high():
    dom = _dom(
        fonts_families=[
            {"family": "Inter", "count": 100},
            {"family": "monospace", "count": 10},
        ],
        fonts_sizes=[
            {"size": "14px", "count": 20},
            {"size": "16px", "count": 100},
            {"size": "20px", "count": 30},
            {"size": "24px", "count": 15},
            {"size": "32px", "count": 8},
        ],
    )
    result = _score_typography(dom)
    assert result.score >= 80
    assert result.name == "typography"


def test_typography_too_many_families():
    families = [{"family": f"Font{i}", "count": 10} for i in range(6)]
    dom = _dom(fonts_families=families)
    result = _score_typography(dom)
    assert result.score < 80
    high_findings = [f for f in result.findings if f.severity == "high"]
    assert len(high_findings) >= 1


def test_typography_too_many_sizes():
    sizes = [{"size": f"{10+i}px", "count": 5} for i in range(15)]
    dom = _dom(fonts_sizes=sizes)
    result = _score_typography(dom)
    assert result.score <= 80
    assert any("font size" in f.message.lower() for f in result.findings)


def test_typography_tight_line_height():
    dom = _dom(layout={
        "viewport_width": 1440, "viewport_height": 900,
        "body_font_size": "16px", "body_line_height": "18px",
        "body_font_family": "Inter", "body_bg": "#fff",
    })
    result = _score_typography(dom)
    assert any("line-height" in f.message.lower() for f in result.findings)


def test_typography_small_body_font():
    dom = _dom(layout={
        "viewport_width": 1440, "viewport_height": 900,
        "body_font_size": "12px", "body_line_height": "18px",
        "body_font_family": "Inter", "body_bg": "#fff",
    })
    result = _score_typography(dom)
    assert any("body font size" in f.message.lower() for f in result.findings)


# ── Color scoring ──


def test_color_clean_palette():
    dom = _dom(
        colors_text=[
            {"color": "#111", "count": 100},
            {"color": "#666", "count": 50},
            {"color": "#0066cc", "count": 20},
        ],
        colors_bg=[
            {"color": "#fff", "count": 100},
            {"color": "#f5f5f5", "count": 30},
        ],
    )
    result = _score_color(dom)
    assert result.score >= 85


def test_color_too_many_text_colors():
    text_colors = [{"color": f"#{i:06x}", "count": 5} for i in range(15)]
    dom = _dom(colors_text=text_colors)
    result = _score_color(dom)
    assert result.score < 70
    assert any("text colour" in f.message.lower() for f in result.findings)


def test_color_one_off_penalty():
    text_colors = [{"color": f"#{i:06x}", "count": 1} for i in range(8)]
    dom = _dom(colors_text=text_colors)
    result = _score_color(dom)
    assert any("only once" in f.message.lower() for f in result.findings)


def test_color_no_dominant():
    text_colors = [{"color": f"#{i:06x}", "count": 10} for i in range(5)]
    dom = _dom(colors_text=text_colors)
    result = _score_color(dom)
    assert any("dominant" in f.message.lower() for f in result.findings)


# ── Spacing scoring ──


def test_spacing_clean_grid():
    dom = _dom(spacing_values=[
        {"value": "8px", "count": 30},
        {"value": "16px", "count": 50},
        {"value": "24px", "count": 20},
        {"value": "32px", "count": 10},
        {"value": "48px", "count": 5},
    ])
    result = _score_spacing(dom)
    assert result.score >= 85


def test_spacing_too_many_values():
    values = [{"value": f"{i}px", "count": 3} for i in range(1, 25)]
    dom = _dom(spacing_values=values)
    result = _score_spacing(dom)
    assert result.score < 60
    assert any("distinct spacing" in f.message.lower() for f in result.findings)


def test_spacing_poor_grid_adherence():
    values = [
        {"value": "7px", "count": 10},
        {"value": "13px", "count": 8},
        {"value": "19px", "count": 6},
        {"value": "23px", "count": 5},
        {"value": "37px", "count": 3},
        {"value": "41px", "count": 2},
    ]
    dom = _dom(spacing_values=values)
    result = _score_spacing(dom)
    assert any("grid" in f.message.lower() for f in result.findings)


def test_spacing_empty():
    dom = _dom(spacing_values=[])
    result = _score_spacing(dom)
    assert result.score == 50  # default for no data


# ── Interactive scoring ──


def test_interactive_all_good():
    elements = [
        {"element": "button.primary", "text": "Submit", "width": 120, "height": 48,
         "meets_touch_target": True, "has_aria_label": False, "has_visible_label": True},
        {"element": "button.secondary", "text": "Cancel", "width": 100, "height": 48,
         "meets_touch_target": True, "has_aria_label": False, "has_visible_label": True},
    ]
    state_tests = [
        {"selector": "button.primary",
         "default_state": {"backgroundColor": "#0066cc", "color": "#fff"},
         "hover_state": {"backgroundColor": "#0055aa", "color": "#fff"}},
        {"selector": "button.secondary",
         "default_state": {"backgroundColor": "#eee", "color": "#333"},
         "hover_state": {"backgroundColor": "#ddd", "color": "#333"}},
    ]
    dom = _dom(interactive_elements=elements, state_tests=state_tests)
    result = _score_interactive(dom)
    assert result.score >= 80


def test_interactive_undersized_targets():
    elements = [
        {"element": "a.link", "text": "Click", "width": 30, "height": 20,
         "meets_touch_target": False, "has_aria_label": False, "has_visible_label": True},
        {"element": "a.link2", "text": "More", "width": 25, "height": 18,
         "meets_touch_target": False, "has_aria_label": False, "has_visible_label": True},
        {"element": "a.link3", "text": "Go", "width": 20, "height": 15,
         "meets_touch_target": False, "has_aria_label": False, "has_visible_label": True},
    ]
    # Use mobile viewport so 44px threshold applies
    dom = _dom(interactive_elements=elements, layout={
        "viewport_width": 390, "viewport_height": 844,
        "body_font_size": "16px", "body_line_height": "24px",
        "body_font_family": "Inter", "body_bg": "#ffffff",
    })
    result = _score_interactive(dom)
    assert result.score < 80
    assert any("touch target" in f.message.lower() or "44x44" in f.message for f in result.findings)


def test_interactive_no_hover_states():
    elements = [
        {"element": "button.btn", "text": "Go", "width": 100, "height": 44,
         "meets_touch_target": True, "has_aria_label": False, "has_visible_label": True},
    ]
    state_tests = [
        {"selector": "button.btn",
         "default_state": {"backgroundColor": "#0066cc", "color": "#fff"},
         "hover_state": {"backgroundColor": "#0066cc", "color": "#fff"}},
    ]
    dom = _dom(interactive_elements=elements, state_tests=state_tests)
    result = _score_interactive(dom)
    assert any("hover" in f.message.lower() for f in result.findings)


def test_interactive_unlabelled():
    elements = [
        {"element": "button.icon", "text": "", "width": 44, "height": 44,
         "meets_touch_target": True, "has_aria_label": False, "has_visible_label": False},
    ]
    dom = _dom(interactive_elements=elements)
    result = _score_interactive(dom)
    assert any("label" in f.message.lower() for f in result.findings)


def test_interactive_empty():
    dom = _dom(interactive_elements=[])
    result = _score_interactive(dom)
    assert result.score == 50


# ── Hierarchy scoring ──


def test_hierarchy_good_structure():
    dom = _dom(
        headings=[
            {"level": 1, "text": "Welcome"},
            {"level": 2, "text": "Features"},
            {"level": 2, "text": "Pricing"},
            {"level": 3, "text": "Starter"},
            {"level": 3, "text": "Pro"},
        ],
        landmarks={"main": 1, "nav": 1, "header": 1, "footer": 1},
        interactive_elements=[
            {"element": "button.cta", "text": "Get Started", "width": 200, "height": 56,
             "meets_touch_target": True, "has_aria_label": False, "has_visible_label": True},
            {"element": "a.nav-link", "text": "About", "width": 60, "height": 24,
             "meets_touch_target": False, "has_aria_label": False, "has_visible_label": True},
        ],
    )
    result = _score_hierarchy(dom)
    assert result.score >= 80


def test_hierarchy_no_h1():
    dom = _dom(headings=[{"level": 2, "text": "Section"}])
    result = _score_hierarchy(dom)
    assert any("h1" in f.message.lower() for f in result.findings)


def test_hierarchy_multiple_h1():
    dom = _dom(headings=[
        {"level": 1, "text": "Title 1"},
        {"level": 1, "text": "Title 2"},
    ])
    result = _score_hierarchy(dom)
    assert any("h1" in f.message.lower() and "competing" in f.message.lower() for f in result.findings)


def test_hierarchy_level_gap():
    dom = _dom(headings=[
        {"level": 1, "text": "Title"},
        {"level": 3, "text": "Subsection"},
    ])
    result = _score_hierarchy(dom)
    assert any("gap" in f.message.lower() for f in result.findings)


def test_hierarchy_no_main_landmark():
    dom = _dom(landmarks={"main": 0, "nav": 1, "header": 1, "footer": 1})
    result = _score_hierarchy(dom)
    assert any("main" in f.message.lower() for f in result.findings)


# ── Pattern scoring ──


def _dom_with_form(input_count, unlabelled=0):
    """Build DOM data with a form of given complexity."""
    breakdown = {
        "with_label_element": input_count - unlabelled,
        "with_aria_label": 0,
        "with_aria_labelledby": 0,
        "with_title": 0,
        "unlabelled": unlabelled,
    }
    inputs_without = [{"type": "text", "placeholder": f"field{i}"} for i in range(unlabelled)]
    return _dom(
        headings=[{"level": 1, "text": "Form Page"}],
    ) | {
        "html_structure": {
            "headings": [{"level": 1, "text": "Form Page"}],
            "landmarks": {"main": 1, "nav": 1, "header": 1, "footer": 1},
            "forms": {
                "inputs_without_labels": inputs_without,
                "selects_without_labels": [],
                "label_breakdown": breakdown,
            },
            "aria_usage": {"roles": [], "labels": 0, "described_by": 0, "live_regions": 0},
            "images_without_alt": 0,
            "title": "Test Page",
        },
    }


def test_patterns_clean_page():
    dom = _dom()
    result = _score_patterns(dom)
    assert result.score >= 80
    assert result.name == "patterns"


def test_patterns_too_many_form_fields():
    dom = _dom_with_form(12)
    result = _score_patterns(dom)
    assert any("form" in f.message.lower() and "field" in f.message.lower() for f in result.findings)
    assert result.score < 90


def test_patterns_unlabelled_inputs():
    dom = _dom_with_form(5, unlabelled=3)
    result = _score_patterns(dom)
    assert any("no label" in f.message.lower() for f in result.findings)


def test_patterns_images_without_alt():
    dom = _dom()
    dom["html_structure"]["images_without_alt"] = 5
    result = _score_patterns(dom)
    assert any("alt" in f.message.lower() for f in result.findings)


def test_patterns_too_many_links():
    links = [
        {"element": f"a.link{i}", "text": f"Link {i}", "width": 60, "height": 24,
         "meets_touch_target": False, "has_aria_label": False, "has_visible_label": True}
        for i in range(15)
    ]
    dom = _dom(interactive_elements=links)
    result = _score_patterns(dom)
    assert any("link" in f.message.lower() for f in result.findings)


def test_patterns_button_with_navigation_label():
    elements = [
        {"element": "button.btn", "text": "Read more", "width": 100, "height": 40,
         "meets_touch_target": False, "has_aria_label": False, "has_visible_label": True},
    ]
    dom = _dom(interactive_elements=elements)
    result = _score_patterns(dom)
    assert any("navigation" in f.message.lower() or "link" in f.message.lower() for f in result.findings)


# ── Copy scoring ──


def test_copy_clean_labels():
    elements = [
        {"element": "button.primary", "text": "Create account", "width": 120, "height": 44,
         "meets_touch_target": True, "has_aria_label": False, "has_visible_label": True},
        {"element": "button.secondary", "text": "View pricing", "width": 100, "height": 44,
         "meets_touch_target": True, "has_aria_label": False, "has_visible_label": True},
        {"element": "a.nav", "text": "Download app", "width": 80, "height": 24,
         "meets_touch_target": False, "has_aria_label": False, "has_visible_label": True},
    ]
    dom = _dom(interactive_elements=elements)
    result = _score_copy(dom)
    assert result.score >= 80
    assert result.name == "copy"


def test_copy_generic_labels():
    elements = [
        {"element": "button.btn1", "text": "Submit", "width": 100, "height": 44,
         "meets_touch_target": True, "has_aria_label": False, "has_visible_label": True},
        {"element": "a.link1", "text": "Click here", "width": 60, "height": 24,
         "meets_touch_target": False, "has_aria_label": False, "has_visible_label": True},
        {"element": "button.btn2", "text": "OK", "width": 50, "height": 44,
         "meets_touch_target": True, "has_aria_label": False, "has_visible_label": True},
    ]
    dom = _dom(interactive_elements=elements)
    result = _score_copy(dom)
    assert any("generic" in f.message.lower() for f in result.findings)
    assert result.score < 90


def test_copy_noun_labels():
    elements = [
        {"element": "button.btn1", "text": "Account", "width": 100, "height": 44,
         "meets_touch_target": True, "has_aria_label": False, "has_visible_label": True},
        {"element": "button.btn2", "text": "Settings", "width": 100, "height": 44,
         "meets_touch_target": True, "has_aria_label": False, "has_visible_label": True},
        {"element": "button.btn3", "text": "Dashboard", "width": 100, "height": 44,
         "meets_touch_target": True, "has_aria_label": False, "has_visible_label": True},
        {"element": "button.btn4", "text": "Profile", "width": 100, "height": 44,
         "meets_touch_target": True, "has_aria_label": False, "has_visible_label": True},
    ]
    dom = _dom(interactive_elements=elements)
    result = _score_copy(dom)
    assert any("verb" in f.message.lower() for f in result.findings)


def test_copy_duplicate_labels():
    elements = [
        {"element": f"button.btn{i}", "text": "Edit", "width": 60, "height": 32,
         "meets_touch_target": False, "has_aria_label": False, "has_visible_label": True}
        for i in range(4)
    ]
    dom = _dom(interactive_elements=elements)
    result = _score_copy(dom)
    assert any("repeated" in f.message.lower() or "duplicate" in f.message.lower() for f in result.findings)


def test_copy_long_headings():
    dom = _dom(headings=[
        {"level": 1, "text": "This is an extremely long heading that goes on and on and really should have been shorter for readability"},
    ])
    result = _score_copy(dom)
    assert any("heading" in f.message.lower() and "60" in f.message for f in result.findings)


def test_copy_all_caps_heading():
    dom = _dom(headings=[
        {"level": 1, "text": "WELCOME TO OUR WEBSITE"},
    ])
    result = _score_copy(dom)
    assert any("caps" in f.message.lower() for f in result.findings)


def test_copy_no_page_title():
    dom = _dom()
    dom["html_structure"]["title"] = ""
    result = _score_copy(dom)
    assert any("title" in f.message.lower() for f in result.findings)


def test_copy_long_page_title():
    dom = _dom()
    dom["html_structure"]["title"] = "A" * 80
    result = _score_copy(dom)
    assert any("title" in f.message.lower() and "truncated" in f.message.lower() for f in result.findings)


# ── Overall report ──


def test_run_ui_review_returns_all_categories():
    dom = _dom()
    report = run_ui_review(dom)
    names = {c.name for c in report.categories}
    assert names == set(WEIGHTS.keys())


def test_run_ui_review_empty_dom():
    report = run_ui_review({})
    assert report.overall_score >= 0
    assert len(report.categories) == len(WEIGHTS)


def test_run_ui_review_none_dom():
    report = run_ui_review(None)
    assert report.overall_score == 0


def test_overall_score_weighted():
    report = UIReviewReport(categories=[
        CategoryScore(name="typography", score=100),
        CategoryScore(name="color", score=100),
        CategoryScore(name="spacing", score=100),
        CategoryScore(name="interactive", score=100),
        CategoryScore(name="hierarchy", score=100),
        CategoryScore(name="patterns", score=100),
        CategoryScore(name="copy", score=100),
    ])
    assert report.overall_score == 100.0


def test_overall_score_weighted_partial():
    report = UIReviewReport(categories=[
        CategoryScore(name="typography", score=50),
        CategoryScore(name="color", score=50),
        CategoryScore(name="spacing", score=50),
        CategoryScore(name="interactive", score=50),
        CategoryScore(name="hierarchy", score=50),
        CategoryScore(name="patterns", score=50),
        CategoryScore(name="copy", score=50),
    ])
    assert report.overall_score == 50.0


def test_category_score_clamped():
    cs = CategoryScore(name="test", score=120)
    assert cs.score == 100
    cs2 = CategoryScore(name="test", score=-10)
    assert cs2.score == 0


# ── Report output ──


def test_to_dict_schema():
    dom = _dom()
    report = run_ui_review(dom)
    d = report.to_dict()
    assert "schema_version" in d
    assert d["schema_version"] == 1
    assert "overall_score" in d
    assert "categories" in d
    assert "llm_suggestions" in d
    for name in WEIGHTS:
        assert name in d["categories"]
        cat = d["categories"][name]
        assert "score" in cat
        assert "weight" in cat
        assert "findings" in cat


def test_to_markdown_structure():
    dom = _dom(
        fonts_families=[{"family": f"Font{i}", "count": 5} for i in range(6)],
    )
    report = run_ui_review(dom)
    md = report.to_markdown()
    assert "UI Review" in md
    assert "Overall score" in md
    assert "Typography" in md
    assert "Color" in md
    assert "Spacing" in md
    assert "Interactive" in md
    assert "Hierarchy" in md
    assert "Patterns" in md
    assert "Copy" in md


def test_to_markdown_with_llm_suggestions():
    report = UIReviewReport(
        categories=[CategoryScore(name="typography", score=80)],
        llm_suggestions=[
            {"title": "Fix layout", "rationale": "It's off", "action": "Adjust grid"},
        ],
    )
    md = report.to_markdown()
    assert "Fix layout" in md
    assert "Design Suggestions" in md


def test_to_dict_json_serialisable():
    dom = _dom(
        fonts_families=[{"family": "Inter", "count": 50}],
        fonts_sizes=[{"size": "16px", "count": 100}],
    )
    report = run_ui_review(dom)
    # Should not raise
    serialised = json.dumps(report.to_dict())
    parsed = json.loads(serialised)
    assert isinstance(parsed["overall_score"], (int, float))


# ── LLM suggestions (mocked) ──


def test_get_llm_suggestions_returns_list_on_failure(monkeypatch):
    """When the LLM call fails, should return empty list, not raise."""
    def _boom(*a, **kw):
        raise RuntimeError("LLM unavailable")

    monkeypatch.setattr("src.providers.llm.call_llm", _boom)
    dom = _dom()
    report = run_ui_review(dom)
    result = get_llm_suggestions(report, None, dom)
    assert result == []


def test_get_llm_suggestions_parses_json(monkeypatch):
    """When LLM returns valid JSON, should parse it."""
    suggestions = [
        {"title": "Fix spacing", "rationale": "Too tight", "action": "Use 8px grid"},
    ]

    def _mock_llm(*a, **kw):
        return json.dumps(suggestions)

    monkeypatch.setattr("src.providers.llm.call_llm", _mock_llm)
    dom = _dom()
    report = run_ui_review(dom)
    result = get_llm_suggestions(report, "/tmp/fake.png", dom)
    assert len(result) == 1
    assert result[0]["title"] == "Fix spacing"


def test_get_llm_suggestions_handles_code_fence(monkeypatch):
    """When LLM wraps JSON in code fences, should still parse."""
    suggestions = [{"title": "Test", "rationale": "R", "action": "A"}]

    def _mock_llm(*a, **kw):
        return f"```json\n{json.dumps(suggestions)}\n```"

    monkeypatch.setattr("src.providers.llm.call_llm", _mock_llm)
    dom = _dom()
    report = run_ui_review(dom)
    result = get_llm_suggestions(report, None, dom)
    assert len(result) == 1


# ── 60-30-10 colour rule ──


def test_color_surface_variety_low():
    """Only one bg colour used more than once should flag low surface variety."""
    bg_colors = [
        {"color": "#fff", "count": 100},
        {"color": "#f5f5f5", "count": 1},
        {"color": "#eee", "count": 1},
    ]
    dom = _dom(colors_bg=bg_colors)
    result = _score_color(dom)
    assert any("surface" in f.message.lower() for f in result.findings)


def test_color_surface_variety_good():
    """Multiple bg colours with meaningful usage should not flag."""
    bg_colors = [
        {"color": "#fff", "count": 100},
        {"color": "#f5f5f5", "count": 30},
        {"color": "#eee", "count": 10},
    ]
    dom = _dom(colors_bg=bg_colors)
    result = _score_color(dom)
    assert not any("surface" in f.message.lower() and "depth" in f.message.lower() for f in result.findings)


# ── Spacing range ──


def test_spacing_narrow_range():
    dom = _dom(spacing_values=[
        {"value": "4px", "count": 20},
        {"value": "6px", "count": 15},
        {"value": "8px", "count": 10},
    ])
    result = _score_spacing(dom)
    assert any("narrow" in f.message.lower() or "range" in f.message.lower() for f in result.findings)


# ── Token audit ──


def _dom_with_tokens(**extra):
    """DOM data with CSS custom properties defined."""
    base = _dom()
    base["css_tokens"] = {
        "color": [
            {"name": "--color-bg-base", "value": "#0f1117"},
            {"name": "--color-bg-surface", "value": "#1a1d27"},
            {"name": "--color-text-primary", "value": "#e1e4ed"},
            {"name": "--color-accent", "value": "#4f46e5"},
        ],
        "spacing": [
            {"name": "--space-sm", "value": "8px"},
            {"name": "--space-md", "value": "16px"},
            {"name": "--space-lg", "value": "24px"},
        ],
        "font": [
            {"name": "--font-size-base", "value": "16px"},
        ],
    }
    base.update(extra)
    return base


def test_audit_tokens_with_existing_system():
    dom = _dom_with_tokens()
    result = audit_tokens(dom)
    assert result.has_token_system is True
    assert result.token_count == 8  # 4 color + 3 spacing + 1 font


def test_audit_tokens_without_system():
    dom = _dom()
    dom["css_tokens"] = {}
    result = audit_tokens(dom)
    assert result.has_token_system is False
    assert result.token_count == 0


def test_audit_tokens_finds_hardcoded_colors():
    dom = _dom_with_tokens()
    # Add a frequently-used color that's not in the token system
    dom["colors"] = {
        "text": [
            {"color": "#e1e4ed", "count": 100},  # matches token
            {"color": "#ff0000", "count": 50},    # hardcoded, no match
        ],
        "background": [],
    }
    result = audit_tokens(dom)
    hardcoded_colors = [h for h in result.hardcoded_values if h["type"] == "color"]
    # #ff0000 should be flagged as hardcoded (no close token match)
    assert any(h["value"] == "#ff0000" for h in hardcoded_colors)


def test_audit_tokens_to_markdown_with_tokens():
    dom = _dom_with_tokens()
    result = audit_tokens(dom)
    md = result.to_markdown()
    assert "Design Token Audit" in md
    assert "8 tokens defined" in md


def test_audit_tokens_to_markdown_without_tokens():
    dom = _dom()
    dom["css_tokens"] = {}
    result = audit_tokens(dom)
    md = result.to_markdown()
    assert "No CSS custom properties" in md


def test_audit_tokens_to_dict():
    dom = _dom_with_tokens()
    result = audit_tokens(dom)
    d = result.to_dict()
    assert "has_token_system" in d
    assert "token_count" in d
    assert "existing_tokens" in d
    assert "hardcoded_values" in d


def test_run_ui_review_includes_token_audit():
    dom = _dom_with_tokens()
    report = run_ui_review(dom)
    assert report.token_audit is not None
    assert isinstance(report.token_audit, TokenAudit)


def test_report_to_dict_includes_token_audit():
    dom = _dom_with_tokens()
    report = run_ui_review(dom)
    d = report.to_dict()
    assert "token_audit" in d
    assert d["token_audit"] is not None


# ── Colour clustering ──


def test_cluster_colors_merges_similar():
    entries = [
        {"color": "#111111", "count": 100},
        {"color": "#121212", "count": 50},  # close to #111111
        {"color": "#ff0000", "count": 30},
    ]
    clusters = _cluster_colors(entries, max_clusters=6)
    # #111111 and #121212 should merge, leaving 2 clusters
    assert len(clusters) == 2


def test_cluster_colors_respects_max():
    entries = [{"color": f"#{i:02x}{i:02x}{i:02x}", "count": 10} for i in range(0, 255, 50)]
    clusters = _cluster_colors(entries, max_clusters=3)
    assert len(clusters) <= 3


# ── Responsive report ──


def test_responsive_report_regressions():
    desktop = UIReviewReport(categories=[
        CategoryScore(name="typography", score=90),
        CategoryScore(name="interactive", score=85),
    ])
    mobile = UIReviewReport(categories=[
        CategoryScore(name="typography", score=90),
        CategoryScore(name="interactive", score=50),  # 35-point drop
    ])
    resp = ResponsiveReport(breakpoint_reports={"desktop": desktop, "mobile": mobile})
    regs = resp.regressions
    assert len(regs) == 1
    assert regs[0]["category"] == "interactive"
    assert regs[0]["drop"] == 35


def test_responsive_report_no_regressions():
    desktop = UIReviewReport(categories=[
        CategoryScore(name="typography", score=80),
    ])
    mobile = UIReviewReport(categories=[
        CategoryScore(name="typography", score=75),  # only 5 points, below threshold
    ])
    resp = ResponsiveReport(breakpoint_reports={"desktop": desktop, "mobile": mobile})
    assert len(resp.regressions) == 0


def test_responsive_report_markdown():
    desktop = UIReviewReport(categories=[
        CategoryScore(name="typography", score=90),
    ])
    mobile = UIReviewReport(categories=[
        CategoryScore(name="typography", score=70),
    ])
    resp = ResponsiveReport(breakpoint_reports={"desktop": desktop, "mobile": mobile})
    md = resp.to_markdown()
    assert "Responsive" in md
    assert "Typography" in md


def test_responsive_report_to_dict():
    desktop = UIReviewReport(categories=[
        CategoryScore(name="typography", score=90),
    ])
    resp = ResponsiveReport(breakpoint_reports={"desktop": desktop})
    d = resp.to_dict()
    assert "breakpoints" in d
    assert "regressions" in d
    assert "desktop" in d["breakpoints"]
