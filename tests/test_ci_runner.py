"""Tests for the CI gate evaluator (pragmatic + strict modes)."""

import json

from src.analysis.ci_runner import (
    EXIT_PASS,
    EXIT_THRESHOLD_FAILED,
    EXIT_TECHNICAL_ERROR,
    SCHEMA_VERSION,
    PragmaticConfig,
    evaluate,
)
from src.analysis.history import RunRecord
from src.analysis.wcag_checker import WcagReport, WcagResult


# ── Helpers ──


def _report(
    *,
    pass_count: int = 10,
    fail_criterion: str | None = None,
    violations: list | None = None,
) -> WcagReport:
    """Build a WcagReport with controllable score + specific failing violations."""
    report = WcagReport()
    for _ in range(pass_count):
        report.results.append(WcagResult("pass-x", "AA", "pass", "ok"))
    if fail_criterion:
        vs = violations or [{"element": "button.x", "issue": "below 24x24"}]
        report.results.append(WcagResult(
            criterion=fail_criterion, level="AA", status="fail",
            details="bad", count=len(vs), violations=vs,
        ))
    return report


def _dom(axe_violations: list | None = None) -> dict:
    return {"axe_results": {"violations": axe_violations or []}}


def _prev_run(
    *, score: float, issues: list | None = None
) -> RunRecord:
    return RunRecord(
        timestamp="2026-01-01T00:00:00",
        url="https://x.com",
        device="desktop",
        pages_crawled=1,
        score=int(score),
        wcag_score=score,
        issues=issues or [],
    )


def _fp_dict(criterion: str, element: str, issue: str) -> dict:
    """Build a dict with the fingerprint fields a stored run uses."""
    return {"criterion": criterion, "element": element, "details": issue}


# ── Pragmatic mode: first run (no baseline) ──


def test_pragmatic_first_run_passes_and_captures_baseline():
    result = evaluate(
        url="https://x.com",
        wcag_report=_report(pass_count=6, fail_criterion="2.5.8"),  # 85.7%
        dom_data=_dom(axe_violations=[{"impact": "critical", "id": "color-contrast"}]),
        previous_run=None,
    )
    assert result.exit_code == EXIT_PASS
    assert result.mode == "pragmatic"
    assert any("baseline-captured" in t.name for t in result.thresholds)


# ── Pragmatic mode: NEW violations gate ──


def test_pragmatic_new_critical_violation_fails():
    previous = _prev_run(score=90.0, issues=[])
    result = evaluate(
        url="https://x.com",
        wcag_report=_report(pass_count=10),
        dom_data=_dom(axe_violations=[
            {"impact": "critical", "id": "color-contrast",
             "nodes": [{"target": [".new-banner"]}], "description": "fail"}
        ]),
        previous_run=previous,
    )
    assert result.exit_code == EXIT_THRESHOLD_FAILED
    assert len(result.new_violations) == 1
    no_new_th = [t for t in result.thresholds if "no-new-violations" in t.name]
    assert no_new_th and not no_new_th[0].passed


def test_pragmatic_pre_existing_violation_does_not_fail():
    # Same violation present in baseline → grandfathered → no gate.
    previous_fp = _fp_dict("axe:color-contrast", ".banner", "critical fail")
    previous = _prev_run(score=85.0, issues=[previous_fp])
    result = evaluate(
        url="https://x.com",
        wcag_report=_report(pass_count=10),
        dom_data=_dom(axe_violations=[
            {"impact": "critical", "id": "color-contrast",
             "nodes": [{"target": [".banner"]}], "description": "fail"}
        ]),
        previous_run=previous,
    )
    assert result.exit_code == EXIT_PASS
    assert len(result.new_violations) == 0
    assert len(result.pre_existing_violations) == 1


def test_pragmatic_fixed_violation_is_celebrated():
    previous_fp = _fp_dict("axe:color-contrast", ".old-banner", "critical fail")
    previous = _prev_run(score=85.0, issues=[previous_fp])
    result = evaluate(
        url="https://x.com",
        wcag_report=_report(pass_count=10),
        dom_data=_dom(axe_violations=[]),  # nothing bad now
        previous_run=previous,
    )
    assert result.exit_code == EXIT_PASS
    assert len(result.fixed_violations) == 1
    assert len(result.new_violations) == 0


# ── Pragmatic mode: severity floor ──


def test_pragmatic_minor_violations_do_not_gate_by_default():
    previous = _prev_run(score=90.0, issues=[])
    result = evaluate(
        url="https://x.com",
        wcag_report=_report(pass_count=10),
        dom_data=_dom(axe_violations=[
            {"impact": "minor", "id": "meta-viewport", "nodes": [{"target": ["head"]}],
             "description": "nit"}
        ]),
        previous_run=previous,
    )
    # Minor violations don't cross the 'serious' default floor → not gated.
    assert result.exit_code == EXIT_PASS
    assert len(result.new_violations) == 0


def test_pragmatic_lowering_severity_floor_gates_moderate():
    previous = _prev_run(score=90.0, issues=[])
    cfg = PragmaticConfig(severity_floor="moderate")
    result = evaluate(
        url="https://x.com",
        wcag_report=_report(pass_count=10),
        dom_data=_dom(axe_violations=[
            {"impact": "moderate", "id": "region", "nodes": [{"target": ["body"]}],
             "description": "nope"}
        ]),
        previous_run=previous,
        pragmatic=cfg,
    )
    assert result.exit_code == EXIT_THRESHOLD_FAILED


# ── Pragmatic mode: score tolerance ──


def test_pragmatic_score_drop_within_tolerance_passes():
    previous = _prev_run(score=90.0, issues=[])
    # Current score 88.9% (one fail out of 9) → drop ~1.1pp, under 2.0 default.
    result = evaluate(
        url="https://x.com",
        wcag_report=_report(pass_count=8, fail_criterion="2.5.8"),
        dom_data=_dom(),
        previous_run=previous,
    )
    drop_th = [t for t in result.thresholds if "score-drop" in t.name]
    assert drop_th and drop_th[0].passed


def test_pragmatic_score_drop_exceeds_tolerance_fails():
    previous = _prev_run(score=90.0, issues=[])
    # Current score 50% → drop 40pp, far over 2.0 tolerance.
    result = evaluate(
        url="https://x.com",
        wcag_report=_report(pass_count=5, fail_criterion="2.5.8"),  # 5/10 = 50%
        dom_data=_dom(),
        previous_run=previous,
    )
    assert result.exit_code == EXIT_THRESHOLD_FAILED
    drop_th = [t for t in result.thresholds if "score-drop" in t.name]
    assert drop_th and not drop_th[0].passed


def test_pragmatic_custom_tolerance_widens_band():
    previous = _prev_run(score=90.0, issues=[])
    cfg = PragmaticConfig(score_tolerance=50.0)
    result = evaluate(
        url="https://x.com",
        wcag_report=_report(pass_count=5, fail_criterion="2.5.8"),  # 50%
        dom_data=_dom(),
        previous_run=previous,
        pragmatic=cfg,
    )
    drop_th = [t for t in result.thresholds if "score-drop" in t.name]
    assert drop_th and drop_th[0].passed


# ── Strict mode ──


def test_strict_any_aa_violation_fails():
    result = evaluate(
        url="https://x.com",
        wcag_report=_report(pass_count=9, fail_criterion="2.5.8"),
        dom_data=_dom(),
        strict=True,
    )
    assert result.mode == "strict"
    assert result.exit_code == EXIT_THRESHOLD_FAILED


def test_strict_zero_violations_passes():
    result = evaluate(
        url="https://x.com",
        wcag_report=_report(pass_count=10),
        dom_data=_dom(),
        strict=True,
    )
    assert result.exit_code == EXIT_PASS


def test_strict_score_drop_actually_fails():
    previous = _prev_run(score=90.0, issues=[])
    # 7 passes + 1 fail → 87.5%
    result = evaluate(
        url="https://x.com",
        wcag_report=_report(pass_count=7, fail_criterion="2.5.8"),
        dom_data=_dom(),
        previous_run=previous,
        strict=True,
    )
    assert result.exit_code == EXIT_THRESHOLD_FAILED


def test_strict_grandfathers_nothing():
    # Pre-existing violation that pragmatic would grandfather.
    previous_fp = _fp_dict("axe:color-contrast", ".banner", "critical fail")
    previous = _prev_run(score=100.0, issues=[previous_fp])
    result = evaluate(
        url="https://x.com",
        wcag_report=_report(pass_count=10),
        dom_data=_dom(axe_violations=[
            {"impact": "critical", "id": "color-contrast",
             "nodes": [{"target": [".banner"]}], "description": "fail"}
        ]),
        previous_run=previous,
        strict=True,
    )
    # Strict gates on any critical/serious — existence alone is enough.
    assert result.exit_code == EXIT_THRESHOLD_FAILED


# ── min-score works in both modes ──


def test_min_score_below_floor_fails_in_pragmatic():
    # 1 pass + 1 fail criterion → 50% score (below the 70 floor).
    result = evaluate(
        url="https://x.com",
        wcag_report=_report(pass_count=1, fail_criterion="2.5.8"),
        dom_data=_dom(),
        previous_run=_prev_run(score=50.0, issues=[]),
        min_score=70,
    )
    assert result.exit_code == EXIT_THRESHOLD_FAILED
    ms = [t for t in result.thresholds if t.name == "min-score"]
    assert ms and not ms[0].passed


def test_min_score_above_floor_passes_in_both_modes():
    for strict_mode in (True, False):
        result = evaluate(
            url="https://x.com",
            wcag_report=_report(pass_count=10),
            dom_data=_dom(),
            previous_run=_prev_run(score=100.0, issues=[]),
            min_score=70,
            strict=strict_mode,
        )
        ms = [t for t in result.thresholds if t.name == "min-score"]
        assert ms and ms[0].passed


# ── Blocked + errors ──


def test_blocked_returns_exit_two():
    result = evaluate(
        url="https://x.com",
        wcag_report=None,
        dom_data={},
        blocked=True,
    )
    assert result.exit_code == EXIT_TECHNICAL_ERROR
    assert any("blocked" in e.lower() for e in result.errors)


# ── JSON schema contract ──


def test_schema_version_is_v2():
    result = evaluate(
        url="https://x.com",
        wcag_report=_report(pass_count=10),
        dom_data=_dom(),
    )
    assert result.schema_version == 2
    assert SCHEMA_VERSION == 2


def test_json_output_carries_required_keys():
    previous = _prev_run(score=90.0, issues=[])
    result = evaluate(
        url="https://x.com",
        wcag_report=_report(pass_count=9, fail_criterion="2.5.8"),
        dom_data=_dom(axe_violations=[
            {"impact": "critical", "id": "x", "nodes": [{"target": ["a"]}], "description": "d"}
        ]),
        previous_run=previous,
        min_score=50,
    )
    data = json.loads(result.to_json())
    required = {
        "schema_version", "url", "mode", "score", "score_previous",
        "score_delta", "wcag_violation_total", "aa_violation_total",
        "axe_critical", "axe_serious", "new_violations",
        "fixed_violations", "pre_existing_violations",
        "thresholds", "exit_code", "errors", "pragmatic_config",
    }
    assert required.issubset(data.keys())
    assert data["mode"] == "pragmatic"
    assert data["pragmatic_config"] is not None
    assert data["pragmatic_config"]["severity_floor"] == "serious"


def test_strict_mode_omits_pragmatic_config_in_json():
    result = evaluate(
        url="https://x.com",
        wcag_report=_report(pass_count=10),
        dom_data=_dom(),
        strict=True,
    )
    data = json.loads(result.to_json())
    assert data["mode"] == "strict"
    assert data["pragmatic_config"] is None


# ── Human output ──


# ── Internal helpers: fingerprinting + severity ──


def test_violation_fingerprint_key_is_stable():
    from src.analysis.ci_runner import ViolationFingerprint
    a = ViolationFingerprint("2.5.8", "button.x", "20x20px")
    b = ViolationFingerprint("2.5.8", "button.x", "20x20px")
    assert a.key == b.key
    # And sensitive to each field
    c = ViolationFingerprint("2.5.8", "button.x", "22x22px")
    assert a.key != c.key


def test_pragmatic_config_impacts_above_floor():
    # serious floor (default) → serious + critical
    assert PragmaticConfig(severity_floor="serious").impacts_above_floor() == {"serious", "critical"}
    # critical floor → only critical
    assert PragmaticConfig(severity_floor="critical").impacts_above_floor() == {"critical"}
    # moderate floor → moderate + serious + critical
    assert PragmaticConfig(severity_floor="moderate").impacts_above_floor() == {"moderate", "serious", "critical"}
    # minor floor → everything
    assert PragmaticConfig(severity_floor="minor").impacts_above_floor() == {"minor", "moderate", "serious", "critical"}
    # unknown floor → falls back to serious
    assert PragmaticConfig(severity_floor="bogus").impacts_above_floor() == {"serious", "critical"}


def test_fingerprint_wcag_criterion_level_failure_with_no_violations():
    """Criteria like 3.1.1 Language fail without a per-element list."""
    from src.analysis.ci_runner import _fingerprint_wcag_violations
    report = WcagReport()
    report.results.append(WcagResult(
        criterion="3.1.1 Language of Page", level="A", status="fail",
        details="Missing lang attribute on <html>", count=1, violations=[],
    ))
    fps = _fingerprint_wcag_violations(report)
    assert len(fps) == 1
    assert fps[0].criterion == "3.1.1 Language of Page"
    assert fps[0].element == ""
    assert "lang" in fps[0].issue.lower()


def test_fingerprint_wcag_expands_violation_list():
    from src.analysis.ci_runner import _fingerprint_wcag_violations
    report = WcagReport()
    report.results.append(WcagResult(
        criterion="2.5.8", level="AA", status="fail", details="2 below",
        count=2,
        violations=[
            {"element": "button.a", "issue": "20x20"},
            {"element": "button.b", "issue": "16x16"},
        ],
    ))
    fps = _fingerprint_wcag_violations(report)
    assert len(fps) == 2
    elements = {f.element for f in fps}
    assert elements == {"button.a", "button.b"}


def test_fingerprint_wcag_ignores_passes_and_warnings():
    from src.analysis.ci_runner import _fingerprint_wcag_violations
    report = WcagReport()
    report.results.append(WcagResult("pass-x", "AA", "pass", "ok"))
    report.results.append(WcagResult("warn-x", "AA", "warning", "close"))
    report.results.append(WcagResult(
        "fail-x", "AA", "fail", "bad", count=1,
        violations=[{"element": "a", "issue": "bad"}],
    ))
    fps = _fingerprint_wcag_violations(report)
    assert len(fps) == 1


def test_fingerprint_axe_multi_node_produces_multiple_fingerprints():
    from src.analysis.ci_runner import _fingerprint_axe_violations
    dom = {"axe_results": {"violations": [
        {
            "id": "color-contrast",
            "impact": "serious",
            "description": "Elements must have sufficient contrast",
            "nodes": [{"target": [".a"]}, {"target": [".b"]}, {"target": [".c"]}],
        }
    ]}}
    fps = _fingerprint_axe_violations(dom, {"serious", "critical"})
    assert len(fps) == 3
    assert {f.element for f in fps} == {".a", ".b", ".c"}


def test_fingerprint_axe_respects_severity_filter():
    from src.analysis.ci_runner import _fingerprint_axe_violations
    dom = {"axe_results": {"violations": [
        {"id": "a", "impact": "critical", "description": "",
         "nodes": [{"target": [".x"]}]},
        {"id": "b", "impact": "minor", "description": "",
         "nodes": [{"target": [".y"]}]},
        {"id": "c", "impact": "moderate", "description": "",
         "nodes": [{"target": [".z"]}]},
    ]}}
    # Only critical + serious gate
    fps = _fingerprint_axe_violations(dom, {"critical", "serious"})
    elements = {f.element for f in fps}
    assert ".x" in elements
    assert ".y" not in elements
    assert ".z" not in elements


def test_baseline_keys_reads_from_run_record_issues():
    from src.analysis.ci_runner import _baseline_keys
    prev = RunRecord(
        timestamp="2026-01-01", url="https://x.com", device="desktop",
        pages_crawled=1, score=80, wcag_score=80.0,
        issues=[
            {"criterion": "2.5.8", "element": "button.x", "details": "20x20"},
            {"criterion": "axe:color-contrast", "element": ".a", "details": "serious fail"},
        ],
    )
    keys = _baseline_keys(prev)
    assert "2.5.8|button.x|20x20" in keys
    assert "axe:color-contrast|.a|serious fail" in keys


def test_baseline_keys_empty_when_no_previous_run():
    from src.analysis.ci_runner import _baseline_keys
    assert _baseline_keys(None) == set()


# ── Integration scenarios ──


def test_pragmatic_mixed_new_fixed_persistent():
    """A run that introduces 1 new, fixes 2 old, keeps 1 persistent."""
    previous = _prev_run(score=80.0, issues=[
        _fp_dict("2.5.8", "button.persistent", "20x20"),
        _fp_dict("2.5.8", "button.fixed-1", "18x18"),
        _fp_dict("2.5.8", "button.fixed-2", "16x16"),
    ])
    current_report = _report(pass_count=9)
    current_report.results.append(WcagResult(
        criterion="2.5.8", level="AA", status="fail", details="2 below",
        count=2,
        violations=[
            {"element": "button.persistent", "issue": "20x20"},  # same as baseline
            {"element": "button.new", "issue": "12x12"},  # new
        ],
    ))
    result = evaluate(
        url="https://x.com",
        wcag_report=current_report,
        dom_data=_dom(),
        previous_run=previous,
    )
    assert len(result.new_violations) == 1
    assert result.new_violations[0]["element"] == "button.new"
    assert len(result.fixed_violations) == 2
    assert len(result.pre_existing_violations) == 1
    assert result.pre_existing_violations[0]["element"] == "button.persistent"
    assert result.exit_code == EXIT_THRESHOLD_FAILED  # 1 new fails the gate


def test_score_delta_computed_correctly():
    previous = _prev_run(score=75.0, issues=[])
    result = evaluate(
        url="https://x.com",
        wcag_report=_report(pass_count=8, fail_criterion="x"),  # 88.9%
        dom_data=_dom(),
        previous_run=previous,
    )
    assert result.score_previous == 75.0
    # 8/9 = 88.9%, delta = +13.9
    assert result.score_delta is not None
    assert result.score_delta > 13 and result.score_delta < 14


def test_score_delta_none_when_no_baseline():
    result = evaluate(
        url="https://x.com",
        wcag_report=_report(pass_count=10),
        dom_data=_dom(),
        previous_run=None,
    )
    assert result.score_previous is None
    assert result.score_delta is None


def test_strict_mode_with_min_score_combined():
    result = evaluate(
        url="https://x.com",
        wcag_report=_report(pass_count=9, fail_criterion="2.5.8"),  # 90%
        dom_data=_dom(),
        previous_run=_prev_run(score=90.0, issues=[]),
        strict=True,
        min_score=70,
    )
    # 1 A/AA violation (from fail_criterion) → strict fails; min-score passes.
    names = [t.name for t in result.thresholds]
    assert "min-score" in names
    assert "strict/no-aa-violations" in names
    assert result.exit_code == EXIT_THRESHOLD_FAILED


def test_pragmatic_config_populated_in_result():
    cfg = PragmaticConfig(severity_floor="critical", score_tolerance=5.0)
    result = evaluate(
        url="https://x.com",
        wcag_report=_report(pass_count=10),
        dom_data=_dom(),
        pragmatic=cfg,
    )
    assert result.pragmatic_config is not None
    assert result.pragmatic_config["severity_floor"] == "critical"
    assert result.pragmatic_config["score_tolerance"] == 5.0


def test_baseline_captured_threshold_has_explanatory_detail():
    """First run should produce a threshold with helpful detail text."""
    result = evaluate(
        url="https://x.com",
        wcag_report=_report(pass_count=10),
        dom_data=_dom(),
        previous_run=None,
    )
    baseline_th = [t for t in result.thresholds if "baseline" in t.name]
    assert baseline_th
    assert "first run" in baseline_th[0].detail.lower()
    assert baseline_th[0].passed


def test_human_output_shows_mode_and_buckets():
    previous = _prev_run(score=85.0, issues=[])
    result = evaluate(
        url="https://x.com",
        wcag_report=_report(pass_count=10),
        dom_data=_dom(axe_violations=[
            {"impact": "critical", "id": "x", "nodes": [{"target": ["a"]}], "description": "d"}
        ]),
        previous_run=previous,
    )
    out = result.to_human()
    assert "pragmatic" in out
    assert "new" in out.lower()
    assert "pre-existing" in out.lower()
    assert "Exit:" in out
