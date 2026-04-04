"""
Design System Agent — focused on token architecture, consistency,
naming conventions, and design system maturity.

Receives: CSS tokens + computed styles + font/color/spacing data
Focus: Token root cause analysis, naming consistency, gaps, duplication.
"""

from src.agents.base import BaseAgent
from src.input.models import DesignInput
from src.knowledge.retriever import retrieve


SYSTEM_PROMPT = """\
You are a design systems architect. You evaluate CSS token architecture, \
naming conventions, consistency of usage, and design system maturity.

You will receive:
1. **CSS custom properties** (design tokens) found on :root
2. **Computed style data** — actual colors, font sizes, spacing values in use
3. **Screenshots** for visual context

## What to evaluate:

1. **Token architecture** — Is there a proper layered system? Primitives (raw values) \
vs semantic tokens (contextual meaning) vs component tokens (scoped)? Or is it flat?

2. **Root cause analysis** — When a computed value is wrong (e.g. low contrast), trace it \
back to the token. Which token maps to the failing value? What's the one-line fix at the \
token level?

3. **Naming conventions** — Are tokens named consistently? Do they follow a pattern like \
`--color-[category]-[variant]`? Are there duplicates or aliases that resolve to the same value?

4. **Token coverage** — Which computed values are tokenised vs hardcoded? Only flag \
hardcoded values that appear 10+ times.

5. **Token duplication** — Are multiple tokens resolving to the same value? Which can be \
consolidated?

6. **Design system maturity** — Rate the system's maturity: None → Emerging → Established \
→ Mature → Systematic.

## Output format:

### Token Architecture Analysis
Describe the token structure (layers, naming, coverage).

### Root Cause Findings
For each visual/contrast/spacing issue, trace it to the responsible token and provide \
the token-level fix.

### Token Audit Table
| Token | Value | Usage | Issue |

### Duplication Report
List tokens that resolve to identical values.

### Maturity Rating
Rate and justify the design system maturity level.

### Recommendations
Prioritised list of token-level changes. Only recommend new tokens for values used 10+ times.

## Rules:
- Trace every issue to its token root cause, not just the computed symptom.
- Reference tokens by name (e.g. `var(--color-gray-40)` not just `#b8b8b8`).
- Do NOT recommend new features or UI changes — only token/system architecture.
"""


class DesignSystemAgent(BaseAgent):
    def system_prompt(self) -> str:
        return SYSTEM_PROMPT

    def get_image_paths(self, design_input: DesignInput) -> list[str]:
        if design_input.image_path:
            return [design_input.image_path]
        return []

    def retrieve_knowledge(self, design_input: DesignInput) -> str:
        return retrieve(
            tags=["design-system", "design-tokens", "css-variables", "naming",
                  "atomic-design", "components", "figma", "reference"],
            max_tokens=3000,
        )

    def build_user_prompt(self, design_input: DesignInput, context: str = "") -> str:
        parts = []

        if context:
            parts.append(f"## Context\n{context}")

        # CSS tokens
        tokens = design_input.dom_data.get("css_tokens", {})
        has_tokens = any(tokens.get(cat) for cat in tokens)
        if has_tokens:
            parts.append("## CSS Custom Properties (Design Tokens)")
            for category in ["color", "spacing", "radius", "font", "other"]:
                entries = tokens.get(category, [])
                if entries:
                    parts.append(f"\n**{category.title()} tokens ({len(entries)}):**")
                    for t in entries:
                        parts.append(f"- `{t['name']}`: `{t['value']}`")
        else:
            parts.append("## CSS Custom Properties\n**No design tokens found.**")

        # Computed values in use
        colors = design_input.dom_data.get("colors", {})
        if colors.get("text"):
            parts.append("\n## Computed Colors in Use")
            parts.append("**Text:**")
            for c in colors["text"][:10]:
                parts.append(f"- `{c['color']}` ({c['count']} elements)")
        if colors.get("background"):
            parts.append("**Background:**")
            for c in colors["background"][:10]:
                parts.append(f"- `{c['color']}` ({c['count']} elements)")

        fonts = design_input.dom_data.get("fonts", {})
        if fonts.get("sizes"):
            parts.append("\n## Font Sizes in Use")
            for f in fonts["sizes"][:12]:
                parts.append(f"- `{f['size']}` ({f['count']} elements)")

        spacing = design_input.dom_data.get("spacing_values", [])
        if spacing:
            parts.append("\n## Spacing Values in Use")
            for s in spacing[:15]:
                parts.append(f"- `{s['value']}` ({s['count']} uses)")

        # Contrast failures for root cause tracing
        contrast = design_input.dom_data.get("contrast_pairs", [])
        failures = [c for c in contrast if not c.get("passes_aa")]
        if failures:
            parts.append("\n## Contrast Failures (trace to token root cause)")
            for c in failures:
                parts.append(
                    f"- `{c['text_color']}` on `{c['bg_color']}` = {c['ratio']}:1 "
                    f"[{c.get('element', '?')}]"
                )

        parts.append("\nAnalyse the design token system. Trace issues to token root causes. Rate system maturity.")

        return "\n".join(parts)
