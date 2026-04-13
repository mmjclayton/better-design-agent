"""Tests for the competitive comparison module."""

from src.analysis.competitive import (
    ComparisonReport,
    Metric,
    build_comparison,
    _contrast_pass_rate,
    _target_size_pass_rate,
    _landmark_coverage,
    _heading_valid,
)
from src.analysis.wcag_checker import WcagReport, WcagResult


# ── Metric winner logic ──


def test_metric_higher_is_better_you_win():
    m = Metric("s", "Score", higher_is_better=True, your_value=80, competitor_value=60)
    assert m.winner == "you"
    assert m.delta == 20


def test_metric_higher_is_better_them_win():
    m = Metric("s", "Score", higher_is_better=True, your_value=60, competitor_value=80)
    assert m.winner == "them"
    assert m.delta == -20


def test_metric_lower_is_better_flips_sign():
    # Fewer violations is better — you have fewer, so you win, delta positive.
    m = Metric("v", "Violations", higher_is_better=False, your_value=2, competitor_value=10)
    assert m.winner == "you"
    assert m.delta == 8


def test_metric_lower_is_better_loss():
    m = Metric("v", "Violations", higher_is_better=False, your_value=10, competitor_value=2)
    assert m.winner == "them"
    assert m.delta == -8


def test_metric_tie():
    m = Metric("x", "X", higher_is_better=True, your_value=5, competitor_value=5)
    assert m.winner == "tie"


def test_metric_display_defaults_from_value():
    m = Metric("x", "X", higher_is_better=True, your_value=7, competitor_value=3.5)
    assert m.your_display == "7"
    assert m.competitor_display == "3.5"


# ── Extractor helpers ──


def test_contrast_pass_rate():
    dom = {"contrast_pairs": [
        {"passes_aa": True},
        {"passes_aa": True},
        {"passes_aa": False},
        {"passes_aa": True},
    ]}
    assert _contrast_pass_rate(dom) == 75.0


def test_contrast_pass_rate_empty():
    assert _contrast_pass_rate({}) == 0.0


def test_target_size_pass_rate():
    dom = {"interactive_elements": [
        {"width": 48, "height": 48},
        {"width": 20, "height": 40},
        {"width": 30, "height": 30},
    ]}
    # 2 of 3 pass the 24px threshold
    assert _target_size_pass_rate(dom) == round(2 / 3 * 100, 1)


def test_landmark_coverage():
    dom = {"html_structure": {"landmarks": {"main": 1, "nav": 1, "header": 0, "footer": 0}}}
    assert _landmark_coverage(dom) == 50.0


def test_heading_valid_single_h1_clean():
    dom = {"html_structure": {"headings": [
        {"level": 1, "text": "A"},
        {"level": 2, "text": "B"},
        {"level": 3, "text": "C"},
    ]}}
    assert _heading_valid(dom) == 1


def test_heading_invalid_skipped_level():
    dom = {"html_structure": {"headings": [
        {"level": 1, "text": "A"},
        {"level": 3, "text": "B"},  # skipped h2
    ]}}
    assert _heading_valid(dom) == 0


def test_heading_invalid_multiple_h1():
    dom = {"html_structure": {"headings": [
        {"level": 1, "text": "A"},
        {"level": 1, "text": "B"},
    ]}}
    assert _heading_valid(dom) == 0


def test_heading_invalid_no_h1():
    dom = {"html_structure": {"headings": [{"level": 2, "text": "A"}]}}
    assert _heading_valid(dom) == 0


# ── Report integration ──


def _minimal_wcag(score: float, violations: int) -> WcagReport:
    report = WcagReport()
    # Add enough results so score_percentage math works. A single fail produces
    # testable=1, passed=0, score=0. We fake it by adding passes + one fail.
    # Simpler: monkey-patch via direct pass/fail results.
    passed = int(score / 10)
    failed = 10 - passed
    for _ in range(passed):
        report.results.append(
            WcagResult("x", "AA", "pass", "ok")
        )
    for _ in range(failed):
        report.results.append(
            WcagResult("y", "AA", "fail", "nope", count=1, violations=[{"i": 1}])
        )
    # Manually override violations count expectation isn't clean; test score only.
    return report


def _build_dom(
    contrast_pairs: list | None = None,
    interactive: list | None = None,
    landmarks: dict | None = None,
    headings: list | None = None,
    font_families: list | None = None,
    text_colors: list | None = None,
    css_tokens: dict | None = None,
    axe_violations: list | None = None,
) -> dict:
    return {
        "contrast_pairs": contrast_pairs or [],
        "interactive_elements": interactive or [],
        "html_structure": {
            "landmarks": landmarks or {},
            "headings": headings or [],
        },
        "fonts": {"families": font_families or []},
        "colors": {"text": text_colors or []},
        "css_tokens": css_tokens or {},
        "axe_results": {"violations": axe_violations or []},
    }


def test_build_comparison_full_sweep():
    your_dom = _build_dom(
        contrast_pairs=[{"passes_aa": True}, {"passes_aa": True}],
        interactive=[{"width": 48, "height": 48}, {"width": 48, "height": 48}],
        landmarks={"main": 1, "nav": 1, "header": 1, "footer": 1},
        headings=[{"level": 1}, {"level": 2}],
        font_families=[{"family": "Inter", "count": 50}],
        text_colors=[{"color": "#111", "count": 100}],
        css_tokens={"color": ["--brand"], "space": ["--s-1", "--s-2"]},
        axe_violations=[],
    )
    their_dom = _build_dom(
        contrast_pairs=[{"passes_aa": False}, {"passes_aa": False}],
        interactive=[{"width": 20, "height": 20}],
        landmarks={"main": 0, "nav": 0, "header": 0, "footer": 0},
        headings=[{"level": 2}, {"level": 4}],
        font_families=[{"f": "A"}, {"f": "B"}, {"f": "C"}, {"f": "D"}],
        text_colors=[{"c": f"#{i}"} for i in range(20)],
        css_tokens={},
        axe_violations=[
            {"impact": "critical"}, {"impact": "serious"}, {"impact": "minor"}
        ],
    )
    your_wcag = _minimal_wcag(score=90, violations=0)
    their_wcag = _minimal_wcag(score=40, violations=0)

    report = build_comparison(
        your_url="https://you.com",
        competitor_url="https://them.com",
        your_dom=your_dom,
        competitor_dom=their_dom,
        your_wcag=your_wcag,
        competitor_wcag=their_wcag,
    )

    assert isinstance(report, ComparisonReport)
    # You should win every category in this loaded fixture
    assert report.your_wins == len(report.metrics)
    assert report.their_wins == 0
    assert "You lead" in report.verdict


def test_build_comparison_markdown_shape():
    dom = _build_dom(
        contrast_pairs=[{"passes_aa": True}],
        interactive=[{"width": 48, "height": 48}],
        landmarks={"main": 1, "nav": 1, "header": 1, "footer": 1},
        headings=[{"level": 1}],
        font_families=[{"f": "Inter"}],
        text_colors=[{"c": "#000"}],
        css_tokens={"color": ["--brand"]},
    )
    wcag = _minimal_wcag(score=80, violations=0)
    report = build_comparison(
        your_url="https://a.com",
        competitor_url="https://b.com",
        your_dom=dom,
        competitor_dom=dom,
        your_wcag=wcag,
        competitor_wcag=wcag,
    )
    md = report.to_markdown()
    assert "# Competitive Comparison" in md
    assert "https://a.com" in md
    assert "https://b.com" in md
    assert "## Verdict:" in md
    assert "| Category |" in md
    # All categories identical => every row is a tie
    assert report.ties == len(report.metrics)
    assert "Even —" in md


def test_comparison_report_has_ten_metrics():
    """Lock in the ten-metric contract so regressions are loud."""
    dom = _build_dom()
    wcag = _minimal_wcag(score=0, violations=0)
    report = build_comparison(
        your_url="https://a.com",
        competitor_url="https://b.com",
        your_dom=dom,
        competitor_dom=dom,
        your_wcag=wcag,
        competitor_wcag=wcag,
    )
    assert len(report.metrics) == 10
    keys = {m.key for m in report.metrics}
    assert "wcag_score" in keys
    assert "contrast_pass_rate" in keys
    assert "heading_hierarchy_valid" in keys
    assert "axe_critical_serious" in keys


def test_markdown_shows_fallback_when_no_gaps():
    """When your side matches/beats competitor everywhere, Biggest Gaps shows
    an explicit fallback message."""
    # Strong vs identical weak → all wins for you, no gaps.
    your_dom = _build_dom(
        contrast_pairs=[{"passes_aa": True}],
        interactive=[{"width": 48, "height": 48}],
        landmarks={"main": 1, "nav": 1, "header": 1, "footer": 1},
        headings=[{"level": 1}],
        font_families=[{"f": "Inter"}],
        text_colors=[{"c": "#000"}],
        css_tokens={"color": ["--a"]},
    )
    their_dom = _build_dom(
        contrast_pairs=[{"passes_aa": False}],
        interactive=[{"width": 10, "height": 10}],
        landmarks={},
        headings=[],
        font_families=[{"f": "A"}, {"f": "B"}, {"f": "C"}],
        text_colors=[{"c": f"#{i}"} for i in range(20)],
        css_tokens={},
        axe_violations=[{"impact": "critical"}],
    )
    wcag = _minimal_wcag(score=100, violations=0)
    low = _minimal_wcag(score=10, violations=0)
    report = build_comparison(
        your_url="https://a.com",
        competitor_url="https://b.com",
        your_dom=your_dom, competitor_dom=their_dom,
        your_wcag=wcag, competitor_wcag=low,
    )
    md = report.to_markdown()
    assert report.their_wins == 0
    assert "match or beat" in md


def test_markdown_shows_fallback_when_no_wins():
    """When you lose every category, Where You Lead shows the fallback
    message instead of an empty list."""
    weak = _build_dom(
        contrast_pairs=[{"passes_aa": False}],
        interactive=[{"width": 10, "height": 10}],
        landmarks={},
        headings=[],
        font_families=[{"f": "A"}, {"f": "B"}, {"f": "C"}],
        text_colors=[{"c": f"#{i}"} for i in range(20)],
        css_tokens={},
        axe_violations=[{"impact": "critical"}],
    )
    strong = _build_dom(
        contrast_pairs=[{"passes_aa": True}],
        interactive=[{"width": 48, "height": 48}],
        landmarks={"main": 1, "nav": 1, "header": 1, "footer": 1},
        headings=[{"level": 1}],
        font_families=[{"f": "Inter"}],
        text_colors=[{"c": "#000"}],
        css_tokens={"color": ["--a"]},
    )
    low = _minimal_wcag(score=10, violations=0)
    high = _minimal_wcag(score=100, violations=0)
    report = build_comparison(
        your_url="https://you.com",
        competitor_url="https://them.com",
        your_dom=weak, competitor_dom=strong,
        your_wcag=low, competitor_wcag=high,
    )
    md = report.to_markdown()
    assert report.your_wins == 0
    assert "None in this comparison" in md


def test_verdict_phrasing_variants():
    """Verdict text adapts to lead/even/behind states."""
    dom = _build_dom(
        contrast_pairs=[{"passes_aa": True}],
        interactive=[{"width": 48, "height": 48}],
        landmarks={"main": 1, "nav": 1, "header": 1, "footer": 1},
        headings=[{"level": 1}],
        font_families=[{"f": "Inter"}],
        text_colors=[{"c": "#000"}],
        css_tokens={"color": ["--a"]},
    )
    wcag = _minimal_wcag(score=80, violations=0)
    report = build_comparison(
        your_url="https://a.com",
        competitor_url="https://b.com",
        your_dom=dom, competitor_dom=dom,
        your_wcag=wcag, competitor_wcag=wcag,
    )
    # All identical → "Even"
    assert "Even" in report.verdict


def test_mixed_result_verdict():
    your_dom = _build_dom(
        contrast_pairs=[{"passes_aa": True}],
        interactive=[{"width": 48, "height": 48}],
        landmarks={"main": 1, "nav": 1, "header": 1, "footer": 1},
        headings=[{"level": 1}],
        font_families=[{"f": "Inter"}, {"f": "Mono"}, {"f": "Serif"}, {"f": "Extra"}],
        text_colors=[{"c": f"#{i}"} for i in range(25)],
        css_tokens={},
        axe_violations=[{"impact": "critical"}, {"impact": "critical"}],
    )
    their_dom = _build_dom(
        contrast_pairs=[{"passes_aa": False}, {"passes_aa": False}],
        interactive=[{"width": 10, "height": 10}],
        landmarks={"main": 0, "nav": 0, "header": 0, "footer": 0},
        headings=[],
        font_families=[{"f": "Inter"}],
        text_colors=[{"c": "#000"}],
        css_tokens={"color": ["--a", "--b"]},
        axe_violations=[],
    )
    your_wcag = _minimal_wcag(score=60, violations=0)
    their_wcag = _minimal_wcag(score=50, violations=0)
    report = build_comparison(
        your_url="https://a.com",
        competitor_url="https://b.com",
        your_dom=your_dom,
        competitor_dom=their_dom,
        your_wcag=your_wcag,
        competitor_wcag=their_wcag,
    )
    # This fixture has a mix — the verdict should be coherent either way.
    assert report.your_wins + report.their_wins + report.ties == len(report.metrics)
    assert report.your_wins > 0 and report.their_wins > 0
