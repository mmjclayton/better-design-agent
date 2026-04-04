---
id: mob-002
title: "Responsive Design Principles"
category: mobile
tags: [responsive, mobile, breakpoints, layout, viewport]
source: "Ethan Marcotte (2011) Responsive Web Design + BrowserStack (2025)"
source_authority: canonical
ingested: 2026-04-04
validated: true
validator_notes: "Marcotte coined 'responsive web design' in 2010"
---

## Three Technical Pillars

1. **Fluid grids** - Use relative units (%, rem, vw) instead of fixed pixels for layout widths
2. **Flexible media** - Images and videos scale within their containers (max-width: 100%)
3. **CSS media queries** - Apply different styles at different viewport widths

## Common Breakpoints

| Breakpoint | Viewport | Typical Use |
|-----------|----------|-------------|
| Small | 320-639px | Mobile phones, single column |
| Medium | 640-1023px | Tablets, two columns |
| Large | 1024-1439px | Laptops, full navigation visible |
| Extra large | 1440px+ | Desktops, max content width |

## Key Principles

1. **Mobile-first** - Design for the smallest screen first, then enhance for larger screens. This forces prioritisation of content and features.

2. **Content drives breakpoints** - Set breakpoints where the content breaks, not at arbitrary device widths. If text lines get too long at 900px, break at 900px.

3. **Readable line length** - 45-75 characters per line. Use max-width on text containers to prevent overly wide lines on large screens.

4. **Touch and mouse** - Don't assume input method from viewport size. Tablets are touch devices at "desktop" widths. Laptops have touch screens.

5. **Test real devices** - Emulators don't catch touch target issues, scroll behaviour differences, or rendering bugs.

## Common Violations
- Fixed-width layouts that don't adapt
- Text that's too small on mobile (below 16px)
- Touch targets that shrink below 44px on mobile
- Horizontal scrolling caused by overflow
- Desktop navigation (hamburger-less) forced onto mobile
- Images that don't scale, causing horizontal scroll
