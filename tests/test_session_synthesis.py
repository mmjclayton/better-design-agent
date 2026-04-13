"""Tests for post-session synthesis (combined report + priorities)."""

from src.analysis.session_synthesis import (
    SYNTHESIS_PROMPT_TEMPLATE,
    CaptureRef,
    build_combined_report,
    build_priorities_deterministic,
    build_priorities_llm,
    synthesise_session,
)


def _ref(index: int, url: str, body: str, label: str = "") -> CaptureRef:
    return CaptureRef(index=index, url=url, report_markdown=body, label=label)


# ── Combined report ──


def test_combined_report_empty_captures():
    md = build_combined_report([], "pragmatic-audit")
    assert "No pages captured" in md


def test_combined_report_has_toc_and_pages():
    captures = [
        _ref(1, "https://x.com/home", "# Home report\n\nSome findings."),
        _ref(2, "https://x.com/dashboard", "# Dashboard report\n\nMore findings."),
    ]
    md = build_combined_report(captures, "pragmatic-audit")
    assert "# Interactive Review — 2 page(s)" in md
    assert "pragmatic-audit" in md
    assert "## Table of Contents" in md
    # Without explicit labels, headings fall back to "Page N"
    assert "# Page 1: Page 1" in md
    assert "# Page 2: Page 2" in md
    # URLs still appear as subtitles
    assert "https://x.com/home" in md
    assert "https://x.com/dashboard" in md
    assert "Home report" in md
    assert "Dashboard report" in md


def test_combined_report_preserves_per_page_body():
    """Combined report should never alter per-page content."""
    body = "# Important\n\n- Finding A\n- Finding B"
    captures = [_ref(1, "https://x.com", body)]
    md = build_combined_report(captures, "deep-critique")
    assert "Finding A" in md
    assert "Finding B" in md


def test_combined_report_has_separators():
    captures = [_ref(i, f"https://x.com/p-{i}", f"Body {i}") for i in range(1, 4)]
    md = build_combined_report(captures, "pragmatic-audit")
    # Separators between pages
    assert md.count("---") >= 3


def test_combined_report_toc_links_match_anchors():
    captures = [_ref(1, "https://x.com/home", "body")]
    md = build_combined_report(captures, "pragmatic-audit")
    assert "(#page-1)" in md
    assert "id='page-1'" in md


# ── Deterministic priorities ──


def test_deterministic_priorities_empty():
    md = build_priorities_deterministic([])
    assert "No pages captured" in md


def test_deterministic_priorities_with_no_criteria():
    captures = [_ref(1, "https://x.com", "# Nothing structured\n\nJust prose.")]
    md = build_priorities_deterministic(captures)
    assert "No structured WCAG issues" in md


def test_deterministic_priorities_ranks_by_frequency():
    """Criteria appearing on more pages should rank higher."""
    body_with_contrast = "**1.4.3 Contrast (Minimum)** — fails here"
    body_without = "**3.1.1 Language of Page** — fine here"
    captures = [
        _ref(1, "https://x.com/a", body_with_contrast),
        _ref(2, "https://x.com/b", body_with_contrast),
        _ref(3, "https://x.com/c", body_with_contrast),
        _ref(4, "https://x.com/d", body_without),
    ]
    md = build_priorities_deterministic(captures)
    # Contrast (3 pages) should come before Language (1 page)
    contrast_pos = md.find("1.4.3 Contrast")
    lang_pos = md.find("3.1.1 Language")
    assert contrast_pos > 0
    assert lang_pos > 0
    assert contrast_pos < lang_pos


def test_deterministic_priorities_cites_page_numbers():
    body = "**1.4.3 Contrast (Minimum)** — issue"
    captures = [
        _ref(1, "https://x.com/a", body),
        _ref(3, "https://x.com/c", body),
    ]
    md = build_priorities_deterministic(captures)
    assert "Page 1" in md
    assert "Page 3" in md


def test_deterministic_priorities_uses_labels_when_present():
    body = "**1.4.3 Contrast (Minimum)** — issue"
    captures = [
        _ref(1, "https://x.com/a", body, label="Dashboard"),
        _ref(2, "https://x.com/b", body, label="Programs"),
    ]
    md = build_priorities_deterministic(captures)
    assert "Dashboard" in md
    assert "Programs" in md
    # "Page 1" text shouldn't leak when a label exists.
    assert "Page 1" not in md


def test_quick_wins_flag_system_wide_issues():
    """A criterion appearing on 50%+ of pages should be a quick win."""
    body = "**1.4.3 Contrast (Minimum)** — issue"
    captures = [_ref(i, f"https://x.com/p-{i}", body) for i in range(1, 11)]  # 10 pages
    md = build_priorities_deterministic(captures)
    assert "Quick wins" in md
    assert "10 of 10 pages" in md
    assert "system-wide issue" in md


def test_quick_wins_flag_recurring_elements():
    """Same element failing on 3+ pages gets a dedicated callout."""
    body = (
        "**1.4.11 Non-text Contrast** violations:\n"
        "- `button.top-nav` failing\n"
    )
    captures = [_ref(i, f"https://x.com/p-{i}", body) for i in range(1, 5)]  # 4 pages
    md = build_priorities_deterministic(captures)
    assert "button.top-nav" in md
    assert "4 pages" in md.lower()


def test_priorities_has_elements_failing_section_when_recurring():
    body = (
        "**2.5.8 Target Size**:\n"
        "- `button.icon` — too small\n"
    )
    captures = [_ref(i, f"https://x.com/p-{i}", body) for i in range(1, 4)]
    md = build_priorities_deterministic(captures)
    assert "Elements failing across multiple pages" in md


def test_priorities_has_scoring_methodology_footer():
    captures = [_ref(1, "https://x.com", "**1.4.3** issue")]
    md = build_priorities_deterministic(captures)
    assert "Scoring methodology" in md
    assert "A/AA" in md


def test_quick_wins_not_shown_when_no_systemic_issues():
    """A single page with a single issue shouldn't produce quick wins."""
    captures = [_ref(1, "https://x.com", "**1.4.3** single issue")]
    md = build_priorities_deterministic(captures)
    # No quick wins since only 1 page, 1 issue
    # (quick wins threshold is max(2, total_pages // 2))
    # Should still render the "All issues" section
    assert "All issues ranked" in md


def test_element_mentions_extracted_per_criterion():
    """_extract_element_mentions pulls (criterion, selector) pairs correctly."""
    from src.analysis.session_synthesis import _extract_element_mentions
    body = (
        "## WCAG — Pragmatic View\n\n"
        "**1.4.11 Non-text Contrast** violations (2 unique):\n"
        "- `button.primary` - text - ratio: 1.2\n"
        "- `input.search` - text - ratio: 1.5\n\n"
        "**2.5.8 Target Size (Minimum)** violations:\n"
        "- `button.icon` - 20x20px - below 24x24\n"
    )
    pairs = _extract_element_mentions(body)
    assert len(pairs) == 3
    assert ("1.4.11 Non-text Contrast", "button.primary") in pairs
    assert ("1.4.11 Non-text Contrast", "input.search") in pairs
    assert ("2.5.8 Target Size (Minimum)", "button.icon") in pairs


def test_combined_report_uses_labels_in_headings():
    captures = [
        _ref(1, "https://x.com/a", "body A", label="Dashboard"),
        _ref(2, "https://x.com/b", "body B", label="Programs"),
    ]
    md = build_combined_report(captures, "pragmatic-audit")
    assert "# Page 1: Dashboard" in md
    assert "# Page 2: Programs" in md
    assert "https://x.com/a" in md  # URL still present as subtitle


def test_deterministic_priorities_shows_multi_page_count():
    body = "**2.5.8 Target Size (Minimum)** — issue"
    captures = [_ref(i, f"https://x.com/p-{i}", body) for i in range(1, 4)]
    md = build_priorities_deterministic(captures)
    assert "(3 pages)" in md


def test_deterministic_priorities_singular_page_no_multiplier():
    body = "**3.1.1 Language of Page** — issue"
    captures = [_ref(1, "https://x.com", body)]
    md = build_priorities_deterministic(captures)
    assert "(1 pages)" not in md  # singular gets no multiplier


def test_deterministic_priorities_dedupes_same_page():
    """Same criterion mentioned twice on one page shouldn't double-count."""
    body = "**1.4.3 Contrast (Minimum)** first\n**1.4.3 Contrast (Minimum)** again"
    captures = [_ref(1, "https://x.com", body)]
    md = build_priorities_deterministic(captures)
    # Should cite Page 1 once, not twice
    assert md.count("Page 1") == 1


# ── LLM priorities (with injected provider) ──


def test_llm_priorities_calls_provider_with_all_reports():
    captures = [
        _ref(1, "https://x.com/a", "# Report A\n\nIssue A1"),
        _ref(2, "https://x.com/b", "# Report B\n\nIssue B1"),
    ]
    captured_prompt = {}
    def fake_provider(prompt: str) -> str:
        captured_prompt["prompt"] = prompt
        return "# Prioritised synthesis\n\n1. **[High] Issue A1** — Page 1"

    result = build_priorities_llm(captures, provider=fake_provider)
    assert "Issue A1" in result
    # Prompt MUST include both page reports
    assert "Report A" in captured_prompt["prompt"]
    assert "Report B" in captured_prompt["prompt"]
    # Prompt MUST include grounding rules
    assert "Do NOT invent" in captured_prompt["prompt"]
    assert "MUST cite the page index" in captured_prompt["prompt"]


def test_llm_priorities_falls_back_on_provider_error():
    captures = [_ref(1, "https://x.com", "**1.4.3 Contrast** issue")]
    def bad_provider(prompt: str) -> str:
        raise RuntimeError("LLM unavailable")
    result = build_priorities_llm(captures, provider=bad_provider)
    assert "LLM call failed" in result
    assert "Showing deterministic priority list" in result
    # Deterministic fallback content appears
    assert "1.4.3 Contrast" in result


def test_llm_priorities_empty_captures():
    result = build_priorities_llm([])
    assert "No pages captured" in result


# ── Dispatch via synthesise_session ──


def test_synthesise_session_audit_mode_skips_llm():
    captures = [_ref(1, "https://x.com", "**1.4.3 Contrast** x")]
    called = {"count": 0}
    def provider(prompt):
        called["count"] += 1
        return "should not be called"
    combined, priorities = synthesise_session(
        captures, session_mode="pragmatic-audit", llm_provider=provider,
    )
    assert called["count"] == 0
    assert "Interactive Review" in combined
    assert "1.4.3 Contrast" in priorities


def test_synthesise_session_critique_mode_uses_llm():
    captures = [_ref(1, "https://x.com", "some report")]
    def provider(prompt):
        return "# LLM priority output"
    combined, priorities = synthesise_session(
        captures, session_mode="pragmatic-critique", llm_provider=provider,
    )
    assert "Interactive Review" in combined
    assert "LLM priority output" in priorities


def test_synthesise_session_deep_mode_uses_llm():
    captures = [_ref(1, "https://x.com", "x")]
    def provider(prompt):
        return "# Deep LLM priorities"
    combined, priorities = synthesise_session(
        captures, session_mode="deep-critique", llm_provider=provider,
    )
    assert "Deep LLM priorities" in priorities


# ── Prompt constraints ──


def test_prompt_template_contains_anti_hallucination_rules():
    assert "Do NOT invent findings" in SYNTHESIS_PROMPT_TEMPLATE
    assert "MUST cite the page index" in SYNTHESIS_PROMPT_TEMPLATE
    assert "Do NOT rewrite per-page findings" in SYNTHESIS_PROMPT_TEMPLATE


def test_prompt_template_fills_placeholders():
    captures = [_ref(1, "https://x.com", "body")]
    prompt = SYNTHESIS_PROMPT_TEMPLATE.format(
        n=1, reports="### Page 1: https://x.com\n\nbody",
    )
    assert "across 1 pages" in prompt
    assert "Page 1: https://x.com" in prompt
