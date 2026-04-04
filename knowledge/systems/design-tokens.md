---
id: sys-002
title: "Design Token Taxonomy and Naming"
category: systems
tags: [design-tokens, design-system, css-variables, naming]
source: "https://eightshapes.com"
source_authority: canonical
ingested: 2026-04-04
validated: true
validator_notes: "Nathan Curtis / EightShapes, W3C Design Tokens Community Group"
---

## What Are Design Tokens?

Design tokens are the visual design atoms of a design system: named entities that store visual values. They replace hardcoded values (hex colours, pixel sizes) with semantic, reusable names.

## Token Categories

| Category | Examples | Purpose |
|----------|----------|---------|
| Colour | `--color-primary`, `--color-bg-surface` | Palette and semantic colour assignments |
| Typography | `--font-size-base`, `--font-weight-bold` | Type scale and font properties |
| Spacing | `--space-4`, `--space-8` | Consistent spacing scale |
| Border radius | `--radius-sm`, `--radius-lg` | Corner rounding |
| Shadow | `--shadow-sm`, `--shadow-lg` | Elevation and depth |
| Motion | `--duration-fast`, `--easing-standard` | Animation timing |
| Breakpoints | `--bp-sm`, `--bp-lg` | Responsive breakpoints |

## Three-Tier Token Architecture

1. **Global tokens** - Raw values: `--blue-500: #3B82F6`. Not used directly in components.
2. **Semantic tokens** - Contextual meaning: `--color-primary: var(--blue-500)`. Used in components.
3. **Component tokens** - Component-specific: `--button-bg: var(--color-primary)`. Scoped to a single component.

## Naming Conventions

Format: `--[category]-[property]-[variant]-[state]`

Examples:
- `--color-text-primary`
- `--color-bg-surface`
- `--color-border-default`
- `--font-size-sm`
- `--space-4`
- `--radius-md`

## When to apply
- Audit existing CSS for hardcoded values that should be tokens
- Check token usage consistency across components
- Recommend new tokens for values used 3+ times
- Evaluate naming conventions against the three-tier architecture
