---
id: acc-002
title: "WCAG 2.2 Complete Overview"
category: accessibility
tags: [wcag, accessibility, compliance, standards]
source: "https://www.w3.org/TR/WCAG22/"
source_authority: canonical
ingested: 2026-04-04
validated: true
validator_notes: "W3C Recommendation, October 2023, updated December 2024"
---

## Four Principles (POUR)

1. **Perceivable** - Information and UI components must be presentable in ways users can perceive
2. **Operable** - UI components and navigation must be operable
3. **Understandable** - Information and operation of the UI must be understandable
4. **Robust** - Content must be robust enough for assistive technologies

## Key Success Criteria for UI Critique

### Perceivable
- **1.1.1 Non-text Content** - All non-text content has a text alternative
- **1.3.1 Info and Relationships** - Structure and relationships conveyed through presentation are programmatically determinable (semantic HTML, ARIA)
- **1.4.1 Use of Color** - Color is not the sole means of conveying information
- **1.4.3 Contrast (Minimum)** - Text: 4.5:1, large text: 3:1 (AA)
- **1.4.11 Non-text Contrast** - UI components and graphical objects: 3:1 against adjacent colors

### Operable
- **2.1.1 Keyboard** - All functionality is operable through a keyboard
- **2.4.1 Bypass Blocks** - A mechanism to bypass repeated blocks of content (skip links)
- **2.4.3 Focus Order** - Focusable components receive focus in a meaningful sequence
- **2.4.7 Focus Visible** - Keyboard focus indicator is visible
- **2.5.5 Target Size (Enhanced)** - Target size is at least 44x44 CSS pixels (AAA)
- **2.5.8 Target Size (Minimum)** - Target size is at least 24x24 CSS pixels (AA, new in 2.2)

### Understandable
- **3.1.1 Language of Page** - Default human language is programmatically determinable
- **3.2.6 Consistent Help** - Help mechanisms occur in the same relative order (new in 2.2)
- **3.3.7 Accessible Authentication** - No cognitive function test for authentication (new in 2.2)

### Robust
- **4.1.2 Name, Role, Value** - For all UI components, name and role are programmatically determinable

## New in WCAG 2.2 (9 criteria)
- 2.4.11 Focus Not Obscured (Minimum) (AA)
- 2.4.12 Focus Not Obscured (Enhanced) (AAA)
- 2.4.13 Focus Appearance (AAA)
- 2.5.7 Dragging Movements (AA)
- 2.5.8 Target Size (Minimum) (AA)
- 3.2.6 Consistent Help (A)
- 3.3.7 Accessible Authentication (Minimum) (AA)
- 3.3.8 Accessible Authentication (No Exception) (AAA)
- 3.3.9 Redundant Entry (A)
