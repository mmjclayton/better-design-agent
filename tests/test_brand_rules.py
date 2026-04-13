"""Tests for the custom design-rule engine."""

import json

import pytest

from src.analysis.brand_rules import (
    EXIT_PASS,
    EXIT_TECHNICAL_ERROR,
    EXIT_VIOLATIONS,
    SCHEMA_VERSION,
    BrandRules,
    RulesLoadError,
    _normalise_hex,
    _parse_px,
    _first_family,
    check_allowed_colours,
    check_allowed_fonts,
    check_forbidden_tokens,
    check_min_font_size,
    check_required_tokens,
    evaluate_rules,
    load_rules,
)


def _dom(
    *,
    fonts_families: list[dict] | None = None,
    fonts_sizes: list[dict] | None = None,
    colors_text: list[dict] | None = None,
    colors_bg: list[dict] | None = None,
    tokens: dict | None = None,
) -> dict:
    return {
        "fonts": {
            "families": fonts_families or [],
            "sizes": fonts_sizes or [],
        },
        "colors": {
            "text": colors_text or [],
            "background": colors_bg or [],
        },
        "css_tokens": tokens or {},
    }


# ── Helpers ──


def test_normalise_hex_handles_shorthand_and_case():
    assert _normalise_hex("#FFF") == "ffffff"
    assert _normalise_hex("#AbC") == "aabbcc"
    assert _normalise_hex("#112233") == "112233"
    assert _normalise_hex("112233") == "112233"


def test_parse_px_variants():
    assert _parse_px("14px") == 14.0
    assert _parse_px("16.5px") == 16.5
    assert _parse_px("not-a-number") is None
    assert _parse_px("14") is None


def test_first_family_strips_stack():
    assert _first_family("Inter, sans-serif") == "inter"
    assert _first_family('"Open Sans", Helvetica') == "open sans"
    assert _first_family("Arial") == "arial"


# ── Loading ──


def test_load_rules_missing_file_raises(tmp_path):
    with pytest.raises(RulesLoadError) as exc:
        load_rules(tmp_path / "nope.yaml")
    assert "not found" in str(exc.value).lower()


def test_load_rules_malformed_yaml_raises(tmp_path):
    p = tmp_path / "rules.yaml"
    p.write_text(": this is not valid yaml\n  - broken")
    with pytest.raises(RulesLoadError) as exc:
        load_rules(p)
    assert "malformed" in str(exc.value).lower()


def test_load_rules_non_mapping_raises(tmp_path):
    p = tmp_path / "rules.yaml"
    p.write_text("- item1\n- item2")
    with pytest.raises(RulesLoadError) as exc:
        load_rules(p)
    assert "mapping" in str(exc.value).lower()


def test_load_rules_unknown_key_raises(tmp_path):
    p = tmp_path / "rules.yaml"
    p.write_text("allowed_fonts: [Inter]\nfoo_bar: bad")
    with pytest.raises(RulesLoadError) as exc:
        load_rules(p)
    assert "unknown" in str(exc.value).lower()


def test_load_rules_empty_file_returns_empty_rules(tmp_path):
    p = tmp_path / "rules.yaml"
    p.write_text("")
    rules = load_rules(p)
    assert rules.is_empty


def test_load_rules_parses_all_fields(tmp_path):
    p = tmp_path / "rules.yaml"
    p.write_text(
        "version: 1\n"
        "allowed_fonts:\n  - Inter\n  - Menlo\n"
        "allowed_colours:\n"
        "  text: ['#111', '#333333']\n"
        "  background: ['#fff']\n"
        "min_font_size: 14\n"
        "required_tokens: ['--a']\n"
        "forbidden_tokens: ['--b']\n"
    )
    rules = load_rules(p)
    assert rules.allowed_fonts == ["Inter", "Menlo"]
    assert rules.allowed_colours_text == ["111111", "333333"]
    assert rules.allowed_colours_background == ["ffffff"]
    assert rules.min_font_size == 14
    assert rules.required_tokens == ["--a"]
    assert rules.forbidden_tokens == ["--b"]


def test_load_rules_malformed_colours_section_raises(tmp_path):
    p = tmp_path / "rules.yaml"
    p.write_text("allowed_colours: ['#fff']")  # list, not mapping
    with pytest.raises(RulesLoadError):
        load_rules(p)


# ── allowed_fonts ──


def test_allowed_fonts_passes_when_all_match():
    rules = BrandRules(allowed_fonts=["Inter", "Menlo"])
    dom = _dom(fonts_families=[
        {"family": "Inter, sans-serif"},
        {"family": "Menlo, monospace"},
    ])
    result = check_allowed_fonts(rules, dom)
    assert result.passed
    assert "2 font families" in result.detail


def test_allowed_fonts_flags_disallowed():
    rules = BrandRules(allowed_fonts=["Inter"])
    dom = _dom(fonts_families=[
        {"family": "Inter, sans-serif"},
        {"family": "Comic Sans, cursive"},
    ])
    result = check_allowed_fonts(rules, dom)
    assert not result.passed
    assert len(result.violations) == 1
    assert "comic sans" in result.violations[0].lower()


def test_allowed_fonts_case_insensitive():
    rules = BrandRules(allowed_fonts=["inter"])
    dom = _dom(fonts_families=[{"family": "INTER, sans-serif"}])
    result = check_allowed_fonts(rules, dom)
    assert result.passed


def test_allowed_fonts_skipped_when_not_configured():
    rules = BrandRules()
    dom = _dom(fonts_families=[{"family": "Anything"}])
    result = check_allowed_fonts(rules, dom)
    assert result.passed
    assert "not configured" in result.detail.lower()


# ── allowed_colours ──


def test_allowed_colours_passes_when_palette_matches():
    rules = BrandRules(
        allowed_colours_text=["111111", "333333"],
        allowed_colours_background=["ffffff"],
    )
    dom = _dom(
        colors_text=[{"color": "#111111"}, {"color": "#333"}],
        colors_bg=[{"color": "#fff"}],
    )
    result = check_allowed_colours(rules, dom)
    assert result.passed


def test_allowed_colours_flags_off_palette():
    rules = BrandRules(allowed_colours_text=["111111"])
    dom = _dom(colors_text=[
        {"color": "#111"},
        {"color": "#ff0000"},
    ])
    result = check_allowed_colours(rules, dom)
    assert not result.passed
    assert len(result.violations) == 1
    assert "ff0000" in result.violations[0].lower()


def test_allowed_colours_text_and_bg_independent():
    # Only text is restricted; bg is unrestricted.
    rules = BrandRules(allowed_colours_text=["111111"])
    dom = _dom(
        colors_text=[{"color": "#111"}],
        colors_bg=[{"color": "#fff"}, {"color": "#0f0"}],
    )
    result = check_allowed_colours(rules, dom)
    assert result.passed  # bg colours not policed


def test_allowed_colours_skipped_when_both_empty():
    rules = BrandRules()
    dom = _dom(colors_text=[{"color": "#000"}])
    result = check_allowed_colours(rules, dom)
    assert result.passed
    assert "not configured" in result.detail.lower()


# ── min_font_size ──


def test_min_font_size_passes_when_all_above():
    rules = BrandRules(min_font_size=14)
    dom = _dom(fonts_sizes=[{"size": "14px"}, {"size": "16px"}, {"size": "24px"}])
    result = check_min_font_size(rules, dom)
    assert result.passed


def test_min_font_size_flags_small_text():
    rules = BrandRules(min_font_size=14)
    dom = _dom(fonts_sizes=[{"size": "10px"}, {"size": "12px"}, {"size": "16px"}])
    result = check_min_font_size(rules, dom)
    assert not result.passed
    assert len(result.violations) == 2


def test_min_font_size_ignores_non_px():
    rules = BrandRules(min_font_size=14)
    dom = _dom(fonts_sizes=[{"size": "1rem"}, {"size": "16px"}])
    result = check_min_font_size(rules, dom)
    assert result.passed


def test_min_font_size_skipped_when_not_configured():
    rules = BrandRules()
    dom = _dom(fonts_sizes=[{"size": "8px"}])
    result = check_min_font_size(rules, dom)
    assert result.passed


# ── required_tokens ──


def test_required_tokens_passes_when_all_present():
    rules = BrandRules(required_tokens=["--brand", "--space-1"])
    dom = _dom(tokens={
        "color": [{"name": "--brand", "value": "#000"}],
        "spacing": [{"name": "--space-1", "value": "8px"}],
    })
    result = check_required_tokens(rules, dom)
    assert result.passed


def test_required_tokens_flags_missing():
    rules = BrandRules(required_tokens=["--brand", "--ghost"])
    dom = _dom(tokens={"color": [{"name": "--brand", "value": "#000"}]})
    result = check_required_tokens(rules, dom)
    assert not result.passed
    assert len(result.violations) == 1
    assert "--ghost" in result.violations[0]


def test_required_tokens_skipped_when_not_configured():
    rules = BrandRules()
    dom = _dom(tokens={})
    result = check_required_tokens(rules, dom)
    assert result.passed


# ── forbidden_tokens ──


def test_forbidden_tokens_passes_when_none_present():
    rules = BrandRules(forbidden_tokens=["--legacy"])
    dom = _dom(tokens={"color": [{"name": "--brand", "value": "#000"}]})
    result = check_forbidden_tokens(rules, dom)
    assert result.passed


def test_forbidden_tokens_flags_present():
    rules = BrandRules(forbidden_tokens=["--legacy-blue"])
    dom = _dom(tokens={"color": [{"name": "--legacy-blue", "value": "#0000ff"}]})
    result = check_forbidden_tokens(rules, dom)
    assert not result.passed
    assert len(result.violations) == 1


def test_forbidden_tokens_skipped_when_not_configured():
    rules = BrandRules()
    dom = _dom(tokens={"color": [{"name": "--anything", "value": "#000"}]})
    result = check_forbidden_tokens(rules, dom)
    assert result.passed


# ── Full report ──


def test_evaluate_rules_all_pass():
    rules = BrandRules(
        allowed_fonts=["Inter"],
        min_font_size=14,
    )
    dom = _dom(
        fonts_families=[{"family": "Inter, sans-serif"}],
        fonts_sizes=[{"size": "16px"}],
    )
    report = evaluate_rules(rules, dom, url="https://x.com", rules_path="rules.yaml")
    assert report.passed
    assert report.exit_code == EXIT_PASS
    assert report.violation_count == 0


def test_evaluate_rules_mixed_violations():
    rules = BrandRules(
        allowed_fonts=["Inter"],
        min_font_size=14,
        forbidden_tokens=["--bad"],
    )
    dom = _dom(
        fonts_families=[{"family": "Comic Sans"}],
        fonts_sizes=[{"size": "10px"}],
        tokens={"color": [{"name": "--bad", "value": "#f0f"}]},
    )
    report = evaluate_rules(rules, dom, url="https://x.com", rules_path="rules.yaml")
    assert not report.passed
    assert report.exit_code == EXIT_VIOLATIONS
    assert report.violation_count == 3  # 1 font + 1 size + 1 forbidden token


def test_evaluate_rules_with_errors_returns_exit_two():
    from src.analysis.brand_rules import BrandComplianceReport
    report = BrandComplianceReport(
        schema_version=SCHEMA_VERSION, url="x", rules_path="r",
        errors=["something broke"],
    )
    assert report.exit_code == EXIT_TECHNICAL_ERROR


# ── Report rendering ──


def test_report_markdown_contains_all_sections():
    rules = BrandRules(allowed_fonts=["Inter"], min_font_size=14)
    dom = _dom(
        fonts_families=[{"family": "Comic Sans"}],
        fonts_sizes=[{"size": "10px"}],
    )
    report = evaluate_rules(rules, dom, url="https://x.com", rules_path="rules.yaml")
    md = report.to_markdown()
    assert "# Brand Compliance Report" in md
    assert "**URL:** https://x.com" in md
    assert "**Rules:** rules.yaml" in md
    assert "FAIL" in md
    assert "## Rule Results" in md
    assert "**Exit code:**" in md


def test_report_markdown_shows_pass_status_when_clean():
    rules = BrandRules(allowed_fonts=["Inter"])
    dom = _dom(fonts_families=[{"family": "Inter, sans-serif"}])
    report = evaluate_rules(rules, dom, url="https://x.com", rules_path="rules.yaml")
    md = report.to_markdown()
    assert "PASS" in md
    assert "0** total violation" in md


def test_report_json_schema_shape():
    rules = BrandRules(allowed_fonts=["Inter"])
    dom = _dom(fonts_families=[{"family": "Inter"}])
    report = evaluate_rules(rules, dom, url="https://x.com", rules_path="rules.yaml")
    data = json.loads(report.to_json())
    required = {
        "schema_version", "url", "rules_path", "passed",
        "violation_count", "exit_code", "results", "errors",
    }
    assert required.issubset(data.keys())
    assert data["schema_version"] == SCHEMA_VERSION
    for r in data["results"]:
        assert {"name", "passed", "detail", "violations"}.issubset(r.keys())


def test_report_produces_five_rule_results():
    """Every configured or unconfigured rule always emits one RuleResult."""
    rules = BrandRules()
    dom = _dom()
    report = evaluate_rules(rules, dom, url="x", rules_path="y")
    assert len(report.results) == 5
    names = {r.name for r in report.results}
    assert names == {
        "allowed_fonts", "allowed_colours", "min_font_size",
        "required_tokens", "forbidden_tokens",
    }
