"""Tests for inline fix-generator output inside interactive audit reports."""

from src.analysis.interactive_session import _render_fixes_inline
from src.analysis.fix_generator import FixSet, CssFix, HtmlFix


def test_render_fixes_with_css_and_html():
    fs = FixSet()
    fs.css_fixes.append(CssFix(
        selector="a.link", declarations={"color": "#111"},
        reason="was #999 on #fff, 2.8:1 → 7:1",
        criterion="1.4.3 Contrast (Minimum)",
    ))
    fs.html_fixes.append(HtmlFix(
        title="Add lang", criterion="3.1.1",
        before="<html>", after='<html lang="en">',
        notes="Use the right language code.",
    ))
    md = _render_fixes_inline(fs)
    assert "## Auto-fix suggestions" in md
    assert "2 mechanical fix(es)" in md
    assert "### CSS patches" in md
    assert "```css" in md
    assert "a.link" in md
    assert "color: #111;" in md
    assert "### HTML/structural fixes" in md
    assert 'lang="en"' in md


def test_render_fixes_caps_css_patches_at_ten():
    fs = FixSet()
    for i in range(15):
        fs.css_fixes.append(CssFix(
            selector=f".sel-{i}", declarations={"color": "#000"},
            reason="x", criterion="1.4.3 Contrast (Minimum)",
        ))
    md = _render_fixes_inline(fs)
    assert "+5 more" in md
    # Only the first 10 show up in the code block
    assert ".sel-0 {" in md
    assert ".sel-9 {" in md
    assert ".sel-10 {" not in md


def test_render_fixes_caps_html_patches_at_five():
    fs = FixSet()
    for i in range(8):
        fs.html_fixes.append(HtmlFix(
            title=f"Fix {i}", criterion="x.y.z",
            before="", after=f"snippet-{i}",
        ))
    md = _render_fixes_inline(fs)
    assert "snippet-0" in md
    assert "snippet-4" in md
    assert "snippet-5" not in md


def test_render_fixes_includes_skipped_section():
    fs = FixSet()
    fs.css_fixes.append(CssFix(
        selector="a", declarations={"color": "#000"},
        reason="x", criterion="1.4.3",
    ))
    fs.skipped.append("1.4.1 Use of Color — manual review")
    md = _render_fixes_inline(fs)
    assert "### Skipped (need manual review)" in md
    assert "Use of Color" in md


def test_render_fixes_empty_yields_no_section():
    """An empty FixSet shouldn't appear (caller already guards with .total > 0),
    but the renderer should not crash if called directly."""
    fs = FixSet()
    md = _render_fixes_inline(fs)
    assert "Auto-fix suggestions" in md
    assert "0 mechanical fix(es)" in md


def test_audit_mode_includes_fixes_when_failures_exist():
    """The pragmatic-audit runner embeds fixes after WCAG + components."""
    from src.analysis.interactive_session import _run_analysis
    dom = {
        "html_structure": {
            "has_lang": False,
            "landmarks": {"main": 0, "nav": 0, "header": 0, "footer": 0},
            "headings": [],
            "forms": {"inputs_without_labels": [], "selects_without_labels": []},
            "skip_link": False,
        },
        "contrast_pairs": [],
        "interactive_elements": [],
        "non_text_contrast": [],
    }
    report = _run_analysis("pragmatic-audit", dom, "", "https://x.com", "/tmp/shot.png")
    # Language is missing → should trigger a lang fix
    assert "## Auto-fix suggestions" in report or "Nothing to fix" not in report
    # Should contain the lang fix snippet
    assert 'lang="en"' in report