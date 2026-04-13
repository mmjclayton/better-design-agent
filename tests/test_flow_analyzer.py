"""Tests for the user-flow analyser's pure layer.

Playwright execution is the integration point and isn't unit-tested here.
"""

import json
from datetime import datetime

import pytest

from src.analysis.flow_analyzer import (
    EXIT_FAIL,
    EXIT_PASS,
    EXIT_TECHNICAL_ERROR,
    FLOW_BENCHMARKS,
    SCHEMA_VERSION,
    FlowDefinition,
    FlowLoadError,
    FlowStep,
    StepResult,
    build_flow_report,
    compare_to_benchmark,
    load_flow,
)


def _step(name="step", action="click", **kw) -> FlowStep:
    return FlowStep(name=name, action=action, selector=kw.get("selector", "button"),
                    value=kw.get("value"), url=kw.get("url"))


def _result(name="step", passed=True, duration_ms=100, action="click") -> StepResult:
    return StepResult(name=name, action=action, passed=passed, duration_ms=duration_ms)


def _flow(name="f", flow_type="other", steps=None) -> FlowDefinition:
    return FlowDefinition(name=name, flow_type=flow_type, steps=steps or [_step()])


# ── YAML loading + validation ──


def test_load_flow_missing_file_raises(tmp_path):
    with pytest.raises(FlowLoadError) as exc:
        load_flow(tmp_path / "no.yaml")
    assert "not found" in str(exc.value).lower()


def test_load_flow_malformed_yaml_raises(tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text("name: test\nsteps:\n  - bad: [")
    with pytest.raises(FlowLoadError) as exc:
        load_flow(p)
    assert "malformed" in str(exc.value).lower()


def test_load_flow_not_mapping_raises(tmp_path):
    p = tmp_path / "list.yaml"
    p.write_text("- item\n- item")
    with pytest.raises(FlowLoadError) as exc:
        load_flow(p)
    assert "mapping" in str(exc.value).lower()


def test_load_flow_missing_name_raises(tmp_path):
    p = tmp_path / "no-name.yaml"
    p.write_text("steps:\n  - name: x\n    action: click\n    selector: a")
    with pytest.raises(FlowLoadError) as exc:
        load_flow(p)
    assert "name" in str(exc.value).lower()


def test_load_flow_invalid_type_raises(tmp_path):
    p = tmp_path / "bad-type.yaml"
    p.write_text(
        "name: x\nflow_type: bogus\n"
        "steps:\n  - name: s\n    action: click\n    selector: a"
    )
    with pytest.raises(FlowLoadError) as exc:
        load_flow(p)
    assert "flow_type" in str(exc.value).lower()


def test_load_flow_empty_steps_raises(tmp_path):
    p = tmp_path / "no-steps.yaml"
    p.write_text("name: x\nsteps: []")
    with pytest.raises(FlowLoadError) as exc:
        load_flow(p)
    assert "non-empty" in str(exc.value).lower()


def test_load_flow_unknown_action_raises(tmp_path):
    p = tmp_path / "bad-action.yaml"
    p.write_text(
        "name: x\nsteps:\n"
        "  - name: s\n    action: hover\n    selector: a"
    )
    with pytest.raises(FlowLoadError) as exc:
        load_flow(p)
    assert "action" in str(exc.value).lower()


def test_load_flow_click_requires_selector(tmp_path):
    p = tmp_path / "no-selector.yaml"
    p.write_text("name: x\nsteps:\n  - name: s\n    action: click")
    with pytest.raises(FlowLoadError) as exc:
        load_flow(p)
    assert "selector" in str(exc.value).lower()


def test_load_flow_fill_requires_value(tmp_path):
    p = tmp_path / "no-value.yaml"
    p.write_text(
        "name: x\nsteps:\n"
        "  - name: s\n    action: fill\n    selector: input"
    )
    with pytest.raises(FlowLoadError) as exc:
        load_flow(p)
    assert "value" in str(exc.value).lower()


def test_load_flow_navigate_requires_url(tmp_path):
    p = tmp_path / "no-url.yaml"
    p.write_text("name: x\nsteps:\n  - name: s\n    action: navigate")
    with pytest.raises(FlowLoadError) as exc:
        load_flow(p)
    assert "url" in str(exc.value).lower()


def test_load_flow_assert_text_requires_value(tmp_path):
    p = tmp_path / "no-text.yaml"
    p.write_text("name: x\nsteps:\n  - name: s\n    action: assert_text")
    with pytest.raises(FlowLoadError) as exc:
        load_flow(p)
    assert "value" in str(exc.value).lower()


def test_load_flow_valid_signup(tmp_path):
    p = tmp_path / "signup.yaml"
    p.write_text(
        "name: Signup\n"
        "flow_type: signup\n"
        "steps:\n"
        "  - name: Go to signup\n    action: navigate\n    url: /signup\n"
        "  - name: Fill email\n    action: fill\n    selector: input[name=email]\n    value: a@b.com\n"
        "  - name: Submit\n    action: click\n    selector: button[type=submit]\n"
        "  - name: Welcome\n    action: assert_text\n    value: Welcome\n"
    )
    flow_def = load_flow(p)
    assert flow_def.name == "Signup"
    assert flow_def.flow_type == "signup"
    assert len(flow_def.steps) == 4
    assert flow_def.steps[0].action == "navigate"
    assert flow_def.steps[1].value == "a@b.com"


def test_load_flow_default_flow_type_is_other(tmp_path):
    p = tmp_path / "nofill.yaml"
    p.write_text(
        "name: x\nsteps:\n"
        "  - name: s\n    action: click\n    selector: button"
    )
    flow_def = load_flow(p)
    assert flow_def.flow_type == "other"


def test_load_flow_custom_timeout_parsed(tmp_path):
    p = tmp_path / "timeout.yaml"
    p.write_text(
        "name: x\nsteps:\n"
        "  - name: s\n    action: click\n    selector: button\n    timeout_ms: 5000"
    )
    flow_def = load_flow(p)
    assert flow_def.steps[0].timeout_ms == 5000


# ── Benchmark comparison ──


def test_benchmark_signup_within_limit():
    cmp = compare_to_benchmark("signup", 3)
    assert cmp.within_benchmark
    assert cmp.max_allowed == 3


def test_benchmark_signup_over_limit():
    cmp = compare_to_benchmark("signup", 5)
    assert not cmp.within_benchmark


def test_benchmark_checkout_limits():
    assert compare_to_benchmark("checkout", 5).within_benchmark
    assert not compare_to_benchmark("checkout", 7).within_benchmark


def test_benchmark_login_limits():
    assert compare_to_benchmark("login", 2).within_benchmark
    assert not compare_to_benchmark("login", 3).within_benchmark


def test_benchmark_other_returns_none():
    assert compare_to_benchmark("other", 10) is None


def test_benchmark_unknown_type_returns_none():
    assert compare_to_benchmark("nonsense", 3) is None


def test_all_benchmark_types_defined():
    for t in ("signup", "checkout", "login", "onboarding"):
        assert t in FLOW_BENCHMARKS
        assert "max" in FLOW_BENCHMARKS[t]


# ── Report assembly + exit codes ──


def test_report_all_pass_within_benchmark_exits_zero():
    flow_def = _flow(flow_type="signup", steps=[_step(), _step(), _step()])
    results = [_result(), _result(), _result()]
    report = build_flow_report(
        flow=flow_def, base_url="https://x.com",
        step_results=results, total_duration_ms=500,
    )
    assert report.exit_code == EXIT_PASS
    assert report.benchmark.within_benchmark


def test_report_failed_step_exits_one():
    flow_def = _flow(flow_type="signup", steps=[_step()])
    results = [_result(passed=False)]
    report = build_flow_report(
        flow=flow_def, base_url="https://x.com",
        step_results=results, total_duration_ms=200,
    )
    assert report.exit_code == EXIT_FAIL


def test_report_over_benchmark_exits_one():
    flow_def = _flow(
        flow_type="signup",
        steps=[_step() for _ in range(6)],  # over signup max of 3
    )
    results = [_result() for _ in range(6)]
    report = build_flow_report(
        flow=flow_def, base_url="https://x.com",
        step_results=results, total_duration_ms=100,
    )
    assert report.exit_code == EXIT_FAIL
    assert not report.benchmark.within_benchmark


def test_report_errors_exit_two():
    flow_def = _flow()
    report = build_flow_report(
        flow=flow_def, base_url="https://x.com",
        step_results=[], total_duration_ms=0,
        errors=["Playwright launch failed"],
    )
    assert report.exit_code == EXIT_TECHNICAL_ERROR


def test_report_other_flow_type_no_benchmark():
    flow_def = _flow(flow_type="other", steps=[_step() for _ in range(20)])
    results = [_result() for _ in range(20)]
    report = build_flow_report(
        flow=flow_def, base_url="https://x.com",
        step_results=results, total_duration_ms=100,
    )
    assert report.benchmark is None
    assert report.exit_code == EXIT_PASS


# ── Counts ──


def test_report_counts():
    flow_def = _flow()
    results = [
        _result(passed=True), _result(passed=True),
        _result(passed=False), _result(passed=True),
    ]
    report = build_flow_report(
        flow=flow_def, base_url="x", step_results=results, total_duration_ms=0,
    )
    assert report.passed_count == 3
    assert report.failed_count == 1


# ── Rendering ──


def test_markdown_has_all_sections():
    flow_def = _flow(name="Signup Happy Path", flow_type="signup",
                     steps=[_step(name="Go"), _step(name="Submit")])
    results = [
        _result(name="Go", passed=True, duration_ms=120),
        _result(name="Submit", passed=False, duration_ms=3000),
    ]
    results[1].error = "Element not found"
    report = build_flow_report(
        flow=flow_def, base_url="https://x.com",
        step_results=results, total_duration_ms=3120,
    )
    md = report.to_markdown()
    assert "# Flow: Signup Happy Path" in md
    assert "## Benchmark" in md
    assert "## Step Results" in md
    assert "## Failed Steps" in md
    assert "Element not found" in md
    assert "**Exit code:**" in md


def test_markdown_without_benchmark_skips_section():
    flow_def = _flow(flow_type="other")
    results = [_result()]
    report = build_flow_report(
        flow=flow_def, base_url="x", step_results=results, total_duration_ms=0,
    )
    md = report.to_markdown()
    assert "## Benchmark" not in md


def test_markdown_without_failures_skips_failed_section():
    flow_def = _flow()
    results = [_result(passed=True), _result(passed=True)]
    report = build_flow_report(
        flow=flow_def, base_url="x", step_results=results, total_duration_ms=0,
    )
    md = report.to_markdown()
    assert "## Failed Steps" not in md


def test_json_schema_shape():
    flow_def = _flow(flow_type="signup")
    results = [_result()]
    report = build_flow_report(
        flow=flow_def, base_url="https://x.com",
        step_results=results, total_duration_ms=100,
    )
    data = json.loads(report.to_json())
    required = {
        "schema_version", "flow_name", "flow_type", "base_url", "timestamp",
        "total_duration_ms", "passed_count", "failed_count",
        "step_results", "benchmark", "exit_code", "errors",
    }
    assert required.issubset(data.keys())
    assert data["schema_version"] == SCHEMA_VERSION
    assert data["benchmark"] is not None  # signup has a benchmark


def test_json_step_results_shape():
    flow_def = _flow()
    results = [_result()]
    report = build_flow_report(
        flow=flow_def, base_url="x", step_results=results, total_duration_ms=0,
    )
    data = json.loads(report.to_json())
    for r in data["step_results"]:
        assert {"name", "action", "passed", "duration_ms"}.issubset(r.keys())


def test_now_parameter_controls_timestamp():
    flow_def = _flow()
    fixed_now = datetime(2026, 1, 1, 12, 0, 0)
    report = build_flow_report(
        flow=flow_def, base_url="x", step_results=[_result()], total_duration_ms=0,
        now=fixed_now,
    )
    assert report.timestamp.startswith("2026-01-01T12:00:00")
