"""
Benchmark: Design Critique Output Quality

Scores critique outputs across objective, countable dimensions.
Run: python -m tests.benchmark_critique

Inputs: three critique markdown files
Output: scored comparison table + category breakdowns
"""

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class BenchmarkResult:
    name: str
    scores: dict = field(default_factory=dict)
    details: dict = field(default_factory=dict)

    @property
    def total(self) -> float:
        return sum(self.scores.values())

    @property
    def max_possible(self) -> float:
        return sum(RUBRIC_MAX.values())

    @property
    def percentage(self) -> float:
        return round((self.total / self.max_possible) * 100, 1)


# Maximum points per category
RUBRIC_MAX = {
    "specificity": 20,
    "coverage": 15,
    "actionability": 20,
    "accessibility_depth": 15,
    "design_system_awareness": 10,
    "scope": 10,
    "unique_findings": 10,
}


def count_hex_colors(text: str) -> int:
    """Count unique hex color references."""
    return len(set(re.findall(r"#[0-9a-fA-F]{3,8}", text)))


def count_pixel_values(text: str) -> int:
    """Count unique pixel measurements cited."""
    return len(set(re.findall(r"\d+(?:\.\d+)?px", text)))


def count_contrast_ratios(text: str) -> int:
    """Count contrast ratio citations (e.g., 5.25:1)."""
    return len(re.findall(r"\d+\.?\d*:\d", text))


def count_css_selectors(text: str) -> int:
    """Count CSS selector references (e.g., .class-name, var(--token))."""
    classes = len(re.findall(r"\.[a-z][a-z0-9-_]+", text, re.IGNORECASE))
    variables = len(re.findall(r"var\(--[a-z0-9-]+\)", text, re.IGNORECASE))
    tokens = len(re.findall(r"--[a-z][a-z0-9-]+", text))
    return classes + variables + tokens


def count_wcag_refs(text: str) -> int:
    """Count WCAG success criteria references."""
    criteria = len(re.findall(r"WCAG\s*\d", text, re.IGNORECASE))
    sc_refs = len(re.findall(r"\d+\.\d+\.\d+", text))
    named = len(re.findall(
        r"(?:Focus Visible|Target Size|Non-text Contrast|Bypass Blocks|"
        r"Page Titled|Headings and Labels|Language of Page|Name.? Role.? Value|"
        r"Info and Relationships|Keyboard|Identify Purpose|Focus Not Obscured)",
        text, re.IGNORECASE
    ))
    return criteria + sc_refs + named


def count_findings(text: str) -> int:
    """Count distinct findings/issues."""
    # Count structured findings by looking for bold headers and table rows with findings
    bold_findings = len(re.findall(r"\*\*[A-Z][^*]+\*\*", text))
    table_findings = len(re.findall(r"\|\s*\d+\s*\|", text))
    what_blocks = len(re.findall(r"\*\*What\*\*:", text, re.IGNORECASE))
    return max(bold_findings // 2, table_findings, what_blocks) or bold_findings


def count_fixes_with_values(text: str) -> int:
    """Count fixes that include specific values (px, hex, ratio, token name)."""
    fix_blocks = re.findall(r"\*\*Fix\*\*:?\s*([^\n]+(?:\n(?!\*\*)[^\n]+)*)", text, re.IGNORECASE)
    fix_rows = re.findall(r"\|\s*(?:Fix|Concrete Fix)\s*\|[^|]*\|?\s*\n?\|[^|]*\|([^|]+)\|", text)
    fixes = fix_blocks + fix_rows

    valued = 0
    for fix in fixes:
        if re.search(r"\d+px|#[0-9a-fA-F]{3,8}|\d+:\d|var\(--|--[a-z]", fix):
            valued += 1
    return valued


def count_pages_covered(text: str) -> int:
    """Count distinct pages/views mentioned."""
    pages = set()
    page_keywords = [
        "exercises", "exercise list", "exercise detail",
        "insights", "train", "training",
        "programs", "manage", "settings",
        "sidebar", "detail view", "detail pane",
    ]
    text_lower = text.lower()
    for kw in page_keywords:
        if kw in text_lower:
            # Normalize similar terms
            normalized = kw.replace("exercise list", "exercises").replace("exercise detail", "exercise-detail")
            normalized = normalized.replace("detail view", "exercise-detail").replace("detail pane", "exercise-detail")
            normalized = normalized.replace("training", "train")
            pages.add(normalized)
    return len(pages)


def count_element_references(text: str) -> int:
    """Count specific UI element references (buttons, inputs, cards, etc.)."""
    patterns = [
        r"(?:search|filter|nav|dropdown|select|button|input|card|stat|pill|tab|table|list|sidebar|header|chart|heatmap)",
    ]
    matches = set()
    for p in patterns:
        for m in re.finditer(p, text, re.IGNORECASE):
            matches.add(m.group().lower())
    return len(matches)


def score_specificity(text: str) -> tuple[int, dict]:
    """Score based on specific, measurable references."""
    hex_count = count_hex_colors(text)
    px_count = count_pixel_values(text)
    ratio_count = count_contrast_ratios(text)
    selector_count = count_css_selectors(text)

    details = {
        "hex_colors": hex_count,
        "pixel_values": px_count,
        "contrast_ratios": ratio_count,
        "css_selectors": selector_count,
    }

    # Score: 1 point per hex (max 5), 1 per 2 px values (max 5),
    # 1 per ratio (max 4), 1 per 2 selectors (max 6)
    score = min(hex_count, 5) + min(px_count // 2, 5) + min(ratio_count, 4) + min(selector_count // 2, 6)
    return min(score, 20), details


def score_coverage(text: str) -> tuple[int, dict]:
    """Score based on design categories covered."""
    categories = {
        "visual_hierarchy": r"visual hierarchy|hierarchy|visual weight|reading flow",
        "typography": r"typography|type scale|font size|font family|line.?height",
        "colour": r"colou?r|palette|contrast|hue|saturation",
        "spacing": r"spacing|padding|margin|gap|spacing scale",
        "layout": r"layout|grid|composition|viewport|sidebar|responsive",
        "accessibility": r"accessibility|wcag|screen reader|keyboard|a11y",
        "interaction": r"interaction|hover|focus|active|disabled|loading|states",
        "consistency": r"consistency|consistent|design system|token",
        "information_architecture": r"information architecture|navigation|content organi[sz]|progressive disclosure",
    }

    covered = {}
    for cat, pattern in categories.items():
        covered[cat] = bool(re.search(pattern, text, re.IGNORECASE))

    score = sum(covered.values())
    # Scale: 9 categories possible, max 15 points
    return min(round(score * 15 / 9), 15), covered


def score_actionability(text: str) -> tuple[int, dict]:
    """Score based on concrete, implementable fixes."""
    total_findings = count_findings(text)
    fixes_with_values = count_fixes_with_values(text)
    element_refs = count_element_references(text)

    details = {
        "total_findings": total_findings,
        "fixes_with_specific_values": fixes_with_values,
        "element_types_referenced": element_refs,
    }

    # Score: 1 per finding (max 8), 1.5 per valued fix (max 9), 0.3 per element type (max 3)
    score = min(total_findings, 8) + min(fixes_with_values * 1.5, 9) + min(element_refs * 0.3, 3)
    return min(round(score), 20), details


def score_accessibility_depth(text: str) -> tuple[int, dict]:
    """Score the depth of accessibility analysis."""
    wcag_refs = count_wcag_refs(text)
    contrast_ratios = count_contrast_ratios(text)
    touch_targets_mentioned = len(re.findall(r"touch target|target size|44.?x.?44|24.?x.?24|44px|48px", text, re.IGNORECASE))
    has_audit_section = bool(re.search(r"accessibility audit|accessibility|a11y audit", text, re.IGNORECASE))
    semantic_html = len(re.findall(r"semantic|landmark|<main>|<aside>|<nav>|<header>|aria-|role=|lang=|skip.?link|<label>", text, re.IGNORECASE))
    focus_mentions = len(re.findall(r"focus.?visible|focus.?ring|focus.?style|:focus|keyboard", text, re.IGNORECASE))

    details = {
        "wcag_references": wcag_refs,
        "contrast_ratios_cited": contrast_ratios,
        "touch_target_refs": touch_targets_mentioned,
        "has_audit_section": has_audit_section,
        "semantic_html_refs": semantic_html,
        "focus_management_refs": focus_mentions,
    }

    score = (
        min(wcag_refs, 4)
        + min(contrast_ratios, 3)
        + min(touch_targets_mentioned, 2)
        + (2 if has_audit_section else 0)
        + min(semantic_html, 2)
        + min(focus_mentions, 2)
    )
    return min(score, 15), details


def score_design_system(text: str) -> tuple[int, dict]:
    """Score awareness of existing design tokens and system recommendations."""
    existing_tokens = len(re.findall(r"--[a-z][a-z0-9-]+", text))
    proposed_tokens = len(re.findall(r"--text-|--space-|--radius-|--font-|--color-|--bg-", text))
    token_tables = len(re.findall(r"\|\s*`?--", text))
    mentions_existing = bool(re.search(r"existing|current|already|defined on|:root|partially", text, re.IGNORECASE))
    proposes_scale = bool(re.search(r"proposed|recommend|scale|token system", text, re.IGNORECASE))

    details = {
        "existing_token_refs": existing_tokens,
        "proposed_token_refs": proposed_tokens,
        "token_table_rows": token_tables,
        "acknowledges_existing_system": mentions_existing,
        "proposes_systematic_solution": proposes_scale,
    }

    score = (
        min(existing_tokens // 2, 3)
        + min(proposed_tokens, 2)
        + min(token_tables // 2, 2)
        + (2 if mentions_existing else 0)
        + (1 if proposes_scale else 0)
    )
    return min(score, 10), details


def score_scope(text: str) -> tuple[int, dict]:
    """Score breadth of analysis (pages, views, states)."""
    pages = count_pages_covered(text)
    mentions_empty_state = bool(re.search(r"empty state|empty.?state|placeholder", text, re.IGNORECASE))
    mentions_responsive = bool(re.search(r"responsive|breakpoint|mobile|viewport|screen size", text, re.IGNORECASE))
    mentions_loading = bool(re.search(r"loading|skeleton|spinner", text, re.IGNORECASE))

    details = {
        "pages_covered": pages,
        "mentions_empty_states": mentions_empty_state,
        "mentions_responsive": mentions_responsive,
        "mentions_loading_states": mentions_loading,
    }

    score = min(pages * 2, 6) + (2 if mentions_empty_state else 0) + (1 if mentions_responsive else 0) + (1 if mentions_loading else 0)
    return min(score, 10), details


def score_unique_findings(text: str, other_texts: list[str]) -> tuple[int, dict]:
    """Score findings that are unique to this output (not found in others)."""
    # Extract distinct findings as lowercase phrases
    findings = re.findall(r"\*\*([^*]+)\*\*", text)
    combined_other = " ".join(other_texts).lower()

    unique = []
    for f in findings:
        f_lower = f.lower().strip()
        # Check if the core concept appears in other outputs
        words = [w for w in f_lower.split() if len(w) > 4]
        if words and not any(w in combined_other for w in words[:3]):
            unique.append(f_lower)

    # Deduplicate
    unique = list(set(unique))[:10]

    details = {
        "unique_finding_count": len(unique),
        "examples": unique[:5],
    }

    score = min(len(unique) * 2, 10)
    return score, details


def benchmark_output(name: str, text: str, other_texts: list[str]) -> BenchmarkResult:
    """Run all benchmark categories against a critique output."""
    result = BenchmarkResult(name=name)

    score, details = score_specificity(text)
    result.scores["specificity"] = score
    result.details["specificity"] = details

    score, details = score_coverage(text)
    result.scores["coverage"] = score
    result.details["coverage"] = details

    score, details = score_actionability(text)
    result.scores["actionability"] = score
    result.details["actionability"] = details

    score, details = score_accessibility_depth(text)
    result.scores["accessibility_depth"] = score
    result.details["accessibility_depth"] = details

    score, details = score_design_system(text)
    result.scores["design_system_awareness"] = score
    result.details["design_system_awareness"] = details

    score, details = score_scope(text)
    result.scores["scope"] = score
    result.details["scope"] = details

    score, details = score_unique_findings(text, other_texts)
    result.scores["unique_findings"] = score
    result.details["unique_findings"] = details

    return result


def print_results(results: list[BenchmarkResult]):
    """Print formatted benchmark comparison."""
    print("\n" + "=" * 80)
    print("DESIGN CRITIQUE BENCHMARK")
    print("=" * 80)

    # Summary table
    print(f"\n{'Category':<30}", end="")
    for r in results:
        print(f" {r.name:<20}", end="")
    print(f" {'Max':<10}")
    print("-" * (30 + 20 * len(results) + 10))

    for category in RUBRIC_MAX:
        label = category.replace("_", " ").title()
        print(f"{label:<30}", end="")
        for r in results:
            score = r.scores.get(category, 0)
            max_score = RUBRIC_MAX[category]
            pct = round(score / max_score * 100)
            print(f" {score:>3}/{max_score:<3} ({pct:>3}%)      ", end="")
        print(f" {RUBRIC_MAX[category]:<10}")

    print("-" * (30 + 20 * len(results) + 10))
    print(f"{'TOTAL':<30}", end="")
    for r in results:
        print(f" {r.total:>3}/{r.max_possible:<3} ({r.percentage:>5}%)    ", end="")
    print()

    # Detail breakdowns
    for r in results:
        print(f"\n{'─' * 40}")
        print(f"DETAIL: {r.name}")
        print(f"{'─' * 40}")
        for category, details in r.details.items():
            label = category.replace("_", " ").title()
            print(f"\n  {label}:")
            for key, value in details.items():
                if isinstance(value, dict):
                    for k, v in value.items():
                        print(f"    {k}: {v}")
                elif isinstance(value, list):
                    print(f"    {key}: {value[:5]}")
                else:
                    print(f"    {key}: {value}")


def main():
    # File paths — Excalidraw comparison
    design_intel_deep_path = Path("output/critique-20260404-194036.md")
    design_intel_single_path = Path("output/critique-20260404-182132.md")
    excalidraw_opus_path = Path("output/excalidraw-opus.md")
    excalidraw_sonnet_path = Path("output/excalidraw-sonnet.md")
    sonnet_path = Path(
        "/Users/matt_clayton/Library/Application Support/Claude/"
        "local-agent-mode-sessions/d79e667b-cec2-487a-8759-f28e7966ed58/"
        "b7c0e6be-4d6d-484f-8c22-f19142d6e983/"
        "local_4112ca41-ffff-4a1e-b01d-5df6496b74d3/outputs/design-critique-loadout.md"
    )
    opus_path = Path(
        "/Users/matt_clayton/Library/Application Support/Claude/"
        "local-agent-mode-sessions/d79e667b-cec2-487a-8759-f28e7966ed58/"
        "b7c0e6be-4d6d-484f-8c22-f19142d6e983/"
        "local_9aaa9ecc-4258-43fc-b0ca-fef483f78e21/outputs/loadout-design-critique-opus.md"
    )

    files = {
        "di single": design_intel_single_path,
        "di deep": design_intel_deep_path,
        "Opus 4.6": excalidraw_opus_path,
        "Sonnet 4.6": excalidraw_sonnet_path,
    }

    texts = {}
    for name, path in files.items():
        if not path.exists():
            print(f"ERROR: {name} file not found: {path}")
            sys.exit(1)
        texts[name] = path.read_text()

    # Score each, passing other outputs for unique_findings comparison
    results = []
    names = list(texts.keys())
    for name in names:
        other = [texts[n] for n in names if n != name]
        result = benchmark_output(name, texts[name], other)
        results.append(result)

    print_results(results)


if __name__ == "__main__":
    main()
