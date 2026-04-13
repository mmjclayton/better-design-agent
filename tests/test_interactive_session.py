"""Tests for the interactive-session pure layer.

The Playwright-driven session loop itself is integration-tested manually.
These tests cover mode validation, summary rendering, and capture-result
shape.
"""

import pytest

from src.analysis.interactive_session import (
    VALID_MODES,
    CaptureResult,
    derive_page_label,
    summary_markdown,
    validate_mode,
)


# ── Label derivation ──


def _dom(title: str = "", headings=None) -> dict:
    return {"html_structure": {"title": title, "headings": headings or []}}


def test_label_uses_h1_when_present():
    dom = _dom(headings=[
        {"level": 2, "text": "Sidebar"},
        {"level": 1, "text": "Dashboard"},
        {"level": 2, "text": "Recent activity"},
    ])
    assert derive_page_label(dom, index=3) == "Dashboard"


def test_label_falls_back_to_title_if_no_h1():
    dom = _dom(title="Programs — LOADOUT", headings=[{"level": 2, "text": "nope"}])
    assert derive_page_label(dom, index=1) == "Programs"


def test_label_strips_app_name_suffix_from_title():
    for sep in (" — ", " | ", " - ", " – "):
        dom = _dom(title=f"Settings{sep}My App")
        assert derive_page_label(dom, index=1) == "Settings"


def test_label_falls_back_to_page_n():
    dom = _dom(title="", headings=[])
    assert derive_page_label(dom, index=7) == "Page 7"


def test_label_uses_first_h1_when_multiple():
    dom = _dom(headings=[
        {"level": 1, "text": "First"},
        {"level": 1, "text": "Second"},
    ])
    assert derive_page_label(dom, index=1) == "First"


def test_label_skips_empty_h1():
    dom = _dom(
        title="Fallback Title",
        headings=[{"level": 1, "text": ""}, {"level": 1, "text": "Real"}],
    )
    # The second h1 should be picked since the first is empty.
    assert derive_page_label(dom, index=1) == "Real"


def test_label_truncates_long_text():
    long = "A very long heading " * 10
    dom = _dom(headings=[{"level": 1, "text": long}])
    label = derive_page_label(dom, index=1)
    assert len(label) <= 50
    assert label.endswith("…")


def test_label_collapses_whitespace():
    dom = _dom(headings=[{"level": 1, "text": "Hello   World\n\n"}])
    assert derive_page_label(dom, index=1) == "Hello World"


# ── Mode validation ──


def test_validate_mode_accepts_known_modes():
    for mode in VALID_MODES:
        assert validate_mode(mode) == mode


def test_validate_mode_rejects_unknown():
    with pytest.raises(ValueError) as exc:
        validate_mode("bogus-mode")
    assert "bogus-mode" in str(exc.value)
    assert "Choose from" in str(exc.value)


def test_valid_modes_are_the_three_review_depths():
    assert VALID_MODES == {
        "pragmatic-audit", "pragmatic-critique", "deep-critique",
    }


# ── Summary markdown ──


def test_summary_empty_session():
    md = summary_markdown([])
    assert "No pages captured" in md


def test_summary_single_capture():
    captures = [CaptureResult(
        label="",
        index=1, url="https://x.com/dashboard",
        screenshot_path="/tmp/capture-01.png",
        report_markdown="# Report", mode="pragmatic-audit",
    )]
    md = summary_markdown(captures)
    assert "1 page(s) reviewed" in md
    assert "pragmatic-audit" in md
    assert "https://x.com/dashboard" in md
    assert "capture-01.png" in md


def test_summary_multiple_captures():
    captures = [
        CaptureResult(
            index=i, label="", url=f"https://x.com/page-{i}",
            screenshot_path=f"/tmp/capture-{i:02d}.png",
            report_markdown="", mode="pragmatic-critique",
        )
        for i in range(1, 4)
    ]
    md = summary_markdown(captures)
    assert "3 page(s) reviewed" in md
    assert "page-1" in md
    assert "page-2" in md
    assert "page-3" in md


def test_summary_mode_from_first_capture():
    captures = [CaptureResult(
        label="",
        index=1, url="https://x.com",
        screenshot_path="/tmp/a.png",
        report_markdown="", mode="deep-critique",
    )]
    md = summary_markdown(captures)
    assert "deep-critique" in md


# ── CaptureResult shape ──


def test_capture_result_has_all_fields():
    cr = CaptureResult(
        label="",
        index=7, url="https://x.com", screenshot_path="/p.png",
        report_markdown="# x", mode="pragmatic-audit",
    )
    assert cr.index == 7
    assert cr.url == "https://x.com"
    assert cr.mode == "pragmatic-audit"
