"""Tests for the style guide extraction and comparison engine."""

import yaml

from src.analysis.style_guide import (
    GuideComparison,
    StyleGuide,
    compare_against_guide,
    extract_style_guide,
    list_guides,
    load_guide,
    resolve_guide,
    save_guide,
)

import pytest


# ── Test helpers ──


def _dom(
    *,
    colors_text=None,
    colors_bg=None,
    fonts_families=None,
    fonts_sizes=None,
    spacing_values=None,
    component_styles=None,
    layout=None,
):
    return {
        "colors": {
            "text": colors_text or [{"color": "#111", "count": 100}],
            "background": colors_bg or [{"color": "#fff", "count": 80}],
        },
        "fonts": {
            "families": fonts_families or [{"family": "Inter", "count": 100}],
            "sizes": fonts_sizes or [{"size": "16px", "count": 100}],
        },
        "spacing_values": spacing_values or [{"value": "8px", "count": 50}],
        "component_styles": component_styles or {
            "buttons": [{"selector": "button.primary", "bg": "#0066cc", "color": "#fff",
                         "font_size": "16px", "border_radius": "8px", "padding": "12px 24px"}],
            "inputs": [{"selector": "input.text", "bg": "#fff", "color": "#111",
                        "font_size": "16px", "border_radius": "4px", "border": "1px solid #ccc",
                        "padding": "8px 12px"}],
            "links": [{"selector": "a.nav", "color": "#0066cc", "font_size": "14px"}],
            "cards": [],
            "headings": [
                {"selector": "h1", "font_size": "48px", "font_weight": "700", "color": "#111"},
                {"selector": "h2", "font_size": "32px", "font_weight": "600", "color": "#111"},
            ],
            "images": [],
        },
        "layout": layout or {
            "viewport_width": 1440, "viewport_height": 900,
            "body_font_size": "16px", "body_line_height": "24px",
            "body_font_family": "Inter", "body_bg": "#ffffff",
        },
        "css_tokens": {},
        "html_structure": {"headings": [], "landmarks": {}, "forms": {}},
    }


def _guide(**overrides):
    """Build a StyleGuide with sensible defaults."""
    defaults = dict(
        name="test-guide",
        source_url="https://example.com",
        extracted_at="2026-04-06 12:00",
        colors_text=[{"color": "#111", "count": 100}, {"color": "#666", "count": 50}],
        colors_background=[{"color": "#fff", "count": 80}, {"color": "#f5f5f5", "count": 20}],
        font_families=[{"family": "Inter", "count": 100}],
        font_sizes=[{"size": "14px", "count": 40}, {"size": "16px", "count": 100}, {"size": "24px", "count": 20}],
        spacing_values=[{"value": "8px", "count": 50}, {"value": "16px", "count": 40}, {"value": "24px", "count": 20}],
        buttons=[{"selector": "button.primary", "bg": "#0066cc", "color": "#fff",
                  "font_size": "16px", "border_radius": "8px", "padding": "12px 24px"}],
        inputs=[{"selector": "input.text", "bg": "#fff", "color": "#111",
                 "font_size": "16px", "border_radius": "4px", "border": "1px solid #ccc"}],
        links=[{"selector": "a.nav", "color": "#0066cc", "font_size": "14px"}],
        headings=[
            {"selector": "h1", "font_size": "48px", "font_weight": "700", "color": "#111"},
            {"selector": "h2", "font_size": "32px", "font_weight": "600", "color": "#111"},
        ],
    )
    defaults.update(overrides)
    return StyleGuide(**defaults)


# ── Extraction ──


def test_extract_style_guide_basic():
    dom = _dom()
    guide = extract_style_guide(dom, "https://example.com", "test")
    assert guide.name == "test"
    assert guide.source_url == "https://example.com"
    assert len(guide.colors_text) > 0
    assert len(guide.font_families) > 0
    assert len(guide.buttons) > 0
    assert len(guide.inputs) > 0


def test_extract_style_guide_empty_dom():
    guide = extract_style_guide({}, "https://example.com", "empty")
    assert guide.name == "empty"
    assert guide.colors_text == []


def test_extract_style_guide_includes_headings():
    dom = _dom()
    guide = extract_style_guide(dom, "https://example.com", "test")
    assert len(guide.headings) == 2
    assert guide.headings[0]["font_size"] == "48px"


# ── Serialisation ──


def test_style_guide_to_yaml():
    guide = _guide()
    yaml_str = guide.to_yaml()
    parsed = yaml.safe_load(yaml_str)
    assert parsed["name"] == "test-guide"
    assert "global" in parsed
    assert "components" in parsed
    assert "layout" in parsed


def test_style_guide_roundtrip():
    original = _guide()
    yaml_str = original.to_yaml()
    parsed = yaml.safe_load(yaml_str)
    restored = StyleGuide.from_dict(parsed)
    assert restored.name == original.name
    assert restored.source_url == original.source_url
    assert len(restored.colors_text) == len(original.colors_text)
    assert len(restored.buttons) == len(original.buttons)
    assert len(restored.headings) == len(original.headings)


def test_style_guide_to_markdown():
    guide = _guide()
    md = guide.to_markdown()
    assert "Style Guide: test-guide" in md
    assert "Colors" in md
    assert "Typography" in md
    assert "Buttons" in md


def test_style_guide_to_dict():
    guide = _guide()
    d = guide.to_dict()
    assert d["schema_version"] == 1
    assert d["global"]["colors_text"] == guide.colors_text
    assert d["components"]["buttons"] == guide.buttons
    assert d["layout"]["body_font_size"] == guide.body_font_size


# ── Persistence ──


def test_save_and_load_guide(tmp_path):
    guide = _guide()
    path = save_guide(guide, tmp_path)
    assert path.exists()
    assert path.name == "test-guide.yaml"

    loaded = load_guide(path)
    assert loaded.name == "test-guide"
    assert loaded.source_url == "https://example.com"
    assert len(loaded.buttons) == 1


def test_load_guide_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_guide(tmp_path / "nonexistent.yaml")


def test_list_guides_empty(tmp_path):
    assert list_guides(tmp_path) == []


def test_list_guides_finds_files(tmp_path):
    guide = _guide()
    save_guide(guide, tmp_path)
    guides = list_guides(tmp_path)
    assert len(guides) == 1


def test_resolve_guide_by_name(tmp_path):
    guide = _guide()
    save_guide(guide, tmp_path)
    path = resolve_guide("test-guide", tmp_path)
    assert path.exists()


def test_resolve_guide_by_path(tmp_path):
    guide = _guide()
    saved = save_guide(guide, tmp_path)
    path = resolve_guide(str(saved), tmp_path)
    assert path == saved


def test_resolve_guide_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        resolve_guide("nonexistent", tmp_path)


# ── Comparison — perfect match ──


def test_compare_perfect_match():
    guide = _guide()
    dom = _dom()
    comparison = compare_against_guide(dom, guide)
    assert isinstance(comparison, GuideComparison)
    assert comparison.guide_name == "test-guide"
    # Colors should be a good match since dom and guide use same values
    assert comparison.category_scores.get("colors", 0) >= 50


def test_compare_returns_overall_match():
    guide = _guide()
    dom = _dom()
    comparison = compare_against_guide(dom, guide)
    assert 0 <= comparison.overall_match <= 100


# ── Comparison — mismatches ──


def test_compare_different_colors():
    guide = _guide(
        colors_text=[{"color": "#ff0000", "count": 100}],
        colors_background=[{"color": "#00ff00", "count": 80}],
    )
    dom = _dom(
        colors_text=[{"color": "#0000ff", "count": 100}],
        colors_bg=[{"color": "#ffff00", "count": 80}],
    )
    comparison = compare_against_guide(dom, guide)
    assert comparison.category_scores["colors"] < 50
    different = [f for f in comparison.findings if f.severity == "different"]
    assert len(different) > 0


def test_compare_different_typography():
    guide = _guide(
        font_families=[{"family": "Helvetica", "count": 100}],
        font_sizes=[{"size": "18px", "count": 100}, {"size": "36px", "count": 50}],
    )
    dom = _dom(
        fonts_families=[{"family": "Georgia", "count": 100}],
        fonts_sizes=[{"size": "14px", "count": 100}, {"size": "24px", "count": 50}],
    )
    comparison = compare_against_guide(dom, guide)
    assert comparison.category_scores["typography"] < 80


def test_compare_different_buttons():
    guide = _guide(
        buttons=[{"selector": "button.cta", "bg": "#ff0000", "color": "#fff",
                  "font_size": "18px", "border_radius": "24px"}],
    )
    dom = _dom(component_styles={
        "buttons": [{"selector": "button.btn", "bg": "#0000ff", "color": "#000",
                     "font_size": "14px", "border_radius": "4px"}],
        "inputs": [], "links": [], "cards": [], "headings": [], "images": [],
    })
    comparison = compare_against_guide(dom, guide)
    assert "buttons" in comparison.category_scores
    assert comparison.category_scores["buttons"] < 50


# ── Comparison output ──


def test_comparison_to_markdown():
    guide = _guide()
    dom = _dom()
    comparison = compare_against_guide(dom, guide)
    md = comparison.to_markdown()
    assert "Style Guide Comparison" in md
    assert "Overall match" in md


def test_comparison_to_dict():
    guide = _guide()
    dom = _dom()
    comparison = compare_against_guide(dom, guide)
    d = comparison.to_dict()
    assert "guide_name" in d
    assert "overall_match" in d
    assert "category_scores" in d
    assert "findings" in d


def test_comparison_findings_have_structure():
    guide = _guide(
        colors_text=[{"color": "#ff0000", "count": 100}],
    )
    dom = _dom(colors_text=[{"color": "#0000ff", "count": 100}])
    comparison = compare_against_guide(dom, guide)
    for f in comparison.findings:
        assert hasattr(f, "category")
        assert hasattr(f, "property")
        assert hasattr(f, "actual")
        assert hasattr(f, "reference")
        assert hasattr(f, "severity")
        assert f.severity in ("match", "close", "different")
