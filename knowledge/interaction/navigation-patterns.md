---
id: int-003
title: "Navigation Design Patterns"
category: interaction
tags: [navigation, information-architecture, interaction, patterns]
source: "Apple Human Interface Guidelines + Cooper et al. About Face (4th ed.)"
source_authority: canonical
ingested: 2026-04-04
validated: true
validator_notes: "Synthesised from Apple HIG and About Face navigation patterns"
---

## Navigation Models

1. **Hierarchical** - Tree structure with parent-child relationships. Best for content with clear categories. Example: Settings app with sections and sub-sections.

2. **Flat** - All top-level sections are peers, accessible from a tab bar. Best for apps with 3-5 equal-priority sections. Example: Instagram (Home, Search, Reels, Shop, Profile).

3. **Content-driven** - Navigation determined by content type and relationships. Best for media and document apps. Example: News apps, media players.

4. **Hub-and-spoke** - Central hub with independent spokes. Best for task-based apps where each section is independent. Example: iOS Home screen.

## Navigation Component Guidelines

| Component | Use When | Max Items |
|-----------|----------|-----------|
| Top nav bar | Desktop apps with 4-8 primary sections | 8 |
| Tab bar (bottom) | Mobile apps with 3-5 primary sections | 5 |
| Sidebar | Content-heavy apps, desktop, 10+ sections | Unlimited (with grouping) |
| Hamburger menu | When space is constrained and discoverability is less critical | Unlimited |
| Breadcrumbs | Deep hierarchies where users need to navigate back | N/A |

## Key Principles

- **Current location must always be clear** - Active states on nav items, breadcrumbs, page titles
- **Primary nav should be persistent** - Don't hide it behind a hamburger on desktop
- **Limit top-level items** - 7 +/- 2 maximum before grouping is needed
- **Consistent placement** - Navigation should be in the same location on every page
- **Predictable labels** - Nav labels should clearly describe the destination content
