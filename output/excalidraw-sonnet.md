# Design Critique: Excalidraw (excalidraw.com)

**URL:** https://excalidraw.com
**Date:** 4 April 2026
**Viewport:** 1367x1029px (desktop, Chrome)
**State audited:** Initial load / welcome screen (unauthenticated)
**Model:** claude-sonnet-4-6

---

## Summary

Excalidraw has a confident, distinctive visual identity. The hand-drawn aesthetic is immediately legible and the canvas-first layout correctly subordinates UI chrome to the drawing surface. The design token system underneath is sophisticated - proper semantic layering, a coherent surface scale, and dark mode tokens baked in.

The score is materially dragged down by accessibility failures that go beyond cosmetic. The primary drawing surface (the `<canvas>` element) is invisible to assistive technology. Welcome screen instructional text fails WCAG AA contrast by a factor of more than 2x. There is no `<main>` landmark and no skip link. None of these require visual redesign - they are semantic HTML and token-level fixes. Resolving the top five critical issues would move this from a 57 to approximately a 76.

---

## Score: 57 / 100

| Dimension | Score | Notes |
|---|---|---|
| Visual hierarchy | 8/10 | Canvas dominates correctly; welcome screen hierarchy slightly confused |
| Typography | 6/10 | Good font stack; severe contrast failures on instructional text |
| Colour/contrast | 3/10 | Multiple critical WCAG failures; welcome text at 1.98:1 |
| Spacing/layout | 8/10 | Consistent proportions; toolbar padding tight but coherent |
| Accessibility (WCAG 2.2) | 3/10 | Canvas inaccessible; no skip link; no `<main>`; mixed aria-hidden |
| Interaction patterns | 7/10 | Mostly intuitive; semantic issues with checkbox-as-toggle and welcome dialog |
| Consistency | 7/10 | Good token usage; naming duplication in the system |
| Information architecture | 7/10 | Logical zones; welcome screen overloaded |

## Critical Issues

### 1. Welcome screen and canvas hint text: 1.98:1 contrast - fails WCAG AA at every level

**Elements:** "Your drawings are saved in your browser's storage..." (3-line warning), "Pick a tool & Start drawing!" (canvas hint), "Export, preferences, languages, ..." (hamburger hint), "Shortcuts & help" footer label.

**Colour:** All rendered in `#b8b8b8` (CSS token `--color-gray-40`) on white (`#ffffff`).

**Measured ratio:** 1.98:1. WCAG 2.2 AA requires 4.5:1 for normal text and 3:1 for large text. This fails both thresholds.

**Fix:** Replace all instructional text colour with a minimum of `#767676` (4.54:1) or, better, `--color-gray-70` (`#5c5c5c`, ~7.2:1). The on-surface token `--color-on-surface: #1b1b1f` (17.17:1) should be the default for any text that carries functional information. Reserve `--color-gray-40` (`#b8b8b8`) exclusively for decorative non-text elements.

### 2. Keybinding/shortcut hint text: 4.29:1 - fails AA for normal text

**Elements:** "Cmd+O" and "?" labels on the welcome screen; tool shortcut numbers beneath tool icons.

**Colour:** `#7a7a7a` (CSS token `--color-gray-60`) on white (`#ffffff`).

**Measured ratio:** 4.29:1. Fails SC 1.4.3 AA normal text (requires 4.5:1).

**Fix:** Use `--color-gray-70` (`#5c5c5c`, ~7.2:1) for all shortcut labels.

### 3. Canvas element is completely inaccessible to assistive technology

**Element:** `<canvas width="1367" height="1029">` - the primary application surface.

**Issue:** No `role`, no `aria-label`, no `tabindex`. Screen reader users receive no indication that a drawing surface exists.

**Fix:**
```html
<canvas role="application" aria-label="Excalidraw drawing canvas" tabindex="0"></canvas>
```

Additionally, add an `aria-live="polite"` region:
```html
<div aria-live="polite" aria-atomic="true" class="sr-only" id="canvas-announcer"></div>
```

### 4. No `<main>` landmark and no skip link

**Issue (a):** No `<main>` or `role="main"`. Screen reader users navigating by landmark cannot jump to the primary content area.

**Issue (b):** No skip-to-content link exists. Keyboard users must Tab through all 12+ toolbar controls.

**Fix:** Wrap canvas in `<main>`, add skip link as first focusable element.

### 5. Welcome screen is not a dialog - no focus trap, no role

**Issue:** The welcome screen overlay has no `role="dialog"`, no `aria-modal="true"`, and no focus trap.

**Fix:**
```html
<div role="dialog" aria-modal="true" aria-labelledby="welcome-title">
```
Add JavaScript focus trap and return focus to canvas on dismiss.

### 6. Toolbar radio group has no group semantics

**Issue:** Tool selection radio inputs are not wrapped in `<fieldset>/<legend>` or `role="group"`.

**Fix:**
```html
<div role="group" aria-label="Drawing tools">
  <!-- radio inputs with labels -->
</div>
```

## Improvements

### Typography

| Element | Current | Issue | Fix |
|---|---|---|---|
| UI font | Assistant, system-ui stack | Appropriate | No change needed |
| Welcome warning text | 16px, `#b8b8b8` | 1.98:1 contrast | Darken to `#5c5c5c` minimum |
| Tool shortcut numbers | ~10px subscript, `#1b1b1f` | 17.17:1 contrast - passes. But 10px is below minimum readable size. | Increase to 12px |
| `<kbd>` element usage | Inconsistent | Only some shortcuts use `<kbd>`. | Wrap all keyboard shortcut references in `<kbd>` |

### Colour and Contrast

| Pair | FG | BG | Ratio | AA Normal | AA Large | Fix |
|---|---|---|---|---|---|---|
| Welcome text | #b8b8b8 | #ffffff | **1.98:1** | FAIL | FAIL | `#5c5c5c` (7.2:1) |
| Keyboard shortcuts | #7a7a7a | #ffffff | **4.29:1** | FAIL | PASS | `#5c5c5c` (7.2:1) |
| Link colour | #1c7ed6 | #ffffff | **4.20:1** | FAIL | PASS | `#1864ab` (~5.5:1) |
| Brand on primary-light | #6965db | #e3e2fe | **3.70:1** | FAIL | PASS | Acceptable for icons only |
| Brand on white | #6965db | #ffffff | **4.68:1** | PASS | PASS | Acceptable |
| Body text | #1b1b1f | #ffffff | **17.17:1** | PASS | PASS | Good |
| Active indicator | #4440bf | #e3e2fe | **6.07:1** | PASS | PASS | Good |

### SVG Icon Accessibility

Decorative SVG icons inconsistently marked. Three of five toolbar SVGs lack `aria-hidden`.

**Fix:** Add `aria-hidden="true" focusable="false"` to all decorative SVGs.

### Library Sidebar Toggle Semantics

Library sidebar controlled via `<input type="checkbox">`. Should be `<button aria-expanded>`.

**Fix:**
```html
<button type="button" aria-expanded="false" aria-controls="library-sidebar" aria-label="Toggle library">
```

## Interaction State Audit

| Element | Hover | Selected/Active | Focus | Issues |
|---|---|---|---|---|
| Toolbar tool buttons | Background tint | `#f1f0ff` + border | `box-shadow: 0 0 0 2px #a5d8ff` | Focus ring defined, verify coverage |
| Welcome screen buttons | No hover state observed | N/A | Not confirmed | Verify `:focus-visible` |
| Canvas element | No pointer cursor | N/A | No focus indicator | See Critical Issue 3 |

**Focus highlight colour contrast:** `#a5d8ff` on white = ~1.5:1 - the ring itself is low contrast. Use `2px solid #4440bf` (6.07:1 on white).

## Accessibility Audit (WCAG 2.2)

### Semantic HTML and Landmarks

| Check | Result | Detail |
|---|---|---|
| `<html lang="en">` | PASS | Set correctly |
| `<main>` | FAIL | Not present |
| `<header>` | PASS | Present |
| `role="contentinfo"` | PASS | Present |
| `role="region"` for toolbar | PASS | Present |
| Skip link | FAIL | Not present |
| Dialog semantics on welcome screen | FAIL | No `role="dialog"` |
| Canvas accessibility | FAIL | No `role`, no `aria-label` |
| Toolbar radio group labelled | FAIL | No `<fieldset>/<legend>` |
| SVG `aria-hidden` | FAIL (inconsistent) | 3 of 5 SVGs lack `aria-hidden` |
| Form input labels | PASS | Tool radios have `<label>` elements |

### Touch Targets

| Element | Size | 24px Min | 44px Recommended |
|---|---|---|---|
| Toolbar buttons | 40x40px | PASS | Marginal (-4px) |
| Welcome menu items | ~300x46px | PASS | PASS |

### Focus Management

| Check | Result |
|---|---|
| Focus visible on toolbar buttons | PASS - `box-shadow: 0 0 0 2px #a5d8ff` |
| Focus highlight colour contrast | `#a5d8ff` on white = ~1.5:1 - LOW |
| Focus trapped in welcome dialog | FAIL |
| Canvas receives keyboard focus | FAIL |

### prefers-reduced-motion / prefers-color-scheme

| Feature | Rules found | Status |
|---|---|---|
| `prefers-reduced-motion` | 0 | **Missing** |
| `prefers-color-scheme` | 0 | **Missing** |

## Strengths

- **Canvas-first layout.** Drawing surface dominates correctly.
- **Mature design token system.** Dual-layer architecture (primitive -> semantic) with dark mode tokenised.
- **Toolbar radio semantics.** Correct `<input type="radio">` with `<label>`.
- **Consistent border radius.** 8px for major, 6px for minor.
- **Elevation via box-shadow.** Three-level shadow on toolbar.
- **Keyboard shortcut discoverability.** Inline display.
- **`lang="en"` set correctly.**
- **Distinctive visual language.** Hand-drawn aesthetic.
- **Focus ring colour defined.** Foundation exists - needs wider application.

## Design System Assessment

### Token Architecture

Dual-layer approach:

**Layer 1 - Primitives:**
```
--color-gray-40: #b8b8b8
--color-gray-60: #7a7a7a
--color-gray-70: #5c5c5c
```

**Layer 2 - Semantics:**
```
--color-on-surface: #1b1b1f
--text-primary-color: var(--color-on-surface)
--keybinding-color: var(--color-gray-40)    ← ROOT CAUSE of contrast failure
```

**Gap:** `--keybinding-color` resolves to `--color-gray-40` (`#b8b8b8`). This one token is the primary source of the contrast failure. Changing it fixes the most widespread issue.

**Action:** Create `--color-text-secondary: var(--color-gray-70)` and replace all text usages of `--color-gray-40`.

### Token Duplication

| Token A | Token B | Resolved Value |
|---|---|---|
| `--island-bg-color` | `--color-surface-lowest` | #ffffff |
| `--island-bg-color-alt` | `--color-surface-lowest` | #ffffff |
| `--default-bg-color` | `--color-surface-lowest` | #ffffff |
| `--popup-bg-color` | `var(--island-bg-color)` | #ffffff |

**Action:** Deprecate `--island-bg-color` in favour of `--color-surface-lowest`.

### Component Inconsistencies

| Issue | Detail | Fix |
|---|---|---|
| Dual upgrade CTA | "Excalidraw+" and "Sign up" link to same URL | Standardise to one label |
| Checkbox for sidebar toggle | Uses `<input type="checkbox">` | Replace with `<button aria-expanded>` |
| Mixed `<kbd>` / `<span>` for shortcuts | Inconsistent | Standardise to `<kbd>` |
| `--button-gray-*` parallel scale | Different values from main gray scale | Consolidate |

## Recommended Next Actions

1. **Token fix (1 line):** Change `--keybinding-color` from `var(--color-gray-40)` to `var(--color-gray-70)`.
2. **Canvas semantics (5 lines):** Add `role="application"`, `aria-label`, `tabindex="0"`.
3. **Landmark fix (1 line):** Wrap canvas in `<main>`.
4. **Skip link (3 lines):** Add visually-hidden-until-focused skip link.
5. **Welcome screen dialog (4 lines + JS):** Add `role="dialog"`, focus trap.
6. **Token consolidation:** Deprecate duplicate tokens.
