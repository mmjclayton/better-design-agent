"""
Benchmark: Design System Extractor correctness.

Scores: strategy selection, direct-extraction fidelity (names/values preserved),
synthesis quality (dedup, ordering, naming), file output completeness,
Tailwind config shape, token JSON shape.

Run: python -m tests.benchmark_system_extractor
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from tempfile import TemporaryDirectory
from pathlib import Path

from src.analysis.system_extractor import (
    extract_system,
    write_system_to_dir,
)


RUBRIC_MAX = {
    "strategy_selection": 15,
    "direct_fidelity": 20,
    "synthesis_naming": 20,
    "synthesis_ordering_dedup": 15,
    "file_output_completeness": 15,
    "config_shape": 15,
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


def _dom_with_tokens():
    return {"css_tokens": {
        "color": [
            {"name": "--brand-primary", "value": "#ff6600"},
            {"name": "--brand-secondary", "value": "#0066ff"},
        ],
        "font": [{"name": "--font-sans", "value": "Inter, sans-serif"}],
        "spacing": [{"name": "--space-sm", "value": "8px"}],
        "radius": [{"name": "--radius-md", "value": "8px"}],
        "other": [],
    }}


def _dom_without_tokens():
    return {
        "css_tokens": {"color": [], "font": [], "spacing": [], "radius": [], "other": []},
        "colors": {
            "text": [
                {"color": "#111111", "count": 200},
                {"color": "#333333", "count": 100},
            ],
            "background": [
                {"color": "#ffffff", "count": 300},
                {"color": "#f5f5f5", "count": 80},
            ],
        },
        "fonts": {
            "families": [
                {"family": "Inter, sans-serif"},
                {"family": "Menlo, monospace"},
            ],
            "sizes": [
                {"size": "24px"}, {"size": "14px"}, {"size": "16px"}, {"size": "12px"},
            ],
        },
        "spacing_values": [
            {"value": "24px"}, {"value": "8px"}, {"value": "16px"}, {"value": "4px"},
        ],
    }


# ── Scoring ──


def score_strategy_selection() -> tuple[float, dict]:
    max_points = RUBRIC_MAX["strategy_selection"]
    cases = []

    # Direct when tokens exist
    s = extract_system(_dom_with_tokens(), "https://x.com")
    cases.append(("direct_with_tokens", s.strategy == "direct"))

    # Synthesised when no tokens
    s = extract_system(_dom_without_tokens(), "https://x.com")
    cases.append(("synthesised_without_tokens", s.strategy == "synthesised"))

    # Direct wins even when raw data present
    dom = _dom_without_tokens()
    dom["css_tokens"]["color"] = [{"name": "--x", "value": "#000"}]
    s = extract_system(dom, "https://x.com")
    cases.append(("direct_preferred", s.strategy == "direct"))

    correct = sum(1 for _, ok in cases if ok)
    pct = correct / len(cases)
    return round(pct * max_points, 1), {
        "cases": len(cases), "correct": correct,
        "failed": [n for n, ok in cases if not ok],
    }


def score_direct_fidelity() -> tuple[float, dict]:
    max_points = RUBRIC_MAX["direct_fidelity"]
    s = extract_system(_dom_with_tokens(), "https://x.com")
    checks = [
        ("two_colours", len(s.colours) == 2),
        ("brand_primary_preserved",
         any(t.name == "--brand-primary" and t.value == "#ff6600" for t in s.colours)),
        ("font_sans_preserved",
         any(t.name == "--font-sans" for t in s.typography)),
        ("spacing_token_type_dimension",
         s.spacing[0].type == "dimension"),
        ("colour_token_type_color",
         s.colours[0].type == "color"),
    ]
    correct = sum(1 for _, ok in checks if ok)
    pct = correct / len(checks)
    return round(pct * max_points, 1), {
        "checks": len(checks), "correct": correct,
        "failed": [n for n, ok in checks if not ok],
    }


def score_synthesis_naming() -> tuple[float, dict]:
    max_points = RUBRIC_MAX["synthesis_naming"]
    s = extract_system(_dom_without_tokens(), "https://x.com")
    names = {t.name for t in s.typography}
    checks = [
        ("colours_numbered", s.colours[0].name == "--color-1"),
        ("font_sans_semantic", "--font-sans" in names),
        ("font_mono_semantic", "--font-mono" in names),
        ("font_size_scale_used", any("--font-size-" in t.name for t in s.typography)),
        ("spacing_numbered", s.spacing[0].name == "--space-1"),
    ]
    correct = sum(1 for _, ok in checks if ok)
    pct = correct / len(checks)
    return round(pct * max_points, 1), {
        "checks": len(checks), "correct": correct,
        "failed": [n for n, ok in checks if not ok],
    }


def score_synthesis_ordering() -> tuple[float, dict]:
    max_points = RUBRIC_MAX["synthesis_ordering_dedup"]
    s = extract_system(_dom_without_tokens(), "https://x.com")
    # Spacing should be ascending 4 -> 24
    space_values = [t.value for t in s.spacing]
    # Font sizes also ascending
    size_tokens = [t for t in s.typography if t.name.startswith("--font-size-")]
    size_values_px = [
        float(t.value.replace("px", "")) for t in size_tokens
    ]
    checks = [
        ("spacing_ascending", space_values == ["4px", "8px", "16px", "24px"]),
        ("font_sizes_ascending", size_values_px == sorted(size_values_px)),
        ("no_duplicate_colours", len(s.colours) == 4),  # 2 text + 2 bg, all unique
    ]
    correct = sum(1 for _, ok in checks if ok)
    pct = correct / len(checks)
    return round(pct * max_points, 1), {
        "checks": len(checks), "correct": correct,
        "failed": [n for n, ok in checks if not ok],
    }


def score_file_output() -> tuple[float, dict]:
    max_points = RUBRIC_MAX["file_output_completeness"]
    with TemporaryDirectory() as tmpdir:
        s = extract_system(_dom_with_tokens(), "https://x.com")
        result = write_system_to_dir(s, Path(tmpdir) / "out")
        names = {p.name for p in result.files_written}
        expected = {
            "tokens.css", "colours.css", "typography.css", "spacing.css",
            "tokens.json", "README.md", "tailwind.config.js",
        }
        checks = [
            ("all_files_present", expected == names),
            ("tokens_css_nonempty",
             (result.output_dir / "tokens.css").read_text().strip() != ""),
            ("tokens_json_valid",
             bool(json.loads((result.output_dir / "tokens.json").read_text()))),
            ("readme_mentions_source",
             "https://x.com" in (result.output_dir / "README.md").read_text()),
        ]
    correct = sum(1 for _, ok in checks if ok)
    pct = correct / len(checks)
    return round(pct * max_points, 1), {
        "checks": len(checks), "correct": correct,
        "failed": [n for n, ok in checks if not ok],
    }


def score_config_shape() -> tuple[float, dict]:
    max_points = RUBRIC_MAX["config_shape"]
    with TemporaryDirectory() as tmpdir:
        s = extract_system(_dom_with_tokens(), "https://x.com")
        result = write_system_to_dir(s, Path(tmpdir) / "out")
        tw = (result.output_dir / "tailwind.config.js").read_text()
        json_data = json.loads((result.output_dir / "tokens.json").read_text())

    tw_checks = [
        ("module_exports", "module.exports" in tw),
        ("theme_extend", "theme:" in tw and "extend:" in tw),
        ("colors_block", "colors:" in tw),
        ("spacing_block", "spacing:" in tw),
        ("var_references", "var(--brand-primary)" in tw),
    ]
    json_checks = [
        ("has_schema_version", json_data.get("schema_version") == 1),
        ("has_strategy", json_data.get("strategy") == "direct"),
        ("tokens_are_list", isinstance(json_data.get("tokens"), list)),
        ("figma_shape",
         all({"name", "value", "type"}.issubset(t.keys()) for t in json_data["tokens"])),
    ]
    all_checks = tw_checks + json_checks
    correct = sum(1 for _, ok in all_checks if ok)
    pct = correct / len(all_checks)
    return round(pct * max_points, 1), {
        "checks": len(all_checks), "correct": correct,
        "failed": [n for n, ok in all_checks if not ok],
    }


def run_benchmark() -> BenchmarkResult:
    result = BenchmarkResult()
    for name, fn in [
        ("strategy_selection", score_strategy_selection),
        ("direct_fidelity", score_direct_fidelity),
        ("synthesis_naming", score_synthesis_naming),
        ("synthesis_ordering_dedup", score_synthesis_ordering),
        ("file_output_completeness", score_file_output),
        ("config_shape", score_config_shape),
    ]:
        s, d = fn()
        result.scores[name] = s
        result.details[name] = d
    return result


def print_result(result: BenchmarkResult) -> None:
    print("\n" + "=" * 70)
    print("DESIGN SYSTEM EXTRACTOR BENCHMARK")
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
