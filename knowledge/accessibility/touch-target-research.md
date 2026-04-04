---
id: acc-005
title: "Touch Target Sizing Research"
category: accessibility
tags: [touch-targets, accessibility, mobile, fitts-law]
source: "https://www.nngroup.com/articles/touch-target-size/"
source_authority: canonical
ingested: 2026-04-04
validated: true
validator_notes: "NNGroup research combined with MIT Touch Lab and platform guidelines"
---

## Research Findings

**MIT Touch Lab**: Average fingertip width is 1.6-2cm, thumb averages 2.5cm. The average touch area (finger pad contact) is approximately 10mm x 13mm.

**Fitts's Law**: Time to reach a target is a function of the distance to the target and the size of the target. Smaller targets = more errors and slower interaction.

## Platform-Specific Minimums

| Platform | Minimum | Recommended | Source |
|----------|---------|-------------|--------|
| WCAG 2.2 AA (2.5.8) | 24x24px | 44x44px | W3C |
| WCAG 2.2 AAA (2.5.5) | 44x44px | - | W3C |
| Apple iOS | 44x44pt | - | Apple HIG |
| Material Design | 48x48dp | - | Google M3 |
| Windows | 40x40px | - | Microsoft |

## Key Rules

1. **44x44px is the safe minimum** for any touch-interactive element
2. **Spacing between targets** counts: if two 24px buttons have 8px gap between them, they effectively have 32px targets (WCAG allows spacing to count)
3. **Inline links in text** are exempt from target size requirements
4. **The clickable area can be larger than the visual element** - use padding, not just visible size
5. **Primary actions should be larger** than secondary actions (48-56px for primary CTAs)

## Common Violations
- Navigation tabs at 32-36px height
- Icon-only buttons at 24x24px without padding
- Table row actions (edit, delete) under 44px
- Filter chips and tags under 44px height
- Form select dropdowns at default browser size
