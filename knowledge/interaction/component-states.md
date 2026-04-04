---
id: int-005
title: "Interactive Component State Requirements"
category: interaction
tags: [components, states, interaction, feedback, patterns]
source: "Derived from Material Design 3, Untitled UI, shadcn/ui design systems"
source_authority: high
ingested: 2026-04-04
validated: true
validator_notes: "Cross-referenced with major design system component specifications"
---

## Required States for Interactive Components

Every interactive element must define these states:

| State | Visual Treatment | When |
|-------|-----------------|------|
| Default | Base appearance | No interaction |
| Hover | Subtle background change or underline | Mouse over (desktop) |
| Focus | Visible outline or ring (2px solid, offset 2px) | Keyboard navigation |
| Active/Pressed | Darkened or depressed appearance | During click/tap |
| Disabled | Reduced opacity (40-50%), no pointer events | Not available |
| Loading | Spinner or skeleton replacing content | Awaiting response |
| Error | Red border/outline + error message | Validation failure |
| Success | Green indicator or checkmark | Action completed |

## Component-Specific State Requirements

### Buttons
- Primary, secondary, tertiary, destructive variants
- All 8 states above
- Loading state should disable and show spinner without layout shift

### Text Inputs
- Default, hover, focused (ring), filled, error, disabled
- Error state: red border + message below, not just colour change
- Placeholder text is NOT a substitute for a label

### Checkboxes / Toggles
- Unchecked, checked, indeterminate, disabled
- Clear visual difference between on/off (not colour alone)

### Tabs / Navigation Items
- Default, hover, active/selected, focus
- Selected state must be visually distinct beyond colour (underline, background, weight)

### Cards / List Items (if clickable)
- Default, hover, selected, focus
- Hover should indicate clickability (cursor: pointer + visual change)

## Common Violations
- No hover state on clickable elements
- No focus-visible style (keyboard users can't navigate)
- Disabled state indistinguishable from default
- Loading state causes layout shift
- Error state uses only colour (fails WCAG 1.4.1)
- Toggle on/off states only differentiated by colour
