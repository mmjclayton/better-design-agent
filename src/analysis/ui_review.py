"""
Opinionated UI Review.

Deterministic analysis of typography consistency, colour discipline,
spacing coherence, interactive element polish, and visual hierarchy.
Scores each category 0-100 from real computed CSS values in the DOM
extraction data.  No LLM — pure data transformation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


# ── Category weights (must sum to 100) ──

WEIGHTS = {
    "typography": 20,
    "color": 15,
    "spacing": 15,
    "interactive": 15,
    "hierarchy": 10,
    "patterns": 15,
    "copy": 10,
}


# ── Data classes ──


@dataclass
class Finding:
    category: str
    message: str
    recommendation: str
    severity: str  # "high", "medium", "low"
    data: dict = field(default_factory=dict)


@dataclass
class CategoryScore:
    name: str
    score: int  # 0-100
    max_score: int = 100
    findings: list[Finding] = field(default_factory=list)

    def __post_init__(self):
        self.score = max(0, min(self.score, self.max_score))


@dataclass
class ProposedSystem:
    """A cleaned-up design token system proposed from raw DOM data."""
    colors: list[dict] = field(default_factory=list)       # [{name, value, role}]
    font_sizes: list[dict] = field(default_factory=list)   # [{name, value}]
    spacing: list[dict] = field(default_factory=list)      # [{name, value}]
    font_families: list[dict] = field(default_factory=list)  # [{name, value, role}]

    def to_css(self) -> str:
        """Output as CSS custom properties."""
        lines = [":root {"]
        if self.colors:
            lines.append("  /* Colors */")
            for c in self.colors:
                lines.append(f"  --color-{c['name']}: {c['value']};")
        if self.font_families:
            lines.append("  /* Typography - Families */")
            for f in self.font_families:
                lines.append(f"  --font-{f['name']}: {f['value']};")
        if self.font_sizes:
            lines.append("  /* Typography - Scale */")
            for s in self.font_sizes:
                lines.append(f"  --text-{s['name']}: {s['value']};")
        if self.spacing:
            lines.append("  /* Spacing */")
            for s in self.spacing:
                lines.append(f"  --space-{s['name']}: {s['value']};")
        lines.append("}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "colors": self.colors,
            "font_sizes": self.font_sizes,
            "spacing": self.spacing,
            "font_families": self.font_families,
            "css": self.to_css(),
        }

    def to_markdown(self) -> str:
        lines = ["### Proposed Design System\n"]
        lines.append(
            "Based on the values found in your CSS, here's a cleaned-up "
            "token system you can drop in.\n"
        )
        lines.append("```css")
        lines.append(self.to_css())
        lines.append("```\n")

        if self.colors:
            lines.append("**Colors:**")
            for c in self.colors:
                lines.append(f"- `--color-{c['name']}`: {c['value']} ({c.get('role', '')})")
            lines.append("")
        if self.font_sizes:
            lines.append("**Type scale:**")
            for s in self.font_sizes:
                lines.append(f"- `--text-{s['name']}`: {s['value']}")
            lines.append("")
        if self.spacing:
            lines.append("**Spacing scale:**")
            for s in self.spacing:
                lines.append(f"- `--space-{s['name']}`: {s['value']}")
            lines.append("")

        return "\n".join(lines)


@dataclass
class UIReviewReport:
    categories: list[CategoryScore] = field(default_factory=list)
    llm_suggestions: list[dict] = field(default_factory=list)
    proposed_system: ProposedSystem | None = None

    @property
    def overall_score(self) -> float:
        if not self.categories:
            return 0.0
        total = sum(
            c.score * WEIGHTS.get(c.name, 0)
            for c in self.categories
        )
        weight_sum = sum(WEIGHTS.get(c.name, 0) for c in self.categories)
        if weight_sum == 0:
            return 0.0
        return round(total / weight_sum, 1)

    def category_dict(self) -> dict[str, CategoryScore]:
        return {c.name: c for c in self.categories}

    @property
    def all_findings(self) -> list[Finding]:
        out: list[Finding] = []
        for c in self.categories:
            out.extend(c.findings)
        return out

    @property
    def high_findings(self) -> list[Finding]:
        return [f for f in self.all_findings if f.severity == "high"]

    def to_dict(self) -> dict:
        return {
            "schema_version": 1,
            "overall_score": self.overall_score,
            "categories": {
                c.name: {
                    "score": c.score,
                    "weight": WEIGHTS.get(c.name, 0),
                    "findings": [
                        {
                            "message": f.message,
                            "recommendation": f.recommendation,
                            "severity": f.severity,
                            "data": f.data,
                        }
                        for f in c.findings
                    ],
                }
                for c in self.categories
            },
            "llm_suggestions": self.llm_suggestions,
            "proposed_system": self.proposed_system.to_dict() if self.proposed_system else None,
        }

    def to_markdown(self) -> str:
        lines = [
            "## UI Review — Opinionated Quality Audit\n",
            f"**Overall score: {self.overall_score}/100**\n",
        ]

        # Summary table
        lines.append("| Category | Score | Weight | Findings |")
        lines.append("|----------|-------|--------|----------|")
        for c in sorted(self.categories, key=lambda x: x.score):
            weight = WEIGHTS.get(c.name, 0)
            high = sum(1 for f in c.findings if f.severity == "high")
            med = sum(1 for f in c.findings if f.severity == "medium")
            label = []
            if high:
                label.append(f"{high} high")
            if med:
                label.append(f"{med} medium")
            finding_str = ", ".join(label) if label else "clean"
            lines.append(
                f"| {c.name.title()} | {c.score}/100 | {weight}% | {finding_str} |"
            )
        lines.append("")

        # Per-category detail
        for c in sorted(self.categories, key=lambda x: x.score):
            lines.append(f"### {c.name.title()} — {c.score}/100\n")
            if not c.findings:
                lines.append("No issues found.\n")
                continue
            for f in sorted(c.findings, key=lambda x: {"high": 0, "medium": 1, "low": 2}.get(x.severity, 3)):
                severity_marker = {"high": "!!!", "medium": "!!", "low": "!"}.get(f.severity, "")
                lines.append(f"- **[{f.severity.upper()}]** {f.message}")
                lines.append(f"  - {f.recommendation}")
                if f.data:
                    for k, v in f.data.items():
                        if isinstance(v, list) and len(v) > 8:
                            v = v[:8] + [f"... +{len(v) - 8} more"]
                        lines.append(f"  - *{k}*: `{v}`")
            lines.append("")

        # Proposed design system
        if self.proposed_system:
            lines.append(self.proposed_system.to_markdown())

        # LLM suggestions
        if self.llm_suggestions:
            lines.append("### Design Suggestions\n")
            lines.append(
                "The following are LLM-generated suggestions based on the "
                "deterministic findings and a visual review of the page.\n"
            )
            for i, s in enumerate(self.llm_suggestions, 1):
                lines.append(f"**{i}. {s.get('title', 'Suggestion')}**\n")
                lines.append(f"{s.get('rationale', '')}\n")
                if s.get("action"):
                    lines.append(f"*Action:* {s['action']}\n")

        return "\n".join(lines)


# ── Scoring functions ──


def _parse_px(value: str) -> float | None:
    """Parse a CSS pixel value like '16px' to a float."""
    if not value:
        return None
    v = value.strip().lower()
    if v.endswith("px"):
        try:
            return float(v[:-2])
        except ValueError:
            return None
    return None


def _check_modular_scale(sizes_px: list[float], tolerance: float = 0.15) -> tuple[float | None, int]:
    """Check if font sizes follow a modular scale.

    Returns (best_ratio, count_on_scale).  A perfect modular scale has
    a constant ratio between consecutive sizes.  Common ratios: 1.125
    (major second), 1.2 (minor third), 1.25 (major third), 1.333
    (perfect fourth), 1.5 (perfect fifth).
    """
    if len(sizes_px) < 3:
        return None, len(sizes_px)

    sorted_sizes = sorted(set(sizes_px))
    if len(sorted_sizes) < 3:
        return None, len(sorted_sizes)

    # Try common scales
    best_ratio = None
    best_count = 0
    for ratio in [1.067, 1.125, 1.2, 1.25, 1.333, 1.414, 1.5, 1.618]:
        # Count how many sizes fit this scale from the smallest base
        base = sorted_sizes[0]
        on_scale = 1  # base always counts
        for size in sorted_sizes[1:]:
            # Check if size ≈ base * ratio^n for some integer n
            if base <= 0:
                break
            n = math.log(size / base) / math.log(ratio)
            if abs(n - round(n)) < tolerance:
                on_scale += 1
        if on_scale > best_count:
            best_count = on_scale
            best_ratio = ratio

    return best_ratio, best_count


def _grid_adherence(values_px: list[float], base: int = 4) -> float:
    """What fraction of spacing values are multiples of `base`px?"""
    if not values_px:
        return 1.0
    on_grid = sum(1 for v in values_px if v > 0 and v % base < 0.5)
    return on_grid / len(values_px)


def _score_typography(dom_data: dict) -> CategoryScore:
    """Score typography consistency and discipline."""
    findings: list[Finding] = []
    score = 100

    fonts = dom_data.get("fonts", {}) or {}
    layout = dom_data.get("layout", {}) or {}
    headings = (dom_data.get("html_structure", {}) or {}).get("headings", [])

    # ── Font families ──
    families = fonts.get("families", [])
    family_count = len(families)

    if family_count > 3:
        penalty = min(25, (family_count - 3) * 8)
        score -= penalty
        findings.append(Finding(
            category="typography",
            message=f"{family_count} font families in use — more than 3 creates visual noise.",
            recommendation="Consolidate to 2-3 families: one for headings, one for body, optionally one for code.",
            severity="high" if family_count > 4 else "medium",
            data={"families": [f"{f['family']} ({f['count']}x)" for f in families]},
        ))
    elif family_count <= 2 and family_count > 0:
        pass  # good

    # ── Font sizes ──
    sizes = fonts.get("sizes", [])
    size_count = len(sizes)
    sizes_px = [v for s in sizes if (v := _parse_px(s.get("size", ""))) is not None]

    if size_count > 8:
        penalty = min(20, (size_count - 8) * 3)
        score -= penalty
        findings.append(Finding(
            category="typography",
            message=f"{size_count} distinct font sizes — a clean type scale uses 5-8.",
            recommendation="Define a modular type scale (e.g. 12, 14, 16, 20, 24, 32) and map all text to it.",
            severity="high" if size_count > 12 else "medium",
            data={"sizes": [f"{s['size']} ({s['count']}x)" for s in sizes[:15]]},
        ))
    elif size_count < 3 and size_count > 0:
        findings.append(Finding(
            category="typography",
            message=f"Only {size_count} font sizes — may lack visual hierarchy.",
            recommendation="Ensure headings, body, and small text are differentiated.",
            severity="low",
            data={"sizes": [f"{s['size']} ({s['count']}x)" for s in sizes]},
        ))

    # ── Modular scale check ──
    if len(sizes_px) >= 4:
        ratio, on_scale = _check_modular_scale(sizes_px)
        scale_pct = on_scale / len(set(sizes_px)) if sizes_px else 0
        if scale_pct < 0.5:
            score -= 10
            findings.append(Finding(
                category="typography",
                message="Font sizes don't follow a recognisable modular scale.",
                recommendation="Adopt a scale ratio (1.25 'major third' is a safe default) for harmonious sizing.",
                severity="medium",
                data={"best_ratio": ratio, "sizes_on_scale": f"{on_scale}/{len(set(sizes_px))}"},
            ))

    # ── Body line-height ──
    body_lh = layout.get("body_line_height", "")
    body_fs = layout.get("body_font_size", "")
    if body_lh and body_fs:
        lh_px = _parse_px(body_lh)
        fs_px = _parse_px(body_fs)
        if lh_px and fs_px and fs_px > 0:
            lh_ratio = lh_px / fs_px
            if lh_ratio < 1.3:
                score -= 15
                findings.append(Finding(
                    category="typography",
                    message=f"Body line-height ratio is {lh_ratio:.2f} — too tight for comfortable reading.",
                    recommendation="Set body line-height to 1.4-1.6x the font size for readability.",
                    severity="high",
                    data={"line_height": body_lh, "font_size": body_fs, "ratio": round(lh_ratio, 2)},
                ))
            elif lh_ratio > 2.0:
                score -= 5
                findings.append(Finding(
                    category="typography",
                    message=f"Body line-height ratio is {lh_ratio:.2f} — unusually loose.",
                    recommendation="A ratio above 2.0 can make paragraphs feel disconnected. 1.5-1.7 is typical.",
                    severity="low",
                    data={"line_height": body_lh, "font_size": body_fs, "ratio": round(lh_ratio, 2)},
                ))

    # ── Body font size ──
    if body_fs:
        fs_px = _parse_px(body_fs)
        if fs_px and fs_px < 14:
            score -= 10
            findings.append(Finding(
                category="typography",
                message=f"Body font size is {body_fs} — below 14px hurts readability on most screens.",
                recommendation="Use 16px as body text baseline. 14px is acceptable for secondary text only.",
                severity="high",
                data={"body_font_size": body_fs},
            ))

    return CategoryScore(name="typography", score=score, findings=findings)


def _score_color(dom_data: dict) -> CategoryScore:
    """Score colour palette discipline."""
    findings: list[Finding] = []
    score = 100

    colors = dom_data.get("colors", {}) or {}
    text_colors = colors.get("text", [])
    bg_colors = colors.get("background", [])

    text_count = len(text_colors)
    bg_count = len(bg_colors)
    total_distinct = text_count + bg_count

    # ── Text colour count ──
    if text_count > 8:
        penalty = min(25, (text_count - 8) * 4)
        score -= penalty
        findings.append(Finding(
            category="color",
            message=f"{text_count} distinct text colours — disciplined palettes use 3-6.",
            recommendation="Define semantic colour roles (primary, secondary, muted, accent, error) and stick to them.",
            severity="high" if text_count > 12 else "medium",
            data={"text_colors": [f"{c['color']} ({c['count']}x)" for c in text_colors[:10]]},
        ))

    # ── Background colour count ──
    if bg_count > 6:
        penalty = min(20, (bg_count - 6) * 3)
        score -= penalty
        findings.append(Finding(
            category="color",
            message=f"{bg_count} distinct background colours — more than 6 suggests inconsistent surface treatment.",
            recommendation="Use 2-4 surface colours (background, card, elevated, overlay) consistently.",
            severity="high" if bg_count > 10 else "medium",
            data={"bg_colors": [f"{c['color']} ({c['count']}x)" for c in bg_colors[:10]]},
        ))

    # ── One-off colours (used only once) ──
    one_off_text = [c for c in text_colors if c.get("count", 0) == 1]
    one_off_bg = [c for c in bg_colors if c.get("count", 0) == 1]
    one_off_total = len(one_off_text) + len(one_off_bg)
    if one_off_total > 4:
        penalty = min(15, one_off_total * 2)
        score -= penalty
        findings.append(Finding(
            category="color",
            message=f"{one_off_total} colours used only once — likely inconsistencies or one-off overrides.",
            recommendation="Audit single-use colours. Most should map to an existing palette colour.",
            severity="medium",
            data={"one_off_count": one_off_total},
        ))

    # ── Dominant colour concentration ──
    # A well-designed palette has a clear primary text colour that dominates
    if text_colors:
        top_count = text_colors[0].get("count", 0)
        total_uses = sum(c.get("count", 0) for c in text_colors)
        if total_uses > 0:
            dominance = top_count / total_uses
            if dominance < 0.3:
                score -= 10
                findings.append(Finding(
                    category="color",
                    message=f"No dominant text colour — the most-used colour accounts for only {dominance:.0%} of text elements.",
                    recommendation="A primary text colour should cover 50-70% of text for visual consistency.",
                    severity="medium",
                    data={"top_color": text_colors[0].get("color"), "dominance": f"{dominance:.0%}"},
                ))

    # ── 60-30-10 colour proportion rule ──
    # Good design uses ~60% dominant, ~30% secondary, ~10% accent for backgrounds.
    if bg_colors and len(bg_colors) >= 3:
        total_bg_uses = sum(c.get("count", 0) for c in bg_colors)
        if total_bg_uses > 0:
            proportions = [c.get("count", 0) / total_bg_uses for c in bg_colors]
            dominant = proportions[0]
            secondary = proportions[1] if len(proportions) > 1 else 0
            accent_sum = sum(proportions[2:]) if len(proportions) > 2 else 0

            # Check for balanced distribution — dominant should be 45-75%
            if dominant < 0.35:
                score -= 8
                findings.append(Finding(
                    category="color",
                    message=f"Background colours lack a clear dominant — top colour is only {dominant:.0%} of usage.",
                    recommendation="The 60-30-10 rule: ~60% dominant surface, ~30% secondary, ~10% accent. "
                        f"Currently: {dominant:.0%} / {secondary:.0%} / {accent_sum:.0%}.",
                    severity="medium",
                    data={
                        "proportions": f"{dominant:.0%} / {secondary:.0%} / {accent_sum:.0%}",
                        "ideal": "~60% / ~30% / ~10%",
                    },
                ))
            elif dominant > 0.85 and len(bg_colors) >= 3:
                # One colour dominates too heavily — may lack visual interest
                score -= 3
                findings.append(Finding(
                    category="color",
                    message=f"Background is {dominant:.0%} one colour — page may feel flat or monotonous.",
                    recommendation="Introduce a secondary surface colour for cards, sections, or highlights "
                        "to create visual depth.",
                    severity="low",
                    data={"dominant_proportion": f"{dominant:.0%}"},
                ))

    return CategoryScore(name="color", score=score, findings=findings)


def _score_spacing(dom_data: dict) -> CategoryScore:
    """Score spacing consistency and grid adherence."""
    findings: list[Finding] = []
    score = 100

    spacing_values = dom_data.get("spacing_values", []) or []
    value_count = len(spacing_values)

    if not spacing_values:
        return CategoryScore(name="spacing", score=50, findings=[
            Finding(
                category="spacing",
                message="No spacing data extracted — unable to evaluate.",
                recommendation="This may indicate the page uses minimal padding/margin.",
                severity="low",
            )
        ])

    # ── Distinct value count ──
    if value_count > 15:
        penalty = min(25, (value_count - 15) * 3)
        score -= penalty
        findings.append(Finding(
            category="spacing",
            message=f"{value_count} distinct spacing values — consistent systems use 6-10.",
            recommendation="Adopt an 8-point grid (4, 8, 12, 16, 24, 32, 48, 64) and map all spacing to it.",
            severity="high" if value_count > 20 else "medium",
            data={"values": [f"{s['value']} ({s['count']}x)" for s in spacing_values[:15]]},
        ))
    elif value_count > 10:
        score -= 8
        findings.append(Finding(
            category="spacing",
            message=f"{value_count} distinct spacing values — slightly scattered.",
            recommendation="Consider consolidating to fewer values on a consistent scale.",
            severity="low",
            data={"values": [f"{s['value']} ({s['count']}x)" for s in spacing_values[:12]]},
        ))

    # ── Grid adherence ──
    px_values = [v for s in spacing_values if (v := _parse_px(s.get("value", ""))) is not None]
    if px_values:
        # Try 4px and 8px grids
        adherence_4 = _grid_adherence(px_values, 4)
        adherence_8 = _grid_adherence(px_values, 8)
        best_grid = 8 if adherence_8 >= adherence_4 * 0.8 else 4
        best_adherence = max(adherence_4, adherence_8)

        if best_adherence < 0.5:
            penalty = min(20, int((1 - best_adherence) * 30))
            score -= penalty
            findings.append(Finding(
                category="spacing",
                message=f"Only {best_adherence:.0%} of spacing values align to a {best_grid}px grid.",
                recommendation=f"Align spacing to multiples of {best_grid}px for visual rhythm. Off-grid values: "
                    + ", ".join(f"{v}px" for v in sorted(set(px_values)) if v % best_grid >= 0.5)[:6],
                severity="high" if best_adherence < 0.3 else "medium",
                data={"grid": f"{best_grid}px", "adherence": f"{best_adherence:.0%}"},
            ))
        elif best_adherence < 0.75:
            score -= 8
            off_grid = [v for v in sorted(set(px_values)) if v % best_grid >= 0.5]
            findings.append(Finding(
                category="spacing",
                message=f"{best_adherence:.0%} of spacing values align to a {best_grid}px grid — room for improvement.",
                recommendation=f"Round these off-grid values to the nearest {best_grid}px multiple: "
                    + ", ".join(f"{v}px" for v in off_grid[:6]),
                severity="low",
                data={"grid": f"{best_grid}px", "adherence": f"{best_adherence:.0%}", "off_grid": [f"{v}px" for v in off_grid[:8]]},
            ))

    # ── One-off spacing values ──
    one_offs = [s for s in spacing_values if s.get("count", 0) == 1]
    if len(one_offs) > 5:
        penalty = min(15, len(one_offs) * 2)
        score -= penalty
        findings.append(Finding(
            category="spacing",
            message=f"{len(one_offs)} spacing values used only once — indicates ad-hoc spacing.",
            recommendation="Single-use values are usually mistakes. Map them to the nearest scale value.",
            severity="medium",
            data={"one_off_values": [s["value"] for s in one_offs[:8]]},
        ))

    # ── Spacing range — too compressed or too spread ──
    if px_values and len(px_values) >= 3:
        min_space = min(px_values)
        max_space = max(px_values)
        if max_space > 0 and min_space > 0:
            range_ratio = max_space / min_space
            if range_ratio < 3:
                score -= 5
                findings.append(Finding(
                    category="spacing",
                    message=f"Spacing range is narrow ({min_space:.0f}px to {max_space:.0f}px) — "
                        "may lack visual breathing room between sections.",
                    recommendation="A healthy spacing scale typically ranges from small (4-8px) "
                        "to large (48-96px). Use generous whitespace between major sections.",
                    severity="low",
                    data={"range": f"{min_space:.0f}px–{max_space:.0f}px", "ratio": f"{range_ratio:.1f}x"},
                ))

    return CategoryScore(name="spacing", score=score, findings=findings)


def _score_interactive(dom_data: dict) -> CategoryScore:
    """Score interactive element quality and polish."""
    findings: list[Finding] = []
    score = 100

    interactive = dom_data.get("interactive_elements", []) or []
    state_tests = dom_data.get("state_tests", []) or []
    layout = dom_data.get("layout", {}) or {}
    viewport_width = layout.get("viewport_width", 0)
    is_desktop = viewport_width >= 1024

    if not interactive:
        return CategoryScore(name="interactive", score=50, findings=[
            Finding(
                category="interactive",
                message="No interactive elements detected.",
                recommendation="Page may be static content or elements were not captured.",
                severity="low",
            )
        ])

    # ── Touch targets ──
    # On desktop viewports, 44px is aspirational — 24px minimum for mouse users.
    min_size = 24 if is_desktop else 44
    if is_desktop:
        undersized = [
            el for el in interactive
            if el.get("width", 0) < min_size or el.get("height", 0) < min_size
        ]
    else:
        undersized = [el for el in interactive if not el.get("meets_touch_target")]

    if undersized:
        pct_ok = (len(interactive) - len(undersized)) / len(interactive)
        target_label = f"{min_size}x{min_size}px" + (" (desktop minimum)" if is_desktop else " touch target")
        if pct_ok < 0.7:
            penalty = min(25, int((1 - pct_ok) * 35))
            # Desktop undersized is less severe than mobile
            if is_desktop:
                penalty = penalty // 2
            score -= penalty
            findings.append(Finding(
                category="interactive",
                message=f"{len(undersized)}/{len(interactive)} interactive elements are below {target_label}.",
                recommendation=f"Ensure clickable elements meet {target_label} for comfortable interaction."
                    + (" On mobile, 44x44px is the standard." if is_desktop else ""),
                severity="medium" if is_desktop else "high",
                data={
                    "undersized": [
                        f"{el.get('element')} ({el.get('width')}x{el.get('height')}px)"
                        for el in undersized[:6]
                    ],
                    "compliance": f"{pct_ok:.0%}",
                },
            ))
        elif pct_ok < 0.9:
            score -= 5 if is_desktop else 10
            findings.append(Finding(
                category="interactive",
                message=f"{len(undersized)} interactive elements below {target_label}.",
                recommendation="Review undersized elements — small targets frustrate users.",
                severity="low" if is_desktop else "medium",
                data={"undersized_count": len(undersized), "compliance": f"{pct_ok:.0%}"},
            ))

    # ── Hover state coverage ──
    if state_tests:
        has_hover_change = 0
        for st in state_tests:
            default = st.get("default_state", {}) or {}
            hover = st.get("hover_state", {}) or {}
            if hover and default:
                # Check if any visual property changed on hover
                changed = any(
                    hover.get(k) != default.get(k)
                    for k in ("backgroundColor", "color", "borderColor",
                              "boxShadow", "opacity", "transform")
                    if hover.get(k)
                )
                if changed:
                    has_hover_change += 1

        if state_tests:
            hover_pct = has_hover_change / len(state_tests)
            if hover_pct < 0.5:
                penalty = min(20, int((1 - hover_pct) * 25))
                score -= penalty
                findings.append(Finding(
                    category="interactive",
                    message=f"Only {hover_pct:.0%} of tested elements have a visible hover state change.",
                    recommendation="Every interactive element should provide visual feedback on hover (colour, shadow, or transform).",
                    severity="high" if hover_pct < 0.3 else "medium",
                    data={"with_hover": has_hover_change, "total_tested": len(state_tests)},
                ))

    # ── Size consistency ──
    # Buttons/links of similar type should be consistently sized
    buttons = [
        el for el in interactive
        if el.get("element", "").startswith("button") or "btn" in el.get("element", "")
    ]
    if len(buttons) >= 3:
        heights = [el.get("height", 0) for el in buttons if el.get("height")]
        if heights:
            unique_heights = set(heights)
            if len(unique_heights) > 3:
                score -= 10
                findings.append(Finding(
                    category="interactive",
                    message=f"Buttons have {len(unique_heights)} different heights — inconsistent sizing.",
                    recommendation="Standardise button sizes (e.g. small=32px, medium=40px, large=48px).",
                    severity="medium",
                    data={"heights": sorted(unique_heights)},
                ))

    # ── Labels ──
    unlabelled = [el for el in interactive if not el.get("has_visible_label") and not el.get("has_aria_label")]
    if unlabelled:
        score -= min(15, len(unlabelled) * 5)
        findings.append(Finding(
            category="interactive",
            message=f"{len(unlabelled)} interactive elements have no visible or aria label.",
            recommendation="Every button and link needs a clear label for usability.",
            severity="high" if len(unlabelled) > 2 else "medium",
            data={"unlabelled": [el.get("element", "?") for el in unlabelled[:5]]},
        ))

    return CategoryScore(name="interactive", score=score, findings=findings)


def _score_hierarchy(dom_data: dict) -> CategoryScore:
    """Score visual hierarchy signals."""
    findings: list[Finding] = []
    score = 100

    html = dom_data.get("html_structure", {}) or {}
    headings = html.get("headings", [])
    landmarks = html.get("landmarks", {}) or {}
    interactive = dom_data.get("interactive_elements", []) or []

    # ── H1 presence and uniqueness ──
    h1s = [h for h in headings if h.get("level") == 1]
    if len(h1s) == 0:
        score -= 15
        findings.append(Finding(
            category="hierarchy",
            message="No H1 heading found — the page lacks a clear primary title.",
            recommendation="Every page needs exactly one H1 that communicates its purpose.",
            severity="high",
        ))
    elif len(h1s) > 1:
        score -= 10
        findings.append(Finding(
            category="hierarchy",
            message=f"{len(h1s)} H1 headings found — competing for primary focus.",
            recommendation="Use a single H1 for the page title. Demote others to H2.",
            severity="medium",
            data={"h1_texts": [h.get("text", "")[:50] for h in h1s]},
        ))

    # ── Heading level gaps ──
    if headings:
        levels_used = sorted(set(h.get("level", 0) for h in headings))
        for i in range(len(levels_used) - 1):
            gap = levels_used[i + 1] - levels_used[i]
            if gap > 1:
                score -= 8
                findings.append(Finding(
                    category="hierarchy",
                    message=f"Heading level gap: H{levels_used[i]} jumps to H{levels_used[i+1]} — skips H{levels_used[i]+1}.",
                    recommendation=f"Don't skip heading levels. Add H{levels_used[i]+1} between them for logical structure.",
                    severity="medium",
                ))

    # ── Heading count ──
    if len(headings) < 2 and interactive:
        score -= 10
        findings.append(Finding(
            category="hierarchy",
            message=f"Only {len(headings)} heading(s) on a page with {len(interactive)} interactive elements.",
            recommendation="Use headings to label sections and help users scan the page structure.",
            severity="medium",
        ))

    # ── Landmarks ──
    if not landmarks.get("main"):
        score -= 10
        findings.append(Finding(
            category="hierarchy",
            message="No <main> landmark — page structure is ambiguous.",
            recommendation="Wrap primary content in a <main> element.",
            severity="medium",
        ))

    if not landmarks.get("nav"):
        score -= 5
        findings.append(Finding(
            category="hierarchy",
            message="No <nav> landmark detected.",
            recommendation="Wrap navigation in a <nav> element for clear page structure.",
            severity="low",
        ))

    # ── CTA prominence ──
    # Check that there's at least one prominent interactive element (likely CTA)
    if interactive:
        max_area = max(
            (el.get("width", 0) * el.get("height", 0)) for el in interactive
        )
        median_area = sorted(
            el.get("width", 0) * el.get("height", 0) for el in interactive
        )[len(interactive) // 2]
        if median_area > 0 and max_area < median_area * 1.5:
            score -= 8
            findings.append(Finding(
                category="hierarchy",
                message="No interactive element stands out as a primary action — all similar size.",
                recommendation="Make the primary CTA visually larger or more prominent than secondary actions.",
                severity="medium",
            ))

    return CategoryScore(name="hierarchy", score=score, findings=findings)


# ── Component pattern heuristics ──

# Generic button labels that provide no information about the action
GENERIC_LABELS = frozenset({
    "submit", "click here", "click", "here", "go", "ok", "okay",
    "more", "read more", "learn more", "info", "details", "link",
    "button", "press", "enter", "next", "previous", "back",
})

# Words that indicate a verb-led (good) button label
ACTION_VERBS = frozenset({
    "get", "start", "create", "add", "delete", "remove", "save",
    "send", "sign", "log", "register", "subscribe", "download",
    "upload", "buy", "order", "book", "schedule", "try", "join",
    "view", "open", "close", "edit", "update", "cancel", "confirm",
    "accept", "reject", "share", "copy", "export", "import",
    "search", "find", "filter", "sort", "reset", "apply", "enable",
    "disable", "connect", "disconnect", "install", "uninstall",
    "explore", "browse", "continue", "finish", "complete",
})


def _score_patterns(dom_data: dict) -> CategoryScore:
    """Score component-level design patterns against known best practices."""
    findings: list[Finding] = []
    score = 100

    html = dom_data.get("html_structure", {}) or {}
    interactive = dom_data.get("interactive_elements", []) or []
    forms = html.get("forms", {}) or {}
    headings = html.get("headings", [])
    landmarks = html.get("landmarks", {}) or {}

    # ── Form complexity ──
    label_breakdown = forms.get("label_breakdown", {}) or {}
    total_inputs = sum(label_breakdown.get(k, 0) for k in label_breakdown)
    inputs_without_labels = forms.get("inputs_without_labels", [])

    if total_inputs > 0:
        # Field count heuristic
        if total_inputs > 10:
            score -= 20
            findings.append(Finding(
                category="patterns",
                message=f"Form has {total_inputs} fields — long forms have high abandonment rates.",
                recommendation="Break into multi-step form (3-5 fields per step) or remove non-essential fields.",
                severity="high",
                data={"field_count": total_inputs},
            ))
        elif total_inputs > 7:
            score -= 10
            findings.append(Finding(
                category="patterns",
                message=f"Form has {total_inputs} fields — above the 5-7 sweet spot for completion rates.",
                recommendation="Consider which fields are truly required. Every removed field improves conversion.",
                severity="medium",
                data={"field_count": total_inputs},
            ))

        # Unlabelled inputs
        unlabelled = label_breakdown.get("unlabelled", 0)
        if unlabelled > 0:
            score -= min(15, unlabelled * 5)
            findings.append(Finding(
                category="patterns",
                message=f"{unlabelled} form input(s) have no label — users can't tell what to enter.",
                recommendation="Every input needs a visible <label>. Placeholder text is not a substitute.",
                severity="high",
                data={"unlabelled_inputs": [
                    f"{inp.get('type', '?')} ({inp.get('placeholder', 'no placeholder')})"
                    for inp in inputs_without_labels[:5]
                ]},
            ))

    # ── Navigation complexity ──
    nav_links = [
        el for el in interactive
        if el.get("element", "").startswith("a")
    ]
    if len(nav_links) > 12:
        score -= 10
        findings.append(Finding(
            category="patterns",
            message=f"{len(nav_links)} links on page — navigation may overwhelm users.",
            recommendation="Group links into categories. Top-level nav should have 5-8 items max; "
                "use dropdowns or secondary nav for the rest.",
            severity="medium",
            data={"link_count": len(nav_links)},
        ))

    # ── Images without alt ──
    img_no_alt = html.get("images_without_alt", 0)
    if img_no_alt > 0:
        score -= min(15, img_no_alt * 3)
        findings.append(Finding(
            category="patterns",
            message=f"{img_no_alt} image(s) missing alt text — invisible to screen readers and broken if image fails to load.",
            recommendation="Add descriptive alt text to all meaningful images. Use alt=\"\" for purely decorative images.",
            severity="high" if img_no_alt > 3 else "medium",
            data={"count": img_no_alt},
        ))

    # ── ARIA overuse ──
    aria = html.get("aria_usage", {}) or {}
    roles = aria.get("roles", [])
    # Flag if many custom roles but few landmarks — suggests ARIA used as band-aid
    if len(roles) > 8 and landmarks.get("main", 0) == 0:
        score -= 8
        findings.append(Finding(
            category="patterns",
            message=f"{len(roles)} ARIA roles but no <main> landmark — ARIA may be papering over bad HTML structure.",
            recommendation="Use semantic HTML first (<main>, <nav>, <header>, <section>). "
                "ARIA should supplement, not replace, native semantics.",
            severity="medium",
            data={"roles": roles[:10]},
        ))

    # ── Button vs link usage ──
    buttons = [el for el in interactive if el.get("element", "").startswith("button")]
    links = [el for el in interactive if el.get("element", "").startswith("a")]
    # Heuristic: if many buttons have link-like text (URLs or "read more"), they should be links
    link_like_buttons = [
        b for b in buttons
        if b.get("text", "").lower().strip() in {"read more", "learn more", "see more", "view all", "view more"}
    ]
    if link_like_buttons:
        score -= len(link_like_buttons) * 3
        findings.append(Finding(
            category="patterns",
            message=f"{len(link_like_buttons)} button(s) with navigation-style labels — should probably be links.",
            recommendation="Use <a> for navigation ('View all', 'Read more'). "
                "Use <button> for actions ('Save', 'Delete'). Mixing them confuses users and assistive tech.",
            severity="medium",
            data={"buttons": [b.get("text", "") for b in link_like_buttons[:5]]},
        ))

    return CategoryScore(name="patterns", score=score, findings=findings)


def _score_copy(dom_data: dict) -> CategoryScore:
    """Score microcopy quality — button labels, headings, and text patterns."""
    findings: list[Finding] = []
    score = 100

    interactive = dom_data.get("interactive_elements", []) or []
    html = dom_data.get("html_structure", {}) or {}
    headings = html.get("headings", [])

    # ── Button/link label quality ──
    labelled_elements = [
        el for el in interactive
        if el.get("text", "").strip()
    ]

    if labelled_elements:
        # Check for generic labels
        generic = []
        for el in labelled_elements:
            text = el.get("text", "").strip().lower()
            if text in GENERIC_LABELS:
                generic.append(el)

        if generic:
            penalty = min(20, len(generic) * 5)
            score -= penalty
            findings.append(Finding(
                category="copy",
                message=f"{len(generic)} generic button/link label(s) — 'Submit', 'Click here', etc. tell users nothing.",
                recommendation="Use specific action labels: 'Create account' not 'Submit', 'View pricing' not 'Click here'.",
                severity="high" if len(generic) > 2 else "medium",
                data={"generic_labels": [
                    f"{el.get('element', '?')}: \"{el.get('text', '')}\""
                    for el in generic[:6]
                ]},
            ))

        # Check for verb-led labels (good practice)
        non_generic = [el for el in labelled_elements if el not in generic]
        if non_generic:
            verb_led = 0
            for el in non_generic:
                first_word = el.get("text", "").strip().split()[0].lower() if el.get("text", "").strip() else ""
                if first_word in ACTION_VERBS:
                    verb_led += 1

            if len(non_generic) >= 3:
                verb_pct = verb_led / len(non_generic)
                if verb_pct < 0.3:
                    score -= 10
                    noun_labels = [
                        el for el in non_generic
                        if el.get("text", "").strip()
                        and el.get("text", "").strip().split()[0].lower() not in ACTION_VERBS
                    ]
                    findings.append(Finding(
                        category="copy",
                        message=f"Only {verb_pct:.0%} of button labels start with an action verb.",
                        recommendation="Lead with verbs: 'Get started', 'Create project', 'Download report'. "
                            "Verbs tell users what will happen.",
                        severity="medium",
                        data={"noun_labels": [
                            f"\"{el.get('text', '')}\"" for el in noun_labels[:5]
                        ]},
                    ))

        # Check for duplicate labels
        label_texts = [el.get("text", "").strip().lower() for el in labelled_elements if el.get("text", "").strip()]
        seen_labels: dict[str, int] = {}
        for lt in label_texts:
            seen_labels[lt] = seen_labels.get(lt, 0) + 1
        duplicates = {k: v for k, v in seen_labels.items() if v > 2 and k not in {"", " "}}
        if duplicates:
            score -= min(10, len(duplicates) * 3)
            findings.append(Finding(
                category="copy",
                message=f"{len(duplicates)} label(s) repeated 3+ times — users can't distinguish between them.",
                recommendation="Differentiate repeated labels with context: 'Edit profile' vs 'Edit settings' instead of 'Edit' x5.",
                severity="medium",
                data={"duplicates": [f"\"{k}\" x{v}" for k, v in sorted(duplicates.items(), key=lambda x: -x[1])[:5]]},
            ))

    # ── Heading quality ──
    if headings:
        # Check for very long headings
        long_headings = [h for h in headings if len(h.get("text", "")) > 60]
        if long_headings:
            score -= min(10, len(long_headings) * 3)
            findings.append(Finding(
                category="copy",
                message=f"{len(long_headings)} heading(s) over 60 characters — headings should be scannable.",
                recommendation="Keep headings concise (under 60 chars). Move detail into body text.",
                severity="low",
                data={"long_headings": [f"H{h.get('level')}: \"{h.get('text', '')[:70]}...\"" for h in long_headings[:3]]},
            ))

        # Check for all-caps headings (SHOUTING)
        all_caps = [
            h for h in headings
            if h.get("text", "").strip()
            and h["text"].upper() == h["text"]
            and len(h["text"]) > 3  # ignore short acronyms
            and any(c.isalpha() for c in h["text"])
        ]
        if all_caps:
            score -= min(8, len(all_caps) * 3)
            findings.append(Finding(
                category="copy",
                message=f"{len(all_caps)} heading(s) in ALL CAPS — feels aggressive and harms readability.",
                recommendation="Use CSS text-transform: uppercase if you want the visual effect. "
                    "Keep source text in sentence/title case for screen readers.",
                severity="low",
                data={"all_caps": [f"H{h.get('level')}: \"{h.get('text', '')[:50]}\"" for h in all_caps[:3]]},
            ))

    # ── Page title ──
    title = html.get("title", "")
    if not title:
        score -= 10
        findings.append(Finding(
            category="copy",
            message="Page has no <title> — appears as blank in browser tabs and bookmarks.",
            recommendation="Set a descriptive <title> that includes the page purpose and site name.",
            severity="high",
        ))
    elif len(title) > 70:
        score -= 5
        findings.append(Finding(
            category="copy",
            message=f"Page title is {len(title)} characters — will be truncated in browser tabs and search results.",
            recommendation="Keep <title> under 60-70 characters. Lead with the most important words.",
            severity="low",
            data={"title": title[:80]},
        ))

    return CategoryScore(name="copy", score=score, findings=findings)


# ── Design system cleanup proposal ──

# Named scale for proposed font sizes (ascending order)
_SIZE_NAMES = ["xs", "sm", "base", "md", "lg", "xl", "2xl", "3xl", "4xl", "5xl"]

# Named scale for proposed spacing (ascending order)
_SPACE_NAMES = ["px", "0.5", "1", "1.5", "2", "3", "4", "5", "6", "8", "10", "12", "16", "20", "24"]


def _hex_to_rgb(hex_str: str) -> tuple[int, int, int] | None:
    """Parse a hex colour string to RGB tuple."""
    h = hex_str.lstrip("#")
    if len(h) == 3:
        h = h[0]*2 + h[1]*2 + h[2]*2
    if len(h) != 6:
        return None
    try:
        return (int(h[0:2], 16), int(h[1:4][:2], 16), int(h[4:6], 16))
    except ValueError:
        return None


def _color_distance(c1: tuple[int, int, int], c2: tuple[int, int, int]) -> float:
    """Simple Euclidean distance in RGB space."""
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(c1, c2)))


def _cluster_colors(
    color_entries: list[dict], max_clusters: int = 6,
) -> list[dict]:
    """Cluster colours by proximity, keeping the most-used representative."""
    if not color_entries:
        return []

    # Sort by usage count descending — most-used colours become cluster centers
    sorted_entries = sorted(color_entries, key=lambda c: c.get("count", 0), reverse=True)

    clusters: list[dict] = []
    for entry in sorted_entries:
        rgb = _hex_to_rgb(entry.get("color", ""))
        if not rgb:
            continue

        # Check if this colour is close to an existing cluster center
        merged = False
        for cluster in clusters:
            center_rgb = _hex_to_rgb(cluster["value"])
            if center_rgb and _color_distance(rgb, center_rgb) < 50:
                cluster["merged_count"] = cluster.get("merged_count", 0) + 1
                merged = True
                break

        if not merged and len(clusters) < max_clusters:
            clusters.append({
                "value": entry["color"],
                "count": entry.get("count", 0),
                "merged_count": 0,
            })

    return clusters


def _snap_to_grid(value: float, grid: int = 4) -> int:
    """Snap a value to the nearest grid multiple."""
    return max(grid, round(value / grid) * grid)


def generate_clean_system(dom_data: dict) -> ProposedSystem:
    """Generate a proposed clean design token system from raw DOM data.

    Clusters raw values into a disciplined palette, type scale, and
    spacing scale. Pure data transformation — no LLM.
    """
    fonts = dom_data.get("fonts", {}) or {}
    colors = dom_data.get("colors", {}) or {}
    layout = dom_data.get("layout", {}) or {}
    spacing_values = dom_data.get("spacing_values", []) or []

    # ── Colours ──
    # Merge text and background colours, cluster by proximity
    text_colors = colors.get("text", [])
    bg_colors = colors.get("background", [])

    # Propose semantic roles from clustered background colours
    bg_clusters = _cluster_colors(bg_colors, max_clusters=4)
    text_clusters = _cluster_colors(text_colors, max_clusters=4)

    proposed_colors: list[dict] = []
    bg_role_names = ["surface", "surface-alt", "surface-elevated", "surface-overlay"]
    for i, cluster in enumerate(bg_clusters):
        role = bg_role_names[i] if i < len(bg_role_names) else f"surface-{i+1}"
        proposed_colors.append({
            "name": role,
            "value": cluster["value"],
            "role": f"Background ({cluster['count']}x used)",
        })

    text_role_names = ["text-primary", "text-secondary", "text-muted", "text-accent"]
    for i, cluster in enumerate(text_clusters):
        role = text_role_names[i] if i < len(text_role_names) else f"text-{i+1}"
        proposed_colors.append({
            "name": role,
            "value": cluster["value"],
            "role": f"Text ({cluster['count']}x used)",
        })

    # ── Font families ──
    families = fonts.get("families", [])
    proposed_families: list[dict] = []
    family_roles = ["body", "heading", "mono"]
    for i, fam in enumerate(families[:3]):
        role = family_roles[i] if i < len(family_roles) else f"font-{i+1}"
        proposed_families.append({
            "name": role,
            "value": fam["family"],
            "role": f"{role} font ({fam['count']}x used)",
        })

    # ── Font sizes — build a clean scale ──
    raw_sizes = fonts.get("sizes", [])
    sizes_px = sorted(set(
        v for s in raw_sizes if (v := _parse_px(s.get("size", ""))) is not None
    ))

    proposed_sizes: list[dict] = []
    if sizes_px:
        # Pick the most-used size as "base", build a scale around it
        most_used_size = max(raw_sizes, key=lambda s: s.get("count", 0)).get("size", "16px")
        base_px = _parse_px(most_used_size) or 16

        # Generate a modular scale with ratio 1.25 (major third)
        ratio = 1.25
        scale_values = []

        # Build downward from base
        current = base_px
        down_values = []
        for _ in range(3):
            current = current / ratio
            rounded = max(10, round(current))
            if rounded not in down_values:
                down_values.append(rounded)
        down_values.reverse()

        # Base
        scale_values = down_values + [round(base_px)]

        # Build upward from base
        current = base_px
        for _ in range(6):
            current = current * ratio
            rounded = round(current)
            if rounded not in scale_values:
                scale_values.append(rounded)

        # Trim to reasonable size and name them
        scale_values = sorted(set(scale_values))[:len(_SIZE_NAMES)]
        for i, px in enumerate(scale_values):
            name = _SIZE_NAMES[i] if i < len(_SIZE_NAMES) else f"size-{i}"
            proposed_sizes.append({"name": name, "value": f"{px}px"})

    # ── Spacing — snap to an 8px grid ──
    raw_px = sorted(set(
        v for s in spacing_values if (v := _parse_px(s.get("value", ""))) is not None
    ))

    proposed_spacing: list[dict] = []
    if raw_px:
        # Build an 8-point grid scale
        grid_values = [4, 8, 12, 16, 24, 32, 48, 64, 96, 128]
        # Filter to values that are actually near something in the raw data
        used_grid = []
        for gv in grid_values:
            # Check if any raw value is within 4px of this grid value
            if any(abs(rv - gv) <= 4 for rv in raw_px):
                used_grid.append(gv)

        # Always include at least the core scale
        if not used_grid:
            used_grid = [4, 8, 16, 24, 32, 48, 64]

        for i, px in enumerate(used_grid):
            name = _SPACE_NAMES[i] if i < len(_SPACE_NAMES) else f"space-{i}"
            proposed_spacing.append({"name": name, "value": f"{px}px"})

    return ProposedSystem(
        colors=proposed_colors,
        font_sizes=proposed_sizes,
        spacing=proposed_spacing,
        font_families=proposed_families,
    )


# ── Main entry point ──


def run_ui_review(dom_data: dict) -> UIReviewReport:
    """Run the full deterministic UI review.

    Returns a UIReviewReport with scored categories and findings.
    The LLM suggestion layer is added separately by the caller.
    """
    if not dom_data or not isinstance(dom_data, dict):
        return UIReviewReport(categories=[
            CategoryScore(name=name, score=0, findings=[
                Finding(
                    category=name,
                    message="No DOM data available for analysis.",
                    recommendation="Ensure the URL is accessible and DOM extraction succeeded.",
                    severity="high",
                )
            ])
            for name in WEIGHTS
        ])

    categories = [
        _score_typography(dom_data),
        _score_color(dom_data),
        _score_spacing(dom_data),
        _score_interactive(dom_data),
        _score_hierarchy(dom_data),
        _score_patterns(dom_data),
        _score_copy(dom_data),
    ]

    proposed_system = generate_clean_system(dom_data)

    return UIReviewReport(categories=categories, proposed_system=proposed_system)


# ── Responsive comparison ──

BREAKPOINTS = {
    "mobile": {"width": 375, "height": 812, "label": "Mobile (375px)"},
    "tablet": {"width": 768, "height": 1024, "label": "Tablet (768px)"},
    "desktop": {"width": 1440, "height": 900, "label": "Desktop (1440px)"},
}


@dataclass
class ResponsiveReport:
    """Comparison of UI review results across breakpoints."""
    breakpoint_reports: dict[str, UIReviewReport] = field(default_factory=dict)

    @property
    def regressions(self) -> list[dict]:
        """Find categories that score significantly worse at a breakpoint."""
        if len(self.breakpoint_reports) < 2:
            return []

        regressions = []
        bp_names = list(self.breakpoint_reports.keys())
        # Use desktop as the baseline
        baseline_name = "desktop" if "desktop" in bp_names else bp_names[-1]
        baseline = self.breakpoint_reports[baseline_name]
        baseline_cats = baseline.category_dict()

        for bp_name, report in self.breakpoint_reports.items():
            if bp_name == baseline_name:
                continue
            for cat in report.categories:
                base_cat = baseline_cats.get(cat.name)
                if base_cat and base_cat.score - cat.score >= 15:
                    regressions.append({
                        "breakpoint": bp_name,
                        "category": cat.name,
                        "desktop_score": base_cat.score,
                        "breakpoint_score": cat.score,
                        "drop": base_cat.score - cat.score,
                    })

        return sorted(regressions, key=lambda r: -r["drop"])

    def to_dict(self) -> dict:
        return {
            "breakpoints": {
                bp: report.to_dict()
                for bp, report in self.breakpoint_reports.items()
            },
            "regressions": self.regressions,
        }

    def to_markdown(self) -> str:
        lines = ["## Responsive UI Audit\n"]

        # Comparison table
        lines.append("| Category | " + " | ".join(
            BREAKPOINTS.get(bp, {}).get("label", bp)
            for bp in self.breakpoint_reports
        ) + " |")
        lines.append("|----------|" + "|".join(
            "-------" for _ in self.breakpoint_reports
        ) + "|")

        # Get all category names from first report
        first_report = next(iter(self.breakpoint_reports.values()))
        for cat in first_report.categories:
            scores = []
            for bp, report in self.breakpoint_reports.items():
                bp_cat = report.category_dict().get(cat.name)
                score = bp_cat.score if bp_cat else "—"
                scores.append(str(score))
            lines.append(f"| {cat.name.title()} | " + " | ".join(scores) + " |")

        # Overall scores
        overall = []
        for bp, report in self.breakpoint_reports.items():
            overall.append(f"{report.overall_score}")
        lines.append("| **Overall** | " + " | ".join(f"**{s}**" for s in overall) + " |")
        lines.append("")

        # Regressions
        regs = self.regressions
        if regs:
            lines.append(f"### Responsive Regressions ({len(regs)} found)\n")
            for r in regs:
                bp_label = BREAKPOINTS.get(r["breakpoint"], {}).get("label", r["breakpoint"])
                lines.append(
                    f"- **{r['category'].title()}** drops {r['drop']} points on {bp_label} "
                    f"({r['desktop_score']} -> {r['breakpoint_score']})"
                )
            lines.append("")
        else:
            lines.append("No significant regressions across breakpoints.\n")

        # Per-breakpoint detail — only show findings unique to non-desktop
        desktop_findings = set()
        if "desktop" in self.breakpoint_reports:
            for f in self.breakpoint_reports["desktop"].all_findings:
                desktop_findings.add(f.message)

        for bp, report in self.breakpoint_reports.items():
            if bp == "desktop":
                continue
            unique = [f for f in report.all_findings if f.message not in desktop_findings]
            if unique:
                bp_label = BREAKPOINTS.get(bp, {}).get("label", bp)
                lines.append(f"### {bp_label} — unique findings\n")
                for f in unique:
                    lines.append(f"- **[{f.severity.upper()}]** {f.message}")
                    lines.append(f"  - {f.recommendation}")
                lines.append("")

        return "\n".join(lines)


# ── LLM opinion layer ──

_REVIEW_SYSTEM_PROMPT = """\
You are a senior product designer reviewing a live website. You are direct,
opinionated, and practical. You do not hedge.

You will receive:
1. A screenshot of the page.
2. Deterministic audit results — scored categories with specific findings
   about typography, colour, spacing, interactive elements, and hierarchy.
3. Raw DOM metrics (colours, fonts, spacing values, interactive elements).

Your job is to add the human-eye layer: things the deterministic checks
cannot catch. Focus on:
- **Layout and visual balance** — is the page weighted oddly? Is content
  crammed or lost in whitespace?
- **Clarity of purpose** — can a user tell what this page does within 3
  seconds? Is the primary action obvious?
- **Visual flow** — does the eye move naturally through the content?
  Are there competing focal points?
- **Polish and craft** — does this feel finished? Are there rough edges
  that undermine trust (misaligned elements, inconsistent corner radii,
  mixed visual styles)?
- **Practical improvements** — what 3-5 changes would make the biggest
  visual impact for the least effort?

Do NOT repeat what the deterministic audit already found. Reference it
("the audit flagged 14 font sizes — visually, the effect is...") but add
new observations.

Respond with ONLY a JSON array of 3-5 suggestion objects:
[
  {
    "title": "Short title",
    "rationale": "Why this matters — what the user sees/feels",
    "action": "Concrete step to fix it"
  }
]

No markdown, no preamble, just the JSON array.
"""


def get_llm_suggestions(
    report: UIReviewReport,
    image_path: str | None,
    dom_data: dict,
) -> list[dict]:
    """Call the LLM to produce opinionated design suggestions.

    Returns a list of suggestion dicts with title/rationale/action keys.
    """
    import json

    from src.providers.llm import call_llm

    # Build a compact summary of the deterministic results
    summary_parts = [f"Overall score: {report.overall_score}/100\n"]
    for cat in report.categories:
        summary_parts.append(f"## {cat.name.title()} — {cat.score}/100")
        for f in cat.findings:
            summary_parts.append(f"- [{f.severity}] {f.message}")
        summary_parts.append("")

    # Include key DOM metrics
    fonts = dom_data.get("fonts", {}) or {}
    colors = dom_data.get("colors", {}) or {}
    layout = dom_data.get("layout", {}) or {}

    dom_summary = ["\n## Raw DOM metrics\n"]
    if layout:
        dom_summary.append(f"Viewport: {layout.get('viewport_width')}x{layout.get('viewport_height')}px")
        dom_summary.append(f"Body font: {layout.get('body_font_size')} / {layout.get('body_line_height')} {layout.get('body_font_family')}")
    if fonts.get("families"):
        dom_summary.append(f"Font families: {', '.join(f['family'] for f in fonts['families'][:5])}")
    if fonts.get("sizes"):
        dom_summary.append(f"Font sizes: {', '.join(s['size'] for s in fonts['sizes'][:10])}")
    if colors.get("text"):
        dom_summary.append(f"Text colours: {', '.join(c['color'] for c in colors['text'][:8])}")
    if colors.get("background"):
        dom_summary.append(f"Background colours: {', '.join(c['color'] for c in colors['background'][:8])}")

    user_prompt = (
        "## Deterministic audit results\n\n"
        + "\n".join(summary_parts)
        + "\n".join(dom_summary)
    )

    image_paths = [image_path] if image_path else []

    try:
        raw = call_llm(
            system_prompt=_REVIEW_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            image_paths=image_paths,
            max_tokens=2000,
            temperature=0.3,
        )
        # Parse JSON from the response — handle markdown code fences
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
        suggestions = json.loads(text)
        if isinstance(suggestions, list):
            return suggestions
        return []
    except Exception:
        return []
