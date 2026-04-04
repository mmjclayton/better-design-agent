"""
Accessibility Agent — focused on ARIA semantics, keyboard navigation,
screen reader experience, and component intent analysis.

Receives: WCAG checker report + DOM structure + screenshots
Focus: What the WCAG checker CAN'T catch — semantic meaning, component
intent, ARIA patterns, focus management logic, screen reader experience.
"""

from src.agents.base import BaseAgent
from src.analysis.wcag_checker import run_wcag_check, run_wcag_check_multi
from src.input.models import DesignInput
from src.knowledge.retriever import retrieve


SYSTEM_PROMPT = """\
You are a WCAG 2.2 accessibility specialist. You evaluate web interfaces for \
screen reader compatibility, keyboard operability, and assistive technology support.

You will receive:
1. A **pre-computed WCAG audit** with deterministic pass/fail results (100% accurate)
2. **HTML structure data** including landmarks, headings, ARIA attributes, form labels
3. **Screenshots** for visual context

Your job is to find accessibility issues the automated checker CANNOT detect:

## What to evaluate (the checker already handles contrast, touch targets, landmarks, labels):

1. **Component intent vs semantics** — Is a checkbox being used where a toggle button \
(`button[aria-expanded]`) would be correct? Is a div acting as a button? Is a list of \
links acting as tabs without `role="tablist"`?

2. **ARIA patterns** — Do custom widgets follow WAI-ARIA Authoring Practices? Are \
`aria-expanded`, `aria-controls`, `aria-selected`, `aria-live` used correctly? Are \
`role` attributes semantically accurate?

3. **Focus management** — Does focus move logically after actions? Is focus trapped in \
modals? Does focus return to the trigger when a dialog closes? Can users skip repetitive \
content?

4. **Screen reader experience** — Would a screen reader user understand the page structure? \
Are interactive elements announced with correct roles and names? Are state changes \
(tool selected, panel opened, item deleted) announced?

5. **Canvas/SVG/custom rendering accessibility** — Are `<canvas>` elements labelled? Do \
they have `role="application"` or `role="img"`? Are SVGs decorative (`aria-hidden="true"`) \
or informative (with `aria-label`)?

6. **Dynamic content** — Are `aria-live` regions used for status updates, toast messages, \
loading states? Are they `polite` or `assertive` appropriately?

7. **prefers-reduced-motion / prefers-color-scheme** — Does the app respect OS preferences?

## Output format:

### Accessibility Deep Dive

For each finding:
- **What**: The specific element and its current implementation
- **Why it's wrong**: Which ARIA pattern or WCAG principle it violates
- **Correct implementation**: Exact HTML/ARIA fix with code snippets
- **Severity**: 0-4 (Nielsen scale)

### Component Intent Analysis
List any elements where the semantic HTML or ARIA role doesn't match the component's \
actual behaviour. Provide the correct pattern from WAI-ARIA APG.

### Screen Reader Narrative
Describe what a VoiceOver/NVDA user would hear navigating this page. Identify where \
the experience breaks down.

## Rules:
- DO NOT re-evaluate contrast ratios, touch targets, or landmark presence — the checker \
handles these. Focus on what code can't catch.
- DO reference specific WAI-ARIA Authoring Practices patterns by name.
- Every fix must include a code snippet.
"""


class AccessibilityAgent(BaseAgent):
    def system_prompt(self) -> str:
        return SYSTEM_PROMPT

    def get_image_paths(self, design_input: DesignInput) -> list[str]:
        if design_input.pages and len(design_input.pages) > 1:
            return [p.image_path for p in design_input.pages[:3] if p.image_path]
        if design_input.image_path:
            return [design_input.image_path]
        return []

    def retrieve_knowledge(self, design_input: DesignInput) -> str:
        return retrieve(
            tags=["accessibility", "wcag", "aria", "semantics", "screen-reader",
                  "annotation", "coga", "inclusive-design", "vestibular",
                  "reduced-motion", "states"],
            max_tokens=4000,
        )

    def build_user_prompt(self, design_input: DesignInput, context: str = "") -> str:
        parts = []

        if context:
            parts.append(f"## Context\n{context}")

        # Pre-computed WCAG report
        if design_input.pages and len(design_input.pages) > 1:
            wcag = run_wcag_check_multi(design_input.pages)
        else:
            wcag = run_wcag_check(design_input.dom_data)
        parts.append(f"## Pre-Computed WCAG Audit (already handled — do not re-evaluate)\n\n{wcag.to_markdown()}")

        # HTML structure
        html = design_input.dom_data.get("html_structure", {})
        if html:
            parts.append("## HTML Structure Data")
            parts.append(f"- lang: {html.get('lang_value', 'MISSING')}")
            parts.append(f"- Skip link: {'Yes' if html.get('skip_link') else 'No'}")

            landmarks = html.get("landmarks", {})
            parts.append(f"- Landmarks: {', '.join(f'<{k}>: {v}' for k, v in landmarks.items())}")

            headings = html.get("headings", [])
            if headings:
                heading_strs = [f"h{h['level']} \"{h['text']}\"" for h in headings]
            parts.append(f"- Headings: {', '.join(heading_strs)}")

            aria = html.get("aria_usage", {})
            parts.append(f"- ARIA roles used: {', '.join(aria.get('roles', [])) or 'none'}")
            parts.append(f"- aria-label count: {aria.get('labels', 0)}")
            parts.append(f"- aria-live regions: {aria.get('live_regions', 0)}")

            # Focus-visible rules
            fv = html.get("focus_visible_rules", [])
            if fv:
                parts.append(f"- Focus-visible CSS rules: {', '.join(r.get('selector', '?') for r in fv)}")
            elif html.get("has_global_focus_visible"):
                parts.append("- Global :focus-visible rules detected")
            else:
                parts.append("- No :focus-visible rules found")

            # Form labels
            unlabelled = html.get("forms", {}).get("inputs_without_labels", [])
            unlabelled_sel = html.get("forms", {}).get("selects_without_labels", [])
            if unlabelled or unlabelled_sel:
                parts.append(f"- Unlabelled inputs: {len(unlabelled) + len(unlabelled_sel)}")

        # State test results
        states = design_input.dom_data.get("state_tests", [])
        if states:
            parts.append("\n## Interactive State Test Results")
            for s in states:
                parts.append(f"- `{s['selector']}` \"{s['text']}\": hover={s.get('has_hover_state')}, focus={s.get('has_focus_state')}")

        parts.append("\nAnalyse the accessibility of this interface. Focus on semantic issues, ARIA patterns, and screen reader experience — not contrast or touch targets.")

        return "\n".join(parts)
