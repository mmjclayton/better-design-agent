---
id: mob-003
title: "Platform-Specific Design Conventions"
category: mobile
tags: [platform, ios, android, conventions, mobile]
source: "Apple HIG + Material Design 3"
source_authority: canonical
ingested: 2026-04-04
validated: true
validator_notes: "Synthesised from Apple and Google platform guidelines"
---

## iOS vs Android Key Differences

| Pattern | iOS (Apple HIG) | Android (Material Design) |
|---------|-----------------|--------------------------|
| Navigation | Tab bar (bottom, 5 items max) | Bottom nav or nav drawer |
| Back | System back swipe + nav bar back | System back button/gesture |
| Primary action | Prominent button in content | Floating Action Button (FAB) |
| Alerts | Centre-screen modal with 2 buttons | Centre-screen dialog |
| Toasts/snackbars | Not native pattern | Bottom-anchored snackbar |
| Typography | SF Pro, Dynamic Type required | Roboto or custom, Material type scale |
| Touch targets | 44x44pt | 48x48dp |
| Segmented controls | Native UISegmentedControl | Chips or toggle buttons |

## Cross-Platform Web Apps

When building for both platforms (web apps, PWAs):
1. **Follow the web platform** - Use web conventions (top nav, standard form elements) rather than mimicking a specific mobile OS
2. **Respect OS preferences** - Dark mode, reduced motion, font size
3. **Touch-friendly by default** - Design for touch on all viewports since touch-enabled desktops and laptops are common
4. **Bottom navigation for mobile web** - Matches both iOS and Android conventions

## When to apply
- Evaluating native apps against platform conventions
- Assessing cross-platform web apps for consistency
- Checking that OS-level preferences (dark mode, reduced motion) are respected
- Reviewing navigation patterns against platform standards
