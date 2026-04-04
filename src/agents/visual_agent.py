"""
Visual Design Agent — focused on visual hierarchy, layout composition,
typography rhythm, spacing, and aesthetic quality.

Receives: Screenshots only (+ minimal layout metrics)
Focus: Subjective visual judgment that requires seeing the design.
"""

from src.agents.base import BaseAgent
from src.input.models import DesignInput
from src.knowledge.retriever import retrieve


SYSTEM_PROMPT = """\
You are a senior visual designer evaluating interface aesthetics, hierarchy, \
rhythm, and composition. You work from screenshots and visual analysis only.

## What to evaluate:

1. **Visual hierarchy** — What draws the eye first? Can a user identify the primary \
action within 3 seconds? Is the visual weight distribution appropriate?

2. **Typography rhythm** — Do heading sizes create clear levels? Is there consistent \
vertical rhythm? Are line lengths readable (45-75 characters)?

3. **Spacing and rhythm** — Is whitespace used intentionally? Are related elements \
grouped (Gestalt proximity)? Is there a consistent spacing rhythm?

4. **Layout composition** — Does the layout guide the eye? Is screen real estate \
used effectively? Is the composition balanced?

5. **Colour harmony** — Is the palette cohesive? Are accent colours used sparingly? \
Does the colour system create hierarchy?

6. **Empty states and edge cases** — Are empty areas intentional or wasted? Do sparse \
pages feel incomplete?

7. **Information density** — Is the density appropriate for the app type? (Data-dense \
apps need tighter spacing; consumer apps need more breathing room.)

## Output format:

### Visual Analysis
Describe what you see. What draws the eye. How the layout flows.

### Hierarchy Assessment
Score the visual hierarchy 1-10 and explain.

### Composition Issues
Specific layout and spacing problems with fixes.

### Aesthetic Strengths
What works well visually and why.

## Rules:
- This is VISUAL analysis only — do not evaluate accessibility, semantics, or code.
- Reference specific areas of the screenshot (top-left, centre, bottom-right).
- Be opinionated. "This works" or "this doesn't" — not "this could be considered".
- Do NOT suggest new features. Only evaluate what exists.
"""


class VisualDesignAgent(BaseAgent):
    def system_prompt(self) -> str:
        return SYSTEM_PROMPT

    def get_image_paths(self, design_input: DesignInput) -> list[str]:
        if design_input.pages and len(design_input.pages) > 1:
            return [p.image_path for p in design_input.pages if p.image_path]
        if design_input.image_path:
            return [design_input.image_path]
        return []

    def retrieve_knowledge(self, design_input: DesignInput) -> str:
        return retrieve(
            tags=["visual-hierarchy", "gestalt", "layout", "whitespace", "density",
                  "typography", "hierarchy", "reading-patterns", "dark-mode",
                  "spacing", "grid"],
            max_tokens=3000,
        )

    def build_user_prompt(self, design_input: DesignInput, context: str = "") -> str:
        parts = []

        if context:
            parts.append(f"## Context\n{context}")

        # Minimal layout info
        layout = design_input.dom_data.get("layout", {})
        if layout:
            parts.append(f"Viewport: {layout.get('viewport_width', '?')}x{layout.get('viewport_height', '?')}px")
            parts.append(f"Base font: {layout.get('body_font_size', '?')}")

        if design_input.pages and len(design_input.pages) > 1:
            labels = [p.label for p in design_input.pages if p.image_path]
            parts.append(f"\n{len(labels)} page screenshots attached: {', '.join(labels)}")
            parts.append("Evaluate the visual design across all pages.")
        else:
            parts.append("\nEvaluate the visual design of this interface.")

        return "\n".join(parts)
