"""
Interaction Agent — focused on affordances, state visibility,
feedback patterns, and interaction quality.

Receives: State test results + interactive element data + screenshots
Focus: Missing states, broken affordances, feedback gaps.
"""

from src.agents.base import BaseAgent
from src.input.models import DesignInput
from src.knowledge.retriever import retrieve


SYSTEM_PROMPT = """\
You are an interaction design specialist evaluating UI affordances, state \
management, feedback patterns, and interaction quality.

You will receive:
1. **Interactive state test results** — Playwright hovered and focused each element, \
recording which states exist and what changes
2. **Interactive element inventory** — all buttons, inputs, links with dimensions
3. **Screenshots** for visual context

## What to evaluate:

1. **Missing states** — Every interactive element needs: default, hover, focus, active, \
and (where applicable) disabled, loading, error, selected states. Flag any missing.

2. **Hover affordance** — Does the cursor change to pointer? Does the element visually \
respond? Is the response immediate or delayed?

3. **Focus visibility** — Is the focus indicator visible against the background? Does it \
use a consistent style? Is it at least 2px and high-contrast?

4. **Selected/active states** — Are selected items clearly distinguished from unselected? \
Is the distinction non-colour-only?

5. **Feedback patterns** — After user actions, does the UI provide clear feedback? Are \
state transitions smooth? Are loading states present where needed?

6. **Platform conventions** — Do interactive patterns follow web platform expectations? \
Links look like links, buttons look like buttons, inputs look like inputs?

7. **Error prevention** — Are destructive actions guarded? Do form inputs validate inline?

## Output format:

### State Audit Results
Per-element assessment of hover, focus, active, disabled states.

### Missing Interaction Patterns
Patterns that should exist but don't (loading states, error states, confirmations).

### Affordance Issues
Elements that don't look interactive but are, or look interactive but aren't.

### Recommendations
Prioritised list of interaction fixes.

## Rules:
- Use the state test data as ground truth — don't guess about hover/focus states.
- Reference specific elements by selector.
- Focus on interaction quality, not visual design or accessibility compliance.
"""


class InteractionAgent(BaseAgent):
    def system_prompt(self) -> str:
        return SYSTEM_PROMPT

    def get_image_paths(self, design_input: DesignInput) -> list[str]:
        if design_input.image_path:
            return [design_input.image_path]
        return []

    def retrieve_knowledge(self, design_input: DesignInput) -> str:
        return retrieve(
            tags=["interaction", "states", "feedback", "microinteractions",
                  "forms", "navigation", "patterns", "components",
                  "platform-conventions"],
            max_tokens=3000,
        )

    def build_user_prompt(self, design_input: DesignInput, context: str = "") -> str:
        parts = []

        if context:
            parts.append(f"## Context\n{context}")

        # Viewport context — so recommendations match the device being evaluated
        layout = design_input.dom_data.get("layout", {})
        vw = layout.get("viewport_width", 0) if layout else 0
        vh = layout.get("viewport_height", 0) if layout else 0
        if vw and vh:
            is_desktop = vw >= 1024
            parts.append(
                f"## Viewport\nReviewing **{'desktop' if is_desktop else 'mobile/tablet'}** "
                f"viewport ({vw}x{vh}px). "
                + (
                    "Focus interaction critique on mouse + keyboard users. "
                    "Don't speculate about 'desktop users accessing mobile view' — "
                    "that's not this run's audience."
                    if not is_desktop else
                    "Focus interaction critique on mouse + keyboard + pointer users. "
                    "Touch-target sizing (44x44px) is a mobile convention — apply it "
                    "loosely here; mouse users don't need 44px targets."
                )
            )

        # State test results
        states = design_input.dom_data.get("state_tests", [])
        if states:
            parts.append("## Interactive State Test Results")
            parts.append("Each element was hovered and focused via Playwright:\n")

            for s in states:
                hover_detail = ""
                if s.get("has_hover_state"):
                    changes = s.get("hover_changes", {})
                    hover_detail = " (" + ", ".join(f"{k}: {v['from']} -> {v['to']}" for k, v in changes.items()) + ")" if changes else ""
                focus_detail = ""
                if s.get("has_focus_state"):
                    changes = s.get("focus_changes", {})
                    focus_detail = " (" + ", ".join(f"{k}: {v['from']} -> {v['to']}" for k, v in changes.items()) + ")" if changes else ""

                parts.append(
                    f"- `{s['selector']}` \"{s['text']}\"\n"
                    f"  Hover: {'YES' + hover_detail if s.get('has_hover_state') else 'NONE'}\n"
                    f"  Focus: {'YES' + focus_detail if s.get('has_focus_state') else 'NONE'}\n"
                    f"  Cursor: {s.get('cursor_on_hover', 'unknown')}"
                )
        else:
            parts.append("## No state test data available.")

        # Interactive elements
        interactive = design_input.dom_data.get("interactive_elements", [])
        if interactive:
            parts.append(f"\n## Interactive Element Inventory ({len(interactive)} elements)")
            for e in interactive[:20]:
                parts.append(
                    f"- `{e['element']}` \"{e['text']}\" — {e['width']}x{e['height']}px"
                )

        parts.append("\nEvaluate the interaction quality of this interface based on the state test data.")

        return "\n".join(parts)
