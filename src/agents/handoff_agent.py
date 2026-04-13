"""
Design Handoff Agent — generates developer handoff specs from
extracted DOM data and visual analysis.
"""

from src.agents.base import BaseAgent
from src.input.models import DesignInput
from src.knowledge.retriever import retrieve


SYSTEM_PROMPT = """\
You are a design-to-development handoff specialist. You generate comprehensive \
developer specifications from design analysis data.

You will receive:
1. **CSS custom properties** (design tokens) with exact values
2. **Computed styles** — all colours, font sizes, spacing values in use
3. **Interactive elements** with dimensions and state test results
4. **HTML structure** — landmarks, headings, ARIA attributes
5. **Screenshots** for visual reference

## Generate a complete handoff specification covering:

### 1. Design Tokens
List all CSS custom properties grouped by category. For each, show the token \
name, resolved value, and where it's used. Flag any hardcoded values that should \
reference tokens.

### 2. Layout Specification
- Grid system / layout structure
- Responsive breakpoints and behaviour at each
- Container widths, padding, margins
- Section spacing

### 3. Component Inventory
For each identified component type:
- Exact dimensions (width, height, padding, margin)
- All variants observed
- All states required (default, hover, active, focus, disabled, loading, error)
- Typography (font, size, weight, colour, line-height)
- Colours (background, text, border)
- Border radius
- Box shadow / elevation

### 4. Interaction Specifications
For each interactive element:
- Click/tap behaviour (from state tests)
- Hover state (exact CSS changes)
- Focus state (outline/ring specification)
- Transition timing and easing
- Keyboard interaction (Tab, Enter, Space, Escape, Arrow keys)

### 5. Accessibility Requirements
- ARIA roles and attributes needed
- Keyboard interaction model
- Focus management rules
- Screen reader announcements
- Touch target minimums

### 6. Edge Cases
- Empty states (what to show when no data)
- Loading states (skeleton or spinner)
- Error states (validation, network, permission)
- Overflow behaviour (long text, many items)
- Minimum/maximum content scenarios

## Output format:

Use markdown tables for structured data. Use code blocks for CSS/HTML snippets. \
Reference token names (not raw values) wherever tokens exist.

## Rules:
- Use exact values from the extracted data — do not approximate
- Reference tokens by name: `var(--color-primary)` not `#4f46e5`
- Every dimension should be in px or rem
- Include code snippets for complex interactions
- Do NOT include design opinions — this is a spec, not a critique
"""


class HandoffAgent(BaseAgent):
    def system_prompt(self) -> str:
        return SYSTEM_PROMPT

    def get_image_paths(self, design_input: DesignInput) -> list[str]:
        if design_input.pages and len(design_input.pages) > 1:
            return [p.image_path for p in design_input.pages[:5] if p.image_path]
        if design_input.image_path:
            return [design_input.image_path]
        return []

    def retrieve_knowledge(self, design_input: DesignInput) -> str:
        return retrieve(
            tags=["design-tokens", "design-system", "components", "states",
                  "interaction", "accessibility", "annotation", "handoff"],
            max_tokens=3000,
        )

    def build_user_prompt(self, design_input: DesignInput, context: str = "") -> str:
        parts = []

        if context:
            parts.append(f"## Context\n{context}")

        dom = design_input.dom_data

        # Tokens
        tokens = dom.get("css_tokens", {})
        has_tokens = any(tokens.get(cat) for cat in tokens)
        if has_tokens:
            parts.append("## Design Tokens")
            for category in ["color", "spacing", "radius", "font", "other"]:
                entries = tokens.get(category, [])
                if entries:
                    parts.append(f"\n**{category.title()} ({len(entries)}):**")
                    for t in entries:
                        parts.append(f"- `{t['name']}`: `{t['value']}`")

        # Layout
        layout = dom.get("layout", {})
        if layout:
            parts.append("\n## Layout")
            parts.append(f"- Viewport: {layout.get('viewport_width')}x{layout.get('viewport_height')}px")
            parts.append(f"- Body font: {layout.get('body_font_size')} / {layout.get('body_line_height')}")
            parts.append(f"- Font family: {layout.get('body_font_family')}")
            parts.append(f"- Body background: `{layout.get('body_bg')}`")

        # Colors
        colors = dom.get("colors", {})
        if colors.get("text"):
            parts.append("\n## Colours in Use")
            parts.append("**Text:**")
            for c in colors["text"][:10]:
                parts.append(f"- `{c['color']}` ({c['count']} elements)")
            if colors.get("background"):
                parts.append("**Background:**")
                for c in colors["background"][:10]:
                    parts.append(f"- `{c['color']}` ({c['count']} elements)")

        # Typography
        fonts = dom.get("fonts", {})
        if fonts.get("sizes"):
            parts.append("\n## Font Sizes")
            for f in fonts["sizes"][:12]:
                parts.append(f"- `{f['size']}` ({f['count']} elements)")
        if fonts.get("families"):
            parts.append("\n## Font Families")
            for f in fonts["families"][:5]:
                parts.append(f"- {f['family']} ({f['count']} elements)")

        # Spacing
        spacing = dom.get("spacing_values", [])
        if spacing:
            parts.append("\n## Spacing Values")
            for s in spacing[:15]:
                parts.append(f"- `{s['value']}` ({s['count']} uses)")

        # Interactive elements
        interactive = dom.get("interactive_elements", [])
        if interactive:
            parts.append(f"\n## Interactive Elements ({len(interactive)})")
            for e in interactive[:20]:
                parts.append(
                    f"- `{e['element']}` \"{e['text']}\" - {e['width']}x{e['height']}px"
                )

        # State tests
        states = dom.get("state_tests", [])
        if states:
            parts.append("\n## State Test Results")
            for s in states:
                hover = "yes" if s.get("has_hover_state") else "none"
                focus = "yes" if s.get("has_focus_state") else "none"
                parts.append(f"- `{s['selector']}`: hover={hover}, focus={focus}")
                if s.get("hover_changes"):
                    for k, v in s["hover_changes"].items():
                        parts.append(f"  {k}: `{v['from']}` -> `{v['to']}`")
                if s.get("focus_changes"):
                    for k, v in s["focus_changes"].items():
                        parts.append(f"  {k}: `{v['from']}` -> `{v['to']}`")

        # HTML structure
        html = dom.get("html_structure", {})
        if html:
            parts.append("\n## HTML Structure")
            parts.append(f"- lang: {html.get('lang_value', 'not set')}")
            landmarks = html.get("landmarks", {})
            parts.append(f"- Landmarks: {', '.join(f'<{k}>: {v}' for k, v in landmarks.items())}")
            headings = html.get("headings", [])
            if headings:
                for h in headings:
                    parts.append(f"- h{h['level']}: \"{h['text']}\"")
            aria = html.get("aria_usage", {})
            if aria.get("roles"):
                parts.append(f"- ARIA roles: {', '.join(aria['roles'])}")

        # Non-text contrast
        ntc = dom.get("non_text_contrast", [])
        if ntc:
            parts.append(f"\n## Component Contrast ({len(ntc)} elements)")
            for n in ntc[:10]:
                status = "pass" if n.get("passes_3_to_1") else "FAIL"
                parts.append(
                    f"- `{n['element']}` bg={n['component_bg']} vs {n['adjacent_bg']} "
                    f"= {n['bg_ratio']}:1 [{status}]"
                )

        parts.append("\nGenerate a comprehensive developer handoff specification from this data.")

        return "\n".join(parts)
