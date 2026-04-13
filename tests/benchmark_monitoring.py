"""
Benchmark: Scheduled Monitoring correctness.

Scores: exit-code semantics, fingerprint-diff correctness (vs history
baseline), trend-window truncation, alert-firing discipline (fire only on
regression; never crash on webhook error), markdown completeness, JSON
schema shape.

Run: python -m tests.benchmark_monitoring
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from src.analysis.monitoring import (
    EXIT_REGRESSION,
    EXIT_STABLE,
    EXIT_TECHNICAL_ERROR,
    build_monitor_report,
    _build_trend,
)
from src.analysis.history import RunRecord
from src.analysis.wcag_checker import WcagReport, WcagResult


RUBRIC_MAX = {
    "exit_code_semantics": 25,
    "fingerprint_diff_vs_baseline": 20,
    "trend_truncation": 15,
    "alert_discipline": 20,
    "markdown_completeness": 10,
    "json_schema_shape": 10,
}


@dataclass
class BenchmarkResult:
    scores: dict[str, float] = field(default_factory=dict)
    details: dict[str, dict] = field(default_factory=dict)

    @property
    def total(self) -> float:
        return sum(self.scores.values())

    @property
    def percentage(self) -> float:
        return round((self.total / sum(RUBRIC_MAX.values())) * 100, 1)


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


def _run(score: float, ts: str = "2026-01-01", issues=None) -> RunRecord:
    return RunRecord(
        timestamp=ts, url="https://x.com", device="desktop",
        pages_crawled=1, score=int(score), wcag_score=score,
        issues=issues or [],
    )


# ── Scoring ──


def score_exit_codes() -> tuple[float, dict]:
    max_points = RUBRIC_MAX["exit_code_semantics"]
    cases = []

    # Stable
    r = build_monitor_report(
        url="https://x.com",
        wcag_report=_wcag(10), dom_data={},
        history=[_run(100.0)], previous_run=_run(100.0, issues=[]),
    )
    cases.append(("stable", r.exit_code == EXIT_STABLE))

    # New violation
    r = build_monitor_report(
        url="https://x.com",
        wcag_report=_wcag(9, [{"element": "btn.x", "issue": "new"}]),
        dom_data={},
        history=[_run(100.0)], previous_run=_run(100.0, issues=[]),
    )
    cases.append(("new_violation", r.exit_code == EXIT_REGRESSION))

    # Big score drop (same violation persistent → not new, but score delta)
    r = build_monitor_report(
        url="https://x.com",
        wcag_report=_wcag(5, [{"element": "btn.x", "issue": "z"}]),
        dom_data={},
        history=[_run(100.0)],
        previous_run=_run(100.0, issues=[
            {"criterion": "2.5.8", "element": "btn.x", "details": "z"}
        ]),
    )
    cases.append(("score_drop", r.exit_code == EXIT_REGRESSION))

    # Improvement (old issue fixed)
    r = build_monitor_report(
        url="https://x.com",
        wcag_report=_wcag(10), dom_data={},
        history=[_run(80.0)],
        previous_run=_run(80.0, issues=[
            {"criterion": "2.5.8", "element": "btn.x", "details": "z"}
        ]),
    )
    cases.append(("improvement", r.exit_code == EXIT_STABLE))

    # Error
    r = build_monitor_report(
        url="https://x.com",
        wcag_report=_wcag(10), dom_data={},
        history=[], previous_run=None,
        errors=["unreachable"],
    )
    cases.append(("tech_error", r.exit_code == EXIT_TECHNICAL_ERROR))

    correct = sum(1 for _, ok in cases if ok)
    pct = correct / len(cases)
    return round(pct * max_points, 1), {
        "cases": len(cases), "correct": correct,
        "failed": [n for n, ok in cases if not ok],
    }


def score_fingerprint_diff() -> tuple[float, dict]:
    max_points = RUBRIC_MAX["fingerprint_diff_vs_baseline"]
    previous = _run(80.0, issues=[
        {"criterion": "2.5.8", "element": "btn.a", "details": "z"},
        {"criterion": "2.5.8", "element": "btn.b", "details": "y"},
    ])
    r = build_monitor_report(
        url="https://x.com",
        wcag_report=_wcag(8, [
            {"element": "btn.a", "issue": "z"},      # persistent
            {"element": "btn.c", "issue": "new"},    # new
        ]),
        dom_data={},
        history=[previous], previous_run=previous,
    )
    checks = [
        ("one_new", len(r.new_violations) == 1),
        ("new_is_c", r.new_violations[0]["element"] == "btn.c"),
        ("one_fixed", len(r.fixed_violations) == 1),
        ("fixed_is_b", r.fixed_violations[0]["element"] == "btn.b"),
    ]
    correct = sum(1 for _, ok in checks if ok)
    pct = correct / len(checks)
    return round(pct * max_points, 1), {
        "checks": len(checks), "correct": correct,
        "failed": [n for n, ok in checks if not ok],
    }


def score_trend_truncation() -> tuple[float, dict]:
    max_points = RUBRIC_MAX["trend_truncation"]
    runs = [_run(float(i), ts=f"2026-01-{i+1:02d}") for i in range(20)]
    cases = [
        ("window_5", len(_build_trend(runs, 5)) == 5),
        ("window_10", len(_build_trend(runs, 10)) == 10),
        ("window_100", len(_build_trend(runs, 100)) == 20),
        ("window_0", _build_trend(runs, 0) == []),
        ("window_negative", _build_trend(runs, -1) == []),
    ]
    correct = sum(1 for _, ok in cases if ok)
    pct = correct / len(cases)
    return round(pct * max_points, 1), {
        "cases": len(cases), "correct": correct,
        "failed": [n for n, ok in cases if not ok],
    }


def score_alert_discipline() -> tuple[float, dict]:
    max_points = RUBRIC_MAX["alert_discipline"]
    calls = []

    def capture(url, payload):
        calls.append(("fire", url))
        return True, None

    def fail_poster(url, payload):
        calls.append(("fail", url))
        return False, "HTTP 503"

    cases = []

    # Alert NOT fired on stable run
    r = build_monitor_report(
        url="https://x.com",
        wcag_report=_wcag(10), dom_data={},
        history=[_run(100.0)], previous_run=_run(100.0, issues=[]),
        alert_webhook="https://hooks.example/x",
        webhook_poster=capture,
    )
    cases.append(("no_fire_on_stable", not r.alert_fired))

    # Alert FIRED on regression
    r = build_monitor_report(
        url="https://x.com",
        wcag_report=_wcag(9, [{"element": "btn.x", "issue": "new"}]),
        dom_data={},
        history=[_run(100.0)], previous_run=_run(100.0, issues=[]),
        alert_webhook="https://hooks.example/y",
        webhook_poster=capture,
    )
    cases.append(("fire_on_regression", r.alert_fired))

    # Webhook failure recorded but doesn't crash
    r = build_monitor_report(
        url="https://x.com",
        wcag_report=_wcag(9, [{"element": "btn.x", "issue": "new"}]),
        dom_data={},
        history=[_run(100.0)], previous_run=_run(100.0, issues=[]),
        alert_webhook="https://hooks.example/z",
        webhook_poster=fail_poster,
    )
    cases.append(("failure_recorded", r.alert_error == "HTTP 503"))
    cases.append(("failure_does_not_crash_exit", r.exit_code == EXIT_REGRESSION))

    # No webhook → no payload
    r = build_monitor_report(
        url="https://x.com",
        wcag_report=_wcag(10), dom_data={},
        history=[_run(100.0)], previous_run=_run(100.0, issues=[]),
    )
    cases.append(("no_webhook_no_payload", r.alert_payload is None))

    correct = sum(1 for _, ok in cases if ok)
    pct = correct / len(cases)
    return round(pct * max_points, 1), {
        "cases": len(cases), "correct": correct,
        "failed": [n for n, ok in cases if not ok],
    }


def score_markdown() -> tuple[float, dict]:
    max_points = RUBRIC_MAX["markdown_completeness"]
    r = build_monitor_report(
        url="https://x.com",
        wcag_report=_wcag(9, [{"element": "btn.x", "issue": "20x20"}]),
        dom_data={},
        history=[_run(90.0, ts="2026-01-01"), _run(80.0, ts="2026-01-08")],
        previous_run=_run(80.0, issues=[]),
    )
    md = r.to_markdown()
    required = [
        "# Monitoring Report",
        "## Score",
        "## Regressions",
        "## Trend",
        "**Exit code:**",
    ]
    present = sum(1 for s in required if s in md)
    pct = present / len(required)
    return round(pct * max_points, 1), {
        "sections_expected": len(required), "sections_present": present,
        "missing": [s for s in required if s not in md],
    }


def score_json_schema() -> tuple[float, dict]:
    max_points = RUBRIC_MAX["json_schema_shape"]
    r = build_monitor_report(
        url="https://x.com",
        wcag_report=_wcag(10), dom_data={},
        history=[_run(100.0)], previous_run=_run(100.0, issues=[]),
    )
    data = json.loads(r.to_json())
    required = {
        "schema_version", "url", "timestamp", "score",
        "score_previous", "score_delta", "trend",
        "new_violations", "fixed_violations",
        "alert_fired", "alert_payload", "alert_error",
        "exit_code", "errors",
    }
    present = len(required & data.keys())
    pct = present / len(required)
    return round(pct * max_points, 1), {
        "expected_keys": len(required), "present": present,
        "missing": list(required - data.keys()),
    }


def run_benchmark() -> BenchmarkResult:
    result = BenchmarkResult()
    for name, fn in [
        ("exit_code_semantics", score_exit_codes),
        ("fingerprint_diff_vs_baseline", score_fingerprint_diff),
        ("trend_truncation", score_trend_truncation),
        ("alert_discipline", score_alert_discipline),
        ("markdown_completeness", score_markdown),
        ("json_schema_shape", score_json_schema),
    ]:
        s, d = fn()
        result.scores[name] = s
        result.details[name] = d
    return result


def print_result(result: BenchmarkResult) -> None:
    print("\n" + "=" * 70)
    print("MONITORING BENCHMARK")
    print("=" * 70)
    print(f"\n{'Category':<34}{'Score':<12}{'Max':<8}{'Pct':<6}")
    print("-" * 60)
    for cat, max_score in RUBRIC_MAX.items():
        label = cat.replace("_", " ").title()
        s = result.scores.get(cat, 0)
        pct = round(s / max_score * 100) if max_score else 0
        print(f"{label:<34}{s:<12}{max_score:<8}{pct}%")
    print("-" * 60)
    print(f"{'TOTAL':<34}{result.total:<12}{sum(RUBRIC_MAX.values()):<8}{result.percentage}%")
    for cat, details in result.details.items():
        label = cat.replace("_", " ").title()
        print(f"\n  {label}:")
        for k, v in details.items():
            print(f"    {k}: {v}")


def main() -> int:
    result = run_benchmark()
    print_result(result)
    if result.percentage < 90:
        print(f"\nFAIL: benchmark score {result.percentage}% below 90% floor")
        return 1
    print(f"\nPASS: benchmark score {result.percentage}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
