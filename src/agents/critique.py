from src.agents.base import BaseAgent
from src.analysis.wcag_checker import run_wcag_check, run_wcag_check_multi
from src.input.models import DesignInput, InputType
from src.knowledge.retriever import retrieve

CRITIQUE_SYSTEM_PROMPT = """\
You are a senior UX/UI designer and accessibility specialist with 15+ years of experience \
across consumer and enterprise products. You deliver direct, specific, actionable design \
critique grounded in exact data. You do not hedge or equivocate.

You will receive:
1. **A screenshot** of the design for visual analysis
2. **Extracted DOM metrics** with exact computed CSS values - colors, font sizes, contrast \
ratios, touch target dimensions, spacing values, and layout data
3. **CSS custom properties** (design tokens) defined on :root - these tell you what design \
system the developer has already built. Reference these tokens by name (e.g. `var(--accent)`) \
and recommend extending the existing system rather than proposing a new one
4. **HTML structure audit** - semantic elements, landmarks, headings, ARIA attributes, \
form labels, skip links
5. **Non-text contrast audit** - UI component boundaries against adjacent backgrounds
6. **Focus style audit** - which interactive elements have custom focus styles

USE ALL OF THIS DATA. Every finding must reference exact values, CSS selectors, token names, \
or DOM attributes. Do not guess when data is provided.

## Your critique covers these categories:

1. **Visual Hierarchy** - Is the most important content visually dominant? Can a user identify \
the primary action within 3 seconds? What is the visual weight distribution?
2. **Typography** - Analyse the actual type scale from the DOM data. Reference specific sizes \
and the CSS tokens used (or missing). Flag arbitrary sizes that don't follow a modular scale. \
Propose a scale using existing token naming conventions.
3. **Colour & Contrast** - Use the extracted contrast ratios. For every failing pair, state \
the exact colors by their CSS token name where available (e.g. `var(--text-muted)` #8B8FA3), \
the computed ratio, and the WCAG requirement. Reference WCAG 2.2 AA standards.
4. **Spacing & Rhythm** - Analyse the extracted spacing values. Identify which values follow \
a system and which are arbitrary. Reference existing spacing tokens if defined.
5. **Layout & Composition** - Grid structure, screen real estate distribution, responsive \
readiness.
6. **Accessibility (WCAG 2.2)** - You will receive a **pre-computed WCAG audit report** with \
deterministic pass/fail results. DO NOT re-evaluate these criteria yourself. The programmatic \
checker is 100% accurate. Instead:
   - Include the WCAG report verbatim in your Accessibility Audit section
   - Add subjective commentary where relevant (e.g. "the focus ring colour may not be \
visible enough on this specific background")
   - Only flag accessibility issues NOT covered by the checker (e.g. cognitive load, \
content readability, error message quality, colour-only information)
7. **Interaction Patterns** - Affordances, state visibility, platform conventions.
8. **Consistency** - Reference the CSS tokens to identify where the design system is followed \
vs where values are hardcoded. Flag inconsistencies between tokens and actual usage.
9. **Information Architecture** - Content organisation, navigation, progressive disclosure.

## Output format:

### Summary
2-3 sentence overall assessment with severity: **Critical** / **Needs Work** / **Solid**. \
Be direct.

### Score
Rate the design out of 100 across these categories (include exact scores):

| Category | Score | Max |
|----------|-------|-----|
| Visual Hierarchy | /15 | 15 |
| Typography | /10 | 10 |
| Colour & Contrast | /15 | 15 |
| Spacing & Rhythm | /10 | 10 |
| Layout & Composition | /10 | 10 |
| Accessibility | /20 | 20 |
| Interaction States | /10 | 10 |
| Consistency | /5 | 5 |
| Information Architecture | /5 | 5 |
| **Total** | **/100** | **100** |

Be strict. A "perfectly fine" design scores 60-70. Scores above 80 indicate genuinely \
strong work. Scores below 40 indicate critical issues.

### Critical Issues
Severity-ranked issues. Each:
- **What**: Reference exact elements by CSS selector, token name, or DOM attribute
- **Why it matters**: Impact on users, citing WCAG criteria where applicable
- **Fix**: Concrete CSS or HTML fix, using existing token names where possible
- **Severity**: 0-4 (Nielsen scale)

### Improvements
Same format as Critical Issues.

### Interaction State Audit
You will receive state test results showing which elements have hover and focus states. \
For each element tested:
- Does it have a hover state? What changes? Is the change sufficient?
- Does it have a focus state? Is it visible on the dark background?
- Does the cursor change to pointer on hover for clickable elements?
Flag elements missing hover, focus, or cursor changes. Reference the test data exactly.

### Accessibility Audit
Dedicated section with sub-headings:
- **Semantic HTML**: Landmark elements found/missing, heading hierarchy issues
- **Contrast**: Table of all pairs with ratios, pass/fail, token names
- **Non-text Contrast**: UI component boundary analysis (WCAG 1.4.11)
- **Touch Targets**: Table of violations with selectors and exact dimensions
- **Focus Management**: Use the state test results to cite exactly which elements \
have/lack focus-visible styles and what their focus styles look like
- **Forms**: Inputs without programmatic labels
- **Keyboard Navigation**: Skip link, tab order concerns

### Strengths
Specific positives with exact values and token references.

### Design System Assessment
- List all CSS custom properties found, grouped by category
- Identify which tokens are used consistently vs inconsistently
- Flag hardcoded values that should use existing tokens (only values used 10+ times)
- Only propose new tokens for values that appear frequently enough to warrant it
- Do NOT recommend tokens for one-off or rare values

## Evaluation Frameworks

Ground your critique in these established frameworks:

**Nielsen's 10 Usability Heuristics** - Evaluate against: visibility of system status, match \
between system and real world, user control and freedom, consistency and standards, error \
prevention, recognition over recall, flexibility and efficiency, aesthetic and minimalist \
design, error recovery, and help/documentation. Reference by name when a violation is found.

**Severity Rating** - Rate each finding on the Nielsen 0-4 scale:
- 0: Not a problem
- 1: Cosmetic only
- 2: Minor usability problem
- 3: Major usability problem
- 4: Usability catastrophe
Map to priority: 4 = must fix before release, 3 = high priority, 2 = low priority, 1 = if time allows.

**Gestalt Principles** - Reference proximity, similarity, closure, continuity, figure-ground, \
and common region when evaluating visual grouping and hierarchy.

**Fitts's Law** - Time to reach a target is a function of distance and target size. Cite when \
evaluating touch targets, button placement, and interactive element sizing.

## Rules:
- **Reference CSS selectors** (e.g. `.exercise-item`, `.top-nav-tab`) not just "the list items"
- **Reference token names** (e.g. `var(--accent)` #4F46E5) not just hex values
- **Cite WCAG criteria by number** (e.g. WCAG 2.5.8 Target Size, WCAG 1.4.11 Non-text Contrast)
- **Cite heuristics by name** (e.g. "Violates Heuristic #4: Consistency and Standards")
- Every criticism must include a concrete fix with specific values
- Rate every finding with a severity (0-4)
- If analysing a screenshot, describe what you see before critiquing

## Critical Guardrails — Avoid These False Positive Patterns:
- **Do NOT confuse sparse content with empty states.** If a page shows 2 items, that is real \
data, not an empty state. Only flag actual empty states (zero items with no messaging).
- **Do NOT suggest new features.** "Add a recommended badge", "Add a Select button", "Show \
recent activity" are feature requests, not design critique. Only flag problems with what \
exists — not what could be added.
- **Do NOT recommend reducing intentional spacing or card sizes.** If elements have generous \
padding or height, assume it is intentional unless it breaks a specific principle.
- **Do NOT recommend new design tokens for values used fewer than 10 times.** Infrequent \
values are not worth tokenising. Only flag hardcoded values that appear frequently enough \
to warrant systematic treatment.
- **Do NOT flag sub-pixel font sizes** (e.g. 13.3333px, 15.5px) — these are browser \
rendering artifacts, not authored CSS values.
"""

CRITIQUE_TONE_VARIANTS = {
    "opinionated": "Be direct and confident. State what's wrong, not what 'might be considered'.",
    "balanced": "Be direct but diplomatic. Acknowledge trade-offs where they exist.",
    "gentle": "Be constructive and encouraging. Lead with strengths, then frame issues as opportunities.",
}


def _format_dom_data(dom_data: dict) -> str:
    """Format extracted DOM metrics into a comprehensive analysis section."""
    if not dom_data:
        return ""

    sections = ["## Extracted DOM Metrics\n"]

    # Layout
    layout = dom_data.get("layout", {})
    if layout:
        vw = layout.get("viewport_width", 0)
        vh = layout.get("viewport_height", 0)
        is_desktop = vw >= 1024
        viewport_kind = "DESKTOP" if is_desktop else "MOBILE/TABLET"
        sections.append("### Page Layout")
        sections.append(
            f"- Viewport: {vw}x{vh}px ({viewport_kind})"
        )
        if is_desktop:
            sections.append(
                "- **Viewport guidance:** this is a desktop viewport. Touch-target "
                "findings (WCAG 2.5.8, sub-24px/44px) apply less stringently because "
                "mouse/trackpad users have sub-pixel precision. Flag touch-target "
                "issues only if they'd also hurt mouse users (e.g. <8x8px targets), "
                "not as critical accessibility failures on a desktop-only run."
            )
        sections.append(f"- Base font: {layout.get('body_font_size', '?')} / {layout.get('body_line_height', '?')}")
        sections.append(f"- Font family: {layout.get('body_font_family', '?')}")
        sections.append(f"- Body background: `{layout.get('body_bg', '?')}`")
        sections.append("")

    # CSS Custom Properties (Design Tokens)
    tokens = dom_data.get("css_tokens", {})
    has_tokens = any(tokens.get(cat) for cat in tokens)
    if has_tokens:
        sections.append("### CSS Custom Properties (Design Tokens on :root)")
        for category in ["color", "spacing", "radius", "font", "other"]:
            entries = tokens.get(category, [])
            if entries:
                sections.append(f"\n**{category.title()} tokens:**")
                for t in entries:
                    sections.append(f"- `{t['name']}`: `{t['value']}`")
        sections.append("")

    # HTML Structure Audit
    html = dom_data.get("html_structure", {})
    if html:
        sections.append("### HTML Structure Audit")
        sections.append(f"- `<html lang>`: {'`' + html['lang_value'] + '`' if html.get('lang_value') else '**MISSING**'}")
        sections.append(f"- `<title>`: {html.get('title') or '**MISSING**'}")
        sections.append(f"- Skip link: {'Yes' if html.get('skip_link') else '**MISSING**'}")
        sections.append("")

        landmarks = html.get("landmarks", {})
        sections.append("**Landmarks:**")
        for tag, count in landmarks.items():
            status = f"{count} found" if count > 0 else "**MISSING**"
            sections.append(f"- `<{tag}>`: {status}")
        sections.append("")

        headings = html.get("headings", [])
        if headings:
            sections.append("**Heading hierarchy:**")
            for h in headings:
                sections.append(f"- `<h{h['level']}>`: \"{h['text']}\"")
        else:
            sections.append("**Heading hierarchy:** **No headings found**")
        sections.append("")

        # Form labels
        unlabelled_inputs = html.get("forms", {}).get("inputs_without_labels", [])
        unlabelled_selects = html.get("forms", {}).get("selects_without_labels", [])
        if unlabelled_inputs or unlabelled_selects:
            sections.append("**Form elements without programmatic labels:**")
            for inp in unlabelled_inputs:
                sections.append(
                    f"- `{inp['selector']}` type={inp['type']}"
                    f"{' placeholder=\"' + inp['placeholder'] + '\"' if inp.get('placeholder') else ''}"
                    f" - **no label, aria-label, or aria-labelledby**"
                )
            for sel in unlabelled_selects:
                sections.append(
                    f"- `{sel['selector']}` (first option: \"{sel.get('first_option', '?')}\")"
                    f" - **no label or aria-label**"
                )
            sections.append("")

        # ARIA
        aria = html.get("aria_usage", {})
        sections.append("**ARIA usage:**")
        sections.append(f"- Roles: {', '.join(aria.get('roles', [])) or 'none'}")
        sections.append(f"- aria-label: {aria.get('labels', 0)} elements")
        sections.append(f"- aria-describedby: {aria.get('described_by', 0)} elements")
        sections.append(f"- aria-live regions: {aria.get('live_regions', 0)}")
        sections.append("")

    # Colors
    colors = dom_data.get("colors", {})
    if colors.get("text"):
        sections.append("### Color Palette (by frequency)")
        sections.append("**Text colors:**")
        for c in colors["text"]:
            sections.append(f"- `{c['color']}` ({c['count']} elements)")
        sections.append("")
    if colors.get("background"):
        sections.append("**Background colors:**")
        for c in colors["background"]:
            sections.append(f"- `{c['color']}` ({c['count']} elements)")
        sections.append("")

    # Fonts
    fonts = dom_data.get("fonts", {})
    if fonts.get("sizes"):
        sections.append("### Typography")
        sections.append("**Font sizes in use:**")
        for f in fonts["sizes"]:
            sections.append(f"- `{f['size']}` ({f['count']} elements)")
        sections.append("")
    if fonts.get("families"):
        sections.append("**Font families:**")
        for f in fonts["families"]:
            sections.append(f"- {f['family']} ({f['count']} elements)")
        sections.append("")

    # Spacing
    spacing = dom_data.get("spacing_values", [])
    if spacing:
        sections.append("### Spacing Values (padding, margin, gap)")
        for s in spacing:
            sections.append(f"- `{s['value']}` ({s['count']} uses)")
        sections.append("")

    # Contrast pairs
    contrast = dom_data.get("contrast_pairs", [])
    if contrast:
        failures = [c for c in contrast if not c.get("passes_aa")]
        passes = [c for c in contrast if c.get("passes_aa")]

        sections.append("### Contrast Analysis (Text)")
        if failures:
            sections.append(f"**FAILURES ({len(failures)}):**")
            for c in failures:
                sections.append(
                    f"- `{c['text_color']}` on `{c['bg_color']}` = **{c['ratio']}:1** "
                    f"(requires {c['required']}:1) - {c['font_size']} {c['font_weight']}wt "
                    f"- \"{c['sample_text']}\" [{c['element']}]"
                )
            sections.append("")
        sections.append(f"**Passing ({len(passes)}):**")
        for c in passes:
            sections.append(
                f"- `{c['text_color']}` on `{c['bg_color']}` = {c['ratio']}:1 "
                f"(requires {c['required']}:1) - {c['font_size']} [{c['element']}]"
            )
        sections.append("")

    # Non-text contrast
    ntc = dom_data.get("non_text_contrast", [])
    if ntc:
        failures = [n for n in ntc if not n.get("passes_3_to_1")]
        sections.append("### Non-text Contrast (WCAG 1.4.11 - UI Components)")
        if failures:
            sections.append(f"**FAILURES ({len(failures)}):**")
            for n in failures:
                sections.append(
                    f"- `{n['element']}` \"{n.get('text', '')}\" - "
                    f"component bg `{n['component_bg']}` vs adjacent `{n['adjacent_bg']}` = "
                    f"**{n['bg_ratio']}:1** (requires 3:1)"
                    f"{' - has border `' + str(n['border_color']) + '` at ' + str(n['border_ratio']) + ':1' if n.get('has_border') else ' - no border'}"
                )
        else:
            sections.append("All UI components pass 3:1 non-text contrast.")
        sections.append("")

    # Interactive elements & touch targets
    interactive = dom_data.get("interactive_elements", [])
    if interactive:
        violations = [e for e in interactive if not e.get("meets_touch_target")]
        sections.append("### Interactive Elements & Touch Targets")
        if violations:
            sections.append(f"**Touch target violations ({len(violations)}):**")
            for e in violations:
                label_status = ""
                if not e.get("has_visible_label") and not e.get("has_aria_label"):
                    label_status = " - **NO LABEL**"
                elif e.get("has_aria_label"):
                    label_status = " (aria-label)"
                sections.append(
                    f"- `{e['element']}` \"{e['text']}\" - {e['width']}x{e['height']}px "
                    f"(minimum 44x44px){label_status}"
                )
        passing = [e for e in interactive if e.get("meets_touch_target")]
        if passing:
            sections.append(f"\n**Passing ({len(passing)}):**")
            for e in passing[:10]:
                sections.append(
                    f"- `{e['element']}` \"{e['text']}\" - {e['width']}x{e['height']}px"
                )
        sections.append("")

    # Focus-visible rule detection (from stylesheet scanning)
    html = dom_data.get("html_structure", {})
    has_global_fv = html.get("has_global_focus_visible", False)
    fv_rules = html.get("focus_visible_rules", [])
    if has_global_fv or fv_rules:
        sections.append("### Focus-Visible Rules Detected")
        if has_global_fv:
            sections.append("**Global :focus-visible rules found in stylesheets.**")
        if fv_rules:
            for rule in fv_rules[:5]:
                sections.append(f"- `{rule['selector']}`")
        sections.append("")
    else:
        sections.append("### Focus-Visible Rules")
        sections.append("**No :focus-visible or :focus rules detected in stylesheets.**")
        sections.append("")

    # Interactive state tests (hover/focus actual results)
    state_tests = dom_data.get("state_tests", [])
    if state_tests:
        sections.append("### Interactive State Test Results (Hover + Focus)")
        sections.append("Elements were hovered and focused via Playwright. Results:\n")

        for st in state_tests:
            selector = st["selector"]
            text = st["text"]
            has_hover = st.get("has_hover_state", False)
            has_focus = st.get("has_focus_state", False)
            cursor = st.get("cursor_on_hover", "auto")

            status_parts = []
            if has_hover:
                changes = st.get("hover_changes", {})
                change_desc = ", ".join(
                    f"{k}: {v['from']} -> {v['to']}" for k, v in changes.items()
                ) or "visual change detected"
                status_parts.append(f"Hover: YES ({change_desc})")
            else:
                status_parts.append("Hover: **NONE**")

            if has_focus:
                changes = st.get("focus_changes", {})
                change_desc = ", ".join(
                    f"{k}: {v['from']} -> {v['to']}" for k, v in changes.items()
                ) or "visual change detected"
                status_parts.append(f"Focus: YES ({change_desc})")
            else:
                status_parts.append("Focus: **NONE**")

            cursor_ok = cursor == "pointer" if st.get("text") else True
            if cursor != "pointer" and st["selector"].startswith("button"):
                status_parts.append(f"Cursor: `{cursor}` (should be `pointer`)")

            sections.append(f"- `{selector}` \"{text}\" - {' | '.join(status_parts)}")

        # Summary
        no_hover = [s for s in state_tests if not s.get("has_hover_state")]
        no_focus_st = [s for s in state_tests if not s.get("has_focus_state")]
        sections.append(f"\n**Summary:** {len(no_hover)}/{len(state_tests)} elements missing hover, "
                        f"{len(no_focus_st)}/{len(state_tests)} missing focus")
        sections.append("")

    return "\n".join(sections)


def _format_multi_page_data(pages) -> str:
    """Format DOM data from multiple pages, highlighting per-page differences."""
    if not pages or len(pages) <= 1:
        return ""

    sections = [f"## Multi-Page Analysis ({len(pages)} pages crawled)\n"]
    sections.append("### Pages Captured")
    for i, p in enumerate(pages):
        sections.append(f"{i + 1}. **{p.label}** - `{p.url}`")
    sections.append("")

    # Merge and deduplicate findings across pages, noting which page each came from
    all_contrast_failures = []
    all_touch_violations = []
    all_focus_issues = []
    all_ntc_failures = []
    all_unlabelled = []
    all_font_sizes = {}
    all_spacing = {}
    page_specific_issues = []

    for p in pages:
        dom = p.dom_data
        if not dom:
            continue

        label = p.label

        # Contrast
        for c in dom.get("contrast_pairs", []):
            if not c.get("passes_aa"):
                c["page"] = label
                all_contrast_failures.append(c)

        # Touch targets
        for e in dom.get("interactive_elements", []):
            if not e.get("meets_touch_target"):
                e["page"] = label
                all_touch_violations.append(e)

        # Non-text contrast
        for n in dom.get("non_text_contrast", []):
            if not n.get("passes_3_to_1"):
                n["page"] = label
                all_ntc_failures.append(n)

        # Unlabelled form elements
        html = dom.get("html_structure", {})
        for inp in html.get("forms", {}).get("inputs_without_labels", []):
            inp["page"] = label
            all_unlabelled.append(inp)
        for sel in html.get("forms", {}).get("selects_without_labels", []):
            sel["page"] = label
            all_unlabelled.append(sel)

        # Font sizes (aggregate)
        for f in dom.get("fonts", {}).get("sizes", []):
            all_font_sizes[f["size"]] = all_font_sizes.get(f["size"], 0) + f["count"]

        # Spacing (aggregate)
        for s in dom.get("spacing_values", []):
            all_spacing[s["value"]] = all_spacing.get(s["value"], 0) + s["count"]

        # Page-specific HTML issues
        landmarks = html.get("landmarks", {})
        missing_landmarks = [k for k, v in landmarks.items() if v == 0]
        if missing_landmarks:
            page_specific_issues.append(
                f"- **{label}**: Missing landmarks: {', '.join('`<' + l + '>`' for l in missing_landmarks)}"
            )

        headings = html.get("headings", [])
        if not headings:
            page_specific_issues.append(f"- **{label}**: No heading elements found")

        if not html.get("has_lang"):
            page_specific_issues.append(f"- **{label}**: Missing `lang` attribute on `<html>`")

        if not html.get("skip_link"):
            page_specific_issues.append(f"- **{label}**: No skip navigation link")

    # Cross-page summary sections
    if all_font_sizes:
        sections.append("### Typography Across All Pages")
        sorted_sizes = sorted(all_font_sizes.items(), key=lambda x: x[1], reverse=True)
        for size, count in sorted_sizes[:12]:
            sections.append(f"- `{size}` ({count} elements)")
        sections.append("")

    if all_spacing:
        sections.append("### Spacing Across All Pages")
        sorted_spacing = sorted(all_spacing.items(), key=lambda x: x[1], reverse=True)
        for val, count in sorted_spacing[:15]:
            sections.append(f"- `{val}` ({count} uses)")
        sections.append("")

    if all_contrast_failures:
        seen = set()
        sections.append(f"### Contrast Failures Across All Pages ({len(all_contrast_failures)} total)")
        for c in all_contrast_failures:
            key = f"{c['text_color']}|{c['bg_color']}"
            if key in seen:
                continue
            seen.add(key)
            sections.append(
                f"- `{c['text_color']}` on `{c['bg_color']}` = **{c['ratio']}:1** "
                f"(requires {c['required']}:1) - [{c['element']}] (found on: {c['page']})"
            )
        sections.append("")

    if all_ntc_failures:
        seen = set()
        sections.append(f"### Non-text Contrast Failures ({len(all_ntc_failures)} total)")
        for n in all_ntc_failures:
            key = f"{n['component_bg']}|{n['adjacent_bg']}"
            if key in seen:
                continue
            seen.add(key)
            sections.append(
                f"- `{n['element']}` - `{n['component_bg']}` vs `{n['adjacent_bg']}` = "
                f"**{n['bg_ratio']}:1** (found on: {n['page']})"
            )
        sections.append("")

    if all_touch_violations:
        seen = set()
        sections.append(f"### Touch Target Violations ({len(all_touch_violations)} total)")
        for e in all_touch_violations:
            key = f"{e['element']}|{e['width']}x{e['height']}"
            if key in seen:
                continue
            seen.add(key)
            sections.append(
                f"- `{e['element']}` \"{e['text']}\" - {e['width']}x{e['height']}px (found on: {e['page']})"
            )
        sections.append("")


    if all_unlabelled:
        sections.append(f"### Unlabelled Form Elements ({len(all_unlabelled)} across all pages)")
        for item in all_unlabelled:
            selector = item.get("selector", "unknown")
            sections.append(f"- `{selector}` on **{item['page']}**")
        sections.append("")

    if page_specific_issues:
        seen = set()
        unique_issues = []
        for issue in page_specific_issues:
            if issue not in seen:
                seen.add(issue)
                unique_issues.append(issue)
        sections.append("### Per-Page HTML Structure Issues")
        sections.extend(unique_issues)
        sections.append("")

    return "\n".join(sections)


SCREENSHOT_ONLY_PROMPT = """\
You are a senior UX/UI designer with 15+ years of experience. You are reviewing \
a design from a SCREENSHOT ONLY. You have NO access to the underlying HTML, CSS, \
or DOM structure.

## CRITICAL CONSTRAINT: You can ONLY evaluate what is VISUALLY VERIFIABLE.

You MUST NOT make claims about:
- Semantic HTML (landmarks, headings, ARIA attributes) — you cannot see the code
- Programmatic labels or aria-label attributes — you cannot see them
- Skip links — you cannot know if one exists unless it's visually shown
- lang attributes — invisible in a screenshot
- Focus or hover states — you cannot interact with the page
- CSS custom properties or design tokens — you cannot see the stylesheets
- Touch target exact pixel measurements — you can only estimate from visual size
- Screen reader experience — you cannot test this from an image
- WCAG compliance for anything requiring code inspection

You CAN evaluate:
1. **Visual hierarchy** — What draws the eye first? Is the primary action clear?
2. **Typography** — Is the type scale visually consistent? Are headings clearly \
differentiated from body text? Is text readable at the apparent size?
3. **Colour and contrast** — Do text/background combinations appear to have \
sufficient contrast? Note: you are estimating, not measuring. Say "appears to \
have low contrast" not "fails WCAG 1.4.3 at 2.85:1".
4. **Spacing and rhythm** — Is whitespace used consistently? Are related elements \
grouped? Is there a visible spacing system?
5. **Layout and composition** — Is the layout balanced? Does the eye flow logically?
6. **Information architecture** — Is navigation logical? Are labels clear? Can \
users find what they need?
7. **Interaction affordances** — Do clickable elements look clickable? Are buttons \
visually distinct from text? Do dropdown indicators exist where expected?
8. **Consistency** — Are similar elements styled the same way? Are there visual \
contradictions?
9. **Content and copy** — Are labels descriptive? Is the language clear?

## Output format:

### Summary
2-3 sentence visual assessment. State the assumed viewport (desktop/tablet/mobile) \
and note that this is a screenshot-only review without code access.

### Score
Rate out of 100 across visual categories only. Apply standards appropriate to \
the detected viewport — do NOT penalise desktop designs for mobile standards \
or vice versa:
| Category | Score | Max |
| Visual Hierarchy | /15 | 15 |
| Typography | /10 | 10 |
| Colour & Contrast (visual estimate) | /15 | 15 |
| Spacing & Rhythm | /10 | 10 |
| Layout & Composition | /10 | 10 |
| Interaction Affordances | /10 | 10 |
| Consistency | /10 | 10 |
| Information Architecture | /10 | 10 |
| Content & Copy | /10 | 10 |
| **Total** | **/100** | **100** |

### Visual Issues
Each issue must be something you can SEE in the screenshot:
- **What**: Describe what you observe
- **Why it matters**: Impact on the user experience
- **Fix**: Visual recommendation

### Visual Strengths
Specific positives you can observe.

## Rules:
- Every finding must reference something VISIBLE in the screenshot
- Do NOT fabricate findings about code, accessibility, or interaction states
- Say "appears to" or "visually suggests" when estimating, not asserting
- If you cannot verify something from the image, do not mention it
"""


PRAGMATIC_MODE_INSTRUCTION = """\

## Pragmatic mode
This run is in PRAGMATIC mode. Output focused, high-signal findings only:
- List at most 3–5 findings per section. Rank by Nielsen severity (0–4).
- Only report findings with severity ≥ 2 (serious usability problem or worse).
- Skip AAA criteria and aspirational polish — they're not the top priority.
- Skip minor spacing nits, micro-typography opinions, and "consider" findings.
- If a section has no severity ≥ 2 findings, write one line: "No serious issues."
- Each finding must name a concrete, implementable fix, not a general principle.
"""


class CritiqueAgent(BaseAgent):
    def __init__(self, tone: str = "opinionated", pragmatic: bool = False):
        self.tone = tone
        self.pragmatic = pragmatic
        self._screenshot_only = False

    def system_prompt(self) -> str:
        tone_instruction = CRITIQUE_TONE_VARIANTS.get(self.tone, CRITIQUE_TONE_VARIANTS["opinionated"])
        base = SCREENSHOT_ONLY_PROMPT if self._screenshot_only else CRITIQUE_SYSTEM_PROMPT
        pragmatic_suffix = PRAGMATIC_MODE_INSTRUCTION if self.pragmatic else ""
        return f"{base}\n\nTone: {tone_instruction}{pragmatic_suffix}"

    def get_image_paths(self, design_input: DesignInput) -> list[str]:
        """Return screenshots from all crawled pages."""
        if design_input.pages and len(design_input.pages) > 1:
            return [p.image_path for p in design_input.pages if p.image_path]
        if design_input.image_path:
            return [design_input.image_path]
        return []

    def _detect_context_tags(self, design_input: DesignInput) -> list[str]:
        """Analyse DOM data to select relevant knowledge tags."""
        tags = set()

        # Always include core frameworks
        tags.update(["heuristics", "usability", "severity", "nielsen",
                      "wcag", "accessibility", "contrast", "touch-targets",
                      "gestalt", "visual-hierarchy", "critique"])

        dom = design_input.dom_data
        if not dom:
            return list(tags)

        # Dark theme detection
        layout = dom.get("layout", {})
        body_bg = layout.get("body_bg", "")
        if body_bg and body_bg.startswith("#"):
            # Check if background is dark (low luminance)
            try:
                r, g, b = int(body_bg[1:3], 16), int(body_bg[3:5], 16), int(body_bg[5:7], 16)
                luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
                if luminance < 0.3:
                    tags.update(["dark-mode", "colour"])
            except (ValueError, IndexError):
                pass

        # Form detection
        html = dom.get("html_structure", {})
        has_forms = (
            html.get("forms", {}).get("inputs_without_labels", [])
            or html.get("forms", {}).get("selects_without_labels", [])
        )
        if has_forms:
            tags.update(["forms", "input", "validation", "aria", "semantics"])

        # Check if there are many font sizes (typography issues)
        fonts = dom.get("fonts", {}).get("sizes", [])
        if len(fonts) > 5:
            tags.update(["type-scale", "typography", "readability", "hierarchy", "modular-scale"])

        # Check for spacing issues
        spacing = dom.get("spacing_values", [])
        if len(spacing) > 10:
            tags.update(["spacing", "whitespace", "density", "grid"])

        # Check for interactive elements (interaction patterns)
        interactive = dom.get("interactive_elements", [])
        if interactive:
            tags.update(["interaction", "states", "components", "microinteractions",
                          "navigation", "patterns"])

        # Check for CSS tokens
        tokens = dom.get("css_tokens", {})
        has_tokens = any(tokens.get(cat) for cat in tokens)
        if has_tokens:
            tags.update(["design-system", "design-tokens", "css-variables", "naming"])
        else:
            tags.update(["design-system", "design-tokens", "atomic-design"])

        # Check for non-text contrast failures
        ntc = dom.get("non_text_contrast", [])
        ntc_failures = [n for n in ntc if not n.get("passes_3_to_1")]
        if ntc_failures:
            tags.update(["colour", "perception"])

        # Check for semantic HTML issues
        landmarks = html.get("landmarks", {})
        missing_landmarks = [k for k, v in landmarks.items() if v == 0]
        if missing_landmarks:
            tags.update(["semantics", "screen-reader", "aria", "annotation"])

        # Mobile/responsive
        viewport_width = layout.get("viewport_width", 1440)
        if viewport_width and viewport_width < 768:
            tags.update(["mobile", "thumb-zone", "responsive", "platform", "ergonomics"])

        # State test results
        state_tests = dom.get("state_tests", [])
        if state_tests:
            no_hover = [s for s in state_tests if not s.get("has_hover_state")]
            no_focus = [s for s in state_tests if not s.get("has_focus_state")]
            if no_hover or no_focus:
                tags.update(["states", "feedback", "interaction"])

        return list(tags)

    def retrieve_knowledge(self, design_input: DesignInput) -> str:
        """Retrieve knowledge based on what's actually in the design."""
        tags = self._detect_context_tags(design_input)
        return retrieve(tags=tags, max_tokens=8000)

    def build_user_prompt(self, design_input: DesignInput, context: str = "") -> str:
        parts = []

        if context:
            parts.append(f"## Context\n{context}")

        # Detect screenshot-only mode (no DOM data available)
        has_dom_data = bool(design_input.dom_data and design_input.dom_data.get("layout"))
        self._screenshot_only = (design_input.type == InputType.SCREENSHOT) or not has_dom_data

        if self._screenshot_only:
            # Detect viewport from image dimensions
            viewport_type = "desktop"
            viewport_note = ""
            if design_input.image_path:
                try:
                    from PIL import Image
                    img = Image.open(design_input.image_path)
                    w, h = img.size
                    if w < 500:
                        viewport_type = "mobile"
                    elif w < 850:
                        viewport_type = "tablet"
                    else:
                        viewport_type = "desktop"
                    viewport_note = f"Image dimensions: {w}x{h}px"
                except Exception:
                    pass

            viewport_instructions = {
                "mobile": (
                    "This is a MOBILE screenshot. Evaluate against mobile design patterns only: "
                    "thumb zone placement, bottom navigation, touch targets (44pt minimum), "
                    "single-column layout, mobile typography (16px minimum body text). "
                    "Do NOT critique desktop-specific patterns (sidebar layouts, hover states, "
                    "multi-column grids, desktop navigation bars)."
                ),
                "tablet": (
                    "This is a TABLET screenshot. Evaluate for tablet patterns: "
                    "touch-friendly targets, adaptive layout, readable typography. "
                    "Do NOT apply mobile-only patterns (bottom nav) or desktop-only patterns "
                    "(dense multi-column layouts, small click targets)."
                ),
                "desktop": (
                    "This is a DESKTOP screenshot. Evaluate against desktop design patterns only: "
                    "navigation bars, hover affordances, information density, multi-column layouts, "
                    "readable line lengths (45-75 chars). "
                    "Do NOT critique mobile-specific patterns (touch targets below 44px are acceptable "
                    "for mouse/trackpad interaction at 24px+, bottom navigation, thumb zones)."
                ),
            }

            # Screenshot-only mode — no DOM data, no WCAG checker, visual analysis only
            parts.append(
                f"## Analysis Mode: SCREENSHOT ONLY\n\n"
                f"**Assumed viewport: {viewport_type.upper()}** ({viewport_note})\n\n"
                f"No DOM extraction or code access is available. "
                f"Evaluate ONLY what is visually verifiable in the attached image. "
                f"Do NOT make claims about HTML structure, ARIA attributes, focus states, "
                f"or any code-level properties.\n\n"
                f"{viewport_instructions[viewport_type]}"
            )

            if design_input.type == InputType.SCREENSHOT:
                parts.append("Critique the design shown in the attached screenshot.")
            elif design_input.type == InputType.TEXT:
                parts.append(f"Critique the following design:\n\n{design_input.page_text}")

            if design_input.image_path:
                parts.append("The screenshot is attached for visual analysis.")

            return "\n\n".join(parts)

        # Full mode — DOM data available
        # Pre-computed WCAG audit (deterministic, 100% accurate)
        if design_input.pages and len(design_input.pages) > 1:
            wcag_report = run_wcag_check_multi(design_input.pages)
        else:
            wcag_report = run_wcag_check(design_input.dom_data)

        wcag_md = wcag_report.to_markdown()
        parts.append(
            "## Pre-Computed WCAG Audit (Deterministic - DO NOT re-evaluate)\n\n"
            "The following results are computed programmatically and are 100% accurate. "
            "Include them verbatim in your Accessibility Audit section. Do not contradict "
            "or re-interpret these results.\n\n"
            + wcag_md
        )

        # Multi-page data (if crawled)
        if design_input.pages and len(design_input.pages) > 1:
            # Primary page DOM metrics
            dom_section = _format_dom_data(design_input.dom_data)
            if dom_section:
                parts.append("## Primary Page (Home) DOM Metrics\n" + dom_section)

            # Cross-page analysis
            multi_section = _format_multi_page_data(design_input.pages)
            if multi_section:
                parts.append(multi_section)

            # Page image mapping
            page_labels = [p.label for p in design_input.pages if p.image_path]
            parts.append(
                f"## Screenshots\n"
                f"{len(page_labels)} page screenshots are attached in order: "
                f"{', '.join(page_labels)}. "
                f"Visually analyse each screenshot for issues not captured in DOM data "
                f"(visual hierarchy, layout balance, whitespace, typography rhythm, "
                f"empty states, loading states)."
            )

            parts.append(
                f"Critique this application across all {len(design_input.pages)} pages. "
                f"DOM data and state test results have been extracted from all pages. "
                f"Identify issues that are consistent across pages vs page-specific issues. "
                f"Reference which page(s) each finding applies to."
            )
        else:
            # Single page
            dom_section = _format_dom_data(design_input.dom_data)
            if dom_section:
                parts.append(dom_section)

        if design_input.type == InputType.SCREENSHOT:
            parts.append("Critique the design shown in the attached screenshot.")
        elif design_input.type == InputType.URL:
            parts.append(f"Critique the design of this page: {design_input.url}")
            if design_input.page_text:
                parts.append(f"## Extracted page text\n```\n{design_input.page_text[:2000]}\n```")
        elif design_input.type == InputType.TEXT:
            parts.append(f"Critique the following design based on this description:\n\n{design_input.page_text}")

        if design_input.image_path and not (design_input.pages and len(design_input.pages) > 1):
            parts.append("The screenshot is attached for visual analysis.")

        return "\n\n".join(parts)
