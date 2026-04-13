"""
Component-level detection and scoring.

Identifies UI components from DOM structure and scores each
against established pattern standards.
"""

from dataclasses import dataclass, field


@dataclass
class ComponentScore:
    name: str
    type: str  # nav, form, card, table, button-group, modal, list, toolbar
    selector: str
    score: int
    max_score: int
    issues: list[str] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)

    def __post_init__(self):
        # Clamp score to [0, max_score]. Protects the report from arithmetic
        # bugs in per-component scorers that could produce negative values.
        self.score = max(0, min(self.score, self.max_score))


@dataclass
class ComponentReport:
    components: list[ComponentScore] = field(default_factory=list)

    @property
    def total_score(self) -> int:
        return sum(c.score for c in self.components)

    @property
    def total_max(self) -> int:
        return sum(c.max_score for c in self.components)

    @property
    def percentage(self) -> float:
        if self.total_max == 0:
            return 0.0
        return round((self.total_score / self.total_max) * 100, 1)

    def to_markdown(self) -> str:
        lines = [
            "## Component Inventory & Scoring\n",
            f"**Overall: {self.total_score}/{self.total_max} ({self.percentage}%)**\n",
            f"**{len(self.components)} components detected**\n",
        ]

        # Summary table
        lines.append("| Component | Type | Score | Issues |")
        lines.append("|-----------|------|-------|--------|")
        for c in sorted(self.components, key=lambda x: x.score / max(x.max_score, 1)):
            pct = round(c.score / c.max_score * 100) if c.max_score else 0
            issue_label = "issue" if len(c.issues) == 1 else "issues"
            lines.append(f"| {c.name} | {c.type} | {c.score}/{c.max_score} ({pct}%) | {len(c.issues)} {issue_label} |")
        lines.append("")

        # Detail per component
        for c in self.components:
            pct = round(c.score / c.max_score * 100) if c.max_score else 0
            lines.append(f"### {c.name} ({c.type}) - {c.score}/{c.max_score} ({pct}%)\n")
            lines.append(f"Selector: `{c.selector}`\n")
            if c.issues:
                lines.append("**Issues:**")
                for issue in c.issues:
                    lines.append(f"- {issue}")
            if c.strengths:
                lines.append("\n**Strengths:**")
                for s in c.strengths:
                    lines.append(f"- {s}")
            lines.append("")

        return "\n".join(lines)

    def to_pragmatic_markdown(self, threshold: int = 60) -> str:
        """High-signal component report: only components below threshold %."""
        below = [
            c for c in self.components
            if (c.score / max(c.max_score, 1) * 100) < threshold
        ]
        lines = [
            "## Components — Pragmatic View\n",
            f"**{len(below)}/{len(self.components)} components below {threshold}%** "
            f"— these are the ones worth attention.\n",
        ]
        if not below:
            lines.append(f"All components score at or above {threshold}%. Nothing flagged.")
            return "\n".join(lines)

        for c in sorted(below, key=lambda x: x.score / max(x.max_score, 1)):
            pct = round(c.score / c.max_score * 100) if c.max_score else 0
            lines.append(f"### {c.name} ({c.type}) — {c.score}/{c.max_score} ({pct}%)\n")
            lines.append(f"Selector: `{c.selector}`\n")
            if c.issues:
                lines.append("**Top issues:**")
                for issue in c.issues[:5]:
                    lines.append(f"- {issue}")
                if len(c.issues) > 5:
                    lines.append(f"- … +{len(c.issues) - 5} more")
            lines.append("")

        return "\n".join(lines)


def _score_navigation(nav_data: dict, interactive: list, dom_data: dict) -> ComponentScore:
    """Score a navigation component."""
    score = 0
    max_score = 10
    issues = []
    strengths = []

    landmarks = dom_data.get("html_structure", {}).get("landmarks", {})
    nav_count = landmarks.get("nav", 0)

    # Semantic nav element
    if nav_count > 0:
        score += 2
        strengths.append("Uses `<nav>` landmark")
    else:
        issues.append("Not wrapped in `<nav>` element")

    # Active state indication
    has_active = any("active" in str(e.get("element", "")) for e in interactive
                     if "nav" in str(e.get("element", "")).lower() or "tab" in str(e.get("element", "")).lower())
    if has_active:
        score += 2
        strengths.append("Active state visible on current page")
    else:
        issues.append("No active/current state indicator")

    # Touch target compliance
    nav_elements = [e for e in interactive
                    if "nav" in str(e.get("element", "")).lower() or "tab" in str(e.get("element", "")).lower()]
    if nav_elements:
        all_pass = all(e.get("meets_touch_target", False) for e in nav_elements)
        if all_pass:
            score += 2
            strengths.append("All nav items meet 44px target size")
        else:
            failing = [e for e in nav_elements if not e.get("meets_touch_target")]
            issues.append(f"{len(failing)} nav items below 44px target size")

    # Focus and hover styles (from Playwright state tests — ground truth)
    state_tests = dom_data.get("state_tests", [])
    nav_states = [s for s in state_tests if "nav" in s.get("selector", "").lower() or "tab" in s.get("selector", "").lower()]

    # Also check for global :focus-visible rules
    html = dom_data.get("html_structure", {})
    has_global_focus = html.get("has_global_focus_visible", False)

    if nav_states:
        with_focus = [s for s in nav_states if s.get("has_focus_state")]
        if len(with_focus) == len(nav_states) or has_global_focus:
            score += 2
            strengths.append("All nav items have focus styles (verified by state test)")
        else:
            tested_without = len(nav_states) - len(with_focus)
            issues.append(f"{tested_without}/{len(nav_states)} tested nav items missing focus styles")

        with_hover = [s for s in nav_states if s.get("has_hover_state")]
        if len(with_hover) == len(nav_states):
            score += 2
            strengths.append("All nav items have hover states (verified by state test)")
        else:
            tested_without = len(nav_states) - len(with_hover)
            issues.append(f"{tested_without}/{len(nav_states)} tested nav items missing hover states")
    elif has_global_focus:
        score += 2
        strengths.append("Global :focus-visible rule covers all nav items")

    selector = nav_elements[0]["element"] if nav_elements else "nav"
    return ComponentScore("Navigation", "nav", selector, score, max_score, issues, strengths)


def _score_forms(dom_data: dict) -> ComponentScore | None:
    """Score form components."""
    html = dom_data.get("html_structure", {})
    forms = html.get("forms", {})
    unlabelled_inputs = forms.get("inputs_without_labels", [])
    unlabelled_selects = forms.get("selects_without_labels", [])
    interactive = dom_data.get("interactive_elements", [])

    form_elements = [e for e in interactive
                     if e.get("element", "").startswith(("input", "select", "textarea"))]

    if not form_elements:
        return None

    score = 0
    max_score = 10
    issues = []
    strengths = []

    total_inputs = len(form_elements)
    unlabelled = len(unlabelled_inputs) + len(unlabelled_selects)
    # `unlabelled` counts every form input on the page (including hidden ones),
    # while `total_inputs` counts only visible interactive inputs. Clamp so the
    # labelled count can't go negative when the page has hidden inputs.
    labelled = max(0, total_inputs - unlabelled)

    # Labels
    if unlabelled == 0:
        score += 4
        strengths.append(f"All {total_inputs} inputs have programmatic labels")
    else:
        label_pct = (labelled / total_inputs) if total_inputs else 0
        label_pct = max(0.0, min(1.0, label_pct))
        score += round(4 * label_pct)
        issues.append(f"{unlabelled} form input(s) missing programmatic labels")

    # Touch targets
    form_targets = [e for e in form_elements if e.get("meets_touch_target")]
    if len(form_targets) == len(form_elements):
        score += 2
        strengths.append("All form inputs meet 44px target minimum")
    else:
        failing = len(form_elements) - len(form_targets)
        issues.append(f"{failing} form inputs below 44px target size")

    # Placeholder-only labelling
    placeholder_only = [i for i in unlabelled_inputs if i.get("placeholder")]
    if placeholder_only:
        issues.append(f"{len(placeholder_only)} inputs use placeholder as sole label")
    else:
        score += 2
        strengths.append("No placeholder-only labelling detected")

    # ARIA attributes
    aria = html.get("aria_usage", {})
    if aria.get("described_by", 0) > 0:
        score += 2
        strengths.append("Uses aria-describedby for input descriptions")

    selector = form_elements[0]["element"] if form_elements else "form"
    return ComponentScore("Forms", "form", selector, score, max_score, issues, strengths)


def _score_buttons(dom_data: dict) -> ComponentScore:
    """Score button components."""
    interactive = dom_data.get("interactive_elements", [])
    buttons = [e for e in interactive if e.get("element", "").startswith("button")]

    score = 0
    max_score = 10
    issues = []
    strengths = []

    if not buttons:
        return ComponentScore("Buttons", "button-group", "button", 0, max_score,
                              ["No buttons found"], [])

    # Touch targets
    passing = [b for b in buttons if b.get("meets_touch_target")]
    if len(passing) == len(buttons):
        score += 3
        strengths.append(f"All {len(buttons)} buttons meet 44px target size")
    else:
        failing = len(buttons) - len(passing)
        issues.append(f"{failing}/{len(buttons)} buttons below 44px target size")
        score += round(3 * len(passing) / len(buttons))

    # Labels
    labelled = [b for b in buttons if b.get("has_visible_label") or b.get("has_aria_label")]
    if len(labelled) == len(buttons):
        score += 2
        strengths.append("All buttons have accessible labels")
    else:
        missing = len(buttons) - len(labelled)
        issues.append(f"{missing} buttons missing accessible labels")

    # State tests
    state_tests = dom_data.get("state_tests", [])
    btn_states = [s for s in state_tests if s.get("selector", "").startswith("button")]
    if btn_states:
        with_hover = [s for s in btn_states if s.get("has_hover_state")]
        with_focus = [s for s in btn_states if s.get("has_focus_state")]

        if len(with_hover) == len(btn_states):
            score += 2
            strengths.append("All tested buttons have hover states")
        else:
            issues.append(f"{len(btn_states) - len(with_hover)} buttons missing hover")

        if len(with_focus) == len(btn_states):
            score += 2
            strengths.append("All tested buttons have focus states")
        else:
            issues.append(f"{len(btn_states) - len(with_focus)} buttons missing focus")
    else:
        score += 1  # Partial credit if no state tests

    # Non-text contrast
    ntc = dom_data.get("non_text_contrast", [])
    btn_ntc = [n for n in ntc if n.get("element", "").startswith("button")]
    if btn_ntc:
        passing_ntc = [n for n in btn_ntc if n.get("passes_3_to_1")]
        if len(passing_ntc) == len(btn_ntc):
            score += 1
            strengths.append("All buttons meet non-text contrast")
        else:
            issues.append(f"{len(btn_ntc) - len(passing_ntc)} buttons fail non-text contrast")

    selector = buttons[0]["element"] if buttons else "button"
    return ComponentScore("Buttons", "button-group", selector, score, max_score, issues, strengths)


def _score_content_list(dom_data: dict) -> ComponentScore | None:
    """Score list/card content patterns."""
    interactive = dom_data.get("interactive_elements", [])

    # Look for list items, cards, or repeated content patterns
    list_items = [e for e in interactive
                  if any(kw in str(e.get("element", "")).lower()
                         for kw in ["item", "card", "list", "row", "entry"])]

    if len(list_items) < 3:
        return None

    score = 0
    max_score = 10
    issues = []
    strengths = []

    # Consistent sizing
    heights = [e.get("height", 0) for e in list_items]
    widths = [e.get("width", 0) for e in list_items]
    if heights and max(heights) - min(heights) < 5:
        score += 3
        strengths.append(f"Consistent item height ({heights[0]}px)")
    elif heights:
        issues.append(f"Inconsistent item heights: {min(heights)}px to {max(heights)}px")
        score += 1

    # Touch targets
    passing = [e for e in list_items if e.get("meets_touch_target")]
    if len(passing) == len(list_items):
        score += 3
        strengths.append("All list items meet 44px target minimum")
    else:
        issues.append(f"{len(list_items) - len(passing)} items below 44px target size")
        score += round(3 * len(passing) / len(list_items))

    # Labels
    labelled = [e for e in list_items if e.get("has_visible_label")]
    if len(labelled) == len(list_items):
        score += 2
        strengths.append("All items have visible labels")
    else:
        issues.append(f"{len(list_items) - len(labelled)} items missing labels")

    # State tests
    state_tests = dom_data.get("state_tests", [])
    item_states = [s for s in state_tests
                   if any(kw in s.get("selector", "").lower() for kw in ["item", "card", "row"])]
    if item_states:
        with_hover = [s for s in item_states if s.get("has_hover_state")]
        if with_hover:
            score += 2
            strengths.append("List items have hover feedback")
        else:
            issues.append("List items lack hover states")

    selector = list_items[0]["element"] if list_items else "div"
    return ComponentScore("Content List", "list", selector, score, max_score, issues, strengths)


def detect_and_score_components(dom_data: dict) -> ComponentReport:
    """Detect components from DOM data and score each one."""
    report = ComponentReport()
    interactive = dom_data.get("interactive_elements", [])

    # Navigation
    nav_elements = [e for e in interactive
                    if any(kw in str(e.get("element", "")).lower()
                           for kw in ["nav", "tab", "menu"])]
    if nav_elements:
        report.components.append(_score_navigation({}, interactive, dom_data))

    # Forms
    form_score = _score_forms(dom_data)
    if form_score:
        report.components.append(form_score)

    # Buttons
    buttons = [e for e in interactive if e.get("element", "").startswith("button")]
    if buttons:
        report.components.append(_score_buttons(dom_data))

    # Content lists/cards
    list_score = _score_content_list(dom_data)
    if list_score:
        report.components.append(list_score)

    return report


def detect_and_score_multi(pages: list) -> ComponentReport:
    """Detect and score components across multiple pages."""
    # Use the first page with the most interactive elements
    best_page = None
    best_count = 0
    for page in pages:
        dom = page.dom_data if hasattr(page, 'dom_data') else page.get("dom_data", {})
        count = len(dom.get("interactive_elements", []))
        if count > best_count:
            best_count = count
            best_page = dom

    if best_page:
        return detect_and_score_components(best_page)
    return ComponentReport()
