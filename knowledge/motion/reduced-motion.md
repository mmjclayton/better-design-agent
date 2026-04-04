---
id: mot-002
title: "Reduced Motion and Vestibular Accessibility"
category: motion
tags: [motion, accessibility, reduced-motion, vestibular]
source: "https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/At-rules/@media/prefers-reduced-motion"
source_authority: canonical
ingested: 2026-04-04
validated: true
validator_notes: "MDN Web Docs + WCAG 2.2 SC 2.3.3"
---

## The Problem

Vestibular motion disorders affect approximately 35% of adults over 40. Symptoms triggered by screen motion include dizziness, nausea, and disorientation. Parallax scrolling, auto-playing carousels, and zooming animations are common triggers.

## WCAG Requirements

- **2.3.1 Three Flashes or Below Threshold (A)** - No content flashes more than 3 times per second
- **2.3.3 Animation from Interactions (AAA)** - Motion triggered by interaction can be disabled, unless essential

## Implementation

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

## What to Reduce vs Remove

| Reduce | Keep |
|--------|------|
| Parallax scrolling | Opacity fades (non-moving) |
| Auto-playing carousels | Colour transitions |
| Zooming/scaling animations | Focus ring appearance |
| Sliding page transitions | Loading spinners (essential) |
| Background video | Static state changes |
| Bouncing/shaking effects | Progress bar advancement |

## When to apply
- Check for prefers-reduced-motion support in any design with animation
- Flag auto-playing carousels and parallax effects
- Verify loading states work without animation
- Ensure no content relies solely on motion to convey meaning
