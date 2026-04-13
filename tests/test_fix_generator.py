"""Tests for the auto-fix generator."""

from src.analysis.fix_generator import (
    _adjust_to_ratio,
    _contrast_ratio,
    _parse_color,
    _to_hex,
    generate_fixes,
)
from src.analysis.wcag_checker import WcagReport, WcagResult


# ── Colour maths ──


def test_parse_hex_and_rgb():
    assert _parse_color("#000000") == (0, 0, 0)
    assert _parse_color("#fff") == (255, 255, 255)
    assert _parse_color("rgb(128, 64, 32)") == (128, 64, 32)
    assert _parse_color("rgba(10, 20, 30, 0.5)") == (10, 20, 30)
    assert _parse_color("") is None
    assert _parse_color("nonsense") is None


def test_contrast_ratio_known_values():
    # Black on white = 21:1
    assert round(_contrast_ratio((0, 0, 0), (255, 255, 255)), 1) == 21.0
    # White on white = 1:1
    assert round(_contrast_ratio((255, 255, 255), (255, 255, 255)), 1) == 1.0


def test_adjust_to_ratio_darkens_on_light_bg():
    # Light grey text on white -> should darken until >= 4.5:1
    text = (170, 170, 170)  # ~2.6:1 against white
    bg = (255, 255, 255)
    fixed = _adjust_to_ratio(text, bg, 4.5)
    assert _contrast_ratio(fixed, bg) >= 4.5
    # Result should be darker than the original
    assert sum(fixed) < sum(text)


def test_adjust_to_ratio_lightens_on_dark_bg():
    text = (80, 80, 80)
    bg = (0, 0, 0)
    fixed = _adjust_to_ratio(text, bg, 4.5)
    assert _contrast_ratio(fixed, bg) >= 4.5
    assert sum(fixed) > sum(text)


def test_to_hex_clamps_and_formats():
    assert _to_hex((0, 0, 0)) == "#000000"
    assert _to_hex((255, 255, 255)) == "#ffffff"
    assert _to_hex((300, -5, 128)) == "#ff0080"


# ── Fix generation ──


def _report_with(*results) -> WcagReport:
    r = WcagReport()
    r.results.extend(results)
    return r


def test_generate_fixes_contrast_produces_css_rule():
    report = _report_with(
        WcagResult(
            criterion="1.4.3 Contrast (Minimum)",
            level="AA",
            status="fail",
            details="1 pair below ratio",
            count=1,
            violations=[{
                "element": "p.muted",
                "text": "Sign up now",
                "ratio": 2.6,
                "issue": "#aaaaaa on #ffffff = 2.6:1 (requires 4.5:1)",
            }],
        )
    )
    fixes = generate_fixes(report)
    assert len(fixes.css_fixes) == 1
    fix = fixes.css_fixes[0]
    assert fix.selector == "p.muted"
    assert "color" in fix.declarations
    # Emitted colour must actually meet 4.5:1 on white
    new_rgb = _parse_color(fix.declarations["color"])
    assert new_rgb is not None
    assert _contrast_ratio(new_rgb, (255, 255, 255)) >= 4.5


def test_generate_fixes_target_size_emits_min_dimensions():
    report = _report_with(
        WcagResult(
            criterion="2.5.8 Target Size (Minimum)",
            level="AA",
            status="fail",
            details="1 element below 24x24",
            count=1,
            violations=[{
                "element": "button.icon",
                "text": "X",
                "size": "20x20px",
                "issue": "Below 24x24px minimum",
            }],
        )
    )
    fixes = generate_fixes(report)
    assert len(fixes.css_fixes) == 1
    fix = fixes.css_fixes[0]
    assert fix.declarations["min-width"] == "24px"
    assert fix.declarations["min-height"] == "24px"
    assert "padding" in fix.declarations


def test_generate_fixes_lang_produces_html_snippet():
    report = _report_with(
        WcagResult(
            criterion="3.1.1 Language of Page",
            level="A",
            status="fail",
            details="Missing lang",
            count=1,
            violations=[{"issue": "No lang attribute on <html> element"}],
        )
    )
    fixes = generate_fixes(report)
    assert len(fixes.html_fixes) == 1
    assert 'lang="en"' in fixes.html_fixes[0].after


def test_generate_fixes_skips_non_deterministic_failures():
    report = _report_with(
        WcagResult(
            criterion="1.4.1 Use of Color",
            level="A",
            status="fail",
            details="manual review",
            count=1,
            violations=[],
        )
    )
    fixes = generate_fixes(report)
    assert fixes.total == 0
    assert any("Use of Color" in s for s in fixes.skipped)


def test_generate_fixes_ignores_passes_and_warnings():
    report = _report_with(
        WcagResult("1.4.3 Contrast (Minimum)", "AA", "pass", "ok"),
        WcagResult("2.5.8 Target Size (Minimum)", "AA", "warning", "close"),
    )
    fixes = generate_fixes(report)
    assert fixes.total == 0


def test_css_file_output_has_header_and_rules():
    report = _report_with(
        WcagResult(
            criterion="1.4.3 Contrast (Minimum)",
            level="AA",
            status="fail",
            details="1 pair",
            count=1,
            violations=[{
                "element": "a.link",
                "text": "read more",
                "ratio": 3.0,
                "issue": "#888888 on #ffffff = 3.0:1 (requires 4.5:1)",
            }],
        )
    )
    fixes = generate_fixes(report)
    css = fixes.to_css_file()
    assert "Auto-generated by design-intel fix" in css
    assert "a.link" in css
    assert "color:" in css


def test_non_text_contrast_picks_dark_border_on_light_background():
    report = _report_with(
        WcagResult(
            criterion="1.4.11 Non-text Contrast",
            level="AA",
            status="fail",
            details="1 component",
            count=1,
            violations=[{
                "element": "input.search",
                "text": "",
                "ratio": 1.1,
                "issue": "#fafafa vs #ffffff = 1.1:1",
            }],
        )
    )
    fixes = generate_fixes(report)
    assert len(fixes.css_fixes) == 1
    border = fixes.css_fixes[0].declarations["border"]
    # Adjacent background is #ffffff (light) → expect dark border.
    assert "#1a1a1a" in border


def test_non_text_contrast_picks_light_border_on_dark_background():
    report = _report_with(
        WcagResult(
            criterion="1.4.11 Non-text Contrast",
            level="AA",
            status="fail",
            details="1 component",
            count=1,
            violations=[{
                "element": "button.ghost",
                "text": "",
                "ratio": 1.1,
                "issue": "#111111 vs #222222 = 1.1:1",
            }],
        )
    )
    fixes = generate_fixes(report)
    assert len(fixes.css_fixes) == 1
    border = fixes.css_fixes[0].declarations["border"]
    # Adjacent background is #222 (dark) → expect light border.
    assert "#e5e5e5" in border


def test_non_text_contrast_fallback_border_when_bg_unparseable():
    report = _report_with(
        WcagResult(
            criterion="1.4.11 Non-text Contrast",
            level="AA",
            status="fail",
            details="1 component",
            count=1,
            violations=[{
                "element": "input",
                "issue": "garbled issue string without the expected format",
            }],
        )
    )
    fixes = generate_fixes(report)
    assert len(fixes.css_fixes) == 1
    border = fixes.css_fixes[0].declarations["border"]
    # Fallback neutral border.
    assert "#6b7280" in border


def test_fix_set_total_counts_both_lists():
    from src.analysis.fix_generator import FixSet, CssFix, HtmlFix
    fs = FixSet()
    fs.css_fixes.append(CssFix("a", {"color": "#000"}, "why", "x"))
    fs.css_fixes.append(CssFix("b", {"color": "#000"}, "why", "x"))
    fs.html_fixes.append(HtmlFix("t", "x", "", "after"))
    assert fs.total == 3


def test_contrast_fix_respects_aaa_required_ratio():
    """A 7:1 requirement (AAA) must produce a colour meeting 7:1, not 4.5:1."""
    report = _report_with(
        WcagResult(
            criterion="1.4.3 Contrast (Minimum)",
            level="AA",
            status="fail",
            details="1 pair",
            count=1,
            violations=[{
                "element": "h1.headline",
                "text": "Important",
                "ratio": 2.0,
                "issue": "#cccccc on #ffffff = 2.0:1 (requires 7:1)",
            }],
        )
    )
    fixes = generate_fixes(report)
    assert len(fixes.css_fixes) == 1
    new_rgb = _parse_color(fixes.css_fixes[0].declarations["color"])
    assert _contrast_ratio(new_rgb, (255, 255, 255)) >= 7.0


def test_form_labels_fix_uses_placeholder_as_label_seed():
    report = _report_with(
        WcagResult(
            criterion="4.1.2 Name, Role, Value (Form Labels)",
            level="A",
            status="fail",
            details="1 input unlabelled",
            count=1,
            violations=[{
                "element": "input",
                "issue": 'Input type=email has no label (placeholder: "Your email")',
            }],
        )
    )
    fixes = generate_fixes(report)
    assert len(fixes.html_fixes) == 1
    assert "Your email" in fixes.html_fixes[0].after
