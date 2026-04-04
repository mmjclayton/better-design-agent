---
id: typ-002
title: "Typographic Hierarchy for Interfaces"
category: typography
tags: [typography, hierarchy, readability, type-scale]
source: "Robert Bringhurst (2004) Elements of Typographic Style + Tim Brown (2011) More Meaningful Typography"
source_authority: canonical
ingested: 2026-04-04
validated: true
validator_notes: "Bringhurst (canonical) + Brown (A List Apart, practical web application)"
---

## Creating Hierarchy

Three tools for establishing typographic hierarchy, in order of effectiveness:

1. **Size** - Larger text reads as more important. Minimum 1.2x ratio between levels.
2. **Weight** - Bolder text draws attention. Use 2-3 weights maximum (400, 600, 700).
3. **Colour/opacity** - Lighter text reads as secondary. Use 60-70% opacity for secondary text.

## Line Length (Measure)

- **Optimal**: 45-75 characters per line (including spaces)
- **Comfortable maximum**: 80 characters
- **Minimum for readability**: 30 characters
- Calculate: `max-width` of approximately 65ch on text containers

## Line Height (Leading)

| Text Type | Recommended Line Height |
|-----------|------------------------|
| Body text (14-18px) | 1.4-1.6 |
| Small text (12-13px) | 1.4-1.5 |
| Headings (20-40px) | 1.1-1.3 |
| Large display (40px+) | 1.0-1.2 |

Line height should decrease proportionally as font size increases.

## Font Pairing Rules

1. **One typeface is usually enough** - Use weight and size for hierarchy
2. **If pairing, contrast clearly** - Serif + sans-serif, not two similar sans-serifs
3. **System fonts are fine** - -apple-system, system-ui provide native feel with zero load time
4. **Maximum two typefaces** - One for headings, one for body. Three is almost always too many.

## When to apply
- Evaluating whether a design has clear visual hierarchy through typography alone
- Checking line length on wide screens (common failure: full-width text)
- Assessing heading levels for consistent size progression
