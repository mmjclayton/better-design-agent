---
id: col-003
title: "ColorBrewer and Data Visualisation Colour"
category: colour
tags: [colour, data-visualisation, colorbrewer, accessibility]
source: "https://colorbrewer2.org"
source_authority: canonical
ingested: 2026-04-04
validated: true
validator_notes: "Brewer & Harrower (2003), standard reference for data viz colour"
---

## Three Palette Types

1. **Sequential** - For ordered data from low to high. Single hue, varying lightness. Example: light blue to dark blue for temperature range.

2. **Diverging** - For data with a meaningful midpoint. Two hues diverge from a neutral centre. Example: red-white-blue for above/below average.

3. **Qualitative** - For categorical data with no inherent order. Distinct hues at similar lightness. Example: different colours for different categories.

## Rules for Colour in Charts and Data

- **Maximum 7 colours** in a qualitative palette before differentiation drops
- **Test for colourblind safety** - 8% of males have colour vision deficiency. Avoid red-green only distinctions.
- **Use lightness as the primary differentiator** - It survives greyscale printing and most colour vision deficiencies
- **Label directly** when possible instead of relying on colour legends
- **Sequential data should never use rainbow palettes** - they have no perceptual ordering

## When to apply
- Dashboard charts and graphs
- Heatmaps and status matrices
- Progress indicators and gauges
- Any data representation using colour encoding
- Choosing accessible status colour sets (success/warning/error)
