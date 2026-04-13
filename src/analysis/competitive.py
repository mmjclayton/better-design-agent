"""
Competitive benchmarking: side-by-side deterministic comparison of two sites.

Takes two design inputs plus their WCAG reports, scores each across a fixed
set of objective dimensions, and emits a verdict with per-category
winner/tie/loser callouts. No LLM — the comparison is reproducible.

Higher-is-better and lower-is-better metrics are tracked explicitly so the
"who wins" logic doesn't accidentally prefer more violations.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# ── Metric definition ──


@dataclass
class Metric:
    """One comparable dimension."""

    key: str
    label: str
    higher_is_better: bool
    your_value: float
    competitor_value: float
    your_display: str = ""
    competitor_display: str = ""

    def __post_init__(self):
        if not self.your_display:
            self.your_display = _fmt(self.your_value)
        if not self.competitor_display:
            self.competitor_display = _fmt(self.competitor_value)

    @property
    def winner(self) -> str:
        """Returns 'you', 'them', or 'tie'."""
        if self.your_value == self.competitor_value:
            return "tie"
        your_better = (
            self.your_value > self.competitor_value
            if self.higher_is_better
            else self.your_value < self.competitor_value
        )
        return "you" if your_better else "them"

    @property
    def delta(self) -> float:
        """Your value minus competitor, signed so positive = you better."""
        diff = self.your_value - self.competitor_value
        return diff if self.higher_is_better else -diff


def _fmt(value: float) -> str:
    if value == int(value):
        return str(int(value))
    return f"{value:.1f}"


# ── Report ──


@dataclass
class ComparisonReport:
    your_url: str
    competitor_url: str
    metrics: list[Metric] = field(default_factory=list)

    @property
    def your_wins(self) -> int:
        return sum(1 for m in self.metrics if m.winner == "you")

    @property
    def their_wins(self) -> int:
        return sum(1 for m in self.metrics if m.winner == "them")

    @property
    def ties(self) -> int:
        return sum(1 for m in self.metrics if m.winner == "tie")

    @property
    def verdict(self) -> str:
        if self.your_wins > self.their_wins:
            return f"You lead in {self.your_wins}/{len(self.metrics)} categories"
        if self.their_wins > self.your_wins:
            return f"Competitor leads in {self.their_wins}/{len(self.metrics)} categories"
        return f"Even — {self.your_wins} each, {self.ties} ties"

    def to_markdown(self) -> str:
        lines = [
            "# Competitive Comparison",
            "",
            f"**You:** {self.your_url}",
            f"**Competitor:** {self.competitor_url}",
            "",
            f"## Verdict: {self.verdict}",
            "",
            f"You: {self.your_wins} wins &nbsp;|&nbsp; "
            f"Competitor: {self.their_wins} wins &nbsp;|&nbsp; "
            f"Ties: {self.ties}",
            "",
            "## Category Scores",
            "",
            "| Category | You | Competitor | Winner |",
            "|----------|-----|------------|--------|",
        ]
        for m in self.metrics:
            marker = {"you": "**You**", "them": "**Competitor**", "tie": "Tie"}[m.winner]
            lines.append(
                f"| {m.label} | {m.your_display} | {m.competitor_display} | {marker} |"
            )

        lines += ["", "## Biggest Gaps (your side)", ""]
        losing = sorted(
            (m for m in self.metrics if m.winner == "them"),
            key=lambda m: m.delta,
        )
        if losing:
            for m in losing[:5]:
                lines.append(
                    f"- **{m.label}**: you {m.your_display} vs competitor "
                    f"{m.competitor_display}"
                )
        else:
            lines.append("- None — you match or beat competitor in every tracked category.")

        lines += ["", "## Where You Lead", ""]
        winning = sorted(
            (m for m in self.metrics if m.winner == "you"),
            key=lambda m: -abs(m.delta),
        )
        if winning:
            for m in winning[:5]:
                lines.append(
                    f"- **{m.label}**: you {m.your_display} vs competitor "
                    f"{m.competitor_display}"
                )
        else:
            lines.append("- None in this comparison.")

        return "\n".join(lines)


# ── Metric extractors ──


def _contrast_pass_rate(dom_data: dict) -> float:
    pairs = dom_data.get("contrast_pairs", [])
    if not pairs:
        return 0.0
    passing = sum(1 for p in pairs if p.get("passes_aa"))
    return round((passing / len(pairs)) * 100, 1)


def _target_size_pass_rate(dom_data: dict) -> float:
    elements = dom_data.get("interactive_elements", [])
    if not elements:
        return 0.0
    passing = sum(
        1 for e in elements
        if e.get("width", 0) >= 24 and e.get("height", 0) >= 24
    )
    return round((passing / len(elements)) * 100, 1)


def _landmark_coverage(dom_data: dict) -> float:
    landmarks = dom_data.get("html_structure", {}).get("landmarks", {})
    tracked = ["main", "nav", "header", "footer"]
    present = sum(1 for tag in tracked if landmarks.get(tag, 0) > 0)
    return round((present / len(tracked)) * 100, 1)


def _heading_valid(dom_data: dict) -> int:
    """1 if single h1 + no skipped levels, 0 otherwise."""
    headings = dom_data.get("html_structure", {}).get("headings", [])
    if not headings:
        return 0
    levels = [h["level"] for h in headings]
    if levels.count(1) != 1:
        return 0
    prev = 0
    for level in levels:
        if prev > 0 and level > prev + 1:
            return 0
        prev = level
    return 1


def _font_family_count(dom_data: dict) -> int:
    families = dom_data.get("fonts", {}).get("families", [])
    return len(families)


def _unique_text_colors(dom_data: dict) -> int:
    return len(dom_data.get("colors", {}).get("text", []))


def _design_token_count(dom_data: dict) -> int:
    tokens = dom_data.get("css_tokens", {})
    if isinstance(tokens, dict):
        # css_tokens is grouped by category, flatten
        return sum(
            len(v) if isinstance(v, (list, dict)) else 1
            for v in tokens.values()
        )
    return 0


def _interactive_count(dom_data: dict) -> int:
    return len(dom_data.get("interactive_elements", []))


def _axe_critical_count(dom_data: dict) -> int:
    axe = dom_data.get("axe_results", {})
    violations = axe.get("violations", []) if isinstance(axe, dict) else []
    return sum(
        1 for v in violations
        if v.get("impact") in ("critical", "serious")
    )


# ── Main entry ──


def build_comparison(
    your_url: str,
    competitor_url: str,
    your_dom: dict,
    competitor_dom: dict,
    your_wcag,
    competitor_wcag,
) -> ComparisonReport:
    """Score both sites across the fixed metric set and return the report."""

    metrics = [
        Metric(
            key="wcag_score",
            label="WCAG Score",
            higher_is_better=True,
            your_value=your_wcag.score_percentage,
            competitor_value=competitor_wcag.score_percentage,
            your_display=f"{your_wcag.score_percentage}%",
            competitor_display=f"{competitor_wcag.score_percentage}%",
        ),
        Metric(
            key="wcag_violations",
            label="WCAG A/AA Violations",
            higher_is_better=False,
            your_value=your_wcag.total_violations,
            competitor_value=competitor_wcag.total_violations,
        ),
        Metric(
            key="contrast_pass_rate",
            label="Contrast Pass Rate",
            higher_is_better=True,
            your_value=_contrast_pass_rate(your_dom),
            competitor_value=_contrast_pass_rate(competitor_dom),
            your_display=f"{_contrast_pass_rate(your_dom)}%",
            competitor_display=f"{_contrast_pass_rate(competitor_dom)}%",
        ),
        Metric(
            key="target_size_pass_rate",
            label="Target Size Pass Rate",
            higher_is_better=True,
            your_value=_target_size_pass_rate(your_dom),
            competitor_value=_target_size_pass_rate(competitor_dom),
            your_display=f"{_target_size_pass_rate(your_dom)}%",
            competitor_display=f"{_target_size_pass_rate(competitor_dom)}%",
        ),
        Metric(
            key="landmark_coverage",
            label="Landmark Coverage",
            higher_is_better=True,
            your_value=_landmark_coverage(your_dom),
            competitor_value=_landmark_coverage(competitor_dom),
            your_display=f"{_landmark_coverage(your_dom)}%",
            competitor_display=f"{_landmark_coverage(competitor_dom)}%",
        ),
        Metric(
            key="heading_hierarchy_valid",
            label="Heading Hierarchy Valid",
            higher_is_better=True,
            your_value=_heading_valid(your_dom),
            competitor_value=_heading_valid(competitor_dom),
            your_display="yes" if _heading_valid(your_dom) else "no",
            competitor_display="yes" if _heading_valid(competitor_dom) else "no",
        ),
        Metric(
            key="design_token_count",
            label="Design Token Count",
            higher_is_better=True,
            your_value=_design_token_count(your_dom),
            competitor_value=_design_token_count(competitor_dom),
        ),
        Metric(
            key="font_family_count",
            label="Font Family Count (lower = more disciplined)",
            higher_is_better=False,
            your_value=_font_family_count(your_dom),
            competitor_value=_font_family_count(competitor_dom),
        ),
        Metric(
            key="unique_text_colors",
            label="Text Colour Palette Size",
            higher_is_better=False,
            your_value=_unique_text_colors(your_dom),
            competitor_value=_unique_text_colors(competitor_dom),
        ),
        Metric(
            key="axe_critical_serious",
            label="Axe Critical + Serious Issues",
            higher_is_better=False,
            your_value=_axe_critical_count(your_dom),
            competitor_value=_axe_critical_count(competitor_dom),
        ),
    ]

    return ComparisonReport(
        your_url=your_url,
        competitor_url=competitor_url,
        metrics=metrics,
    )
