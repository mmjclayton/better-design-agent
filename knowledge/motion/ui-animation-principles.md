---
id: mot-001
title: "UI Animation Principles"
category: motion
tags: [motion, animation, transitions, feedback]
source: "https://m3.material.io/styles/motion"
source_authority: canonical
ingested: 2026-04-04
validated: true
validator_notes: "Material Design 3 motion guidelines + Google Design (2016)"
---

## Four Purposes of Motion in UI

1. **Informational** - Communicates change. A card expanding shows where the content came from. A loading spinner shows the system is working.

2. **Focused** - Guides attention. Motion draws the eye to what changed. A new notification slides in from the edge.

3. **Expressive** - Communicates brand personality. Playful bounces vs professional fades.

4. **Efficient** - Feels quick and responsive. Avoids unnecessary delay. Motion should never block the user.

## M3 Transition Patterns

| Pattern | Duration | Use |
|---------|----------|-----|
| Container transform | 300ms | Opening/closing cards, expanding list items |
| Shared axis | 300ms | Navigating between related pages (forward/back) |
| Fade through | 200ms | Switching between unrelated content |
| Fade | 150ms | Simple appear/disappear |

## Duration Guidelines

- **Micro-interactions** (button press, toggle): 100-200ms
- **Standard transitions** (page change, modal open): 200-350ms
- **Complex transitions** (layout reflow, multi-element): 300-500ms
- **Never exceed 500ms** for UI transitions - it feels sluggish

## Easing

- **Standard (ease-in-out)**: Most transitions
- **Deceleration (ease-out)**: Elements entering the screen
- **Acceleration (ease-in)**: Elements leaving the screen
- **Never use linear easing** for UI motion - it feels mechanical

## When to apply
- Evaluate transition timing and easing
- Check that motion serves a purpose (information, focus, expression, efficiency)
- Verify reduced motion support (prefers-reduced-motion)
