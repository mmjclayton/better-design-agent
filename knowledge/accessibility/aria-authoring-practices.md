---
id: acc-003
title: "WAI-ARIA Authoring Practices"
category: accessibility
tags: [aria, accessibility, semantics, screen-reader]
source: "https://www.w3.org/WAI/ARIA/apg/"
source_authority: canonical
ingested: 2026-04-04
validated: true
validator_notes: "W3C WAI ARIA Authoring Practices Guide"
---

## Core ARIA Rules

1. **Use semantic HTML first** - If an HTML element or attribute provides the semantics and behavior you need, use it instead of ARIA. ARIA is a supplement, not a replacement.

2. **Do not change native semantics** - Do not use `role="heading"` on a `<div>` when `<h1>`-`<h6>` would work. Do not use `role="button"` on an `<a>` unless absolutely necessary.

3. **All interactive ARIA controls must be keyboard operable** - If you create a widget with `role="button"`, it must respond to Enter and Space key presses.

4. **Do not use `role="presentation"` or `aria-hidden="true"` on visible focusable elements** - This makes them invisible to assistive technology while still being interactive.

5. **All interactive elements must have an accessible name** - Every button, link, input, and widget needs a name via label, aria-label, or aria-labelledby.

## Common ARIA Patterns for UI Components

- **Tabs**: `role="tablist"`, `role="tab"`, `role="tabpanel"`, `aria-selected`, `aria-controls`
- **Modals**: `role="dialog"`, `aria-modal="true"`, `aria-labelledby`, focus trapping
- **Menus**: `role="menu"`, `role="menuitem"`, arrow key navigation
- **Accordions**: `aria-expanded`, `aria-controls`, toggle with Enter/Space
- **Combobox**: `role="combobox"`, `aria-expanded`, `aria-autocomplete`, `role="listbox"`
- **Live regions**: `aria-live="polite"` for non-urgent updates, `aria-live="assertive"` for critical

## When to apply
- Custom components that don't use native HTML elements
- SPAs with dynamic content updates (use aria-live)
- Navigation patterns that differ from standard HTML (tabs, tree views)
- Form validation messages (aria-describedby linking error to input)
