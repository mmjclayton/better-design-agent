# Design Critique Report (Multi-Agent Analysis)

This report was produced by four specialized agents analysing the design in parallel, plus a deterministic WCAG 2.2 checker.

---

## WCAG 2.2 Automated Audit

**Score: 44.4%** (4 pass, 4 fail, 2 warning, 43 total violations)

### Failures (A/AA - must fix for compliance)

| Criterion | Level | Violations | Details |
|-----------|-------|------------|---------|
| 1.3.1 Info and Relationships (Headings) | A | 2 | 2 unique violations across pages |
| 4.1.2 Name, Role, Value (Form Labels) | A | 3 | 3 unique violations across pages |
| 1.4.11 Non-text Contrast | AA | 10 | 10 unique violations across pages |

**1.3.1 Info and Relationships (Headings)** violations (2 unique elements):
- Heading level skipped: <h1> followed by <h3> "Select an exercise"
- Found 2 <h1> elements - should have exactly one

**4.1.2 Name, Role, Value (Form Labels)** violations (3 unique elements):
- `input` - Input type=file has no label
- `input.program-date-input` - Input type=date has no label
- `input.settings-select` - Input type=number has no label

**1.4.11 Non-text Contrast** violations (10 unique elements):
- `button.top-nav-tab` - "Insights" - ratio: 1.12:1 - #1a1d27 vs #0f1117 = 1.12:1
- `button.time-filter-btn` - "Last 3 Months" - ratio: 1.12:1 - #1a1d27 vs #0f1117 = 1.12:1
- `button.show-all-btn` - "Show All" - ratio: 1.15:1 - #242836 vs #1a1d27 = 1.15:1
- `button.show-all-btn` - "Sort by Est. 1RM" - ratio: 2.67:1 - #4f46e5 vs #1a1d27 = 2.67:1
- `input` - "Search exercises..." - ratio: 1.15:1 - #242836 vs #1a1d27 = 1.15:1
- `button.filter-pill` - "All" - ratio: 2.67:1 - #4f46e5 vs #1a1d27 = 2.67:1
- `button.filter-pill` - "Abs" - ratio: 1.15:1 - #242836 vs #1a1d27 = 1.15:1
- `input.program-date-input` - ratio: 1.15:1 - #242836 vs #1a1d27 = 1.15:1
- `button.settings-btn-option` - "Pounds (lbs)" - ratio: 1.29:1 - #242836 vs #0f1117 = 1.29:1
- `input.settings-select` - ratio: 1.29:1 - #242836 vs #0f1117 = 1.29:1

### AAA Aspirational (nice to have, not required for compliance)

| Criterion | Level | Violations | Details |
|-----------|-------|------------|---------|
| 2.5.5 Target Size (Enhanced) | AAA | 28 | 28 unique violations across pages |


### Warnings

| Criterion | Level | Details |
|-----------|-------|---------|
| 1.3.1 Info and Relationships (Landmarks) | A | Required landmarks present, 1 recommended landmarks missing |
| 2.5.8 Target Size (Minimum) | AA | All elements meet 24px AA minimum, but 7 below 44px recommended |


### Passing

| Criterion | Level | Details |
|-----------|-------|---------|
| 3.1.1 Language of Page | A | lang="en" set on <html> |
| 2.4.1 Bypass Blocks | A | Skip navigation link present |
| 1.4.3 Contrast (Minimum) | AA | All 6 text/background pairs meet AA requirements |
| 2.4.7 Focus Visible | AA | Global :focus-visible rules found () |

---

## Visual Design Analysis

## Visual Analysis

The eye immediately lands on the top navigation bar, which creates a strong horizontal line across all pages. The #4f46e5 accent colour draws attention to the active navigation state, creating a clear focal point. The layout flows vertically with generous whitespace, following a single-column structure that guides the eye downward naturally.

Most pages feel sparse with large empty areas below the fold. The Insights page stands out as the most visually dense, with a grid of metric cards and data visualizations that create visual interest. The About page breaks this pattern with a more content-rich layout featuring structured sections and cards.

## Hierarchy Assessment

**Score: 6/10**

The visual hierarchy works but lacks strength. Page titles like "Workout Logger" and "Training Insights" establish clear primary headings using #e1e4ed text. However, the hierarchy breaks down in several areas:

- The navigation uses inconsistent visual weight - active states in #4f46e5 are clear, but inactive states in #8b8fa3 blend into the background
- Secondary content lacks clear hierarchy - metric cards on Insights use similar text sizes throughout
- Empty states provide no visual guidance about what should happen next

The single program card on multiple pages (Home, Train) creates a weak focal point that doesn't drive action effectively.

## Composition Issues

**Critical spacing problems:**
- Excessive empty space below content on most pages wastes screen real estate
- The single program card feels lost in the vast #0f1117 background
- No clear content boundaries or sections to break up the monotony

**Layout improvements needed:**
- Add more content or reduce page height to eliminate dead space
- Use the #1a1d27 background colour to create elevated surfaces for better hierarchy
- Group related elements more tightly using proximity principles

**Data table issues (Manage page):**
- Good use of alternating row colours for scannability
- Proper alignment of tabular data
- Could benefit from tighter row spacing to reduce overall table height

## Aesthetic Strengths

**Excellent dark mode implementation:** The colour palette follows dark mode best practices perfectly. The #0f1117 base avoids pure black, #e1e4ed text prevents halation, and the #4f46e5 accent has appropriate saturation for dark backgrounds.

**Clean typography rhythm:** Consistent text sizing creates readable hierarchy where it exists. The 16px base font size ensures good readability.

**Effective use of elevation:** The #1a1d27 cards and containers create proper figure-ground separation without relying on shadows.

**Strong navigation pattern:** The horizontal navigation with pill-style active states provides clear wayfinding across the application.

**Data visualization excellence:** The Insights page demonstrates sophisticated use of colour-coded metrics and charts that maintain readability against the dark background.

The visual system is solid but underutilized - the sparse layouts don't take advantage of the well-designed component library and colour system.

---

## Accessibility Deep Dive

# Accessibility Deep Dive

## Critical Findings

### 1. Navigation Tabs Missing ARIA Pattern
**What**: The main navigation uses `role="tablist"` and `role="tab"` but lacks essential ARIA properties
**Why it's wrong**: Violates WAI-ARIA Authoring Practices for Tabs pattern - missing `aria-selected` and `aria-controls`
**Correct implementation**:
```html
<nav role="tablist" aria-label="Main navigation">
  <button role="tab" aria-selected="false" aria-controls="insights-panel" id="insights-tab">Insights</button>
  <button role="tab" aria-selected="true" aria-controls="train-panel" id="train-tab">Train</button>
  <button role="tab" aria-selected="false" aria-controls="exercises-panel" id="exercises-tab">Exercises</button>
</nav>
<div role="tabpanel" id="train-panel" aria-labelledby="train-tab">
  <!-- Train content -->
</div>
```
**Severity**: 3 (Major - breaks screen reader navigation)

### 2. Filter Pills Acting as Radio Buttons Without Proper Semantics
**What**: Exercise filter buttons ("All", "Abs", "Back", "Biceps") behave like radio buttons but use generic `button` elements
**Why it's wrong**: Screen readers can't understand this is a single-select group. Missing `role="radiogroup"` and `aria-checked`
**Correct implementation**:
```html
<div role="radiogroup" aria-labelledby="filter-label">
  <span id="filter-label" class="sr-only">Filter exercises by muscle group</span>
  <button role="radio" aria-checked="true">All</button>
  <button role="radio" aria-checked="false">Abs</button>
  <button role="radio" aria-checked="false">Back</button>
  <button role="radio" aria-checked="false">Biceps</button>
</div>
```
**Severity**: 3 (Major - users can't understand selection state)

### 3. Data Visualization Charts Completely Inaccessible
**What**: The "Strength Trend by Muscle Group" chart appears to be canvas/SVG without any accessibility markup
**Why it's wrong**: Violates WCAG 1.1.1 - complex data visualizations need text alternatives or data tables
**Correct implementation**:
```html
<div role="img" aria-labelledby="chart-title" aria-describedby="chart-desc">
  <h3 id="chart-title">Strength Trend by Muscle Group</h3>
  <p id="chart-desc">Bar chart showing percentage change in estimated 1RM by muscle group. Hamstrings increased 43.6%, Biceps 37.9%, Shoulders 24.5%, Triceps 22%, Chest 20.9%, Abs 4%.</p>
  <!-- Chart visualization -->
</div>
<!-- Or provide a data table alternative -->
<table aria-label="Strength trend data">
  <caption>Percentage change in estimated 1RM by muscle group</caption>
  <thead>
    <tr><th>Muscle Group</th><th>% Change</th></tr>
  </thead>
  <tbody>
    <tr><td>Hamstrings</td><td>+43.6%</td></tr>
    <tr><td>Biceps</td><td>+37.9%</td></tr>
    <!-- etc -->
  </tbody>
</table>
```
**Severity**: 4 (Critical - data completely unavailable to screen readers)

### 4. Exercise List Missing List Semantics
**What**: The exercise list (Ab Crunch, Barbell Decline Chest Press, etc.) appears to be individual buttons without list structure
**Why it's wrong**: Screen readers can't announce list context ("item 1 of 15") or provide list navigation shortcuts
**Correct implementation**:
```html
<ul role="list" aria-label="Exercise list">
  <li>
    <button type="button" aria-describedby="ab-crunch-category">
      Ab Crunch
      <span id="ab-crunch-category" class="category-tag">Abs</span>
    </button>
  </li>
  <li>
    <button type="button" aria-describedby="barbell-decline-category">
      Barbell Decline Chest Press
      <span id="barbell-decline-category" class="category-tag">Chest</span>
    </button>
  </li>
</ul>
```
**Severity**: 2 (Moderate - affects navigation efficiency)

### 5. Loading State Missing Live Region
**What**: "Computing overload rates..." text appears without `aria-live` announcement
**Why it's wrong**: Screen reader users won't know the system is processing their request
**Correct implementation**:
```html
<div aria-live="polite" aria-label="Loading status">
  Computing overload rates...
</div>
```
**Severity**: 2 (Moderate - affects user feedback)

## Component Intent Analysis

1. **Main Navigation**: Currently uses tab semantics but behaves more like navigation links. If these are true tabs (showing/hiding panels), the ARIA implementation needs completion. If they're navigation links, remove `role="tab"` and use standard navigation.

2. **Filter Pills**: Acting as radio buttons (single selection) but implemented as independent buttons. Should use `role="radiogroup"` pattern.

3. **Exercise List**: Behaving as a selectable list but missing list semantics and selection state management.

4. **Workout Program Card**: The "HST 13" card appears clickable but lacks proper button semantics or selection state.

## Screen Reader Narrative

A VoiceOver user would experience:

1. **Navigation**: "Tab, Insights, tab, Train selected, tab, Exercises..." - but no indication of what content each tab controls
2. **Filter section**: "Button, All, button, Abs, button, Back..." - no indication these are mutually exclusive options
3. **Exercise list**: Individual buttons with no list context or count
4. **Charts**: Complete silence - no indication that data visualization exists
5. **Loading states**: No announcement when data is being computed

The experience breaks down primarily at data visualization (complete information loss) and component relationships (tabs without panels, filters without grouping).

## Recommendations

1. **Immediate**: Add `aria-live="polite"` to loading states and `role="img"` with descriptions to charts
2. **High Priority**: Complete the tabs pattern with `aria-controls` and `aria-selected`, or convert to navigation links
3. **Medium Priority**: Implement radiogroup pattern for filters and list semantics for exercises
4. **Consider**: Adding skip links within long exercise lists and keyboard shortcuts for common actions

---

## Design System Analysis

## Token Architecture Analysis

This system demonstrates a **hybrid layered approach** with both primitive tokens (`--color-bg-base`) and semantic aliases (`--bg`, `--surface`). The architecture has three distinct layers:

1. **Primitive tokens**: Full semantic names like `--color-bg-base`, `--color-text-primary`
2. **Alias tokens**: Shortened references like `--bg: var(--color-bg-base)`
3. **Component-specific tokens**: Domain tokens like `--color-muscle-biceps`, `--tooltip-bg`

**Naming conventions** follow a consistent `--[category]-[context]-[variant]` pattern for primitives, but aliases break this consistency with abbreviated names. **Token coverage** is excellent—nearly all computed values trace back to tokens, with minimal hardcoding detected.

## Root Cause Findings

**No critical visual issues detected** in the provided screenshot. The dark theme implementation appears consistent with token values:
- Background hierarchy properly established via `--color-bg-base` (#0f1117) → `--color-bg-surface` (#1a1d27)
- Text contrast adequate with `--color-text-primary` (#e1e4ed) on dark backgrounds
- Interactive elements use proper accent tokens (`--color-accent-primary`: #4f46e5)

## Token Audit Table

| Token | Value | Usage | Issue |
|-------|-------|-------|-------|
| `--color-text-secondary` | `#8b8fa3` | 26 elements | None - proper contrast ratio |
| `--color-text-primary` | `#e1e4ed` | 20 elements | None - high contrast |
| `--color-accent-light` | `#a78bfa` | 8 elements | None - adequate contrast |
| `--type-body` | `16px` | 37 elements | None - appropriate base size |
| `--space-md` | `16px` | 17 uses | None - consistent spacing |
| `--radius-sm` | `6px` | 12 uses | None - consistent radius |

## Duplication Report

**Semantic duplicates** (multiple tokens resolving to identical values):
- `--color-error` and `--error` both resolve to `#ef4444`
- `--color-error-tint` and `--error-tint` both resolve to `#ef444430`
- `--color-info` and `--blue` both resolve to `#4a90e2`
- `--color-warning` and `--accent3` both resolve to `#f0a050`
- `--color-mint` and `--accent2` both resolve to `#58d5a0`

**Consolidation opportunities**: The alias tokens (`--error`, `--blue`, `--accent2`, `--accent3`) appear to be legacy remnants and could be deprecated in favor of the semantic naming convention.

## Maturity Rating

**Established (3/5)** - This system demonstrates solid design system fundamentals with room for optimization:

**Strengths:**
- Comprehensive token coverage across color, spacing, typography, and radius
- Consistent primitive naming convention
- Proper semantic layering with contextual tokens
- Domain-specific tokens for specialized use cases (muscle groups)

**Areas for improvement:**
- Mixed naming conventions (primitives vs aliases)
- Token duplication without clear deprecation strategy
- Missing component-level tokens for complex UI patterns
- No documented token hierarchy or usage guidelines evident

## Recommendations

### Priority 1: Consolidate Duplicate Tokens
- **Deprecate alias tokens**: Remove `--error`, `--blue`, `--accent2`, `--accent3` in favor of semantic equivalents
- **Update references**: Migrate all instances to use `--color-error`, `--color-info`, `--color-mint`, `--color-warning`

### Priority 2: Standardize Naming Convention
- **Eliminate shortened aliases**: Replace `--bg`, `--surface`, `--text` with full semantic names
- **Maintain consistency**: All tokens should follow `--[category]-[context]-[variant]` pattern

### Priority 3: Expand Component Token Layer
- **Add interactive state tokens**: `--color-button-hover`, `--color-button-active`, `--color-button-disabled`
- **Create focus tokens**: `--color-focus-ring`, `--space-focus-offset` for accessibility

### Priority 4: Optimize Spacing Scale
- **Address hardcoded values**: The `14px` spacing (2 uses) and `56px` spacing (1 use) should be tokenized if usage increases
- **Consider t-shirt sizing**: Evaluate if current `xs/sm/md/lg/xl/2xl` scale covers all use cases effectively

The system shows strong foundational work but would benefit from consolidation and standardization to reach **Mature** status.

---

## Interaction Quality Analysis

## State Audit Results

### Navigation Tabs (Top Bar)
- **Inactive tabs** (`button.top-nav-tab`): ✅ Good hover state (background darkens), ✅ Good focus state (purple outline), ✅ Proper cursor pointer
- **Active tab** (`button.top-nav-tab.active` "Train"): ❌ **Missing hover state** - no visual response on hover, ✅ Good focus state, ✅ Proper cursor pointer

### Skip Link
- **Skip link** (`a.skip-link`): ⚠️ **Untested states** - no hover/focus data captured, likely needs verification

### Program Card
- **HST 13 card**: ⚠️ **No interactive state data** - appears clickable (has chevron indicator) but not captured in test results

## Missing Interaction Patterns

1. **Inconsistent hover behavior**: Active navigation tab lacks hover feedback while inactive tabs provide it
2. **Card interaction unclear**: The HST 13 program card appears interactive (chevron suggests navigation) but has no captured hover/focus states
3. **No loading states**: No indication of what happens during program selection or navigation
4. **No error states**: No visible error handling for failed navigation or program loading

## Affordance Issues

1. **Active tab hover inconsistency**: Users expect consistent hover feedback across all interactive elements. The active "Train" tab should still provide hover feedback even when selected.

2. **Program card affordance unclear**: The HST 13 card has a chevron suggesting it's clickable, but without hover states, users may be uncertain about its interactivity.

3. **Navigation pattern follows conventions**: Tab-style navigation is appropriate and follows web platform expectations.

## Recommendations

### High Priority
1. **Add hover state to active navigation tab** - Even selected tabs should provide hover feedback for consistency. Consider a subtle background change or opacity shift.

2. **Implement program card hover states** - If the HST 13 card is interactive, add hover feedback (background change, subtle elevation, cursor pointer).

### Medium Priority  
3. **Add loading states** - When users click navigation tabs or program cards, show loading indicators to provide feedback during transitions.

4. **Verify skip link functionality** - Ensure the skip link has proper focus states and keyboard navigation support.

### Low Priority
5. **Consider active state feedback** - Add brief active/pressed states to navigation tabs for tactile feedback during clicks.

The navigation follows good interaction patterns overall, but the inconsistent hover behavior on the active tab breaks user expectations and should be addressed first.

---

## Interaction Test Report

**Results:** 2 pass, 1 fail, 2 warning/skip

### Failures

- **Responsive layout**: 2 issues across breakpoints

### Passing

- **Focus indicator visibility**: All 8 focusable elements have visible focus indicators
- **Tab order**: 8 elements reachable via keyboard in logical order

### Keyboard Tab Order

Elements reached by pressing Tab repeatedly:

1. `a.skip-link` "Skip to main content" - focus: visible
2. `button.top-nav-tab` "Insights" - focus: visible
3. `button.top-nav-tab` "Exercises" - focus: visible
4. `button.top-nav-tab` "Train" - focus: visible
5. `button.top-nav-tab` "Programs" - focus: visible
6. `button.top-nav-tab` "Manage" - focus: visible
7. `button.top-nav-tab` "Settings" - focus: visible
8. `button.top-nav-tab` "About" - focus: visible

### Responsive Breakpoint Issues

- **375px**: 6 text elements below 12px on mobile - may be unreadable
- **375px**: 1 interactive elements below 44x44px touch target on mobile


---

## Component Inventory & Scoring

**Overall: 11/30 (36.7%)**

**3 components detected**

| Component | Type | Score | Issues |
|-----------|------|-------|--------|
| Forms | form | 3/10 (30%) | 1 issues |
| Navigation | nav | 4/10 (40%) | 3 issues |
| Buttons | button-group | 4/10 (40%) | 4 issues |

### Navigation (nav) - 4/10 (40%)

Selector: `button.top-nav-tab`

**Issues:**
- No active/current state indicator
- 7 nav items below 44px touch target
- 3/4 tested nav items missing hover states

**Strengths:**
- Uses `<nav>` landmark
- All nav items have focus styles (verified by state test)

### Forms (form) - 3/10 (30%)

Selector: `input.program-date-input`

**Issues:**
- 13/10 inputs missing labels

**Strengths:**
- All form inputs meet touch target minimum
- No placeholder-only labelling detected

### Buttons (button-group) - 4/10 (40%)

Selector: `button.top-nav-tab`

**Issues:**
- 7/19 buttons below 44px touch target
- 4 buttons missing hover
- 4 buttons missing focus
- 6 buttons fail non-text contrast

**Strengths:**
- All buttons have accessible labels
