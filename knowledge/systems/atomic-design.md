---
id: sys-001
title: "Atomic Design Methodology"
category: systems
tags: [atomic-design, design-system, components, hierarchy]
source: "https://atomicdesign.bradfrost.com"
source_authority: canonical
ingested: 2026-04-04
validated: true
validator_notes: "Brad Frost (2016), full book free online"
---

## The Five Levels

1. **Atoms** - Basic HTML elements: buttons, inputs, labels, icons, colours, fonts. Cannot be broken down further.

2. **Molecules** - Simple groups of atoms functioning together: a search field (input + button + label), a media object (image + text).

3. **Organisms** - Complex components made of molecules and atoms: a header (logo + nav + search), a product card, a form section.

4. **Templates** - Page-level layouts composed of organisms. Define content structure and hierarchy without final content.

5. **Pages** - Templates with real content. Where you test that the design system works with actual data, edge cases, and varying content lengths.

## Key Principles

- **Design systems, not pages** - Build a library of reusable components, not one-off page designs
- **Interface inventory first** - Before designing, audit what exists. Collect all current buttons, forms, headers into a visual inventory
- **Content shapes design** - Components must work with real content variations (short names, long names, missing data, error states)
- **Document as you build** - A design system without documentation is just a collection of components

## When to apply
- Evaluating consistency: are similar elements using the same atoms/molecules?
- Identifying missing components: is there a gap in the component library?
- Assessing reuse: are components being duplicated with slight variations instead of being parameterised?
