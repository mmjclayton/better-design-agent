---
id: acc-007
title: "Accessibility Annotation Standards"
category: accessibility
tags: [accessibility, annotation, documentation, wcag, handoff]
source: "CVS Health Web Accessibility Annotation Kit + EightShapes Include plugin"
source_authority: high
ingested: 2026-04-04
validated: true
validator_notes: "Industry-standard annotation practices from CVS Health (7.9k+ users) and EightShapes"
---

## What to Annotate for Accessibility

Every design handoff should document these accessibility specifications:

### 1. Heading Structure
- Mark heading levels (h1-h6) on every page
- Only one h1 per page
- Headings must not skip levels (h1 then h3 without h2)
- Visual heading size may differ from semantic level

### 2. Landmarks
- Identify regions: `<main>`, `<nav>`, `<aside>`, `<header>`, `<footer>`
- Label repeated landmarks (e.g. two `<nav>` elements need distinct aria-labels)

### 3. Focus Order
- Document tab order for interactive elements
- Mark focus trap boundaries (modals, drawers)
- Specify where focus moves after actions (close modal, delete item, submit form)

### 4. Alternative Text
- Write alt text for all meaningful images
- Mark decorative images as `alt=""`
- Charts and graphs need descriptive alt text or linked data table

### 5. Form Labels
- Every input must have a programmatic label
- Specify label text, not just visual placement
- Document error message text and where it appears

### 6. ARIA Roles and Properties
- Custom components need role annotations (e.g. tabs, accordions, menus)
- Document aria-expanded, aria-selected, aria-controls relationships
- Specify live region behaviour for dynamic content

### 7. Colour Independence
- Document where information is conveyed by colour
- Specify the non-colour alternative (icon, text, pattern)

## When to apply
- Design spec reviews: check that accessibility annotations are present
- Critique output: recommend annotation when semantic structure is ambiguous
- Handoff evaluation: flag designs missing accessibility documentation
