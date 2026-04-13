"""
Benchmark: Competitive Comparison correctness.

Verifies the comparison module on fabricated DOM fixtures with known winners.
Scores across: metric coverage, winner correctness, symmetry (swap both sides
→ flip verdicts), tie handling, and markdown output completeness.

Run: python -m tests.benchmark_competitive
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.analysis.competitive import build_comparison
from src.analysis.wcag_checker import WcagReport, WcagResult


RUBRIC_MAX = {
    "metric_count": 10,
    "winner_correctness": 30,
    "symmetry": 20,
    "tie_handling": 15,
    "lower_is_better_discipline": 15,
    "markdown_shape": 10,
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
    base = {
        "contrast_pairs": [],
        "interactive_elements": [],
        "html_structure": {"landmarks": {}, "headings": []},
        "fonts": {"families": []},
        "colors": {"text": []},
        "css_tokens": {},
        "axe_results": {"violations": []},
    }
    hs = base["html_structure"]
    base.update({k: v for k, v in overrides.items() if k not in ("landmarks", "headings")})
    if "landmarks" in overrides:
        hs["landmarks"] = overrides["landmarks"]
    if "headings" in overrides:
        hs["headings"] = overrides["headings"]
    return base


def _wcag(score: float) -> WcagReport:
    report = WcagReport()
    passes = int(score / 10)
    for _ in range(passes):
        report.results.append(WcagResult("x", "AA", "pass", "ok"))
    for _ in range(10 - passes):
        report.results.append(
            WcagResult("y", "AA", "fail", "nope", count=1, violations=[{"i": 1}])
        )
    return report


# ── Fixtures: winners known in advance ──


def _strong_dom():
    return _dom(
        contrast_pairs=[{"passes_aa": True}] * 10,
        interactive_elements=[{"width": 48, "height": 48}] * 5,
        landmarks={"main": 1, "nav": 1, "header": 1, "footer": 1},
        headings=[{"level": 1}, {"level": 2}, {"level": 3}],
        fonts={"families": [{"f": "Inter"}]},
        colors={"text": [{"c": "#000"}, {"c": "#333"}]},
        css_tokens={"color": ["--a", "--b"], "space": ["--s1"]},
        axe_results={"violations": []},
    )


def _weak_dom():
    return _dom(
        contrast_pairs=[{"passes_aa": False}] * 10,
        interactive_elements=[{"width": 14, "height": 14}] * 5,
        landmarks={"main": 0, "nav": 0, "header": 0, "footer": 0},
        headings=[{"level": 2}, {"level": 4}],
        fonts={"families": [{"f": f} for f in "ABCDE"]},
        colors={"text": [{"c": f"#{i:03d}"} for i in range(30)]},
        css_tokens={},
        axe_results={"violations": [
            {"impact": "critical"}, {"impact": "serious"}, {"impact": "critical"}
        ]},
    )


# ── Scoring ──


def score_metric_count(report) -> tuple[float, dict]:
    max_points = RUBRIC_MAX["metric_count"]
    expected = 10
    actual = len(report.metrics)
    return (
        max_points if actual == expected else 0,
        {"expected": expected, "actual": actual},
    )


def score_winner_correctness(strong_vs_weak) -> tuple[float, dict]:
    """Strong fixture must win every single category vs weak fixture."""
    max_points = RUBRIC_MAX["winner_correctness"]
    total = len(strong_vs_weak.metrics)
    you_wins = sum(1 for m in strong_vs_weak.metrics if m.winner == "you")
    pct = you_wins / total
    return round(pct * max_points, 1), {
        "categories": total,
        "you_won": you_wins,
        "losers": [m.key for m in strong_vs_weak.metrics if m.winner != "you"],
    }


def score_symmetry(strong_vs_weak, weak_vs_strong) -> tuple[float, dict]:
    """Swapping sides must flip every metric's winner (you↔them, ties stay)."""
    max_points = RUBRIC_MAX["symmetry"]
    mismatches = []
    for m1, m2 in zip(strong_vs_weak.metrics, weak_vs_strong.metrics):
        expected = {"you": "them", "them": "you", "tie": "tie"}[m1.winner]
        if m2.winner != expected:
            mismatches.append(f"{m1.key}: {m1.winner} → expected {expected}, got {m2.winner}")
    total = len(strong_vs_weak.metrics)
    correct = total - len(mismatches)
    pct = correct / total
    return round(pct * max_points, 1), {
        "checked": total,
        "correct": correct,
        "mismatches": mismatches,
    }


def score_tie_handling(strong_vs_strong) -> tuple[float, dict]:
    """Same fixture on both sides must be all ties."""
    max_points = RUBRIC_MAX["tie_handling"]
    ties = sum(1 for m in strong_vs_strong.metrics if m.winner == "tie")
    total = len(strong_vs_strong.metrics)
    pct = ties / total
    return round(pct * max_points, 1), {
        "ties": ties,
        "total": total,
        "non_ties": [m.key for m in strong_vs_strong.metrics if m.winner != "tie"],
    }


def score_lower_is_better_discipline(strong_vs_weak) -> tuple[float, dict]:
    """A metric with more violations on the weak side must have weak=losing.

    This specifically verifies that lower-is-better metrics don't get inverted.
    """
    max_points = RUBRIC_MAX["lower_is_better_discipline"]
    # Look at violation-style metrics
    to_check = [
        m for m in strong_vs_weak.metrics
        if not m.higher_is_better
    ]
    correct = 0
    for m in to_check:
        # Weak side has more violations / larger palette / more fonts.
        # Strong side should therefore win (winner == "you").
        if m.your_value <= m.competitor_value and m.winner in ("you", "tie"):
            correct += 1
        elif m.your_value == m.competitor_value:
            correct += 1  # tie is acceptable
    pct = correct / len(to_check) if to_check else 1.0
    return round(pct * max_points, 1), {
        "lower_is_better_metrics": len(to_check),
        "correct": correct,
        "metrics": [m.key for m in to_check],
    }


def score_markdown_shape(report) -> tuple[float, dict]:
    """Rendered markdown must contain every required section."""
    max_points = RUBRIC_MAX["markdown_shape"]
    md = report.to_markdown()
    required = [
        "# Competitive Comparison",
        "## Verdict:",
        "## Category Scores",
        "## Biggest Gaps",
        "## Where You Lead",
        "| Category |",
    ]
    present = sum(1 for r in required if r in md)
    pct = present / len(required)
    return round(pct * max_points, 1), {
        "sections_expected": len(required),
        "sections_present": present,
        "missing": [r for r in required if r not in md],
    }


# ── Runner ──


def run_benchmark() -> BenchmarkResult:
    strong = _strong_dom()
    weak = _weak_dom()
    wcag_high = _wcag(90)
    wcag_low = _wcag(30)

    strong_vs_weak = build_comparison(
        your_url="https://good.example",
        competitor_url="https://bad.example",
        your_dom=strong, competitor_dom=weak,
        your_wcag=wcag_high, competitor_wcag=wcag_low,
    )
    weak_vs_strong = build_comparison(
        your_url="https://bad.example",
        competitor_url="https://good.example",
        your_dom=weak, competitor_dom=strong,
        your_wcag=wcag_low, competitor_wcag=wcag_high,
    )
    strong_vs_strong = build_comparison(
        your_url="https://good.example",
        competitor_url="https://good.example",
        your_dom=strong, competitor_dom=strong,
        your_wcag=wcag_high, competitor_wcag=wcag_high,
    )

    result = BenchmarkResult()

    s, d = score_metric_count(strong_vs_weak)
    result.scores["metric_count"] = s; result.details["metric_count"] = d

    s, d = score_winner_correctness(strong_vs_weak)
    result.scores["winner_correctness"] = s; result.details["winner_correctness"] = d

    s, d = score_symmetry(strong_vs_weak, weak_vs_strong)
    result.scores["symmetry"] = s; result.details["symmetry"] = d

    s, d = score_tie_handling(strong_vs_strong)
    result.scores["tie_handling"] = s; result.details["tie_handling"] = d

    s, d = score_lower_is_better_discipline(strong_vs_weak)
    result.scores["lower_is_better_discipline"] = s
    result.details["lower_is_better_discipline"] = d

    s, d = score_markdown_shape(strong_vs_weak)
    result.scores["markdown_shape"] = s; result.details["markdown_shape"] = d

    return result


def print_result(result: BenchmarkResult) -> None:
    print("\n" + "=" * 70)
    print("COMPETITIVE COMPARISON BENCHMARK")
    print("=" * 70)
    print(f"\n{'Category':<32}{'Score':<12}{'Max':<8}{'Pct':<6}")
    print("-" * 58)
    for cat, max_score in RUBRIC_MAX.items():
        label = cat.replace("_", " ").title()
        s = result.scores.get(cat, 0)
        pct = round(s / max_score * 100) if max_score else 0
        print(f"{label:<32}{s:<12}{max_score:<8}{pct}%")
    print("-" * 58)
    print(f"{'TOTAL':<32}{result.total:<12}{sum(RUBRIC_MAX.values()):<8}{result.percentage}%")

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
    if result.percentage < 90:
        print(f"\nFAIL: benchmark score {result.percentage}% below 90% floor")
        return 1
    print(f"\nPASS: benchmark score {result.percentage}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
