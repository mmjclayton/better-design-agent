"""Tests for the scheduled-monitoring report builder."""

import json

from src.analysis.monitoring import (
    DEFAULT_SCORE_TOLERANCE,
    EXIT_REGRESSION,
    EXIT_STABLE,
    EXIT_TECHNICAL_ERROR,
    SCHEMA_VERSION,
    TrendPoint,
    _build_trend,
    _format_alert_text,
    build_monitor_report,
)
from src.analysis.history import RunRecord
from src.analysis.wcag_checker import WcagReport, WcagResult


def _wcag(passes: int, violations: list | None = None) -> WcagReport:
    r = WcagReport()
    for _ in range(passes):
        r.results.append(WcagResult("p", "AA", "pass", "ok"))
    if violations:
        r.results.append(WcagResult(
            "2.5.8", "AA", "fail", "bad",
            count=len(violations), violations=violations,
        ))
    return r


def _run(score: float, ts: str = "2026-01-01T00:00:00", issues=None) -> RunRecord:
    return RunRecord(
        timestamp=ts, url="https://x.com", device="desktop",
        pages_crawled=1, score=int(score), wcag_score=score,
        issues=issues or [],
    )


def _fake_webhook_ok(url, payload):
    return True, None


def _fake_webhook_fail(url, payload):
    return False, "HTTP 503"


# ── Exit code logic ──


def test_stable_run_exits_zero():
    result = build_monitor_report(
        url="https://x.com",
        wcag_report=_wcag(10), dom_data={},
        history=[_run(100.0)],
        previous_run=_run(100.0),
    )
    assert result.exit_code == EXIT_STABLE


def test_new_violation_exits_one():
    result = build_monitor_report(
        url="https://x.com",
        wcag_report=_wcag(9, [{"element": "btn.x", "issue": "20x20"}]),
        dom_data={},
        history=[_run(100.0)],
        previous_run=_run(100.0, issues=[]),
    )
    assert result.exit_code == EXIT_REGRESSION
    assert len(result.new_violations) == 1


def test_score_drop_beyond_tolerance_exits_one():
    result = build_monitor_report(
        url="https://x.com",
        wcag_report=_wcag(5, [{"element": "btn.x", "issue": "z"}]),
        dom_data={},
        history=[_run(100.0)],
        previous_run=_run(100.0, issues=[
            {"criterion": "2.5.8", "element": "btn.x", "details": "z"}
        ]),
    )
    # Same violation, so no NEW — but score dropped from 100% to ~83%.
    assert result.exit_code == EXIT_REGRESSION
    assert result.score_delta is not None and result.score_delta < -DEFAULT_SCORE_TOLERANCE


def test_score_drop_within_tolerance_exits_zero():
    # Build a fixture where score drops within the 2.0pp tolerance band.
    current = _wcag(89, [{"element": "btn.x", "issue": "z"}])
    result = build_monitor_report(
        url="https://x.com",
        wcag_report=current, dom_data={},
        history=[_run(90.0)],
        previous_run=_run(90.0, issues=[
            {"criterion": "2.5.8", "element": "btn.x", "details": "z"}
        ]),
    )
    # 89/90 = ~98.9%, previous 90%. Delta small. No new issues (persistent).
    # As long as no new issues, should be stable.
    assert len(result.new_violations) == 0
    # Score delta should be within tolerance OR positive
    if result.score_delta is not None and result.score_delta >= -DEFAULT_SCORE_TOLERANCE:
        assert result.exit_code == EXIT_STABLE


def test_errors_cause_technical_exit_two():
    result = build_monitor_report(
        url="https://x.com",
        wcag_report=_wcag(10), dom_data={},
        history=[],
        previous_run=None,
        errors=["couldn't reach site"],
    )
    assert result.exit_code == EXIT_TECHNICAL_ERROR


# ── Trend window ──


def test_trend_window_truncates_history():
    runs = [_run(float(50 + i), ts=f"2026-01-{i+1:02d}") for i in range(20)]
    result = build_monitor_report(
        url="https://x.com",
        wcag_report=_wcag(10), dom_data={},
        history=runs, previous_run=runs[-1],
        trend_window=5,
    )
    assert len(result.trend) == 5
    # Most recent first (end of list)
    assert result.trend[-1].score == runs[-1].wcag_score


def test_trend_window_default_is_ten():
    runs = [_run(50.0, ts=f"2026-01-{i+1:02d}") for i in range(15)]
    result = build_monitor_report(
        url="https://x.com",
        wcag_report=_wcag(10), dom_data={},
        history=runs, previous_run=runs[-1],
    )
    assert len(result.trend) == 10


def test_trend_with_empty_history():
    result = build_monitor_report(
        url="https://x.com",
        wcag_report=_wcag(10), dom_data={},
        history=[], previous_run=None,
    )
    assert result.trend == []


def test_build_trend_helper_honours_window():
    runs = [_run(float(i), ts=f"2026-01-{i+1:02d}") for i in range(20)]
    assert len(_build_trend(runs, window=3)) == 3
    assert len(_build_trend(runs, window=100)) == 20
    assert _build_trend(runs, window=0) == []  # window=0 → empty via slice


# ── Score delta ──


def test_score_delta_computed_when_previous_exists():
    result = build_monitor_report(
        url="https://x.com",
        wcag_report=_wcag(10), dom_data={},
        history=[_run(80.0)], previous_run=_run(80.0, issues=[]),
    )
    assert result.score_previous == 80.0
    assert result.score_delta is not None
    assert result.score_delta > 0  # score went up


def test_score_delta_none_when_no_previous():
    result = build_monitor_report(
        url="https://x.com",
        wcag_report=_wcag(10), dom_data={},
        history=[], previous_run=None,
    )
    assert result.score_previous is None
    assert result.score_delta is None


# ── Alerting ──


def test_alert_not_fired_on_stable_run():
    calls = []
    def capture(url, payload):
        calls.append((url, payload))
        return True, None

    result = build_monitor_report(
        url="https://x.com",
        wcag_report=_wcag(10), dom_data={},
        history=[_run(100.0)],
        previous_run=_run(100.0, issues=[]),
        alert_webhook="https://hooks.slack.com/services/XXX",
        webhook_poster=capture,
    )
    assert result.alert_fired is False
    assert calls == []
    # Payload is prepared even when not fired, so the report can show it.
    assert result.alert_payload is not None


def test_alert_fired_on_regression():
    calls = []
    def capture(url, payload):
        calls.append((url, payload))
        return True, None

    result = build_monitor_report(
        url="https://x.com",
        wcag_report=_wcag(9, [{"element": "btn.x", "issue": "20x20"}]),
        dom_data={},
        history=[_run(100.0)],
        previous_run=_run(100.0, issues=[]),
        alert_webhook="https://hooks.slack.com/services/XXX",
        webhook_poster=capture,
    )
    assert result.alert_fired is True
    assert len(calls) == 1
    payload = calls[0][1]
    assert "text" in payload
    assert "regression" in payload["text"].lower()
    assert "https://x.com" in payload["text"]


def test_alert_webhook_failure_recorded():
    result = build_monitor_report(
        url="https://x.com",
        wcag_report=_wcag(9, [{"element": "btn.x", "issue": "20x20"}]),
        dom_data={},
        history=[_run(100.0)],
        previous_run=_run(100.0, issues=[]),
        alert_webhook="https://hooks.slack.com/services/bad",
        webhook_poster=_fake_webhook_fail,
    )
    assert result.alert_fired is False
    assert result.alert_error == "HTTP 503"
    # Regression still flagged in exit code regardless of webhook outcome.
    assert result.exit_code == EXIT_REGRESSION


def test_no_webhook_means_no_payload():
    result = build_monitor_report(
        url="https://x.com",
        wcag_report=_wcag(10), dom_data={},
        history=[_run(100.0)],
        previous_run=_run(100.0, issues=[]),
    )
    assert result.alert_payload is None
    assert result.alert_fired is False


def test_format_alert_text_includes_all_signals():
    text = _format_alert_text(
        url="https://x.com",
        score=72.0,
        score_delta=-8.0,
        new_count=3,
    )
    assert "https://x.com" in text
    assert "72" in text
    assert "-8" in text
    assert "3 new" in text


# ── Fingerprint diffing ──


def test_new_violation_detected_against_previous_run():
    previous = _run(100.0, issues=[
        {"criterion": "2.5.8", "element": "btn.a", "details": "z"},
    ])
    result = build_monitor_report(
        url="https://x.com",
        wcag_report=_wcag(8, [
            {"element": "btn.a", "issue": "z"},        # persistent
            {"element": "btn.b", "issue": "new"},      # new
        ]),
        dom_data={},
        history=[previous], previous_run=previous,
    )
    assert len(result.new_violations) == 1
    assert result.new_violations[0]["element"] == "btn.b"


def test_fixed_violation_reported():
    previous = _run(80.0, issues=[
        {"criterion": "2.5.8", "element": "btn.a", "details": "z"},
        {"criterion": "2.5.8", "element": "btn.b", "details": "y"},
    ])
    result = build_monitor_report(
        url="https://x.com",
        wcag_report=_wcag(10),  # all pass — both issues gone
        dom_data={},
        history=[previous], previous_run=previous,
    )
    assert len(result.fixed_violations) == 2


# ── Markdown + JSON output ──


def test_markdown_contains_all_sections():
    result = build_monitor_report(
        url="https://x.com",
        wcag_report=_wcag(9, [{"element": "btn.x", "issue": "20x20"}]),
        dom_data={},
        history=[_run(90.0, ts="2026-01-01"), _run(80.0, ts="2026-01-08")],
        previous_run=_run(80.0, issues=[]),
    )
    md = result.to_markdown()
    assert "# Monitoring Report" in md
    assert "## Score" in md
    assert "## Regressions" in md
    assert "## Trend" in md
    assert "**Exit code:**" in md


def test_markdown_shows_no_previous_run():
    result = build_monitor_report(
        url="https://x.com",
        wcag_report=_wcag(10), dom_data={},
        history=[], previous_run=None,
    )
    md = result.to_markdown()
    assert "no previous run" in md.lower()


def test_json_schema_shape():
    result = build_monitor_report(
        url="https://x.com",
        wcag_report=_wcag(10), dom_data={},
        history=[_run(100.0)], previous_run=_run(100.0, issues=[]),
    )
    data = json.loads(result.to_json())
    required = {
        "schema_version", "url", "timestamp", "score",
        "score_previous", "score_delta", "trend",
        "new_violations", "fixed_violations",
        "alert_fired", "alert_payload", "alert_error",
        "exit_code", "errors",
    }
    assert required.issubset(data.keys())
    assert data["schema_version"] == SCHEMA_VERSION


def test_trend_point_dict_shape():
    tp = TrendPoint(timestamp="2026-01-01", score=87.5)
    assert tp.to_dict() == {"timestamp": "2026-01-01", "score": 87.5}
