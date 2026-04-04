---
id: col-001
title: "Dark Mode Design Guidelines"
category: colour
tags: [dark-mode, colour, contrast, accessibility]
source: "https://m3.material.io/styles/color/dark-theme"
source_authority: canonical
ingested: 2026-04-04
validated: true
validator_notes: "Synthesised from Material Design 3 and Apple HIG dark mode guidelines"
---

## Core Principles

1. **Avoid pure black (#000000)** - Use dark grey (e.g. #121212, #1a1a1a) as the base surface. Pure black creates harsh contrast with white text and causes halation (glowing effect).

2. **Avoid pure white (#FFFFFF) for body text** - Use off-white (#E0E0E0 to #F0F0F0) to reduce eye strain. Reserve pure white for emphasis only.

3. **Use elevated surfaces for hierarchy** - In dark mode, use lighter backgrounds (not shadows) to convey elevation. Each level of elevation should be slightly lighter.

4. **Desaturate accent colours** - Highly saturated colours vibrate against dark backgrounds. Reduce saturation by 10-20% compared to light mode variants.

5. **Maintain contrast ratios** - Dark mode does not exempt from WCAG requirements. Text must still meet 4.5:1 (normal) and 3:1 (large) against its background.

## Material Design 3 Dark Surface Scale

| Elevation Level | Surface Colour | Tint Opacity |
|----------------|---------------|-------------|
| Surface | #121212 | 0% |
| +1 | #1E1E1E | 5% tint |
| +2 | #232323 | 7% tint |
| +3 | #252525 | 8% tint |
| +4 | #272727 | 9% tint |
| +5 | #2C2C2C | 11% tint |

## Common Violations
- Pure black backgrounds (#000000) causing eye strain
- Pure white text on dark backgrounds creating halation
- Fully saturated accent colours vibrating against dark surfaces
- Insufficient contrast between adjacent dark surfaces (cards on background)
- Shadows invisible on dark backgrounds - use lighter surfaces instead
- Status colours (red, green, yellow) not adjusted for dark backgrounds
