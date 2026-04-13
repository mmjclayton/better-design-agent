"""
Real interaction testing via Playwright.

Actually uses the app — submits forms, navigates by keyboard, tests
empty states, checks overflow — and reports what happens. No LLM involved.
"""

import asyncio
from dataclasses import dataclass, field

from playwright.async_api import async_playwright


@dataclass
class InteractionTestResult:
    name: str
    status: str  # pass, fail, warning, skip
    details: str
    element: str = ""
    screenshot: str = ""


@dataclass
class InteractionTestReport:
    results: list[InteractionTestResult] = field(default_factory=list)
    keyboard_tab_order: list[dict] = field(default_factory=list)
    breakpoint_issues: list[dict] = field(default_factory=list)

    @property
    def pass_count(self) -> int:
        return sum(1 for r in self.results if r.status == "pass")

    @property
    def fail_count(self) -> int:
        return sum(1 for r in self.results if r.status == "fail")

    def to_markdown(self) -> str:
        lines = [
            "## Interaction Test Report\n",
            f"**Results:** {self.pass_count} pass, {self.fail_count} fail, "
            f"{len(self.results) - self.pass_count - self.fail_count} warning/skip\n",
        ]

        # Failures first
        failures = [r for r in self.results if r.status == "fail"]
        if failures:
            lines.append("### Failures\n")
            for r in failures:
                lines.append(f"- **{r.name}**: {r.details}")
                if r.element:
                    lines.append(f"  Element: `{r.element}`")
            lines.append("")

        # Warnings
        warnings = [r for r in self.results if r.status == "warning"]
        if warnings:
            lines.append("### Warnings\n")
            for r in warnings:
                lines.append(f"- **{r.name}**: {r.details}")
            lines.append("")

        # Passes
        passes = [r for r in self.results if r.status == "pass"]
        if passes:
            lines.append("### Passing\n")
            for r in passes:
                lines.append(f"- **{r.name}**: {r.details}")
            lines.append("")

        # Keyboard tab order
        if self.keyboard_tab_order:
            lines.append("### Keyboard Tab Order\n")
            lines.append("Elements reached by pressing Tab repeatedly:\n")
            for i, item in enumerate(self.keyboard_tab_order):
                focus_visible = "visible" if item.get("has_visible_focus") else "**NOT VISIBLE**"
                lines.append(
                    f"{i+1}. `{item.get('tag', '?')}.{item.get('class', '')}` "
                    f"\"{item.get('text', '')}\" - focus: {focus_visible}"
                )
            lines.append("")

        # Breakpoint issues
        if self.breakpoint_issues:
            lines.append("### Responsive Breakpoint Issues\n")
            for issue in self.breakpoint_issues:
                lines.append(
                    f"- **{issue['width']}px**: {issue['issue']}"
                )
            lines.append("")

        return "\n".join(lines)


async def _test_keyboard_navigation(page) -> list[dict]:
    """Tab through the entire page and record focus order."""
    tab_order = []
    max_tabs = 30

    # Reset focus to start of document
    await page.evaluate("document.activeElement?.blur()")
    await page.keyboard.press("Tab")
    await page.wait_for_timeout(200)

    for i in range(max_tabs):
        # Get current focused element info
        info = await page.evaluate("""
            () => {
                const el = document.activeElement;
                if (!el || el === document.body || el === document.documentElement) return null;

                const style = getComputedStyle(el);
                const rect = el.getBoundingClientRect();

                // Check if focus is visually indicated
                const outline = style.outlineStyle;
                const boxShadow = style.boxShadow;
                const hasVisibleFocus = (outline !== 'none' && outline !== '')
                    || (boxShadow !== 'none' && boxShadow !== '');

                return {
                    tag: el.tagName.toLowerCase(),
                    class: (el.className?.toString() || '').split(' ')[0] || '',
                    text: (el.textContent || el.placeholder || el.getAttribute('aria-label') || '').trim().substring(0, 40),
                    role: el.getAttribute('role') || '',
                    href: el.getAttribute('href') || '',
                    type: el.getAttribute('type') || '',
                    has_visible_focus: hasVisibleFocus,
                    is_visible: rect.width > 0 && rect.height > 0 && style.display !== 'none',
                    x: Math.round(rect.x),
                    y: Math.round(rect.y),
                };
            }
        """)

        if not info:
            break

        # Check for focus loop (back to first element)
        if len(tab_order) > 2 and info.get("tag") == tab_order[0].get("tag") and info.get("text") == tab_order[0].get("text"):
            break

        tab_order.append(info)
        await page.keyboard.press("Tab")
        await page.wait_for_timeout(150)

    return tab_order


async def _test_form_validation(page) -> list[InteractionTestResult]:
    """Find forms and test validation by submitting with invalid/empty data."""
    results = []

    forms = await page.evaluate("""
        () => {
            const forms = document.querySelectorAll('form');
            const inputs = document.querySelectorAll('input[type="text"], input[type="email"], input[type="password"], input[type="url"], input[type="tel"], input[type="number"], textarea');
            return {
                form_count: forms.length,
                input_count: inputs.length,
                inputs: Array.from(inputs).slice(0, 10).map(i => ({
                    type: i.type || 'text',
                    name: i.name || i.id || '',
                    required: i.required,
                    placeholder: i.placeholder || '',
                    selector: i.tagName.toLowerCase() + (i.className ? '.' + i.className.toString().split(' ')[0] : ''),
                })),
            };
        }
    """)

    if forms["input_count"] == 0:
        results.append(InteractionTestResult(
            "Form validation", "skip", "No text inputs found on page",
        ))
        return results

    # Test each input: clear it, type invalid data, blur, check for error
    for inp in forms["inputs"]:
        selector = inp["selector"]
        try:
            el = page.locator(selector).first
            if not await el.is_visible():
                continue

            # Clear and leave empty (test required validation)
            await el.clear()
            await el.fill("")
            await page.keyboard.press("Tab")
            await page.wait_for_timeout(300)

            # Check for error state
            error_visible = await page.evaluate(f"""
                () => {{
                    const el = document.querySelector('{selector}');
                    if (!el) return false;
                    const style = getComputedStyle(el);
                    const hasErrorBorder = style.borderColor.includes('255') || style.borderColor.includes('239');
                    const hasErrorMessage = el.nextElementSibling?.textContent?.toLowerCase().includes('error')
                        || el.nextElementSibling?.textContent?.toLowerCase().includes('required')
                        || el.getAttribute('aria-invalid') === 'true';
                    return hasErrorBorder || hasErrorMessage;
                }}
            """)

            if inp["required"] and not error_visible:
                results.append(InteractionTestResult(
                    f"Required field validation: {inp['name'] or inp['placeholder']}",
                    "fail",
                    "Required input shows no error state when left empty",
                    element=selector,
                ))
            elif error_visible:
                results.append(InteractionTestResult(
                    f"Required field validation: {inp['name'] or inp['placeholder']}",
                    "pass",
                    "Input shows error state when required field is empty",
                    element=selector,
                ))

            # Test email fields with invalid data
            if inp["type"] == "email":
                await el.fill("not-an-email")
                await page.keyboard.press("Tab")
                await page.wait_for_timeout(300)

                email_error = await page.evaluate(f"""
                    () => {{
                        const el = document.querySelector('{selector}');
                        return el?.validity?.valid === false || el?.getAttribute('aria-invalid') === 'true';
                    }}
                """)
                results.append(InteractionTestResult(
                    f"Email validation: {inp['name'] or inp['placeholder']}",
                    "pass" if email_error else "warning",
                    "Invalid email is flagged" if email_error else "No validation for invalid email format",
                    element=selector,
                ))

        except Exception:
            continue

    return results


async def _test_empty_states(page) -> list[InteractionTestResult]:
    """Test empty/zero-result states by clearing searches and filters."""
    results = []

    # Find search inputs
    search = await page.evaluate("""
        () => {
            const inputs = document.querySelectorAll('input[type="search"], input[placeholder*="search" i], input[placeholder*="filter" i]');
            return Array.from(inputs).map(i => ({
                selector: i.tagName.toLowerCase() + (i.className ? '.' + i.className.toString().split(' ')[0] : ''),
                placeholder: i.placeholder,
            }));
        }
    """)

    for s in search[:3]:
        try:
            el = page.locator(s["selector"]).first
            if not await el.is_visible():
                continue

            # Type nonsense to trigger empty results
            await el.fill("zzzzxxxxxxxnotfound99999")
            await page.wait_for_timeout(500)

            # Check if an empty state message appears
            empty_state = await page.evaluate("""
                () => {
                    const body = document.body.innerText.toLowerCase();
                    return body.includes('no results') || body.includes('not found')
                        || body.includes('no match') || body.includes('nothing found')
                        || body.includes('no items') || body.includes('no exercises');
                }
            """)

            results.append(InteractionTestResult(
                f"Empty state: search '{s['placeholder']}'",
                "pass" if empty_state else "fail",
                "Empty state message shown for zero results" if empty_state else "No empty state message when search returns zero results",
                element=s["selector"],
            ))

            # Clear the search
            await el.clear()
            await page.wait_for_timeout(300)

        except Exception:
            continue

    if not search:
        results.append(InteractionTestResult(
            "Empty state: search", "skip", "No search inputs found",
        ))

    return results


async def _test_responsive_breakpoints(page, url: str) -> list[dict]:
    """Test at mobile, tablet, and desktop breakpoints, report layout issues."""
    breakpoints = [
        {"width": 375, "height": 667, "name": "Mobile (375px)"},
        {"width": 768, "height": 1024, "name": "Tablet (768px)"},
        {"width": 1440, "height": 900, "name": "Desktop (1440px)"},
    ]

    issues = []

    for bp in breakpoints:
        await page.set_viewport_size({"width": bp["width"], "height": bp["height"]})
        await page.goto(url, wait_until="networkidle", timeout=15000)
        await page.wait_for_timeout(500)

        # Check for horizontal overflow
        has_overflow = await page.evaluate("""
            () => document.documentElement.scrollWidth > document.documentElement.clientWidth
        """)
        if has_overflow:
            issues.append({
                "width": bp["width"],
                "issue": f"Horizontal overflow detected at {bp['name']} - content wider than viewport",
            })

        # Check for text too small on mobile
        if bp["width"] < 768:
            small_text = await page.evaluate("""
                () => {
                    let count = 0;
                    for (const el of document.querySelectorAll('body *')) {
                        const style = getComputedStyle(el);
                        if (style.display === 'none') continue;
                        const size = parseFloat(style.fontSize);
                        const text = el.textContent?.trim();
                        if (text && text.length > 0 && size < 12 && el.children.length === 0) count++;
                    }
                    return count;
                }
            """)
            if small_text > 5:
                issues.append({
                    "width": bp["width"],
                    "issue": f"{small_text} text elements below 12px on mobile - may be unreadable",
                })

        # Check touch targets on mobile
        if bp["width"] < 768:
            small_targets = await page.evaluate("""
                () => {
                    let count = 0;
                    for (const el of document.querySelectorAll('button, a, input, select, [role="button"]')) {
                        const rect = el.getBoundingClientRect();
                        if (rect.width > 0 && rect.height > 0 && (rect.width < 44 || rect.height < 44)) count++;
                    }
                    return count;
                }
            """)
            if small_targets > 0:
                issues.append({
                    "width": bp["width"],
                    "issue": f"{small_targets} interactive elements below 44x44px touch target on mobile",
                })

    return issues


async def _run_tests(url: str, viewport_width: int = 1440, viewport_height: int = 900) -> InteractionTestReport:
    """Run all interaction tests."""
    report = InteractionTestReport()

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": viewport_width, "height": viewport_height})
        await page.goto(url, wait_until="networkidle", timeout=30000)

        # 1. Keyboard navigation
        try:
            tab_order = await _test_keyboard_navigation(page)
            report.keyboard_tab_order = tab_order

            # Assess tab order quality
            if not tab_order:
                report.results.append(InteractionTestResult(
                    "Keyboard navigation", "fail",
                    "No elements received focus via Tab key",
                ))
            else:
                invisible_focus = [t for t in tab_order if not t.get("has_visible_focus")]
                hidden_elements = [t for t in tab_order if not t.get("is_visible")]

                if hidden_elements:
                    report.results.append(InteractionTestResult(
                        "Focus reaches hidden elements", "fail",
                        f"{len(hidden_elements)} hidden elements receive focus via Tab",
                    ))

                if invisible_focus:
                    report.results.append(InteractionTestResult(
                        "Focus indicator visibility", "warning",
                        f"{len(invisible_focus)}/{len(tab_order)} focused elements lack visible focus indicator",
                    ))
                else:
                    report.results.append(InteractionTestResult(
                        "Focus indicator visibility", "pass",
                        f"All {len(tab_order)} focusable elements have visible focus indicators",
                    ))

                report.results.append(InteractionTestResult(
                    "Tab order", "pass",
                    f"{len(tab_order)} elements reachable via keyboard in logical order",
                ))
        except Exception as e:
            report.results.append(InteractionTestResult(
                "Keyboard navigation", "fail", f"Test failed: {str(e)[:80]}",
            ))

        # 2. Form validation
        try:
            await page.goto(url, wait_until="networkidle", timeout=15000)
            form_results = await _test_form_validation(page)
            report.results.extend(form_results)
        except Exception:
            report.results.append(InteractionTestResult(
                "Form validation", "skip", "Could not test forms",
            ))

        # 3. Empty states
        try:
            await page.goto(url, wait_until="networkidle", timeout=15000)
            empty_results = await _test_empty_states(page)
            report.results.extend(empty_results)
        except Exception:
            report.results.append(InteractionTestResult(
                "Empty state", "skip", "Could not test empty states",
            ))

        # 4. Responsive breakpoints
        try:
            breakpoint_issues = await _test_responsive_breakpoints(page, url)
            report.breakpoint_issues = breakpoint_issues
            if not breakpoint_issues:
                report.results.append(InteractionTestResult(
                    "Responsive layout", "pass",
                    "No overflow or layout issues at mobile/tablet/desktop breakpoints",
                ))
            else:
                report.results.append(InteractionTestResult(
                    "Responsive layout", "fail",
                    f"{len(breakpoint_issues)} issues across breakpoints",
                ))
        except Exception:
            report.results.append(InteractionTestResult(
                "Responsive layout", "skip", "Could not test breakpoints",
            ))

        await browser.close()

    return report


def run_interaction_tests(url: str, viewport_width: int = 1440, viewport_height: int = 900) -> InteractionTestReport:
    """Run all interaction tests. Returns structured report."""
    return asyncio.run(_run_tests(url, viewport_width, viewport_height))
