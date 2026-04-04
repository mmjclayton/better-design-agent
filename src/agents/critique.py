from src.agents.base import BaseAgent
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
6. **Accessibility (WCAG 2.2)** - This is a major section. Use ALL of the HTML structure data:
   - Semantic HTML: landmarks (`<main>`, `<nav>`, `<aside>`, `<header>`), heading hierarchy
   - `lang` attribute on `<html>`
   - Skip navigation link presence
   - Form inputs without programmatic labels (cite each one with its selector)
   - ARIA usage (roles, labels, live regions)
   - Touch targets below 44x44px (cite each with exact dimensions and selector)
   - Non-text contrast failures (UI component boundaries, WCAG 1.4.11)
   - Focus styles (cite which elements lack custom focus-visible styles)
   - Reference specific WCAG success criteria by number (e.g. WCAG 2.4.7 Focus Visible)
7. **Interaction Patterns** - Affordances, state visibility, platform conventions.
8. **Consistency** - Reference the CSS tokens to identify where the design system is followed \
vs where values are hardcoded. Flag inconsistencies between tokens and actual usage.
9. **Information Architecture** - Content organisation, navigation, progressive disclosure.

## Output format:

### Summary
2-3 sentence overall assessment with severity: **Critical** / **Needs Work** / **Solid**. \
Be direct.

### Critical Issues
Severity-ranked issues. Each:
- **What**: Reference exact elements by CSS selector, token name, or DOM attribute
- **Why it matters**: Impact on users, citing WCAG criteria where applicable
- **Fix**: Concrete CSS or HTML fix, using existing token names where possible
- **Severity**: High / Medium

### Improvements
Same format as Critical Issues.

### Accessibility Audit
Dedicated section with sub-headings:
- **Semantic HTML**: Landmark elements found/missing, heading hierarchy issues
- **Contrast**: Table of all pairs with ratios, pass/fail, token names
- **Non-text Contrast**: UI component boundary analysis (WCAG 1.4.11)
- **Touch Targets**: Table of violations with selectors and exact dimensions
- **Focus Management**: Which elements have/lack focus-visible styles
- **Forms**: Inputs without programmatic labels
- **Keyboard Navigation**: Skip link, tab order concerns

### Strengths
Specific positives with exact values and token references.

### Design System Assessment
- List all CSS custom properties found, grouped by category
- Identify which tokens are used consistently vs inconsistently
- Flag hardcoded values that should use existing tokens
- Propose new tokens to fill gaps, using the existing naming convention
- Recommend a type scale, spacing scale, and radius scale as token tables

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
        sections.append("### Page Layout")
        sections.append(f"- Viewport: {layout.get('viewport_width', '?')}x{layout.get('viewport_height', '?')}px")
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

    # Focus audit
    focus = dom_data.get("focus_audit", [])
    if focus:
        no_focus = [f for f in focus if not f.get("has_outline") and not f.get("has_box_shadow")]
        has_focus = [f for f in focus if f.get("has_outline") or f.get("has_box_shadow")]
        sections.append("### Focus Style Audit")
        if no_focus:
            sections.append(f"**Elements without custom focus styles ({len(no_focus)}):**")
            for f in no_focus[:15]:
                sections.append(f"- `{f['element']}` \"{f['text']}\"")
        if has_focus:
            sections.append(f"\n**Elements with focus styles ({len(has_focus)}):**")
            for f in has_focus[:10]:
                sections.append(
                    f"- `{f['element']}` \"{f['text']}\" - "
                    f"outline: {f['outline_style']}"
                )
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

        # Focus
        for f in dom.get("focus_audit", []):
            if not f.get("has_outline") and not f.get("has_box_shadow"):
                f["page"] = label
                all_focus_issues.append(f)

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

    if all_focus_issues:
        sections.append(f"### Elements Without Focus Styles ({len(all_focus_issues)} across all pages)")
        seen = set()
        for f in all_focus_issues:
            key = f['element']
            if key in seen:
                continue
            seen.add(key)
            sections.append(f"- `{f['element']}` \"{f['text']}\" (found on: {f['page']})")
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


class CritiqueAgent(BaseAgent):
    def __init__(self, tone: str = "opinionated"):
        self.tone = tone

    def system_prompt(self) -> str:
        tone_instruction = CRITIQUE_TONE_VARIANTS.get(self.tone, CRITIQUE_TONE_VARIANTS["opinionated"])
        return f"{CRITIQUE_SYSTEM_PROMPT}\n\nTone: {tone_instruction}"

    def retrieve_knowledge(self, design_input: DesignInput) -> str:
        """Retrieve all knowledge across critique-relevant categories."""
        all_tags = [
            # Accessibility
            "contrast", "wcag", "accessibility", "colour", "aria",
            "touch-targets", "inclusive-design", "cognitive", "coga",
            "annotation", "documentation", "handoff", "semantics",
            "screen-reader", "vestibular",
            # Typography & Layout
            "type-scale", "typography", "readability", "hierarchy",
            "spacing", "layout", "consistency", "grid",
            "gestalt", "visual-hierarchy", "whitespace", "density",
            "reading-patterns", "eye-tracking",
            # Heuristics & Methodology
            "heuristics", "usability", "evaluation", "severity",
            "nielsen", "shneiderman", "critique", "methodology",
            "review", "feedback",
            # Interaction & Patterns
            "forms", "interaction", "navigation", "microinteractions",
            "information-architecture", "input", "validation",
            "states", "patterns", "components",
            # Design Systems & References
            "design-system", "design-tokens", "css-variables",
            "atomic-design", "naming", "figma", "reference", "templates",
            # Colour & Visual
            "dark-mode", "psychology", "data-visualisation",
            "perception", "colorbrewer",
            # Motion
            "motion", "animation", "reduced-motion", "transitions",
            # Mobile & Platform
            "mobile", "thumb-zone", "responsive", "platform",
            "platform-conventions", "ios", "android", "ergonomics",
            "breakpoints", "viewport", "touch",
        ]
        return retrieve(tags=all_tags, max_tokens=8000)

    def build_user_prompt(self, design_input: DesignInput, context: str = "") -> str:
        parts = []

        if context:
            parts.append(f"## Context\n{context}")

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

            parts.append(
                f"Critique this application across all {len(design_input.pages)} pages. "
                f"The screenshot shows the primary page. DOM data has been extracted from all pages. "
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

        if design_input.image_path:
            parts.append("The screenshot is attached for visual analysis.")

        return "\n\n".join(parts)
