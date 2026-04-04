---
id: sys-006
title: "Figma UX/UI Template Reference Standards"
category: systems
tags: [figma, design-system, components, reference, patterns, templates]
source: "Curated Figma UX/UI Template Reference Library (2025-2026)"
source_authority: high
ingested: 2026-04-04
validated: true
validator_notes: "8-category reference covering official and community design systems, UI kits, and accessibility tools"
---

## Authoritative Design System Kits (Pattern Gold Standard)

These official kits define the canonical patterns for their platforms. Use them as the reference standard when evaluating designs:

| System | Components | Key Strengths |
|--------|-----------|---------------|
| Material Design 3 Kit (Google) | 2,000+ | Token architecture, dynamic colour, adaptive navigation |
| iOS 26 UI Kit (Apple) | Full kit | Liquid Glass, SF Symbols, variable collections |
| Carbon v11 (IBM) | 1,800+ | Enterprise accessibility, 4 themes, WCAG compliant by default |
| Polaris v12.2 (Shopify) | Full kit | E-commerce context, component properties and slots |

## Community Design System Standards

| System | Components | Why It's Reference-Quality |
|--------|-----------|---------------------------|
| Untitled UI PRO | 10,000+ | 420+ page examples, variables, Auto Layout 5, SaaS patterns |
| Glow UI | 6,500+ | 440+ variables, SaaS/admin focus, comprehensive state coverage |
| Ant for Figma | 2,100+ | Enterprise tables, token-component-React mapping |
| Tetrisly | Token-first | Design-token-first architecture with Figma + React parity |
| shadcn/ui Kit | Core set | Mirrors headless, accessible React components |

## Pattern Categories for Evaluation

When critiquing a design, compare against these established pattern categories:

### Dashboard & Admin
- Stat cards, data tables, filters, charts, empty states
- Sidebar + main content layout
- Settings pages with segmented controls
- Reference: Glow UI, Untitled UI PRO, Ant for Figma

### E-Commerce
- Product listing, filtering, cart, checkout flows
- Multi-step checkout with error states
- Account management and order history
- Reference: Community e-commerce kits

### Mobile (iOS/Android)
- Tab bar navigation (5 items max iOS, bottom nav Android)
- Touch target compliance (44pt iOS, 48dp Android)
- Thumb zone optimisation for primary actions
- Reference: iOS 26 Kit, Material 3 Kit

### Forms & Inputs
- Input states: default, hover, focus, filled, error, disabled, loading
- Validation patterns: inline on blur, not on submit
- Label placement: top-aligned (fastest completion)
- Reference: Untitled UI, shadcn/ui, Design Library 2025

### Accessibility Annotation
- Heading structure, landmarks, focus order, alt text, ARIA roles
- CVS Health Web Accessibility Annotation Kit is the standard
- EightShapes Include plugin for annotation workflow

## When to apply
- Reference these pattern standards when recommending component implementations
- Compare critique targets against the established patterns from major design systems
- Use as the benchmark for "what good looks like" in each UI category
- Recommend specific templates when a design needs a reference for a pattern it's implementing poorly
