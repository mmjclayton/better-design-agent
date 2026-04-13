"""
Programmatic WCAG 2.2 checker.

Produces deterministic pass/fail results from DOM extraction data.
No LLM involved — 100% accurate for the criteria it can evaluate.
"""

from dataclasses import dataclass, field


@dataclass
class WcagResult:
    criterion: str
    level: str  # A, AA, AAA
    status: str  # pass, fail, na, warning
    details: str
    count: int = 0  # number of violations (0 = pass)
    violations: list[dict] = field(default_factory=list)


@dataclass
class WcagReport:
    results: list[WcagResult] = field(default_factory=list)

    @property
    def pass_count(self) -> int:
        return sum(1 for r in self.results if r.status == "pass")

    @property
    def fail_count(self) -> int:
        return sum(1 for r in self.results if r.status == "fail")

    @property
    def warning_count(self) -> int:
        return sum(1 for r in self.results if r.status == "warning")

    @property
    def total_violations(self) -> int:
        return sum(r.count for r in self.results if r.status == "fail")

    @property
    def score_percentage(self) -> float:
        """Score based on A/AA criteria only (AAA is aspirational)."""
        testable = [r for r in self.results if r.status != "na" and r.level in ("A", "AA")]
        if not testable:
            return 0.0
        passed = sum(1 for r in testable if r.status == "pass")
        return round((passed / len(testable)) * 100, 1)

    def to_dict(self) -> dict:
        return {
            "summary": {
                "pass": self.pass_count,
                "fail": self.fail_count,
                "warning": self.warning_count,
                "total_violations": self.total_violations,
                "score_percentage": self.score_percentage,
            },
            "results": [
                {
                    "criterion": r.criterion,
                    "level": r.level,
                    "status": r.status,
                    "details": r.details,
                    "count": r.count,
                    "violations": r.violations[:10],
                }
                for r in self.results
            ],
        }

    def to_markdown(self) -> str:
        # Separate A/AA (compliance-blocking) from AAA (aspirational) so the
        # summary headline doesn't conflate them.
        aa_fails = [r for r in self.results
                    if r.status == "fail" and r.level in ("A", "AA")]
        aaa_fails = [r for r in self.results
                     if r.status == "fail" and r.level == "AAA"]
        aa_violation_count = sum(r.count for r in aa_fails)
        aaa_violation_count = sum(r.count for r in aaa_fails)

        summary = (
            f"**Score: {self.score_percentage}%** (A/AA only) — "
            f"{self.pass_count} pass, {len(aa_fails)} fail, "
            f"{self.warning_count} warning; "
            f"{aa_violation_count} A/AA violation(s)"
        )
        if aaa_fails:
            summary += f"; {aaa_violation_count} AAA aspirational"

        lines = [
            "## WCAG 2.2 Automated Audit\n",
            summary + "\n",
        ]

        # Failures — separated by level
        failures = [r for r in self.results if r.status == "fail"]
        aa_failures = [r for r in failures if r.level in ("A", "AA")]
        aaa_failures = [r for r in failures if r.level == "AAA"]

        if aa_failures:
            lines.append("### Failures (A/AA - must fix for compliance)\n")
            lines.append("| Criterion | Level | Violations | Details |")
            lines.append("|-----------|-------|------------|---------|")
            for r in aa_failures:
                lines.append(f"| {r.criterion} | {r.level} | {r.count} | {r.details} |")

            for r in aa_failures:
                if r.violations:
                    # Deduplicate violations by element
                    seen = set()
                    unique = []
                    for v in r.violations:
                        key = v.get("element", "") + "|" + v.get("issue", v.get("size", ""))
                        if key not in seen:
                            seen.add(key)
                            unique.append(v)
                    noun = "element" if len(unique) == 1 else "elements"
                    lines.append(f"\n**{r.criterion}** violations ({len(unique)} unique {noun}):")
                    for v in unique[:10]:
                        lines.append(f"- {_format_violation(v)}")
            lines.append("")

        if aaa_failures:
            lines.append("### AAA Aspirational (nice to have, not required for compliance)\n")
            lines.append("| Criterion | Level | Violations | Details |")
            lines.append("|-----------|-------|------------|---------|")
            for r in aaa_failures:
                lines.append(f"| {r.criterion} | {r.level} | {r.count} | {r.details} |")
            lines.append("")

        # Warnings
        warnings = [r for r in self.results if r.status == "warning"]
        if warnings:
            lines.append("\n### Warnings\n")
            lines.append("| Criterion | Level | Details |")
            lines.append("|-----------|-------|---------|")
            for r in warnings:
                lines.append(f"| {r.criterion} | {r.level} | {r.details} |")
            lines.append("")

        # Passes
        passes = [r for r in self.results if r.status == "pass"]
        if passes:
            lines.append("\n### Passing\n")
            lines.append("| Criterion | Level | Details |")
            lines.append("|-----------|-------|---------|")
            for r in passes:
                lines.append(f"| {r.criterion} | {r.level} | {r.details} |")
            lines.append("")

        return "\n".join(lines)

    def to_pragmatic_markdown(self) -> str:
        """High-signal WCAG report: only A/AA failures + their violations.

        Drops passes, warnings, AAA criteria, and na rows. Designed for
        ad-hoc "what should I fix?" reviews rather than full audits.
        """
        aa_failures = [
            r for r in self.results
            if r.status == "fail" and r.level in ("A", "AA")
        ]
        lines = [
            "## WCAG — Pragmatic View\n",
            f"**Score: {self.score_percentage}%** "
            f"({len(aa_failures)} A/AA failures shown, other rows hidden)\n",
        ]
        if not aa_failures:
            lines.append("No A/AA failures — nothing to fix.")
            return "\n".join(lines)

        lines.append("| Criterion | Level | Violations | Details |")
        lines.append("|-----------|-------|------------|---------|")
        for r in aa_failures:
            lines.append(f"| {r.criterion} | {r.level} | {r.count} | {r.details} |")
        lines.append("")

        for r in aa_failures:
            if not r.violations:
                continue
            # Deduplicate violations by element
            seen = set()
            unique = []
            for v in r.violations:
                key = v.get("element", "") + "|" + v.get("issue", v.get("size", ""))
                if key not in seen:
                    seen.add(key)
                    unique.append(v)
            lines.append(f"\n**{r.criterion}** ({len(unique)} unique):")
            for v in unique[:5]:
                lines.append(f"- {_format_violation(v)}")
            if len(unique) > 5:
                lines.append(f"- … +{len(unique) - 5} more")
        return "\n".join(lines)


def _format_violation(v: dict) -> str:
    parts = []
    if v.get("element"):
        parts.append(f"`{v['element']}`")
    if v.get("text"):
        parts.append(f'"{v["text"]}"')
    if v.get("ratio"):
        parts.append(f"ratio: {v['ratio']}:1")
    if v.get("size"):
        parts.append(f"size: {v['size']}")
    if v.get("issue"):
        parts.append(v["issue"])
    return " - ".join(parts) if parts else str(v)


# ── Individual WCAG Checks ──


def check_contrast_minimum(dom_data: dict) -> WcagResult:
    """WCAG 1.4.3 Contrast (Minimum) - AA - 4.5:1 normal, 3:1 large text."""
    pairs = dom_data.get("contrast_pairs", [])
    if not pairs:
        return WcagResult("1.4.3 Contrast (Minimum)", "AA", "na", "No text contrast data")

    violations = []
    for p in pairs:
        if not p.get("passes_aa"):
            violations.append({
                "element": p.get("element", "?"),
                "text": p.get("sample_text", "")[:40],
                "ratio": p.get("ratio"),
                "issue": f"{p.get('text_color')} on {p.get('bg_color')} = {p.get('ratio')}:1 (requires {p.get('required')}:1)",
            })

    if violations:
        return WcagResult(
            "1.4.3 Contrast (Minimum)", "AA", "fail",
            f"{len(violations)} text/background pairs below required ratio",
            count=len(violations), violations=violations,
        )
    return WcagResult(
        "1.4.3 Contrast (Minimum)", "AA", "pass",
        f"All {len(pairs)} text/background pairs meet AA requirements",
    )


def check_non_text_contrast(dom_data: dict) -> WcagResult:
    """WCAG 1.4.11 Non-text Contrast - AA - 3:1 for UI components."""
    ntc = dom_data.get("non_text_contrast", [])
    if not ntc:
        return WcagResult("1.4.11 Non-text Contrast", "AA", "na", "No UI component contrast data")

    violations = []
    for n in ntc:
        if not n.get("passes_3_to_1"):
            violations.append({
                "element": n.get("element", "?"),
                "text": n.get("text", "")[:30],
                "ratio": n.get("bg_ratio"),
                "issue": f"{n.get('component_bg')} vs {n.get('adjacent_bg')} = {n.get('bg_ratio')}:1",
            })

    if violations:
        return WcagResult(
            "1.4.11 Non-text Contrast", "AA", "fail",
            f"{len(violations)} UI components below 3:1 boundary contrast",
            count=len(violations), violations=violations,
        )
    return WcagResult(
        "1.4.11 Non-text Contrast", "AA", "pass",
        f"All {len(ntc)} UI components meet 3:1 boundary contrast",
    )


def _is_offscreen_element(element: dict) -> bool:
    """Check if an element is likely off-screen (skip links, hidden elements)."""
    el_name = element.get("element", "").lower()
    text = element.get("text", "").lower()
    # Skip links are intentionally off-screen and only visible on focus
    if "skip" in el_name or "skip" in text:
        return True
    return False


def check_target_size(dom_data: dict) -> WcagResult:
    """WCAG 2.5.8 Target Size (Minimum) - AA - 24x24px minimum."""
    interactive = dom_data.get("interactive_elements", [])
    if not interactive:
        return WcagResult("2.5.8 Target Size (Minimum)", "AA", "na", "No interactive elements")

    violations_24 = []
    warnings_44 = []
    for e in interactive:
        # Skip off-screen elements (skip links are visible only on focus)
        if _is_offscreen_element(e):
            continue
        w, h = e.get("width", 0), e.get("height", 0)
        if w < 24 or h < 24:
            violations_24.append({
                "element": e.get("element", "?"),
                "text": e.get("text", "")[:30],
                "size": f"{w}x{h}px",
                "issue": "Below 24x24px minimum",
            })
        elif w < 44 or h < 44:
            warnings_44.append({
                "element": e.get("element", "?"),
                "text": e.get("text", "")[:30],
                "size": f"{w}x{h}px",
                "issue": "Below 44x44px recommended",
            })

    if violations_24:
        # Don't mention 44px here — 2.5.5 (AAA) has its own row. Conflating
        # them in the AA detail makes readers double-count.
        return WcagResult(
            "2.5.8 Target Size (Minimum)", "AA", "fail",
            f"{len(violations_24)} elements below 24x24px minimum",
            count=len(violations_24), violations=violations_24,
        )
    if warnings_44:
        return WcagResult(
            "2.5.8 Target Size (Minimum)", "AA", "pass",
            f"All {len(interactive)} elements meet 24x24px AA minimum",
        )
    return WcagResult(
        "2.5.8 Target Size (Minimum)", "AA", "pass",
        f"All {len(interactive)} interactive elements meet 24x24px minimum",
    )


def check_target_size_enhanced(dom_data: dict) -> WcagResult:
    """WCAG 2.5.5 Target Size (Enhanced) - AAA - 44x44px minimum."""
    interactive = dom_data.get("interactive_elements", [])
    if not interactive:
        return WcagResult("2.5.5 Target Size (Enhanced)", "AAA", "na", "No interactive elements")

    violations = [
        {
            "element": e.get("element", "?"),
            "text": e.get("text", "")[:30],
            "size": f"{e.get('width', 0)}x{e.get('height', 0)}px",
        }
        for e in interactive
        if not e.get("meets_touch_target") and not _is_offscreen_element(e)
    ]

    if violations:
        return WcagResult(
            "2.5.5 Target Size (Enhanced)", "AAA", "fail",
            f"{len(violations)} elements below 44x44px",
            count=len(violations), violations=violations,
        )
    return WcagResult(
        "2.5.5 Target Size (Enhanced)", "AAA", "pass",
        f"All {len(interactive)} elements meet 44x44px enhanced requirement",
    )


def check_language(dom_data: dict) -> WcagResult:
    """WCAG 3.1.1 Language of Page - A."""
    html = dom_data.get("html_structure", {})
    has_lang = html.get("has_lang", False)
    lang_value = html.get("lang_value")

    if has_lang and lang_value:
        return WcagResult(
            "3.1.1 Language of Page", "A", "pass",
            f'lang="{lang_value}" set on <html>',
        )
    return WcagResult(
        "3.1.1 Language of Page", "A", "fail",
        "Missing lang attribute on <html>",
        count=1, violations=[{"issue": "No lang attribute on <html> element"}],
    )


def check_bypass_blocks(dom_data: dict) -> WcagResult:
    """WCAG 2.4.1 Bypass Blocks - A - skip link present."""
    html = dom_data.get("html_structure", {})
    has_skip = html.get("skip_link", False)

    if has_skip:
        return WcagResult("2.4.1 Bypass Blocks", "A", "pass", "Skip navigation link present")
    return WcagResult(
        "2.4.1 Bypass Blocks", "A", "fail",
        "No skip navigation link found",
        count=1, violations=[{"issue": "Add <a href='#main' class='skip-link'>Skip to main content</a>"}],
    )


def check_landmarks(dom_data: dict) -> WcagResult:
    """WCAG 1.3.1 Info and Relationships - A - semantic landmarks."""
    html = dom_data.get("html_structure", {})
    landmarks = html.get("landmarks", {})

    required = {"main": "main content area", "nav": "navigation"}
    recommended = {"header": "page header", "footer": "page footer"}

    missing_required = []
    missing_recommended = []

    for tag, desc in required.items():
        if landmarks.get(tag, 0) == 0:
            missing_required.append({"element": f"<{tag}>", "issue": f"Missing {desc} landmark"})

    for tag, desc in recommended.items():
        if landmarks.get(tag, 0) == 0:
            missing_recommended.append({"element": f"<{tag}>", "issue": f"Missing {desc} landmark"})

    if missing_required:
        return WcagResult(
            "1.3.1 Info and Relationships (Landmarks)", "A", "fail",
            f"Missing {len(missing_required)} required landmarks",
            count=len(missing_required), violations=missing_required + missing_recommended,
        )
    if missing_recommended:
        return WcagResult(
            "1.3.1 Info and Relationships (Landmarks)", "A", "warning",
            f"Required landmarks present, {len(missing_recommended)} recommended landmarks missing",
            count=0, violations=missing_recommended,
        )
    return WcagResult(
        "1.3.1 Info and Relationships (Landmarks)", "A", "pass",
        "All required and recommended landmarks present",
    )


def check_heading_hierarchy(dom_data: dict) -> WcagResult:
    """WCAG 1.3.1 / 2.4.6 - Heading hierarchy should not skip levels."""
    html = dom_data.get("html_structure", {})
    headings = html.get("headings", [])

    if not headings:
        return WcagResult(
            "1.3.1 Info and Relationships (Headings)", "A", "fail",
            "No heading elements found on page",
            count=1, violations=[{"issue": "Page has no headings - add at least an <h1>"}],
        )

    violations = []
    levels = [h["level"] for h in headings]

    # Check for h1
    if 1 not in levels:
        violations.append({"issue": "No <h1> element found - every page should have exactly one"})

    # Check for multiple h1s
    h1_count = levels.count(1)
    if h1_count > 1:
        violations.append({"issue": f"Found {h1_count} <h1> elements - should have exactly one"})

    # Check for skipped levels
    prev_level = 0
    for h in headings:
        level = h["level"]
        if level > prev_level + 1 and prev_level > 0:
            violations.append({
                "issue": f'Heading level skipped: <h{prev_level}> followed by <h{level}> "{h["text"]}"'
            })
        prev_level = level

    if violations:
        return WcagResult(
            "1.3.1 Info and Relationships (Headings)", "A", "fail",
            f"{len(violations)} heading hierarchy issues",
            count=len(violations), violations=violations,
        )
    return WcagResult(
        "1.3.1 Info and Relationships (Headings)", "A", "pass",
        f"Heading hierarchy is valid ({len(headings)} headings, proper nesting)",
    )


def check_form_labels(dom_data: dict) -> WcagResult:
    """WCAG 1.3.1 / 4.1.2 - All form inputs must have programmatic labels."""
    html = dom_data.get("html_structure", {})
    forms = html.get("forms", {})
    unlabelled_inputs = forms.get("inputs_without_labels", [])
    unlabelled_selects = forms.get("selects_without_labels", [])
    breakdown = forms.get("label_breakdown", {}) or {}

    violations = []
    for inp in unlabelled_inputs:
        violations.append({
            "element": inp.get("selector", "input"),
            "issue": f"Input type={inp.get('type', 'text')} has no label"
                     + (f" (placeholder: \"{inp['placeholder']}\")" if inp.get("placeholder") else ""),
        })
    for sel in unlabelled_selects:
        violations.append({
            "element": sel.get("selector", "select"),
            "issue": f"Select has no label (first option: \"{sel.get('first_option', '?')}\")",
        })

    def _breakdown_summary() -> str:
        parts = []
        if breakdown.get("with_label_element", 0):
            parts.append(f"{breakdown['with_label_element']} use <label>")
        if breakdown.get("with_aria_label", 0):
            parts.append(f"{breakdown['with_aria_label']} use aria-label")
        if breakdown.get("with_aria_labelledby", 0):
            parts.append(f"{breakdown['with_aria_labelledby']} use aria-labelledby")
        if breakdown.get("with_title", 0):
            parts.append(f"{breakdown['with_title']} use title attr (weak)")
        if breakdown.get("unlabelled", 0):
            parts.append(f"{breakdown['unlabelled']} unlabelled")
        return "; ".join(parts) if parts else ""

    if violations:
        summary = _breakdown_summary()
        detail = f"{len(violations)} form inputs without programmatic labels"
        if summary:
            detail = f"{detail} (labelling breakdown: {summary})"
        return WcagResult(
            "4.1.2 Name, Role, Value (Form Labels)", "A", "fail",
            detail,
            count=len(violations), violations=violations,
        )

    # If no form elements at all, report as NA
    interactive = dom_data.get("interactive_elements", [])
    has_inputs = any(
        e.get("element", "").startswith(("input", "select", "textarea"))
        for e in interactive
    )
    if not has_inputs:
        return WcagResult("4.1.2 Name, Role, Value (Form Labels)", "A", "na", "No form inputs found")

    summary = _breakdown_summary()
    detail = "All form inputs have programmatic labels"
    if summary:
        detail = f"{detail} ({summary})"
    return WcagResult(
        "4.1.2 Name, Role, Value (Form Labels)", "A", "pass", detail,
    )


def check_focus_visible(dom_data: dict) -> WcagResult:
    """WCAG 2.4.7 Focus Visible - AA - focus indicator must be visible."""
    html = dom_data.get("html_structure", {})
    has_global_fv = html.get("has_global_focus_visible", False)
    fv_rules = html.get("focus_visible_rules", [])

    # Also check state test results for focus
    state_tests = dom_data.get("state_tests", [])
    focus_tested = [s for s in state_tests if s.get("has_focus_state")]

    if has_global_fv:
        rule_desc = ", ".join(
            r.get("selector", "?") for r in fv_rules[:3]
            if r.get("selector")
        )
        detail = (
            f"Global :focus-visible rules found ({rule_desc})"
            if rule_desc
            else "Global :focus-visible rules detected in stylesheets"
        )
        return WcagResult(
            "2.4.7 Focus Visible", "AA", "pass", detail,
        )

    if focus_tested:
        total_tested = len(state_tests)
        with_focus = len(focus_tested)
        if with_focus == total_tested:
            return WcagResult(
                "2.4.7 Focus Visible", "AA", "pass",
                f"All {total_tested} tested elements have focus styles",
            )
        missing = total_tested - with_focus
        return WcagResult(
            "2.4.7 Focus Visible", "AA", "warning",
            f"{missing}/{total_tested} tested elements lack focus styles",
            count=missing,
        )

    return WcagResult(
        "2.4.7 Focus Visible", "AA", "warning",
        "Could not determine focus visibility - no global rules or state tests",
    )


def check_color_not_sole_means(dom_data: dict) -> WcagResult:
    """WCAG 1.4.1 Use of Color - A - cannot evaluate fully from DOM, report as manual check."""
    return WcagResult(
        "1.4.1 Use of Color", "A", "na",
        "Requires manual review - cannot determine if color is sole means of conveying information from DOM data",
    )


# ── Main Checker ──


def run_wcag_check(dom_data: dict) -> WcagReport:
    """Run all programmatic WCAG checks against DOM extraction data."""
    report = WcagReport()

    report.results.append(check_language(dom_data))
    report.results.append(check_bypass_blocks(dom_data))
    report.results.append(check_landmarks(dom_data))
    report.results.append(check_heading_hierarchy(dom_data))
    report.results.append(check_form_labels(dom_data))
    report.results.append(check_contrast_minimum(dom_data))
    report.results.append(check_non_text_contrast(dom_data))
    report.results.append(check_target_size(dom_data))
    report.results.append(check_target_size_enhanced(dom_data))
    report.results.append(check_focus_visible(dom_data))
    report.results.append(check_color_not_sole_means(dom_data))

    return report


def run_wcag_check_multi(pages: list) -> WcagReport:
    """Run WCAG checks across multiple pages and aggregate results."""
    if not pages:
        return WcagReport()

    # Run checks on each page
    page_reports = []
    for page in pages:
        dom = page.dom_data if hasattr(page, 'dom_data') else page.get("dom_data", {})
        page_reports.append(run_wcag_check(dom))

    # Aggregate: a criterion fails if it fails on ANY page
    # Violations are merged with page labels
    aggregated = WcagReport()
    criterion_map: dict[str, WcagResult] = {}

    for i, report in enumerate(page_reports):
        label = pages[i].label if hasattr(pages[i], 'label') else pages[i].get("label", f"Page {i}")
        for result in report.results:
            key = result.criterion
            if key not in criterion_map:
                criterion_map[key] = WcagResult(
                    criterion=result.criterion,
                    level=result.level,
                    status=result.status,
                    details=result.details,
                    count=result.count,
                    violations=[{**v, "page": label} for v in result.violations],
                )
            else:
                existing = criterion_map[key]
                # Fail overrides pass/warning, warning overrides pass
                status_priority = {"fail": 3, "warning": 2, "pass": 1, "na": 0}
                if status_priority.get(result.status, 0) > status_priority.get(existing.status, 0):
                    existing.status = result.status
                    existing.details = result.details
                existing.violations.extend([{**v, "page": label} for v in result.violations])

    # Deduplicate violations and recount
    for result in criterion_map.values():
        seen = set()
        unique = []
        for v in result.violations:
            # Deduplicate by element + issue (ignore page)
            key = (v.get("element", ""), v.get("issue", v.get("size", "")))
            if key not in seen:
                seen.add(key)
                unique.append(v)
        result.violations = unique
        result.count = len(unique)
        # Update details with correct count
        if result.count > 0 and result.status == "fail":
            result.details = f"{result.count} unique violations across pages"

    aggregated.results = list(criterion_map.values())
    return aggregated
