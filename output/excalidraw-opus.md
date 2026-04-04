# Design Critique: Excalidraw (excalidraw.com)

**Date:** 4 April 2026
**Scope:** Default welcome/canvas view, desktop (1367x977 viewport)
**Model used:** Claude Opus 4.6

---

## Summary

Excalidraw is a well-known open-source whiteboard tool with a distinctive hand-drawn aesthetic. The core canvas interaction is strong, and the toolbar design is clean and scannable. However, the welcome screen suffers from critically low text contrast that fails WCAG AA at every level, the canvas element lacks any semantic accessibility, and the application has no `<main>` landmark, no skip-link, and no `aria-live` regions for state announcements. The information architecture is minimal but functional for a single-purpose tool.

**Score: 62/100**

## Critical Issues

| # | Issue | Severity | Element | Detail | Fix |
|---|-------|----------|---------|--------|-----|
| 1 | **Welcome heading text fails WCAG AA** | Critical | `.welcome-screen-center__heading` (#b8b8b8 on #fff) | Contrast ratio **1.98:1** - fails AA normal (4.5:1), fails AA large (3:1). Completely invisible to low-vision users. | Darken to at least #767676 (4.54:1) or #595959 (7.05:1 for AAA). |
| 2 | **Welcome menu text fails WCAG AA** | Critical | `.welcome-screen-menu-item__text` (#999 on #fff) | Contrast ratio **2.85:1** - fails AA normal and AA large text. The "Open", "Help", "Live collaboration", and "Sign up" links are unreadable for many users. | Darken to #767676 minimum, or #595959 for comfortable reading. |
| 3 | **Canvas has no ARIA role or label** | Critical | `<canvas>` element (1367x977) | The primary interactive surface has no `role`, no `aria-label`, no `tabindex`. Screen reader users cannot identify or interact with the drawing canvas at all. | Add `role="application"`, `aria-label="Drawing canvas"`, and `tabindex="0"`. Implement keyboard interaction model within the canvas. |
| 4 | **No `<main>` landmark** | Critical | Document structure | The page has `<header>` and `<footer>` but no `<main>`. Screen reader landmark navigation skips the entire application workspace. | Wrap the canvas and toolbar region in `<main role="main">`. |
| 5 | **No skip-link** | Critical | Document | No skip-to-content link exists. Keyboard users must tab through every toolbar button to reach the canvas. | Add `<a class="skip-link" href="#canvas">Skip to canvas</a>` visually hidden until focused. |
| 6 | **Keyboard shortcut hint text fails WCAG AA** | Critical | Shortcut labels e.g. "Cmd+O", "?" (#999 on #fff) | Same 2.85:1 ratio as menu text. Keyboard shortcut hints are decorative-looking but carry functional information. | Darken to #767676 minimum. |

## Improvements

### Visual Hierarchy

| Finding | Detail | Recommendation |
|---------|--------|----------------|
| **Eye draws to logo first, not to actions** | The Excalidraw logo and rocket icon at 36px dominate the centre, but the actual call-to-action ("Pick a tool & Start drawing!") is smaller and lighter, competing poorly. | Increase the CTA text weight or size, or reduce the logo prominence. |
| **Toolbar is well-positioned but visually disconnected** | The floating toolbar at top-centre is clean, but its light grey background (#ececf4) is close to the white canvas, reducing visual separation. | Add a subtle drop shadow to lift the toolbar from the canvas. |
| **Footer controls are orphaned** | Zoom controls (bottom-left) and Help button (bottom-right) are 900+ pixels apart with no visual connection. | Group related controls more tightly. |
| **Hamburger menu hint text floats awkwardly** | "Export, preferences, languages, ..." is positioned with a hand-drawn arrow pointing at the hamburger menu. | Move this guidance into a tooltip on hover/focus. |

### Typography

| Element | Current | Issue | Recommendation |
|---------|---------|-------|----------------|
| Body font | System font stack, 16px | Appropriate | No change needed. |
| Welcome heading | "Excalifont" (custom), 18px, #b8b8b8 | Custom hand-drawn font at low contrast is decorative but harms readability. | Keep the font but increase to at least #767676 and 20px. |
| Menu items | 14px, #999 | Below minimum readable size for secondary actions at this contrast. | Increase to 15-16px and darken to #595959. |
| Toolbar shortcut numbers | ~10px subscript, #1b1b1f | Small but adequate contrast (17.17:1). Hard to read at size. | Increase to 11-12px. |
| Zoom percentage | 14px, standard weight | Readable. | No change needed. |

### Colour and Contrast

| Pair | Foreground | Background | Ratio | WCAG AA (normal) | WCAG AA (large) | WCAG AAA | Verdict |
|------|-----------|------------|-------|-------------------|------------------|----------|---------|
| Welcome heading | #b8b8b8 | #ffffff | **1.98:1** | Fail | Fail | Fail | Must fix |
| Menu text | #999999 | #ffffff | **2.85:1** | Fail | Fail | Fail | Must fix |
| Shortcut hints | #999999 | #ffffff | **2.85:1** | Fail | Fail | Fail | Must fix |
| Body/icon text | #1b1b1f | #ffffff | **17.17:1** | Pass | Pass | Pass | Good |
| Toolbar icons | #1b1b1f | #ececf4 | **14.61:1** | Pass | Pass | Pass | Good |
| Share button | #ffffff | #6965db | **4.68:1** | Pass | Pass | Fail | Acceptable |

## Interaction State Audit

| Element | Hover | Active/Selected | Focus | Disabled | Issues |
|---------|-------|-----------------|-------|----------|--------|
| **Tool radio buttons** | Background lightens | Selected tool shows filled background (#ececf4) with blue accent | Focus indicator not visually apparent | N/A | Focus ring is absent or near-invisible. |
| **Welcome menu buttons** | No visible hover state observed | N/A | Not reachable via keyboard (focus trapped) | N/A | Add hover background and ensure keyboard focusability. |
| **Hamburger menu** | Subtle background change | N/A | Not tested | N/A | Needs visible focus ring. |
| **Share button** | N/A | N/A | Not tested | N/A | Good visual weight. Needs focus ring. |

**Key interaction gaps:**
- Focus was trapped on the container `<div>` after repeated Tab presses
- No visible focus indicators were observed on any element during keyboard navigation testing
- No `aria-live` regions exist (0 found)

## Accessibility Audit (WCAG 2.2)

### Semantic HTML and Landmarks

| Requirement | Status | Detail | Fix |
|-------------|--------|--------|-----|
| `<header>` / banner | Present (1) | Contains the H1. | Adequate. |
| `<nav>` / navigation | **Missing** | The toolbar functions as navigation between tools but has no nav landmark. | Wrap toolbar in `<nav aria-label="Drawing tools">`. |
| `<main>` | **Missing** | No main landmark. | Add `<main>` wrapping the canvas workspace. |
| `<footer>` / contentinfo | Present (1) | Contains zoom and action controls. | Adequate. |
| `<aside>` | Missing | Side panels not semantically marked. | Wrap Library panel in `<aside>`. |
| Skip link | **Missing** | No mechanism to bypass toolbar. | Add a skip link targeting the canvas. |

### Touch Targets (WCAG 2.2 SC 2.5.8)

| Element | Size | Minimum (AA) | Verdict |
|---------|------|--------------|---------|
| Toolbar tool buttons | 40x40px | 24x24px (AA), 44x44px (enhanced) | Passes AA minimum but fails enhanced. |
| Hamburger menu | 40x40px | 24x24px | Passes AA. |
| Zoom +/- buttons | ~32x32px | 24x24px | Passes AA but tight. |
| Undo/Redo buttons | ~32x32px | 24x24px | Passes AA but tight. |
| Help button | ~32x32px | 24x24px | Passes AA. |

### prefers-reduced-motion / prefers-color-scheme

| Feature | CSS rules found | Status |
|---------|----------------|--------|
| `prefers-reduced-motion` | 0 | **Missing** |
| `prefers-color-scheme` | 0 | **Missing** |

## Strengths

- **Distinctive visual identity.** The hand-drawn aesthetic differentiates it from competitors.
- **Clean, minimal toolbar.** Well-organised with radio-button semantics.
- **Good form labelling.** Every toolbar input has proper `<label>` with `aria-label`.
- **Correct heading hierarchy.** H1 for the page, H2 for sections.
- **Generous welcome menu hit targets.** 300x46px - far exceeding minimums.
- **Keyboard shortcut discoverability.** Shortcuts shown inline.
- **Restrained colour palette.** Avoids visual noise.

## Design System Assessment

| Dimension | Assessment |
|-----------|-----------|
| **Colour tokens** | No CSS custom properties detected for colour. Hard-coded. |
| **Spacing scale** | Two sizes (40px, ~32px) without clear scale. |
| **Typography scale** | Three sizes (36px, 18px, 14px). No modular scale. |
| **Component consistency** | Different component patterns (radio, buttons, icon buttons). |
| **Icon system** | Inline SVGs with consistent stroke width. Good. |
| **Motion/animation** | No `prefers-reduced-motion` support. |

## Priority Recommendations

1. **Fix contrast failures immediately.**
2. **Make the canvas keyboard-accessible.**
3. **Fix focus traversal and visibility.**
4. **Add missing landmarks.**
5. **Add `aria-live` regions.**
