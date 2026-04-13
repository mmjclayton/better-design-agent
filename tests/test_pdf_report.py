"""Tests for the PDF report HTML-building layer.

The Playwright render step (`save_pdf_report`) spins up a browser, so it's
not unit-tested here. `build_pdf_html` is pure and fully tested.
"""

from src.output.pdf_report import (
    PRINT_CSS,
    _build_cover_page,
    _build_toc,
    _extract_h2_headings,
    _extract_overall_score,
    _inject_anchors,
    _slugify,
    build_pdf_html,
)


# ── Slugify ──


def test_slugify_basic():
    assert _slugify("Visual Hierarchy") == "visual-hierarchy"
    assert _slugify("WCAG 2.2 Audit") == "wcag-22-audit"
    assert _slugify("  Mixed Case / punctuation!  ") == "mixed-case-punctuation"


def test_slugify_fallback_for_empty():
    assert _slugify("") == "section"
    assert _slugify("!!!") == "section"


def test_slugify_truncates_long_input():
    long = "a" * 200
    assert len(_slugify(long)) <= 80


# ── Heading extraction ──


def test_extract_h2_headings_plain():
    html = """
    <h1>Title</h1>
    <h2>First Section</h2>
    <p>body</p>
    <h2>Second Section</h2>
    <h3>Not an h2</h3>
    """
    headings = _extract_h2_headings(html)
    assert headings == [
        ("First Section", "first-section"),
        ("Second Section", "second-section"),
    ]


def test_extract_h2_strips_inline_html():
    html = '<h2><code>build_pdf_html()</code> API</h2>'
    headings = _extract_h2_headings(html)
    assert headings[0][0] == "build_pdf_html() API"


def test_extract_h2_deduplicates_slugs():
    html = "<h2>Details</h2><h2>Details</h2><h2>Details</h2>"
    headings = _extract_h2_headings(html)
    slugs = [s for _, s in headings]
    assert slugs == ["details", "details-2", "details-3"]


def test_extract_h2_handles_no_headings():
    assert _extract_h2_headings("<p>no headings here</p>") == []


def test_extract_h2_with_attributes():
    html = '<h2 class="something" data-foo="bar">With Attrs</h2>'
    headings = _extract_h2_headings(html)
    assert headings == [("With Attrs", "with-attrs")]


# ── Anchor injection ──


def test_inject_anchors_adds_id_to_each_h2():
    html = "<h2>A</h2><p>x</p><h2>B</h2>"
    headings = [("A", "a"), ("B", "b")]
    result = _inject_anchors(html, headings)
    assert 'id="a"' in result
    assert 'id="b"' in result


def test_inject_anchors_preserves_existing_id():
    html = '<h2 id="custom">A</h2>'
    headings = [("A", "a")]
    result = _inject_anchors(html, headings)
    assert 'id="custom"' in result
    assert 'id="a"' not in result


def test_inject_anchors_preserves_heading_content():
    html = "<h2>Visual Hierarchy</h2>"
    headings = [("Visual Hierarchy", "visual-hierarchy")]
    result = _inject_anchors(html, headings)
    assert "Visual Hierarchy" in result


# ── Score extraction ──


def test_extract_overall_score_from_markdown():
    md = "# Report\n\n**Overall Score: 78/100**\n\nDetails..."
    assert _extract_overall_score(md) == "78/100"


def test_extract_overall_score_no_match():
    assert _extract_overall_score("no score here") is None


def test_extract_overall_score_picks_first_match():
    md = "First: 50/100 then 99/100"
    assert _extract_overall_score(md) == "50/100"


# ── Cover page ──


def test_cover_page_contains_all_metadata():
    html = _build_cover_page("https://example.com", "iPhone 14 Pro", "87/100")
    assert "https://example.com" in html
    assert "iPhone 14 Pro" in html
    assert "87/100" in html
    assert "Design Critique Report" in html
    assert "design-intel" in html
    assert 'class="cover-page"' in html


def test_cover_page_without_score_omits_score_block():
    html = _build_cover_page("https://x.com", "desktop", None)
    assert 'class="cover-score"' not in html


def test_cover_page_without_url_shows_placeholder():
    html = _build_cover_page("", "desktop", None)
    assert "N/A" in html


# ── TOC ──


def test_toc_renders_every_heading_as_link():
    headings = [("Alpha", "alpha"), ("Beta", "beta")]
    html = _build_toc(headings)
    assert 'href="#alpha"' in html
    assert 'href="#beta"' in html
    assert ">Alpha<" in html
    assert ">Beta<" in html
    assert 'class="toc-page"' in html


def test_toc_empty_when_no_headings():
    assert _build_toc([]) == ""


def test_toc_is_ordered_list():
    headings = [("One", "one")]
    html = _build_toc(headings)
    assert "<ol>" in html
    assert "</ol>" in html


# ── Full pipeline ──


def test_build_pdf_html_includes_cover_toc_and_print_css():
    md = """# Report

Overall score: 72/100

## Introduction

Some text.

## Findings

More text.

## Recommendations

Even more text.
"""
    html = build_pdf_html(md, url="https://x.com", device="desktop")

    # Print CSS injected into the style block
    assert "@page" in html
    assert "break-after: avoid" in html

    # Cover page present before anything else
    body_start = html.find("<body>")
    cover_start = html.find('class="cover-page"')
    toc_start = html.find('class="toc-page"')
    assert body_start < cover_start < toc_start

    # TOC has entries for the three h2s
    assert 'href="#introduction"' in html
    assert 'href="#findings"' in html
    assert 'href="#recommendations"' in html

    # h2 anchors injected in the body
    assert 'id="introduction"' in html
    assert 'id="findings"' in html


def test_build_pdf_html_with_no_headings_skips_toc():
    md = "# Just a Title\n\nSome body text with no h2 sections."
    html = build_pdf_html(md, url="https://x.com", device="desktop")
    # Cover still present
    assert 'class="cover-page"' in html
    # TOC section absent (empty string from _build_toc)
    assert 'class="toc-page"' not in html


def test_build_pdf_html_preserves_url_and_device_in_cover():
    md = "# Report"
    html = build_pdf_html(md, url="https://stripe.com", device="iPhone 14 Pro")
    assert "https://stripe.com" in html
    assert "iPhone 14 Pro" in html


def test_print_css_has_required_page_rules():
    assert "@page" in PRINT_CSS
    assert "size: A4" in PRINT_CSS
    assert "break-inside: avoid" in PRINT_CSS
    assert "cover-page" in PRINT_CSS
    assert "toc-page" in PRINT_CSS
