"""
Benchmark: User flow analyser correctness.

Scores: YAML validation coverage, benchmark comparison, exit-code
semantics, report rendering, JSON schema shape, flow-type coverage.

Run: python -m tests.benchmark_flow_analyzer
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from tempfile import TemporaryDirectory
from pathlib import Path

from src.analysis.flow_analyzer import (
    EXIT_FAIL,
    EXIT_PASS,
    EXIT_TECHNICAL_ERROR,
    FLOW_BENCHMARKS,
    FlowDefinition,
    FlowLoadError,
    FlowStep,
    StepResult,
    build_flow_report,
    compare_to_benchmark,
    load_flow,
)


RUBRIC_MAX = {
    "yaml_validation_coverage": 25,
    "benchmark_comparison": 15,
    "exit_code_semantics": 20,
    "report_rendering": 15,
    "json_schema_shape": 10,
    "flow_type_coverage": 15,
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


def _step(name="s", action="click", selector="button") -> FlowStep:
    return FlowStep(name=name, action=action, selector=selector)


def _result(passed=True) -> StepResult:
    return StepResult(name="s", action="click", passed=passed, duration_ms=100)


def _flow(flow_type="other", step_count=1) -> FlowDefinition:
    return FlowDefinition(
        name="f", flow_type=flow_type,
        steps=[_step() for _ in range(step_count)],
    )


# ── Scoring ──


def score_yaml_validation() -> tuple[float, dict]:
    max_points = RUBRIC_MAX["yaml_validation_coverage"]
    cases = []
    with TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # missing file
        try:
            load_flow(tmp / "missing.yaml")
            cases.append(("missing_file", False))
        except FlowLoadError:
            cases.append(("missing_file", True))

        # malformed yaml
        p = tmp / "bad.yaml"
        p.write_text("name: x\nsteps: [")
        try:
            load_flow(p)
            cases.append(("malformed", False))
        except FlowLoadError:
            cases.append(("malformed", True))

        # missing name
        p = tmp / "no-name.yaml"
        p.write_text("steps:\n  - name: s\n    action: click\n    selector: a")
        try:
            load_flow(p)
            cases.append(("missing_name", False))
        except FlowLoadError:
            cases.append(("missing_name", True))

        # empty steps
        p = tmp / "empty.yaml"
        p.write_text("name: x\nsteps: []")
        try:
            load_flow(p)
            cases.append(("empty_steps", False))
        except FlowLoadError:
            cases.append(("empty_steps", True))

        # unknown action
        p = tmp / "bad-action.yaml"
        p.write_text("name: x\nsteps:\n  - name: s\n    action: hover\n    selector: a")
        try:
            load_flow(p)
            cases.append(("unknown_action", False))
        except FlowLoadError:
            cases.append(("unknown_action", True))

        # valid flow loads
        p = tmp / "ok.yaml"
        p.write_text(
            "name: ok\nflow_type: signup\n"
            "steps:\n  - name: s\n    action: navigate\n    url: /x"
        )
        try:
            flow_def = load_flow(p)
            cases.append(("valid_loads", flow_def.flow_type == "signup"))
        except FlowLoadError:
            cases.append(("valid_loads", False))

    correct = sum(1 for _, ok in cases if ok)
    pct = correct / len(cases)
    return round(pct * max_points, 1), {
        "cases": len(cases), "correct": correct,
        "failed": [n for n, ok in cases if not ok],
    }


def score_benchmark_comparison() -> tuple[float, dict]:
    max_points = RUBRIC_MAX["benchmark_comparison"]
    cases = [
        ("signup_within", compare_to_benchmark("signup", 3).within_benchmark),
        ("signup_over", not compare_to_benchmark("signup", 4).within_benchmark),
        ("checkout_within", compare_to_benchmark("checkout", 5).within_benchmark),
        ("checkout_over", not compare_to_benchmark("checkout", 6).within_benchmark),
        ("login_within", compare_to_benchmark("login", 2).within_benchmark),
        ("other_none", compare_to_benchmark("other", 10) is None),
    ]
    correct = sum(1 for _, ok in cases if ok)
    pct = correct / len(cases)
    return round(pct * max_points, 1), {
        "cases": len(cases), "correct": correct,
        "failed": [n for n, ok in cases if not ok],
    }


def score_exit_codes() -> tuple[float, dict]:
    max_points = RUBRIC_MAX["exit_code_semantics"]
    cases = []

    # Pass
    r = build_flow_report(
        flow=_flow("signup", 2), base_url="x",
        step_results=[_result(), _result()], total_duration_ms=0,
    )
    cases.append(("pass", r.exit_code == EXIT_PASS))

    # Failed step
    r = build_flow_report(
        flow=_flow("signup", 1), base_url="x",
        step_results=[_result(passed=False)], total_duration_ms=0,
    )
    cases.append(("failed_step", r.exit_code == EXIT_FAIL))

    # Over benchmark
    r = build_flow_report(
        flow=_flow("signup", 10), base_url="x",
        step_results=[_result() for _ in range(10)], total_duration_ms=0,
    )
    cases.append(("over_benchmark", r.exit_code == EXIT_FAIL))

    # Errors
    r = build_flow_report(
        flow=_flow(), base_url="x", step_results=[], total_duration_ms=0,
        errors=["broken"],
    )
    cases.append(("errors", r.exit_code == EXIT_TECHNICAL_ERROR))

    # Other flow type + many steps = still passes (no benchmark)
    r = build_flow_report(
        flow=_flow("other", 20), base_url="x",
        step_results=[_result() for _ in range(20)], total_duration_ms=0,
    )
    cases.append(("other_no_benchmark_gate", r.exit_code == EXIT_PASS))

    correct = sum(1 for _, ok in cases if ok)
    pct = correct / len(cases)
    return round(pct * max_points, 1), {
        "cases": len(cases), "correct": correct,
        "failed": [n for n, ok in cases if not ok],
    }


def score_rendering() -> tuple[float, dict]:
    max_points = RUBRIC_MAX["report_rendering"]
    flow = _flow("signup", 2)
    results = [_result(passed=True), _result(passed=False)]
    results[1].error = "boom"
    report = build_flow_report(
        flow=flow, base_url="https://x.com",
        step_results=results, total_duration_ms=500,
    )
    md = report.to_markdown()
    required = [
        "# Flow: f", "## Benchmark", "## Step Results",
        "## Failed Steps", "boom", "**Exit code:**",
    ]
    present = sum(1 for s in required if s in md)
    pct = present / len(required)
    return round(pct * max_points, 1), {
        "expected": len(required), "present": present,
        "missing": [s for s in required if s not in md],
    }


def score_json_schema() -> tuple[float, dict]:
    max_points = RUBRIC_MAX["json_schema_shape"]
    flow = _flow("signup", 1)
    report = build_flow_report(
        flow=flow, base_url="x", step_results=[_result()], total_duration_ms=100,
    )
    data = json.loads(report.to_json())
    required = {
        "schema_version", "flow_name", "flow_type", "base_url", "timestamp",
        "total_duration_ms", "passed_count", "failed_count",
        "step_results", "benchmark", "exit_code", "errors",
    }
    present = len(required & data.keys())
    pct = present / len(required)
    return round(pct * max_points, 1), {
        "expected_keys": len(required), "present": present,
        "missing": list(required - data.keys()),
    }


def score_flow_type_coverage() -> tuple[float, dict]:
    max_points = RUBRIC_MAX["flow_type_coverage"]
    expected_types = {"signup", "checkout", "login", "onboarding"}
    present = set(FLOW_BENCHMARKS.keys())
    checks = [
        ("all_types_benchmarked", expected_types == present),
        ("each_has_max", all("max" in FLOW_BENCHMARKS[t] for t in expected_types)),
        ("each_has_description", all("description" in FLOW_BENCHMARKS[t] for t in expected_types)),
    ]
    correct = sum(1 for _, ok in checks if ok)
    pct = correct / len(checks)
    return round(pct * max_points, 1), {
        "checks": len(checks), "correct": correct,
        "failed": [n for n, ok in checks if not ok],
    }


def run_benchmark() -> BenchmarkResult:
    result = BenchmarkResult()
    for name, fn in [
        ("yaml_validation_coverage", score_yaml_validation),
        ("benchmark_comparison", score_benchmark_comparison),
        ("exit_code_semantics", score_exit_codes),
        ("report_rendering", score_rendering),
        ("json_schema_shape", score_json_schema),
        ("flow_type_coverage", score_flow_type_coverage),
    ]:
        s, d = fn()
        result.scores[name] = s
        result.details[name] = d
    return result


def print_result(result: BenchmarkResult) -> None:
    print("\n" + "=" * 70)
    print("USER FLOW ANALYSER BENCHMARK")
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
