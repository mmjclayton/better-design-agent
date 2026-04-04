---
id: sys-005
title: "IBM Carbon Design System Principles"
category: systems
tags: [carbon, ibm, design-system, enterprise, accessibility]
source: "https://carbondesignsystem.com"
source_authority: high
ingested: 2026-04-04
validated: true
validator_notes: "IBM's open-source design system, Apache 2.0 license"
---

## Core Principles

1. **Be essential** - Every element should serve a purpose. Decorative elements that don't support content or function should be removed.

2. **Be consistent** - Create familiarity and strengthen intuition by applying the same solution to the same problem.

3. **Be inclusive** - Accessibility is a foundational requirement, not an afterthought. Carbon is WCAG 2.1 AA compliant by default.

## Notable Carbon Patterns

### 2x Grid System
- Base unit: 8px (mini unit), with a 2x (16px) column grid
- Margin and gutter are both multiples of the mini unit
- Responsive breakpoints: 320, 672, 1056, 1312, 1584px

### Spacing Scale
Two scales:
- **Layout**: 16, 24, 32, 48, 64, 96, 160px (generous, for page sections)
- **Component**: 2, 4, 8, 12, 16, 24, 32, 40, 48px (tight, for internal spacing)

### Type Scale
Uses IBM Plex font family with defined type tokens:
- Caption: 12px/1.33
- Body Short: 14px/1.29
- Body Long: 16px/1.5
- Heading: 14px-42px across 6 levels

## When to apply
- Enterprise application design evaluation
- Accessibility-first design system comparisons
- Spacing and grid system assessment
- Data-dense interface patterns
