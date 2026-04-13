"""Tests for orchestrator helpers that clean up sub-agent outputs."""

from src.agents.orchestrator import (
    ALLOWED_H2_HEADERS,
    _clean_agent_output,
    _enforce_section_headers,
)


# ── _enforce_section_headers ──


def test_enforce_preserves_whitelisted_h2s():
    md = (
        "## WCAG 2.2 Automated Audit\n"
        "body\n"
        "## Visual Design Analysis\n"
        "body\n"
        "## Accessibility Deep Dive\n"
    )
    out = _enforce_section_headers(md)
    assert "## WCAG 2.2 Automated Audit" in out
    assert "## Visual Design Analysis" in out
    assert "## Accessibility Deep Dive" in out


def test_enforce_demotes_unknown_h2_to_h3():
    md = (
        "## Visual Design Analysis\n"
        "## Component Intent Analysis\n"
        "## Screen Reader Narrative\n"
        "body\n"
    )
    out = _enforce_section_headers(md)
    # Check line-by-line since '##' is a substring of '###'
    lines = out.split("\n")
    assert "## Visual Design Analysis" in lines
    assert "### Component Intent Analysis" in lines
    assert "### Screen Reader Narrative" in lines
    # The demoted ones should NOT appear as standalone H2 lines
    assert "## Component Intent Analysis" not in lines
    assert "## Screen Reader Narrative" not in lines


def test_enforce_keeps_mobile_wcag_variant():
    md = "## WCAG 2.2 Automated Audit (Mobile - iPhone 14 Pro, 393x852)\nbody"
    out = _enforce_section_headers(md)
    assert "## WCAG 2.2 Automated Audit (Mobile - iPhone 14 Pro, 393x852)" in out
    assert "###" not in out


def test_enforce_does_not_touch_h3_or_deeper():
    md = "### Subsection\n#### Deeper\n##### Deeper still"
    out = _enforce_section_headers(md)
    assert out == md


def test_enforce_does_not_touch_h1():
    md = "# Desktop Analysis (1440x900)\n## Visual Design Analysis\nbody"
    out = _enforce_section_headers(md)
    assert "# Desktop Analysis (1440x900)" in out


def test_enforce_all_allowed_headers_recognised():
    expected = {
        "WCAG 2.2 Automated Audit",
        "Visual Design Analysis",
        "Accessibility Deep Dive",
        "Design System Analysis",
        "Interaction Quality Analysis",
        "Component Inventory & Scoring",
    }
    assert ALLOWED_H2_HEADERS == expected


def test_enforce_handles_empty_input():
    assert _enforce_section_headers("") == ""


def test_enforce_preserves_body_content():
    md = (
        "## Visual Design Analysis\n"
        "\n"
        "Some important body text with **markdown** formatting.\n"
        "- List item 1\n"
        "- List item 2\n"
    )
    out = _enforce_section_headers(md)
    assert "Some important body text" in out
    assert "List item 1" in out





def test_strips_leading_h1():
    out = _clean_agent_output(
        "# State Audit Results\n\n## Section A\ndetail", "Interaction",
    )
    assert "State Audit Results" not in out
    assert "### Section A" in out  # demoted from ##


def test_strips_leading_h2():
    out = _clean_agent_output(
        "## Visual Analysis\n\n## Hierarchy\ndetail", "Visual",
    )
    assert "Visual Analysis" not in out
    assert "### Hierarchy" in out


def test_demotes_all_remaining_headings():
    out = _clean_agent_output(
        "# Title\n\n## A\n### B\n#### C\n##### D\n###### E", "Title",
    )
    assert "## A" in out
    assert "### B" in out
    assert "#### C" in out
    assert "##### D" in out
    assert "###### E" in out  # caps at h6


def test_preserves_content_without_leading_heading():
    out = _clean_agent_output(
        "Some leading prose with no title\n## First section\ndetail",
        "Whatever",
    )
    assert "Some leading prose" in out
    assert "### First section" in out


def test_strips_blank_lines_after_removed_heading():
    out = _clean_agent_output(
        "# Redundant\n\n\n\n## Section\nbody", "Redundant",
    )
    assert "Redundant" not in out
    assert out.lstrip().startswith("### Section")


def test_does_not_strip_h3_or_lower():
    """An H3 shouldn't be stripped — it's legitimate sub-structure."""
    out = _clean_agent_output(
        "### Subtopic\ndetail", "Whatever",
    )
    # H3 stays (demoted to H4), not stripped
    assert "#### Subtopic" in out


def test_does_not_go_deeper_than_h6():
    out = _clean_agent_output(
        "###### Deep heading\nbody", "x",
    )
    assert "###### Deep heading" in out  # H6 stays at H6


def test_handles_empty_input():
    assert _clean_agent_output("", "x") == ""


def test_handles_whitespace_only_input():
    assert _clean_agent_output("   \n\n  ", "x").strip() == ""


def test_does_not_strip_headings_with_unrelated_keyword():
    """Keyword parameter is no longer used, so any leading H1/H2 gets stripped."""
    out = _clean_agent_output(
        "# Some title\n\nbody", "CompletelyDifferent",
    )
    assert "Some title" not in out
    assert "body" in out


def test_demotes_heading_with_trailing_content():
    """A heading like '## A {#id}' should still demote."""
    out = _clean_agent_output("body line\n## Section Title\nmore", "x")
    assert "### Section Title" in out
