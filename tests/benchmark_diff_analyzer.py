"""
Benchmark: Before/After Diff correctness.

Scores the diff analyser across: fingerprint-diff correctness, exit-code
semantics (matches CI gate behaviour), markdown section completeness, visual
diff detection on synthesised image pairs, score delta math, and JSON schema
shape.

Run: python -m tests.benchmark_diff_analyzer
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image, ImageDraw

from src.analysis.diff_analyzer import (
    EXIT_PASS,
    EXIT_THRESHOLD_FAILED,
    EXIT_TECHNICAL_ERROR,
    build_diff_report,
    diff_fingerprints,
    _compute_visual_diff,
)
from src.analysis.ci_runner import ViolationFingerprint
from src.analysis.wcag_checker import WcagReport, WcagResult


RUBRIC_MAX = {
    "fingerprint_diff_correctness": 25,
    "exit_code_semantics": 20,
    "score_delta_math": 15,
    "markdown_completeness": 10,
    "visual_diff_detection": 20,
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


# ── Scoring ──


def score_fingerprint_diff() -> tuple[float, dict]:
    """Verify all three buckets populate correctly across scenarios."""
    max_points = RUBRIC_MAX["fingerprint_diff_correctness"]
    scenarios = [
        # (before, after, expected_new_count, expected_fixed_count, expected_persistent_count)
        ([], [ViolationFingerprint("x", "a", "bad")], 1, 0, 0),
        ([ViolationFingerprint("x", "a", "bad")], [], 0, 1, 0),
        (
            [ViolationFingerprint("x", "a", "bad")],
            [ViolationFingerprint("x", "a", "bad")],
            0, 0, 1,
        ),
        (
            [
                ViolationFingerprint("x", "a", "keeps"),
                ViolationFingerprint("x", "b", "fixes"),
            ],
            [
                ViolationFingerprint("x", "a", "keeps"),
                ViolationFingerprint("x", "c", "new"),
            ],
            1, 1, 1,
        ),
    ]
    correct = 0
    details = []
    for (before, after, en, ef, ep) in scenarios:
        d = diff_fingerprints(before, after)
        actual = (len(d.new), len(d.fixed), len(d.persistent))
        expected = (en, ef, ep)
        if actual == expected:
            correct += 1
        else:
            details.append(f"expected {expected}, got {actual}")
    pct = correct / len(scenarios)
    return round(pct * max_points, 1), {
        "scenarios": len(scenarios), "correct": correct, "mismatches": details,
    }


def score_exit_codes() -> tuple[float, dict]:
    """Verify exit code matches CI gate semantics."""
    max_points = RUBRIC_MAX["exit_code_semantics"]
    cases = []

    # No new issues, score flat → PASS
    r = build_diff_report(
        before_label="a", after_label="b",
        before_wcag=_wcag(10), before_dom={},
        after_wcag=_wcag(10), after_dom={},
    )
    cases.append(("flat_run", r.exit_code == EXIT_PASS))

    # New issue introduced → FAIL
    r = build_diff_report(
        before_label="a", after_label="b",
        before_wcag=_wcag(10), before_dom={},
        after_wcag=_wcag(9, [{"element": "btn.x", "issue": "20x20"}]), after_dom={},
    )
    cases.append(("new_issue", r.exit_code == EXIT_THRESHOLD_FAILED))

    # Large score drop → FAIL
    r = build_diff_report(
        before_label="a", after_label="b",
        before_wcag=_wcag(10), before_dom={},
        after_wcag=_wcag(5, [{"element": "btn.x", "issue": "z"}]), after_dom={},
    )
    cases.append(("score_drop", r.exit_code == EXIT_THRESHOLD_FAILED))

    # Only fixes → PASS (improvement)
    r = build_diff_report(
        before_label="a", after_label="b",
        before_wcag=_wcag(9, [{"element": "btn.x", "issue": "20x20"}]), before_dom={},
        after_wcag=_wcag(10), after_dom={},
    )
    cases.append(("only_fixes", r.exit_code == EXIT_PASS))

    # Error → EXIT_TECHNICAL_ERROR
    r = build_diff_report(
        before_label="a", after_label="b", errors=["missing file"],
    )
    cases.append(("tech_error", r.exit_code == EXIT_TECHNICAL_ERROR))

    correct = sum(1 for _, ok in cases if ok)
    pct = correct / len(cases)
    return round(pct * max_points, 1), {
        "cases": len(cases), "correct": correct,
        "failed": [n for n, ok in cases if not ok],
    }


def score_score_delta() -> tuple[float, dict]:
    max_points = RUBRIC_MAX["score_delta_math"]
    cases = []

    # 100% → 90% delta = -10.0
    r = build_diff_report(
        before_label="a", after_label="b",
        before_wcag=_wcag(10), before_dom={},
        after_wcag=_wcag(9, [{"element": "x", "issue": "y"}]), after_dom={},
    )
    # 10/10=100%, after 9/10=90% → delta -10
    cases.append(("100_to_90", r.score_delta == -10.0))

    # Flat
    r = build_diff_report(
        before_label="a", after_label="b",
        before_wcag=_wcag(10), before_dom={},
        after_wcag=_wcag(10), after_dom={},
    )
    cases.append(("flat", r.score_delta == 0.0))

    # Missing wcag → None
    r = build_diff_report(before_label="a", after_label="b")
    cases.append(("no_wcag", r.score_delta is None))

    correct = sum(1 for _, ok in cases if ok)
    pct = correct / len(cases)
    return round(pct * max_points, 1), {
        "cases": len(cases), "correct": correct,
        "failed": [n for n, ok in cases if not ok],
    }


def score_markdown_completeness() -> tuple[float, dict]:
    max_points = RUBRIC_MAX["markdown_completeness"]
    r = build_diff_report(
        before_label="v1", after_label="v2",
        before_wcag=_wcag(10), before_dom={},
        after_wcag=_wcag(9, [{"element": "btn.x", "issue": "20x20"}]), after_dom={},
    )
    md = r.to_markdown()
    required = [
        "# Before / After Diff",
        "**Before:**",
        "**After:**",
        "## Score",
        "## Issue Diff",
        "### New Issues",
        "**Exit code:**",
    ]
    present = sum(1 for s in required if s in md)
    pct = present / len(required)
    return round(pct * max_points, 1), {
        "sections_expected": len(required), "sections_present": present,
        "missing": [s for s in required if s not in md],
    }


def score_visual_diff() -> tuple[float, dict]:
    max_points = RUBRIC_MAX["visual_diff_detection"]
    cases = []
    with TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # Identical → 0 regions
        a = tmp / "a.png"; b = tmp / "b.png"; out = tmp / "out.png"
        Image.new("RGB", (400, 300), (255, 255, 255)).save(a)
        Image.new("RGB", (400, 300), (255, 255, 255)).save(b)
        r, p = _compute_visual_diff(a, b, out)
        cases.append(("identical_zero", r == 0 and p is None))

        # Changed box → 1+ regions
        c = tmp / "c.png"; d = tmp / "d.png"; out2 = tmp / "out2.png"
        Image.new("RGB", (400, 300), (255, 255, 255)).save(c)
        img = Image.new("RGB", (400, 300), (255, 255, 255))
        ImageDraw.Draw(img).rectangle((100, 100, 200, 200), fill=(255, 0, 0))
        img.save(d)
        r, p = _compute_visual_diff(c, d, out2)
        cases.append(("changed_box_detected", r >= 1 and p is not None))
        cases.append(("overlay_written", out2.exists()))

        # Missing before → skip
        r, p = _compute_visual_diff(
            tmp / "missing.png", b, tmp / "out3.png",
        )
        cases.append(("missing_file_skipped", r == 0 and p is None))

    correct = sum(1 for _, ok in cases if ok)
    pct = correct / len(cases)
    return round(pct * max_points, 1), {
        "cases": len(cases), "correct": correct,
        "failed": [n for n, ok in cases if not ok],
    }


def score_json_schema() -> tuple[float, dict]:
    max_points = RUBRIC_MAX["json_schema_shape"]
    r = build_diff_report(
        before_label="v1", after_label="v2",
        before_wcag=_wcag(10), before_dom={},
        after_wcag=_wcag(9, [{"element": "btn.x", "issue": "20x20"}]), after_dom={},
    )
    data = json.loads(r.to_json())
    required = {
        "schema_version", "before_label", "after_label",
        "score_before", "score_after", "score_delta",
        "new_issues", "fixed_issues", "persistent_issues",
        "visual_diff_path", "visual_diff_regions", "exit_code", "errors",
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
        ("fingerprint_diff_correctness", score_fingerprint_diff),
        ("exit_code_semantics", score_exit_codes),
        ("score_delta_math", score_score_delta),
        ("markdown_completeness", score_markdown_completeness),
        ("visual_diff_detection", score_visual_diff),
        ("json_schema_shape", score_json_schema),
    ]:
        s, d = fn()
        result.scores[name] = s
        result.details[name] = d
    return result


def print_result(result: BenchmarkResult) -> None:
    print("\n" + "=" * 70)
    print("BEFORE/AFTER DIFF BENCHMARK")
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
