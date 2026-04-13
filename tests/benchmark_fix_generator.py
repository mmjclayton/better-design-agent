"""
Benchmark: Auto-Fix Generator Output Quality

Runs the fix generator against a fixture set of WCAG reports and scores the
output across objective dimensions: coverage (did we emit a fix for every
deterministic failure?), correctness (do the emitted colours / dimensions
actually meet WCAG?), discipline (did we correctly skip non-deterministic
failures?), and selector quality.

Run: python -m tests.benchmark_fix_generator

This benchmark is deterministic — scores should be stable across runs and
regress only if the fix generator's logic changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.analysis.fix_generator import (
    _contrast_ratio,
    _parse_color,
    generate_fixes,
)
from src.analysis.wcag_checker import WcagReport, WcagResult


RUBRIC_MAX = {
    "coverage": 25,
    "contrast_accuracy": 25,
    "target_size_accuracy": 15,
    "html_snippet_validity": 15,
    "determinism_discipline": 10,
    "selector_quality": 10,
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


# ── Fixtures ──


def _contrast_violation(text_hex: str, bg_hex: str, ratio: float, required: float, elem: str):
    return {
        "element": elem,
        "text": "sample",
        "ratio": ratio,
        "issue": f"{text_hex} on {bg_hex} = {ratio}:1 (requires {required}:1)",
    }


CONTRAST_FIXTURES = [
    # (text, bg, current_ratio, required, selector)
    ("#aaaaaa", "#ffffff", 2.3, 4.5, "p.muted"),
    ("#888888", "#ffffff", 3.5, 4.5, "a.link"),
    ("#666666", "#eeeeee", 3.2, 4.5, "span.caption"),
    ("#cccccc", "#000000", 10.4, 4.5, "p.hint"),   # already passing, included to test parser edge
    ("#777777", "#f5f5f5", 3.8, 4.5, "small.footer-note"),
    ("#ff0000", "#ffffff", 4.0, 4.5, "span.error"),
    ("#0066cc", "#ffffff", 4.2, 4.5, "a.primary"),
    ("#444444", "#222222", 1.8, 4.5, "p.dark-muted"),
    ("#bbbbbb", "#ffffff", 1.9, 7.0, "h1.aaa-heading"),  # AAA-level 7:1 requirement
    ("#999999", "#ffffff", 2.8, 4.5, "button.secondary"),
]


TARGET_SIZE_FIXTURES = [
    ("button.icon-close", "20x20px"),
    ("a.tag", "18x14px"),
    ("button.arrow", "16x16px"),
    ("a.breadcrumb", "22x18px"),
    ("button.dot", "12x12px"),
]


FORM_LABEL_FIXTURES = [
    ("input", 'Input type=email has no label (placeholder: "Your email")'),
    ("input", 'Input type=text has no label (placeholder: "Search")'),
    ("select", 'Select has no label (first option: "Choose one")'),
]


def build_fixture_report() -> WcagReport:
    """Synthesise a mixed pass/fail/warning report covering every criterion."""
    report = WcagReport()

    # Contrast (AA) — fail with 10 violations
    report.results.append(
        WcagResult(
            criterion="1.4.3 Contrast (Minimum)",
            level="AA",
            status="fail",
            details=f"{len(CONTRAST_FIXTURES)} text/background pairs below required ratio",
            count=len(CONTRAST_FIXTURES),
            violations=[
                _contrast_violation(t, b, r, req, sel)
                for (t, b, r, req, sel) in CONTRAST_FIXTURES
            ],
        )
    )

    # Non-text contrast (AA) — fail
    report.results.append(
        WcagResult(
            criterion="1.4.11 Non-text Contrast",
            level="AA",
            status="fail",
            details="2 UI components below 3:1",
            count=2,
            violations=[
                {
                    "element": "input.search",
                    "text": "",
                    "ratio": 1.2,
                    "issue": "#fafafa vs #ffffff = 1.2:1",
                },
                {
                    "element": "button.ghost",
                    "text": "",
                    "ratio": 1.1,
                    "issue": "#111111 vs #222222 = 1.1:1",
                },
            ],
        )
    )

    # Target size (AA) — fail
    report.results.append(
        WcagResult(
            criterion="2.5.8 Target Size (Minimum)",
            level="AA",
            status="fail",
            details=f"{len(TARGET_SIZE_FIXTURES)} elements below 24x24px",
            count=len(TARGET_SIZE_FIXTURES),
            violations=[
                {"element": sel, "text": "", "size": size, "issue": "Below 24x24px minimum"}
                for (sel, size) in TARGET_SIZE_FIXTURES
            ],
        )
    )

    # Language (A) — fail
    report.results.append(
        WcagResult(
            criterion="3.1.1 Language of Page",
            level="A",
            status="fail",
            details="Missing lang attribute on <html>",
            count=1,
            violations=[{"issue": "No lang attribute on <html> element"}],
        )
    )

    # Bypass blocks (A) — fail
    report.results.append(
        WcagResult(
            criterion="2.4.1 Bypass Blocks",
            level="A",
            status="fail",
            details="No skip navigation link found",
            count=1,
            violations=[{"issue": "Add skip link"}],
        )
    )

    # Landmarks (A) — fail
    report.results.append(
        WcagResult(
            criterion="1.3.1 Info and Relationships (Landmarks)",
            level="A",
            status="fail",
            details="Missing 2 required landmarks",
            count=2,
            violations=[
                {"element": "<main>", "issue": "Missing main content area landmark"},
                {"element": "<nav>", "issue": "Missing navigation landmark"},
            ],
        )
    )

    # Headings (A) — fail
    report.results.append(
        WcagResult(
            criterion="1.3.1 Info and Relationships (Headings)",
            level="A",
            status="fail",
            details="2 heading hierarchy issues",
            count=2,
            violations=[
                {"issue": "No <h1> element found"},
                {"issue": 'Heading level skipped: <h2> followed by <h4>'},
            ],
        )
    )

    # Form labels (A) — fail
    report.results.append(
        WcagResult(
            criterion="4.1.2 Name, Role, Value (Form Labels)",
            level="A",
            status="fail",
            details=f"{len(FORM_LABEL_FIXTURES)} inputs without labels",
            count=len(FORM_LABEL_FIXTURES),
            violations=[{"element": el, "issue": iss} for el, iss in FORM_LABEL_FIXTURES],
        )
    )

    # Non-deterministic failures that SHOULD be skipped
    report.results.append(
        WcagResult(
            criterion="1.4.1 Use of Color",
            level="A",
            status="fail",
            details="Manual review required",
            count=1,
            violations=[],
        )
    )

    # AAA aspirational — should be skipped (no recipe)
    report.results.append(
        WcagResult(
            criterion="2.5.5 Target Size (Enhanced)",
            level="AAA",
            status="fail",
            details="3 elements below 44x44",
            count=3,
            violations=[
                {"element": "button.a", "text": "", "size": "28x28px"},
                {"element": "button.b", "text": "", "size": "32x32px"},
                {"element": "button.c", "text": "", "size": "36x36px"},
            ],
        )
    )

    # Passes / warnings — MUST NOT generate fixes
    report.results.append(
        WcagResult("2.4.7 Focus Visible", "AA", "pass", "Global :focus-visible rules present")
    )
    report.results.append(
        WcagResult("1.4.3 Contrast (Minimum)", "AA", "warning", "two near-threshold pairs")
    )

    return report


# ── Scoring ──


def score_coverage(report: WcagReport, fixes) -> tuple[float, dict]:
    """Every deterministic failure should produce at least one fix."""
    deterministic_criteria = {
        "1.4.3 Contrast (Minimum)",
        "1.4.11 Non-text Contrast",
        "2.5.8 Target Size (Minimum)",
        "3.1.1 Language of Page",
        "2.4.1 Bypass Blocks",
        "1.3.1 Info and Relationships (Landmarks)",
        "1.3.1 Info and Relationships (Headings)",
        "4.1.2 Name, Role, Value (Form Labels)",
    }
    failing_deterministic = [
        r for r in report.results
        if r.status == "fail" and r.criterion in deterministic_criteria
    ]
    # Criteria that produced any emitted fix
    covered = set()
    for f in fixes.css_fixes:
        covered.add(f.criterion)
    for f in fixes.html_fixes:
        covered.add(f.criterion)

    hit = sum(1 for r in failing_deterministic if r.criterion in covered)
    total = len(failing_deterministic)
    pct = hit / total if total else 0
    return round(pct * RUBRIC_MAX["coverage"], 1), {
        "failing_deterministic_criteria": total,
        "criteria_with_fixes": hit,
        "missing": [r.criterion for r in failing_deterministic if r.criterion not in covered],
    }


def score_contrast_accuracy(fixes) -> tuple[float, dict]:
    """Every emitted contrast fix's new colour must meet the required ratio."""
    contrast_fixes = [f for f in fixes.css_fixes if "Contrast (Minimum)" in f.criterion]
    if not contrast_fixes:
        return 0.0, {"emitted": 0, "correct": 0, "note": "no contrast fixes emitted"}

    correct = 0
    failures = []
    for fix in contrast_fixes:
        new_color = _parse_color(fix.declarations.get("color", ""))
        # Extract background + required ratio from the reason string
        reason = fix.reason
        required = 4.5
        if "requires " in reason:
            try:
                required = float(reason.split("requires ")[1].rstrip(")").strip())
            except (ValueError, IndexError):
                pass
        # Find the fixture that matches this selector to get the bg colour
        bg_hex = None
        for t, b, _r, _req, sel in CONTRAST_FIXTURES:
            if sel == fix.selector:
                bg_hex = b
                break
        # Also allow a.aaa-heading etc.
        if bg_hex is None:
            continue

        bg_rgb = _parse_color(bg_hex)
        if new_color and bg_rgb:
            achieved = _contrast_ratio(new_color, bg_rgb)
            if achieved >= required - 0.01:  # small tolerance for rounding
                correct += 1
            else:
                failures.append(
                    f"{fix.selector}: got {round(achieved, 2)}:1, needed {required}:1"
                )

    # Only count fixes we could actually validate against fixtures
    validated = correct + len(failures)
    pct = correct / validated if validated else 0
    return round(pct * RUBRIC_MAX["contrast_accuracy"], 1), {
        "emitted": len(contrast_fixes),
        "validated": validated,
        "correct": correct,
        "failures": failures,
    }


def score_target_size_accuracy(fixes) -> tuple[float, dict]:
    """Every target-size fix must set min-width and min-height >= 24px."""
    ts_fixes = [f for f in fixes.css_fixes if "Target Size (Minimum)" in f.criterion]
    if not ts_fixes:
        return 0.0, {"emitted": 0, "note": "no target-size fixes emitted"}

    def _px(value: str) -> int:
        try:
            return int(value.replace("px", "").strip())
        except ValueError:
            return 0

    correct = 0
    failures = []
    for f in ts_fixes:
        mw = _px(f.declarations.get("min-width", "0"))
        mh = _px(f.declarations.get("min-height", "0"))
        if mw >= 24 and mh >= 24:
            correct += 1
        else:
            failures.append(f"{f.selector}: min-width={mw}, min-height={mh}")

    pct = correct / len(ts_fixes)
    return round(pct * RUBRIC_MAX["target_size_accuracy"], 1), {
        "emitted": len(ts_fixes),
        "correct": correct,
        "failures": failures,
    }


def score_html_snippet_validity(fixes) -> tuple[float, dict]:
    """HTML snippets must contain the expected patterns for each criterion."""
    expectations = {
        "Language of Page": lambda f: 'lang="' in f.after,
        "Bypass Blocks": lambda f: 'href="#' in f.after and "skip" in f.after.lower(),
        "Landmarks": lambda f: any(tag in f.after for tag in ["<main>", "<nav>", "<header>", "<footer>"]),
        "Headings": lambda f: bool(f.notes) and "heading" in (f.notes + f.title).lower(),
        "Form Labels": lambda f: "<label" in f.after and 'for="' in f.after,
    }

    checks = 0
    passed = 0
    failures = []
    for f in fixes.html_fixes:
        for needle, predicate in expectations.items():
            if needle in f.criterion:
                checks += 1
                if predicate(f):
                    passed += 1
                else:
                    failures.append(f"{f.criterion}: snippet missing expected pattern")
                break

    pct = passed / checks if checks else 0
    return round(pct * RUBRIC_MAX["html_snippet_validity"], 1), {
        "snippets_checked": checks,
        "passed": passed,
        "failures": failures,
    }


def score_determinism_discipline(report: WcagReport, fixes) -> tuple[float, dict]:
    """Non-deterministic and non-fail results must NOT produce fixes."""
    forbidden_criteria = {
        "1.4.1 Use of Color",
        "2.5.5 Target Size (Enhanced)",
        "2.4.7 Focus Visible",
    }
    violations = []

    all_fixes = list(fixes.css_fixes) + list(fixes.html_fixes)
    for f in all_fixes:
        if f.criterion in forbidden_criteria:
            violations.append(f"leaked fix for {f.criterion}")

    # Also confirm the skipped list captures non-deterministic fails
    non_det_fails = [
        r for r in report.results
        if r.status == "fail" and r.criterion in forbidden_criteria
    ]
    skipped_str = " | ".join(fixes.skipped)
    missing_from_skipped = [
        r.criterion for r in non_det_fails if r.criterion not in skipped_str
    ]

    max_points = RUBRIC_MAX["determinism_discipline"]
    if violations:
        score = 0.0  # hard fail: we generated speculative code
    else:
        # Deduct for each non-deterministic failure not recorded as skipped
        deduction = len(missing_from_skipped) * 2
        score = max(0.0, max_points - deduction)

    return round(score, 1), {
        "leaked_fixes": violations,
        "non_deterministic_failures": len(non_det_fails),
        "missing_from_skipped": missing_from_skipped,
    }


def score_selector_quality(fixes) -> tuple[float, dict]:
    """Every CSS fix needs a non-empty, non-generic selector."""
    if not fixes.css_fixes:
        return 0.0, {"emitted": 0, "note": "no CSS fixes emitted"}

    bad = []
    for f in fixes.css_fixes:
        sel = f.selector.strip()
        if not sel or sel == "?" or sel in {"*", "html", "body"}:
            bad.append(f.selector or "(empty)")

    good = len(fixes.css_fixes) - len(bad)
    pct = good / len(fixes.css_fixes)
    return round(pct * RUBRIC_MAX["selector_quality"], 1), {
        "total_css_fixes": len(fixes.css_fixes),
        "good_selectors": good,
        "bad_selectors": bad,
    }


# ── Runner ──


def run_benchmark() -> BenchmarkResult:
    report = build_fixture_report()
    fixes = generate_fixes(report)

    result = BenchmarkResult()

    score, details = score_coverage(report, fixes)
    result.scores["coverage"] = score
    result.details["coverage"] = details

    score, details = score_contrast_accuracy(fixes)
    result.scores["contrast_accuracy"] = score
    result.details["contrast_accuracy"] = details

    score, details = score_target_size_accuracy(fixes)
    result.scores["target_size_accuracy"] = score
    result.details["target_size_accuracy"] = details

    score, details = score_html_snippet_validity(fixes)
    result.scores["html_snippet_validity"] = score
    result.details["html_snippet_validity"] = details

    score, details = score_determinism_discipline(report, fixes)
    result.scores["determinism_discipline"] = score
    result.details["determinism_discipline"] = details

    score, details = score_selector_quality(fixes)
    result.scores["selector_quality"] = score
    result.details["selector_quality"] = details

    return result


def print_result(result: BenchmarkResult) -> None:
    print("\n" + "=" * 70)
    print("FIX GENERATOR BENCHMARK")
    print("=" * 70)
    print(f"\n{'Category':<28}{'Score':<12}{'Max':<8}{'Pct':<6}")
    print("-" * 54)
    for cat, max_score in RUBRIC_MAX.items():
        label = cat.replace("_", " ").title()
        s = result.scores.get(cat, 0)
        pct = round(s / max_score * 100) if max_score else 0
        print(f"{label:<28}{s:<12}{max_score:<8}{pct}%")
    print("-" * 54)
    print(f"{'TOTAL':<28}{result.total:<12}{sum(RUBRIC_MAX.values()):<8}{result.percentage}%")

    for cat, details in result.details.items():
        label = cat.replace("_", " ").title()
        print(f"\n  {label}:")
        for k, v in details.items():
            if isinstance(v, list) and len(v) > 5:
                print(f"    {k}: {v[:5]} (+{len(v) - 5} more)")
            else:
                print(f"    {k}: {v}")


def main() -> int:
    result = run_benchmark()
    print_result(result)
    # Fail the process if score regresses below the expected floor.
    if result.percentage < 90:
        print(f"\nFAIL: benchmark score {result.percentage}% below 90% floor")
        return 1
    print(f"\nPASS: benchmark score {result.percentage}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
