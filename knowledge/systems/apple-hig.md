---
id: sys-004
title: "Apple Human Interface Guidelines Key Principles"
category: systems
tags: [apple, hig, design-system, ios, platform-conventions]
source: "https://developer.apple.com/design/human-interface-guidelines"
source_authority: canonical
ingested: 2026-04-04
validated: true
validator_notes: "Apple's living specification for iOS, macOS, watchOS, visionOS"
---

## Design Themes

1. **Clarity** - Text is legible at every size. Icons are precise and lucid. Adornments are subtle and appropriate. Focus on functionality drives the design.

2. **Deference** - Fluid motion and a crisp interface help people understand and interact with content while never competing with it.

3. **Depth** - Distinct visual layers and realistic motion convey hierarchy, impart vitality, and facilitate understanding.

## Key Platform Conventions

### Touch Targets
- Minimum 44x44 points for all tappable elements
- Provide adequate spacing between interactive elements

### Navigation
- Use standard patterns: Navigation bar, tab bar, sidebar
- Tab bar: 5 items maximum, always visible
- Back button: always available for hierarchical navigation
- Large titles: use for top-level navigation destinations

### Typography (SF Pro)
- Dynamic Type: support all 11 text styles
- Minimum 11pt for legibility
- Use system fonts for consistency with platform

### Dark Mode
- Use semantic colours (not hardcoded) to automatically adapt
- Test both appearances
- Avoid pure black - use system background colours

## When to apply
- Evaluating iOS/macOS apps against platform conventions
- Tab bar and navigation pattern evaluation
- Touch target compliance checking
- Dark mode implementation assessment
