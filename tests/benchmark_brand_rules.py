"""
Benchmark: Custom design-rule engine correctness.

Scores: rule-type coverage, pass/fail detection, violation counts, exit-code
semantics, YAML loading robustness, report shape, skip-when-unconfigured
discipline.

Run: python -m tests.benchmark_brand_rules
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from tempfile import TemporaryDirectory
from pathlib import Path

from src.analysis.brand_rules import (
    EXIT_PASS,
    EXIT_VIOLATIONS,
    BrandRules,
    RulesLoadError,
    evaluate_rules,
    load_rules,
)


RUBRIC_MAX = {
    "rule_type_coverage": 20,
    "violation_detection": 25,
    "exit_code_semantics": 15,
    "unconfigured_skip_discipline": 15,
    "yaml_loading_robustness": 15,
    "report_shape": 10,
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


def _dom(**overrides) -> dict:
    return {
        "fonts": {
            "families": overrides.get("fonts_families", []),
            "sizes": overrides.get("fonts_sizes", []),
        },
        "colors": {
            "text": overrides.get("colors_text", []),
            "background": overrides.get("colors_bg", []),
        },
        "css_tokens": overrides.get("tokens", {}),
    }


# ── Scoring ──


def score_rule_coverage() -> tuple[float, dict]:
    """Every rule type must emit a RuleResult in the report."""
    max_points = RUBRIC_MAX["rule_type_coverage"]
    report = evaluate_rules(BrandRules(), _dom(), url="x", rules_path="y")
    names = {r.name for r in report.results}
    expected = {
        "allowed_fonts", "allowed_colours", "min_font_size",
        "required_tokens", "forbidden_tokens",
    }
    correct = len(expected & names)
    pct = correct / len(expected)
    return round(pct * max_points, 1), {
        "expected": sorted(expected), "got": sorted(names),
        "missing": sorted(expected - names),
    }


def score_violation_detection() -> tuple[float, dict]:
    max_points = RUBRIC_MAX["violation_detection"]
    cases = []

    # Font violation
    r = evaluate_rules(
        BrandRules(allowed_fonts=["Inter"]),
        _dom(fonts_families=[{"family": "Comic Sans"}]),
        url="x", rules_path="y",
    )
    cases.append(("font_violation", not r.passed and r.violation_count == 1))

    # Colour violation
    r = evaluate_rules(
        BrandRules(allowed_colours_text=["111111"]),
        _dom(colors_text=[{"color": "#ff0000"}]),
        url="x", rules_path="y",
    )
    cases.append(("colour_violation", not r.passed and r.violation_count == 1))

    # Font-size violation
    r = evaluate_rules(
        BrandRules(min_font_size=14),
        _dom(fonts_sizes=[{"size": "10px"}, {"size": "8px"}]),
        url="x", rules_path="y",
    )
    cases.append(("font_size_violation", not r.passed and r.violation_count == 2))

    # Missing required token
    r = evaluate_rules(
        BrandRules(required_tokens=["--brand", "--ghost"]),
        _dom(tokens={"color": [{"name": "--brand"}]}),
        url="x", rules_path="y",
    )
    cases.append(("required_token_missing", not r.passed and r.violation_count == 1))

    # Forbidden token present
    r = evaluate_rules(
        BrandRules(forbidden_tokens=["--legacy"]),
        _dom(tokens={"color": [{"name": "--legacy"}]}),
        url="x", rules_path="y",
    )
    cases.append(("forbidden_token_present", not r.passed and r.violation_count == 1))

    correct = sum(1 for _, ok in cases if ok)
    pct = correct / len(cases)
    return round(pct * max_points, 1), {
        "cases": len(cases), "correct": correct,
        "failed": [n for n, ok in cases if not ok],
    }


def score_exit_codes() -> tuple[float, dict]:
    max_points = RUBRIC_MAX["exit_code_semantics"]
    cases = []

    # Pass: all rules clean
    r = evaluate_rules(
        BrandRules(allowed_fonts=["Inter"]),
        _dom(fonts_families=[{"family": "Inter"}]),
        url="x", rules_path="y",
    )
    cases.append(("pass", r.exit_code == EXIT_PASS))

    # Violation
    r = evaluate_rules(
        BrandRules(allowed_fonts=["Inter"]),
        _dom(fonts_families=[{"family": "Wrong"}]),
        url="x", rules_path="y",
    )
    cases.append(("violations_exit_one", r.exit_code == EXIT_VIOLATIONS))

    # No rules configured → all pass
    r = evaluate_rules(BrandRules(), _dom(), url="x", rules_path="y")
    cases.append(("empty_rules_pass", r.exit_code == EXIT_PASS))

    correct = sum(1 for _, ok in cases if ok)
    pct = correct / len(cases)
    return round(pct * max_points, 1), {
        "cases": len(cases), "correct": correct,
        "failed": [n for n, ok in cases if not ok],
    }


def score_unconfigured_skip() -> tuple[float, dict]:
    """Each rule must return passed=True with 'not configured' when unset."""
    max_points = RUBRIC_MAX["unconfigured_skip_discipline"]
    r = evaluate_rules(BrandRules(), _dom(
        fonts_families=[{"family": "Anything"}],
        fonts_sizes=[{"size": "2px"}],
        colors_text=[{"color": "#f0f"}],
        tokens={"color": [{"name": "--anything"}]},
    ), url="x", rules_path="y")
    cases = []
    for rule in r.results:
        cases.append((rule.name, rule.passed and "not configured" in rule.detail.lower()))
    correct = sum(1 for _, ok in cases if ok)
    pct = correct / len(cases)
    return round(pct * max_points, 1), {
        "cases": len(cases), "correct": correct,
        "failed": [n for n, ok in cases if not ok],
    }


def score_yaml_loading() -> tuple[float, dict]:
    max_points = RUBRIC_MAX["yaml_loading_robustness"]
    cases = []
    with TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # Missing file → RulesLoadError
        try:
            load_rules(tmp / "missing.yaml")
            cases.append(("missing_file_raises", False))
        except RulesLoadError:
            cases.append(("missing_file_raises", True))

        # Malformed YAML → RulesLoadError
        p = tmp / "bad.yaml"
        p.write_text(":\n  - unbalanced [")
        try:
            load_rules(p)
            cases.append(("malformed_raises", False))
        except RulesLoadError:
            cases.append(("malformed_raises", True))

        # Unknown key → RulesLoadError
        p = tmp / "unknown.yaml"
        p.write_text("bogus_key: true")
        try:
            load_rules(p)
            cases.append(("unknown_key_raises", False))
        except RulesLoadError:
            cases.append(("unknown_key_raises", True))

        # Empty file → empty BrandRules
        p = tmp / "empty.yaml"
        p.write_text("")
        try:
            r = load_rules(p)
            cases.append(("empty_file_loads", r.is_empty))
        except RulesLoadError:
            cases.append(("empty_file_loads", False))

        # Hex normalisation
        p = tmp / "colours.yaml"
        p.write_text(
            "allowed_colours:\n"
            "  text: ['#FFF', '#112233']\n"
        )
        try:
            r = load_rules(p)
            cases.append((
                "hex_normalised",
                r.allowed_colours_text == ["ffffff", "112233"],
            ))
        except RulesLoadError:
            cases.append(("hex_normalised", False))

    correct = sum(1 for _, ok in cases if ok)
    pct = correct / len(cases)
    return round(pct * max_points, 1), {
        "cases": len(cases), "correct": correct,
        "failed": [n for n, ok in cases if not ok],
    }


def score_report_shape() -> tuple[float, dict]:
    max_points = RUBRIC_MAX["report_shape"]
    r = evaluate_rules(
        BrandRules(allowed_fonts=["Inter"], min_font_size=14),
        _dom(
            fonts_families=[{"family": "Comic Sans"}],
            fonts_sizes=[{"size": "10px"}],
        ),
        url="https://x.com", rules_path="rules.yaml",
    )
    md = r.to_markdown()
    data = json.loads(r.to_json())
    checks = [
        ("md_has_title", "# Brand Compliance Report" in md),
        ("md_has_url", "https://x.com" in md),
        ("md_has_exit_code", "**Exit code:**" in md),
        ("json_has_schema_version", data.get("schema_version") == 1),
        ("json_has_results_array", isinstance(data.get("results"), list)),
    ]
    correct = sum(1 for _, ok in checks if ok)
    pct = correct / len(checks)
    return round(pct * max_points, 1), {
        "cases": len(checks), "correct": correct,
        "failed": [n for n, ok in checks if not ok],
    }


def run_benchmark() -> BenchmarkResult:
    result = BenchmarkResult()
    for name, fn in [
        ("rule_type_coverage", score_rule_coverage),
        ("violation_detection", score_violation_detection),
        ("exit_code_semantics", score_exit_codes),
        ("unconfigured_skip_discipline", score_unconfigured_skip),
        ("yaml_loading_robustness", score_yaml_loading),
        ("report_shape", score_report_shape),
    ]:
        s, d = fn()
        result.scores[name] = s
        result.details[name] = d
    return result


def print_result(result: BenchmarkResult) -> None:
    print("\n" + "=" * 70)
    print("BRAND RULES BENCHMARK")
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
