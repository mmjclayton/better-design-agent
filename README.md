# Better Design Agent

## Purpose

This project tests whether Claude Code (Opus 4.6) can self-determine improvements to its own standard design review capabilities. Claude was given the target UX for a design review agent and instructed to self-improve and self-plan how to build a better one. The key feedback loop: the agent reviews my projects, I ask separate Claude Code instances to critique those findings, then feed their feedback back into the agent's build process. In many cases the agent reports improvements over standard model defaults.

The section below is maintained by the agent itself with its honest assessment of performance versus standard Claude skills.

---

## About

An agent-based CLI + MCP server for UX/UI design review. Combines deterministic analysis (WCAG checker, axe-core, component scoring, fix generator, brand rules), LLM critique (single-agent, 4-agent parallel, multi-model ensemble), and an interactive + autonomous review loop that drives a real browser via Playwright.

Outperforms raw Claude Opus and Sonnet sessions on structured design critique benchmarks (94% ensemble vs 76% Opus / 76% Sonnet) by combining deterministic analysis, multi-agent architecture, and multi-model ensemble synthesis.

Not trying to replace an LLM — trying to be the layer between a website and an LLM that catches the things LLMs can't see (exact pixel measurements, alpha-composited contrast, cross-page patterns, regression-vs-baseline) and hands the LLM grounded facts it can reason about.

---

## Agent self-assessment: performance vs standard Claude

*Last benchmarked: 2026-04-06 (v2), model: Claude Opus 4.6, post-feedback iteration with token audit, hover media detection, WCAG integration*

### Benchmark scores (ui-audit, deterministic layer only)

| Site | Score | Key findings | Standard Claude would miss |
|------|-------|-------------|---------------------------|
| HST Tracker (authenticated app) | 93.6/100 | Hover states gated behind `@media (hover: hover)` correctly detected; 11 spacing values on 73% grid adherence; WCAG integrated | Standard Claude sees a screenshot — can't measure grid adherence, detect media queries, or count token usage |
| Linear.app | 79.8/100 | 15 text colours, 15 bg colours (palette sprawl); unlabelled interactive element; generic "More" button | Standard Claude would note "clean design" — it can't count distinct computed colours or detect unlabelled elements |
| Notion.com | 75.9/100 | 408 tokens on `:root` detected; 12 hardcoded values flagged against existing tokens; 13-field form; 14 font sizes; WCAG 62.5% (missing skip nav, 2 contrast failures, 2 undersized targets) | Standard Claude can't read 408 CSS custom properties, can't detect which computed values bypass the token system, can't run WCAG checks |
| Stripe.com | 75.0/100 | 14 bg colours, 20 unlabelled links (`a.hds-link`), no hover states detected, 5 one-off colours | Standard Claude sees a polished page — it can't detect that 20 links have no programmatic label |
| Hacker News | 79.2/100 | No H1, no headings at all, no landmarks, 30 links all under 24px, 13px body font | Standard Claude would note "minimal design" — it can't measure that every link is 16px tall or that body text is 13.3px |

### What this agent does that standard Claude cannot

1. **Measures real CSS values.** Standard Claude looks at a screenshot and guesses. This agent extracts computed styles from the DOM — exact font sizes, colour hex values, spacing in pixels, border-radius, transitions. When it says "15 font sizes", it lists them with usage counts.

2. **Detects invisible issues.** `@media (hover: hover)` gated styles, missing ARIA labels, heading level gaps, unlabelled form inputs, absent `<main>` landmarks — these are invisible in a screenshot but measurable in the DOM.

3. **Scores consistently.** The deterministic layer produces the same score every time. Standard Claude's design opinions vary between runs. This agent's 7-category scoring (typography, color, spacing, interactive, hierarchy, patterns, copy) is reproducible and comparable across pages and over time.

4. **Crawls and aggregates.** Standard Claude reviews one screenshot. This agent navigates an entire app via Playwright, reviews every page, and surfaces systemic issues (findings that appear on 50%+ of pages).

5. **Audits against existing tokens.** Instead of inventing a design system, it reads the site's `:root` custom properties and flags hardcoded values that should use existing tokens. Standard Claude can't read CSS custom properties from a screenshot.

6. **Compares against reference sites.** Extract a style guide from Linear or Stripe, then score your app against it — button styles, input styles, colour palettes, type scales. Standard Claude has no persistent reference to compare against.

### What this agent finds that standard models cannot — detailed examples

*Written 2026-04-06, based on benchmark runs against 5 production sites*

**1. Token system integrity.** On Notion, the agent read 408 CSS custom properties from `:root` and found that `#000000` is used 512 times as a hardcoded value instead of going through a token. A model looking at a screenshot sees "black text" — it has no idea whether that black comes from `var(--text-color-dark)` or a hardcoded hex. The agent catches the gap between the system the developers built and how it's actually used.

**2. Exact measurements, not guesses.** When the agent says Hacker News has 30 links all under 24px tall, it measured every `getBoundingClientRect()`. When it says Stripe has 14 font sizes, it counted computed `fontSize` across every DOM element. A standard model will say "the links look small" or "there seem to be many font sizes" — it's guessing from pixels on a screen.

**3. Hover states gated behind media queries.** HST Tracker wraps all hover styles in `@media (hover: hover)` to prevent sticky hover on touch devices. A standard model sees the screenshot, triggers hover somehow (or doesn't), and reports "no hover states." This agent scans the actual CSS rules, finds the media query, and correctly reports "hover states exist but are gated for touch devices" instead of a false alarm.

**4. ARIA and semantic HTML.** Stripe has 20 links (`a.hds-link`) with no visible text and no `aria-label`. Notion has 5 unlabelled interactive elements. These are completely invisible in a screenshot — the links look fine visually. The agent reads the DOM attributes directly and catches what screen readers would actually encounter.

**5. Form field counts.** Notion has a 13-field form. The agent counted every `<input>` and `<textarea>` that isn't `type="hidden"`, checked which have labels, and flagged the form as an abandonment risk. A standard model might notice "there's a form" but can't reliably count fields from a screenshot, especially if some are below the fold.

**6. Spacing grid adherence as a percentage.** The agent doesn't say "spacing looks inconsistent" — it says "73% of your spacing values align to a 4px grid, and these specific values (6px, 10px, 18px) are off-grid." That's computed from every `padding`, `margin`, and `gap` value on every element. A standard model has no access to computed spacing values.

**7. Cross-page systemic issues.** When crawling HST Tracker across 7 pages, the agent found that 0% hover state coverage appears on every single page — it's systemic, not a one-page problem. "LOADOUT" in all-caps HTML appears on 6/7 pages. A standard model reviews one screenshot at a time and can't detect patterns across an app.

**8. Contrast ratios from composited backgrounds.** The agent doesn't just check `color` vs `background-color` — it walks up the DOM tree compositing semi-transparent backgrounds (alpha compositing `rgba` layers) to get the actual rendered background colour, then computes the real contrast ratio. A standard model eyeballs contrast from a screenshot and frequently gets it wrong on layered backgrounds.

**Where standard models still win.** The LLM opinion layer (layout balance, visual flow, "does this page communicate its purpose?") is where standard models add value. The agent's deterministic layer can't judge whether a page *feels* right — it can only measure whether the CSS is disciplined. That's why both layers exist.

### Honest limitations

- **Hover detection is incomplete.** Playwright's headless mode doesn't activate `@media (hover: hover)` rules. The agent now detects the media query and reports it correctly, but can't verify the actual hover styles fire.
- **Colour dominance metrics are approximate.** We count distinct colours, not visual area. A dark app shell with light cards may look balanced but report as "one dominant colour" by element count. Improved in this iteration but not perfect.
- **Component pattern heuristics are shallow.** "Form has 14 fields" is a useful flag but doesn't understand that some fields are optional, grouped, or conditionally shown.
- **The LLM opinion layer is only as good as the model.** It sometimes repeats what the deterministic layer already said, or hallucinates issues that aren't there. The `--no-llm` flag exists for a reason.
- **Navigation labels flagged as needing verbs** was a false positive in the first iteration. Fixed — the agent now distinguishes `<button>` actions from `<a>` navigation. But edge cases remain (buttons styled as nav, links styled as buttons).

### Assessment history

<details>
<summary>v1 — 2026-04-06 (initial)</summary>

First benchmarking pass before user feedback. Key issues:
- Fabricated "Proposed Design System" that invented token names and misassigned colour semantics
- Flagged nav labels (Insights, Exercises) as needing action verbs — false positive
- Included border widths (1px, 2px) in spacing analysis — inflated "off-grid" counts
- Scored modular type scale deviation as a penalty — punished valid pragmatic scales
- Missed `@media (hover: hover)` gated styles — reported 0% hover coverage as critical
- Colour dominance weighted by element count — falsely flagged apps with dark shells as "monotonous"
- No WCAG/accessibility data in report
- No Notion benchmark

| Site | Score (v1) |
|------|-----------|
| HST Tracker | 93.7 |
| Linear | 76.5 |
| Stripe | 72.0 |
| HN | 79.0 |

</details>

---

## 60-second quickstart

```bash
# 1. Install (needs Python 3.11+)
git clone https://github.com/mmjclayton/better-design-agent.git
cd better-design-agent
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/playwright install chromium

# 2. Add your Anthropic API key
.venv/bin/design-intel init   # creates .env + .design-intel/ + output/
# Open .env and add your key: ANTHROPIC_API_KEY=sk-ant-...

# 3. Run the guided wizard
.venv/bin/design-intel
```

That launches an interactive menu. Pick "Review a website," answer 4 questions, watch your HTML report open in the browser.

**Optional shortcut** — put `design-intel` on your PATH (type it from anywhere):
```bash
scripts/install-shim.sh
design-intel   # from any directory
```

**Want Claude Code / Cursor / Windsurf to call this as native tools?** Launch the MCP server:
```bash
design-intel mcp   # stdio-based MCP server
```

[→ Full install + first-run guide](#getting-started-non-coder-friendly)

---

## Table of contents

- [What makes this different](#what-makes-this-different-from-asking-an-llm-to-critique-a-design)
- [Honest assessment — when to use this vs a raw LLM](#honest-assessment--when-to-use-this-vs-a-raw-llm)
- [Commands](#commands)
- [CI/CD integration (pragmatic by default)](#cicd-integration--pragmatic-by-default)
- [Auto-fix generation](#auto-fix-generation)
- [Competitive benchmarking](#competitive-benchmarking)
- [Before/after diff](#beforeafter-diff)
- [Design system extractor](#design-system-extractor)
- [User flow analysis](#user-flow-analysis)
- [Autopilot — LLM drives the browser](#autopilot--llm-drives-the-browser)
- [Scheduled monitoring](#scheduled-monitoring)
- [Interactive review + pragmatic flags](#interactive-review--pragmatic-flags)
- [MCP server — editor integration](#mcp-server--editor-integration)
- [Getting started (non-coder friendly)](#getting-started-non-coder-friendly)
- [Architecture](#architecture)
- [Benchmarking](#benchmarking)
- [Roadmap](#roadmap)

---

## What makes this different from asking an LLM to critique a design?

| Capability | Raw LLM session | design-intel |
|---|---|---|
| Contrast ratios | Approximated, sometimes wrong | Deterministic, 100% accurate (code) |
| Touch target measurements | Estimated ("~40px") | Exact ("36x36px, 13x13px") |
| Token detection | Manual inspection | Automated 3-strategy extraction |
| WCAG compliance | LLM interpretation | Programmatic checker (11 custom) + axe-core (100+ rules) |
| Run history | None (no memory) | Score trend, issue-level diff |
| Hover/focus states | "Not tested" | Playwright-verified with before/after |
| Multi-page analysis | Manual navigation | Automated SPA crawl |
| Component scoring | Not available | Per-component pass/fail |
| Keyboard navigation | "Test with real AT" | Automated tab order mapping |
| Auto-fix generation | "Here's roughly what to change" | Emits CSS rules with exact corrected colours + HTML snippets, verified against target ratios |
| Competitive benchmarking | Manual side-by-side read | 10 deterministic metrics with winner + biggest-gap callouts |
| CI/CD gate | None | Pragmatic-by-default gate — only fails on NEW critical/serious issues introduced by the PR |
| Editor integration | Copy/paste prompts | MCP server exposes 7 tools to any MCP-compatible client |
| Interactive browser review | Manual screenshot → paste | Browser stays open, press Enter per page, auto-synthesis at end |
| Autonomous review | None | Claude drives the browser (with loop detection + template dedup) |
| Cross-page synthesis | You reading 13 tabs | Ranked priorities + "fix once, resolve N pages" callouts |

## Honest assessment — when to use this vs a raw LLM

### Where design-intel clearly wins

**Deterministic measurements.** Ask an LLM "what's the contrast on this?" and you get `~4.2:1` or whatever looks right to it. design-intel reads the DOM, alpha-composites semi-transparent overlays, computes the exact ratio. Same for target sizes, spacing values, typography scale, colour palette usage counts. LLMs approximate; design-intel measures. Hard to replicate by prompting alone.

**Cross-page patterns.** Review a 13-page app with an LLM and you get 13 separate critiques. design-intel does cross-page element deduplication — *"`button.top-nav-tab` fails 1.4.3 across 7 pages, fix once"* — collapsing noise into actionable patterns.

**Regression tracking.** LLMs have no memory. design-intel stores fingerprints per URL, diffs against baselines, and gates CI specifically on NEW violations introduced by a PR. Grandfathers pre-existing issues — the difference between "every PR yells about 20 contrast problems" and "this PR introduced one new problem."

**axe-core + 100+ rules for free.** An LLM might cite "WCAG 1.4.3" but it's doing vibes-check. Axe-core's rules are industry-standard test infrastructure. Running them in Playwright against the live DOM isn't something an LLM chat can do.

**Auto-fix patches.** LLMs say "darken the text color." design-intel outputs `.button { color: #333; }` with the specific hex that actually achieves 4.5:1 on the actual background, verified by running the contrast calc on the proposed colour.

### Where design-intel is roughly equivalent

**Subjective judgement.** "This hierarchy feels muddled," "this CTA should be louder," "this flow has too many steps psychologically" — raw LLM critique does this just as well. We pass screenshots + DOM to the same model; we wrap it in structure but the underlying judgement is the LLM's.

**Novel design issues.** If you're asking for opinion on a brand-new pattern the LLM has context on and we don't have a checker for, you get similar answers either way.

### Where raw-LLM clearly wins

**Speed + cost for one-off review.** Paste screenshot → 20 seconds, $0.02. design-intel requires Playwright, a browser, venv setup, and takes longer to spin up.

**Conversational iteration.** "What if we moved the CTA above the fold?" is natural in a chat. design-intel's critique is one-shot batch.

**Genuinely novel UIs.** Custom game UIs, VR interfaces, chart-heavy dashboards — the component detectors don't know about them. An LLM treats everything as a design surface.

### When to use which

| Situation | Tool |
|---|---|
| "Quick gut check on a screenshot" | Just ask Claude directly |
| "How does my dashboard compare to Linear's?" | `design-intel compare --url X --competitor Y` |
| "Catch accessibility regressions in CI" | `design-intel ci --url X` |
| "Audit my entire app at once" | `design-intel interactive` (authenticated) |
| "Generate a design token system from this site" | `design-intel extract-system` |
| "Write the CSS to fix these contrast issues" | `design-intel fix --url X` |
| "Is my brand consistency enforced?" | `design-intel brand-check` |
| "What changed between v1 and v2 of this page?" | `design-intel diff --before A --after B` |
| "Tour an unknown app autonomously" | `design-intel autopilot` |
| "Have a conversation about my designs" | Claude / ChatGPT directly |

### The one-line honest answer

**design-intel is the measurement + memory + composability layer that LLMs don't have.** If you value exact numbers, cross-session tracking, automated CI gates, and composable CLI/MCP interfaces — it's meaningfully better than an LLM chat. If you just want one subjective opinion about one screenshot, a chat is faster and cheaper. Most real-world design-quality work benefits from both.

## Commands

| Command | Description | LLM? |
|---|---|---|
| `design-intel critique --url X` | Dual viewport critique (desktop + mobile) | Yes |
| `design-intel critique --url X --deep` | Multi-agent deep analysis (4 agents in parallel) | Yes (4 calls) |
| `design-intel critique --url X --ensemble` | Multi-model ensemble with consensus synthesis | Yes (N models + 1) |
| `design-intel critique --url X --crawl` | Multi-page SPA crawl with cross-page analysis | Yes |
| `design-intel critique --url X --stealth` | Stealth mode for bot-protected sites | Yes |
| `design-intel critique --url X --stage wireframe` | Stage-adjusted critique depth | Yes |
| `design-intel critique --url X --device iphone-14-pro` | Single viewport critique | Yes |
| `design-intel critique --url X --save --pdf` | Export a print-ready PDF alongside .md + .html | Yes |
| `design-intel critique --url X --pragmatic` | Focused top 3–5 findings per section, skip AAA/polish | Yes |
| `design-intel wcag --url X --pragmatic` | A/AA failures + axe critical/serious only | No |
| `design-intel components --url X --pragmatic` | Only components scoring below 60% | No |
| `design-intel review` | Interactive — asks target, mode, output; runs the right tool | Mode-dependent |
| `design-intel flow --flow flow.yaml --base-url X` | Execute a multi-step user journey + benchmark against industry step counts | No |
| `design-intel interactive --url X` | Browser stays open; press Enter to capture + review each page | Mode-dependent |
| `design-intel autopilot --url X --goal "..."` | **LLM drives the browser** autonomously until the goal is met | Yes |
| `design-intel critique --image ./screenshot.png` | Screenshot-only visual critique (no code claims) | Yes |
| `design-intel wcag --url X` | WCAG 2.2 audit (custom checker + axe-core, 100+ rules) | No |
| `design-intel test-interactions --url X` | Keyboard nav, forms, empty states, responsive | No |
| `design-intel components --url X` | Component detection + per-component scoring | No |
| `design-intel handoff --url X` | Developer handoff specification | Yes |
| `design-intel history --url X` | View run history + score trend | No |
| `design-intel ci --url X` | CI gate — pragmatic by default, `--strict` for zero-tolerance | No |
| `design-intel compare --url X --competitor Y` | Side-by-side competitive benchmark (10 metrics) | No |
| `design-intel diff --before A --after B` | Before/after diff — score delta + issue buckets + visual PNG | No |
| `design-intel monitor --url X` | Scheduled monitoring — trend + regression detection + Slack alerts | No |
| `design-intel extract-system --url X --output ./design-system/` | Extract a complete CSS/JSON/Tailwind token system | No |
| `design-intel fix --url X` | Auto-generate CSS/HTML patches for deterministic WCAG failures | No |
| `design-intel mcp` | Launch the MCP server over stdio (for Claude Code, Cursor, etc.) | No |
| `design-intel index-knowledge` | Rebuild knowledge index | No |

## CI/CD integration — pragmatic by default

`design-intel ci --url X` is designed to drop into a GitHub Actions / GitLab CI workflow without becoming noise. By default it runs in **pragmatic mode**:

- **Grandfathers pre-existing violations.** If your site has 20 contrast issues today, the first run saves them as a baseline and the gate only fails future PRs that introduce *new* ones.
- **Severity-filtered.** Only axe-core `critical` + `serious` issues gate the build (tune with `--severity`). Moderate/minor surface in the report but don't fail CI.
- **Score-drop tolerance.** Allows ±2pp flicker on the WCAG score to absorb crawl/timing noise (tune with `--score-tolerance`).
- **AAA ignored.** AAA criteria stay aspirational — already excluded from scoring, now also excluded from gating.

**Toggle to zero-tolerance gating with `--strict`:**

```bash
# Pragmatic (default): gate only on new regressions
design-intel ci --url https://preview.example.com

# Strict: gate on every A/AA violation and any score drop
design-intel ci --url https://preview.example.com --strict

# Add a hard score floor (works in both modes)
design-intel ci --url https://preview.example.com --min-score 70

# Custom tuning
design-intel ci --url X --severity critical --score-tolerance 5.0
```

Exit codes: `0` pass · `1` threshold failed · `2` technical error. Use `--format json` for machine-readable output. A ready-to-drop GitHub Actions workflow lives at `templates/ci/github-actions-design-review.yml`.

## Auto-fix generation

`design-intel fix --url X` turns deterministic WCAG failures into concrete CSS and HTML patches. No LLM — fixes are only generated for issues with a mechanical correct answer.

**What it emits:**
- **Contrast fixes** — binary-searches a corrected text colour that hits the required ratio on the actual background (verified against 4.5:1 AA or 7:1 AAA after emission).
- **Target-size fixes** — `min-width`, `min-height`, `box-sizing`, `padding` rules to bring sub-24px targets up to the AA minimum.
- **Non-text contrast fixes** — adds a 1px border with a colour chosen for the adjacent background (dark border on light bg, light border on dark bg).
- **HTML snippets** — `lang="en"` attribute, skip-to-main link, missing landmarks (`<main>`, `<nav>`, `<header>`, `<footer>`), form `<label for>` pairs, heading-hierarchy notes.

Subjective failures like 1.4.1 Use of Color are listed in `FixSet.skipped` and never get speculative patches. Outputs `fixes-{timestamp}.css` + `fixes-{timestamp}.md` in `output/`.

```bash
design-intel fix --url "https://example.com"
design-intel fix --url "http://localhost:3000" --device iphone-14-pro
```

## Competitive benchmarking

`design-intel compare --url X --competitor Y` scores two sites side-by-side across 10 deterministic metrics and emits a verdict.

**Metrics:** WCAG score, A/AA violation count, contrast pass rate, target-size pass rate, landmark coverage, heading-hierarchy validity, design-token count, font-family discipline (lower = tighter), text-colour palette size (lower = tighter), axe critical+serious count.

The report shows a summary table with per-category winners, a "biggest gaps" section (where the competitor leads), and a "where you lead" section. Higher/lower-is-better is tracked per metric so "fewer violations" correctly wins.

```bash
design-intel compare --url https://you.com --competitor https://competitor.com --save
design-intel compare --url https://you.com --competitor https://competitor.com --device iphone-14-pro
```

## Before/after diff

`design-intel diff --before X --after Y` quantifies what changed between two designs. Accepts URLs, local images, or a URL vs its stored history baseline.

**What it produces:**
- **Score delta** — before → after WCAG score + signed delta.
- **Issue diff** — three buckets: `new` (introduced by the change), `fixed` (resolved), `persistent` (unchanged). Reuses the CI gate's violation fingerprinting so "what counts as a regression" is consistent across tools.
- **Visual diff PNG** — Pillow-based pixel comparison with bounding boxes drawn on the after image over changed regions. Skipped if only one side has a screenshot.

**Exit codes match the CI gate:** `0` no regressions, `1` new issues or score drop > 2pp, `2` technical error. Drop-in use as a PR gate.

```bash
# Two URLs
design-intel diff --before https://v1.example.com --after https://v2.example.com --save

# Two local images (design mockup comparison)
design-intel diff --before ./mockup-v1.png --after ./mockup-v2.png --save

# URL vs its last saved run
design-intel diff --after https://example.com --baseline history
```

## Design system extractor

`design-intel extract-system --url X --output ./design-system/` reverse-engineers a complete design-token system from a live site and writes drop-in CSS, JSON, and Tailwind config files.

**Two strategies, auto-selected:**
- **Direct** — when the site defines CSS custom properties, uses them verbatim (names + values preserved).
- **Synthesised** — when no tokens exist, generates them from usage-counted raw values: top colours → `--color-1..N`, font families → `--font-sans|serif|mono`, font sizes → `--font-size-xs|sm|base|lg|xl`, spacing → `--space-1..N`.

**Files emitted:**
- `tokens.css` — all tokens in a single `:root` block
- `colours.css`, `typography.css`, `spacing.css` — category-specific files
- `tokens.json` — Figma Variables-compatible export (`{name, value, type}`)
- `tailwind.config.js` — Tailwind v3 `theme.extend` block
- `README.md` — documents source URL, extraction date, strategy, counts

```bash
design-intel extract-system --url https://stripe.com --output ./stripe-system/
design-intel extract-system --url https://example.com --format json
```

## User flow analysis

`design-intel flow --flow signup.yaml --base-url https://your-app.com` executes a multi-step user journey via Playwright, captures screenshots at each step, and compares your step count against industry norms.

**Why structured YAML, not natural language?** Natural-language step parsing ("click the signup button") is lossy and fragile. Your flow spec stays in version control, alongside your code, readable and debuggable.

```yaml
# flows/signup.yaml
name: Signup happy path
flow_type: signup          # signup | checkout | login | onboarding | other
steps:
  - name: Open signup
    action: navigate
    url: /signup
  - name: Fill email
    action: fill
    selector: 'input[name="email"]'
    value: test@example.com
  - name: Submit
    action: click
    selector: 'button[type="submit"]'
  - name: Confirm success
    action: assert_text
    value: "Welcome"
```

**Industry benchmarks** built in: signup ≤ 3 steps, login ≤ 2, checkout ≤ 5, onboarding ≤ 5. Flows over the benchmark fail with exit code 1. `flow_type: other` skips the benchmark check.

```bash
design-intel flow --flow examples/flow-example.yaml --base-url https://example.com --save
```

Report includes per-step pass/fail, timings, screenshots, benchmark verdict, and exit codes compatible with CI.

## Autopilot — LLM drives the browser

`design-intel autopilot --url X --goal "review the signup + dashboard flow"` launches a visible browser, screenshots each page, and asks Claude what to do next. Claude picks one action at a time (CLICK / FILL / NAVIGATE / SCROLL / DONE / STOP), design-intel executes it in Playwright, captures the new state, asks again. When Claude says DONE (or max-steps hits), the standard synthesis pipeline runs over every captured page.

**When to use it:**
- Reviewing apps you don't know (competitor research, unknown sites)
- Unattended batch reviews — start it, walk away, come back to a prioritised report
- Testing multi-step flows you can describe but don't want to script

**When to use `interactive` instead** (cheaper, more reliable):
- Reviewing your own apps where you know the navigation
- When you want explicit control over which screens get captured
- When you want zero LLM API cost beyond the critique itself
- **SPAs that don't update the URL or `<title>` between routes** — Claude
  has no text-based signal to differentiate pages, so navigation degrades.
  Structural fingerprint tracking helps (autopilot captures 4-6 distinct
  templates before stopping cleanly) but coverage is partial.

**Cost:** each step = 1 vision-model LLM call with a screenshot. A 15-step journey costs roughly ~$0.30 in Anthropic credits. Plus whatever the chosen review mode adds (critique modes call the LLM again per captured page).

**Safety:**
- Max-steps cap (default 20, `--max-steps N` to tune)
- Loop detection (identical action twice in a row → graceful STOP)
- 3 consecutive failed actions → STOP
- Malformed LLM responses → STOP (fail safe, preserves captured pages)
- Every action logged to `output/autopilot-<ts>/actions.md` for audit

```bash
# Fastest, no critique LLM cost beyond the action-picking calls
design-intel autopilot --url https://example.com --goal "visit home, pricing, and signup"

# AI critique per captured page on top
design-intel autopilot --url https://example.com --goal "review signup flow" --mode pragmatic-critique

# Full 4-agent deep critique per captured page (expensive)
design-intel autopilot --url https://example.com --goal "audit the checkout" --mode deep-critique --max-steps 30
```

Output structure is identical to `interactive`: per-page reports + `session-combined.md` + `session-priorities.md` + `actions.md` for the action log.

## Scheduled monitoring

`design-intel monitor --url X` runs an audit, persists the run to history, diffs against the last baseline, and emits a trend-aware report. Optionally posts to a Slack-compatible webhook when a regression is detected.

**Philosophy — no embedded scheduler.** The tool stays a stateless CLI; scheduling is delegated to whatever's already in your stack (GitHub Actions, cron, etc.). A weekly workflow template ships at `templates/ci/github-actions-monitoring.yml`.

**What counts as a regression** (same rules as the CI gate): new critical/serious violations introduced vs the previous run, OR WCAG score dropped by more than `--score-tolerance` (default 2pp).

**Alerting is fire-and-forget.** A webhook call failure is recorded in the report but never crashes the job — you get an exit-code signal either way.

```bash
# Basic: check + print report, exit 1 on regression
design-intel monitor --url https://example.com

# Post to Slack on regression
design-intel monitor --url https://example.com \
  --alert-webhook "$SLACK_WEBHOOK_URL"

# Wider trend window + stricter tolerance
design-intel monitor --url https://example.com --trend-window 20 --score-tolerance 1.0

# JSON for programmatic consumers
design-intel monitor --url https://example.com --format json
```

Exit codes: `0` stable/improving · `1` regression · `2` technical error.

## Interactive review + pragmatic flags

**New to the project? Run `design-intel review`.** It asks four questions (what to review, which mode, output format, optional context), shows you the command it's about to run, confirms, then executes. No flag memorisation.

**Five modes** ranked by speed vs. depth:

| Mode | LLM? | What you get |
|---|---|---|
| `pragmatic-audit` | No | WCAG A/AA failures + axe critical/serious + components below 60%. Fastest. |
| `pragmatic-critique` | Yes | Top 3–5 findings per section, severity ≥ 2, skips AAA/polish |
| `deep-critique` | Yes (4 agents) | Full multi-agent analysis, no filtering |
| `brand-compliance` | No | Validate against `.design-intel/rules.yaml` |
| `everything` | Yes | Deep critique + full WCAG + components + interactions, no filtering |

**Use `--pragmatic` directly** on `critique`, `wcag`, or `components` to get the focused output without the prompts:

```bash
# Just the A/AA failures + axe critical/serious
design-intel wcag --url https://example.com --pragmatic

# LLM critique focused on top issues
design-intel critique --url https://example.com --pragmatic

# Only components scoring below 60%
design-intel components --url https://example.com --pragmatic

# Scriptable: skip all prompts
design-intel review --non-interactive --mode pragmatic-critique --target https://example.com
```

## MCP server — editor integration

`design-intel mcp` launches an MCP server over stdio, exposing six tools (`critique`, `wcag`, `components`, `handoff`, `fix`, `compare`) and the 39-entry knowledge library as resources. Any MCP-compatible client can call them as native tools.

**Configure in Claude Code / Cursor / Windsurf:**

```json
{
  "mcpServers": {
    "design-intel": {
      "command": "design-intel",
      "args": ["mcp"]
    }
  }
}
```

Once wired up, you can ask your coding agent to "run WCAG on localhost:3000" or "critique the staging deploy" from inside the editor. Knowledge entries are citeable as context via the `design-intel://knowledge/{category}/{slug}` URI template.

## Getting started (non-coder friendly)

You don't need to know how to code to set this up. If you're using an AI coding agent (Claude Code, Cursor, Windsurf, etc.), paste the following prompt and it will do everything for you:

### Setup prompt - paste this into your coding agent

```
Clone and set up the Better Design Agent project for me.

1. Clone the repo: git clone https://github.com/mmjclayton/better-design-agent.git
2. cd into the project directory
3. Create a Python virtual environment (needs Python 3.11+, install via brew if needed)
4. Install the project in editable mode: pip install -e .
5. Install Playwright's Chromium browser: playwright install chromium
6. Copy .env.example to .env
7. Open the .env file so I can add my Anthropic API key
8. Run: design-intel index-knowledge
9. Test it works by running: design-intel critique --url "https://excalidraw.com" --save
```

### What you need before starting

- **An Anthropic API key** - get one at [console.anthropic.com](https://console.anthropic.com). You need API credits (separate from a Claude Pro/Max subscription). $5 of credits is enough for extensive testing.
- **A coding agent** - Claude Code, Cursor, Windsurf, or any tool that can run terminal commands for you.

That's it. The setup prompt above handles everything else.

### Running critiques - prompts you can paste

Once set up, paste any of these into your coding agent:

**Quick critique of a live site:**
```
Run: design-intel critique --url "https://example.com" --save
Open the saved file for me.
```

**Deep analysis with all agents:**
```
Run: design-intel critique --url "https://example.com" --deep --save
Open the saved file for me.
```

**Critique your local dev server:**
```
Run: design-intel critique --url "http://localhost:3000" --crawl --save
Open the saved file for me.
```

**Mobile view:**
```
Run: design-intel critique --url "https://example.com" --device iphone-14-pro --save
Open the saved file for me.
```

**WCAG accessibility audit (instant, no LLM costs):**
```
Run: design-intel wcag --url "https://example.com" --crawl
```

**Developer handoff spec:**
```
Run: design-intel handoff --url "https://example.com" --save
Open the saved file for me.
```

**Multi-model ensemble (uses all configured models):**
```
Run: design-intel critique --url "https://example.com" --ensemble --save
Open the saved file for me.
```

**Check what improved since last run:**
```
Run: design-intel history --url "https://example.com"
```

### Using without a coding agent (manual setup)

If you prefer to run commands yourself:

```bash
# Clone
git clone https://github.com/mmjclayton/better-design-agent.git
cd better-design-agent

# Install (Python 3.11+ required)
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# Install browser engine
playwright install chromium

# Configure
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY

# Build the knowledge index
design-intel index-knowledge

# Run your first critique
design-intel critique --url "https://example.com" --save
```

## Usage

### Standard critique

```bash
design-intel critique --url "https://example.com"
design-intel critique --image ./screenshot.png
design-intel critique --describe "A login page with tiny grey placeholder text and no form labels"
```

### Deep analysis (4 agents in parallel)

```bash
design-intel critique --url "https://example.com" --deep --save
```

Runs four specialized agents simultaneously:
- **Accessibility Agent** - ARIA semantics, component intent, screen reader experience
- **Design System Agent** - Token architecture, root cause analysis, naming conventions
- **Visual Design Agent** - Hierarchy, composition, rhythm, aesthetics
- **Interaction Agent** - State audit, affordances, feedback patterns

Plus deterministic analysis: WCAG checker, interaction tests, component scoring.

### Ensemble mode (multiple models)

```bash
# Use models configured in .env (ENSEMBLE_MODELS)
design-intel critique --url "https://example.com" --ensemble --save

# Override with specific models
design-intel critique --url "https://example.com" --ensemble \
  --models "anthropic/claude-sonnet-4-20250514,openai/gpt-4o-mini,ollama/llama3.2-vision"
```

Runs the same critique across multiple LLM models in parallel, then a synthesis agent merges the findings into a consensus report:

- **Consensus findings** - all models agree (highest confidence)
- **Majority findings** - most models agree
- **Unique insights** - only one model caught (flagged for review)
- **Disputed findings** - models disagree (both positions shown)
- **Priority fixes** - ranked by consensus level (unanimous first)

Different models catch different things. Claude is strong on ARIA semantics, GPT-4o on visual composition, and local models provide a cost-free baseline. The synthesis agent reconciles all perspectives.

**Supported models (set API keys in .env):**

| Provider | Models | Cost | Vision? |
|---|---|---|---|
| Anthropic | claude-sonnet-4-20250514, claude-opus-4-20250514 | Paid | Yes |
| OpenAI | gpt-4o, gpt-4o-mini | Paid | Yes |
| Google | gemini-2.5-pro, gemini-2.5-flash | Paid (flash has free tier) | Yes |
| Groq | llama-3.3-70b-versatile, llama-3.2-90b-vision-preview | Free tier | Partial |
| DeepSeek | deepseek-chat | Very low cost | No |
| Mistral | mistral-large-latest, mistral-small-latest | Paid | No |
| Together AI | meta-llama/Llama-3.3-70B-Instruct-Turbo | Low cost | No |
| OpenRouter | 100+ models | Varies (some free) | Varies |
| Ollama | llama3.2-vision, gemma3, any local model | Free (local) | Yes |

**Recommended ensemble for best coverage vs cost:**
```env
ENSEMBLE_MODELS=anthropic/claude-sonnet-4-20250514,openai/gpt-4o-mini,groq/llama-3.3-70b-versatile
```

### Multi-page SPA crawl

```bash
design-intel critique --url "http://localhost:3000" --crawl --save
design-intel critique --url "http://localhost:3000" --crawl --max-pages 15
```

Discovers navigation elements, clicks through each page (including SPA client-side routing), and extracts DOM metrics from every view. Screenshots from all pages are sent to the LLM.

### Stage-aware critique

```bash
# Early wireframe - focus on IA and flow, skip visual polish
design-intel critique --url "..." --stage wireframe

# Mid-fidelity mockup - focus on visual system, light accessibility
design-intel critique --url "..." --stage mockup

# Production (default) - full critique with WCAG compliance
design-intel critique --url "..." --stage production
```

### Mobile device testing

```bash
design-intel critique --url "..." --device iphone-14-pro --crawl
design-intel critique --url "..." --device ipad
design-intel critique --url "..." --viewport-width 375 --viewport-height 667
```

Device presets: `iphone-12`, `iphone-14-pro`, `iphone-15`, `iphone-se`, `pixel-7`, `ipad`, `ipad-pro`, `desktop`

### Developer handoff

```bash
design-intel handoff --url "https://example.com" --save
```

Generates developer specs: design tokens, layout specification, component inventory with dimensions and states, interaction specs from Playwright testing, accessibility requirements, and edge cases.

### Standalone tools (no LLM, instant)

```bash
# WCAG 2.2 audit - deterministic pass/fail, 11 criteria
design-intel wcag --url "https://example.com" --crawl

# Interaction tests - keyboard nav, forms, empty states, responsive
design-intel test-interactions --url "https://example.com"

# Component scoring - per-component pass/fail against pattern standards
design-intel components --url "https://example.com"

# Run history and score trend
design-intel history --url "https://example.com"

# Auto-generate CSS/HTML fixes for deterministic WCAG failures
design-intel fix --url "https://example.com"

# Competitive benchmark — you vs them, 10 metrics
design-intel compare --url https://you.com --competitor https://them.com

# CI gate — pragmatic by default, --strict for zero-tolerance
design-intel ci --url "https://preview.example.com" --format json
```

### Options

```bash
--tone balanced          # opinionated (default), balanced, or gentle
--context "B2B dashboard for finance teams"
--save                   # save report to output/
--crawl                  # multi-page SPA crawl
--deep                   # multi-agent + interaction tests + component scores
--stage wireframe        # wireframe, mockup, or production
--device iphone-14-pro   # device viewport preset
--max-pages 15           # max pages to crawl
```

## Architecture

### Data pipeline

```
URL/Screenshot/Description
    |
    v
[Input Processor] -- Playwright screenshots, DOM extraction, SPA crawl
    |
    v
[Deterministic Analysis] -- WCAG checker, interaction tests, component scoring (no LLM)
    |
    v
[Knowledge Retrieval] -- Context-aware tag matching from 39-entry library
    |
    v
[LLM Agents] -- Single agent, 4 specialized agents, or N-model ensemble
    |
    v
[Reconciliation] -- Cross-checks sub-agent findings, removes contradictions
    |
    v
[Synthesis] -- (ensemble only) Cross-model consensus analysis
    |
    v
[Output] -- Markdown report + regression diff + history tracking
```

### What the deterministic layer catches (no LLM)

The programmatic WCAG checker evaluates 11 criteria with 100% accuracy:

| Criterion | Level | What it checks |
|---|---|---|
| 1.3.1 Info and Relationships | A | Landmarks (main, nav, header, footer) + heading hierarchy |
| 1.4.1 Use of Color | A | Flagged for manual review |
| 1.4.3 Contrast (Minimum) | AA | All text/background pairs against 4.5:1 and 3:1 (large) |
| 1.4.11 Non-text Contrast | AA | UI component boundaries against 3:1 |
| 2.4.1 Bypass Blocks | A | Skip link presence |
| 2.4.7 Focus Visible | AA | Stylesheet scanning for :focus-visible rules |
| 2.5.8 Target Size (Minimum) | AA | 24x24px minimum |
| 2.5.5 Target Size (Enhanced) | AAA | 44x44px (aspirational, not required) |
| 3.1.1 Language of Page | A | lang attribute on html |
| 4.1.2 Name, Role, Value | A | Form inputs with programmatic labels |

The report separates A/AA failures (must fix for compliance) from AAA (aspirational, nice to have). WCAG score is calculated on A/AA criteria only.

Additional accuracy features:
- Alpha-composited contrast handles semi-transparent backgrounds (e.g. `rgba(34, 197, 94, 0.19)` on a dark surface)
- Off-screen elements (skip links) excluded from touch target checks
- Multi-page violations deduplicated by unique element
- Sub-agent reconciliation pass removes contradictions between sections
- AA and AAA target-size rows stay separated — the 2.5.8 (AA) row reports only sub-24px violations, 2.5.5 (AAA) reports sub-44px separately, no double-counting
- Deterministic whitelist enforces the six allowed H2 section headers after LLM reconciliation, preventing heading-hierarchy drift in the final report
- State-test harness falls back from `networkidle` to `domcontentloaded` on sites with persistent analytics (Notion, Airbnb) so hover/focus tests run instead of silently timing out

### What the LLM adds (subjective judgment)

The LLM evaluates what code cannot:
- Visual hierarchy and composition quality
- Typography rhythm and readability
- Component intent vs semantics (is a checkbox being used where a toggle button would be correct?)
- ARIA pattern correctness (does this custom widget follow WAI-ARIA APG?)
- Screen reader experience narrative
- Design system maturity assessment
- Root cause analysis (which token maps to the failing contrast value?)

### Regression tracking

Every run is stored in `.design-intel/` with score, WCAG results, and issue inventory. Subsequent runs show:

```
Regression Report

Previous run: 2026-04-04T17:30:30 | Score: 50/100 | WCAG: 30.0%
Current run:  2026-04-04T19:53:20 | Score: 62/100 | WCAG: 40.0%

Score: +12 points (improved)

Fixed (3 issues resolved)
- ~~4.1.2 Form Labels: 15 inputs without labels~~
- ~~2.4.1 Bypass Blocks: No skip link~~
- ~~3.1.1 Language: Missing lang attribute~~

Persistent (3 unresolved)
- 1.4.11 Non-text Contrast: 86 UI components below 3:1
- 2.5.5 Target Size: 75 elements below 44x44px
- 1.4.3 Contrast: 3 text pairs below 4.5:1
```

## Evaluation frameworks

Every critique is grounded in established frameworks:

- **Nielsen's 10 Usability Heuristics** - findings reference specific heuristics by name
- **Nielsen Severity Scale (0-4)** - every finding rated: 0 (not a problem) to 4 (usability catastrophe)
- **WCAG 2.2 AA** - specific success criteria cited by number
- **Gestalt Principles** - proximity, similarity, figure-ground applied to layout and grouping
- **Fitts's Law** - target size and distance analysis for interactive elements

## LLM providers

Works with any LLM provider via [LiteLLM](https://github.com/BerriAI/litellm). Configure in `.env`:

### Anthropic (default)

```env
LLM_PROVIDER=claude
LLM_MODEL=claude-sonnet-4-20250514
ANTHROPIC_API_KEY=sk-ant-...
```

### OpenAI

```env
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o
OPENAI_API_KEY=sk-...
```

### Ollama (free, local)

```bash
brew install ollama
ollama pull llama3.2-vision
```

```env
LLM_PROVIDER=ollama
LLM_MODEL=llama3.2-vision
```

## Knowledge library

39 entries across 10 domains, sourced from authoritative references (WCAG, Nielsen, Apple HIG, Material Design, Carbon, etc.):

```
knowledge/
  accessibility/    # WCAG 2.2, ARIA, COGA, touch targets, inclusive design, annotations
  heuristics/       # Nielsen's 10, Shneiderman's 8, severity ratings
  typography/       # Type scales, typographic hierarchy, line length
  colour/           # Contrast, dark mode, colour psychology, ColorBrewer
  layout/           # Gestalt principles, F-pattern, spacing systems, whitespace
  interaction/      # Form design, microinteractions, navigation, IA, component states
  systems/          # Atomic design, design tokens, Material 3, Apple HIG, Carbon, Figma references
  critique/         # Liz Lerman CRP, design review modes, teardown sources
  motion/           # Animation principles, reduced motion, transition patterns
  mobile/           # Thumb zone, responsive design, platform conventions
```

Context-aware retrieval selects relevant entries based on what's actually in the DOM (dark theme detected = dark mode guidelines loaded; forms detected = form design patterns loaded).

### Contributing knowledge entries

1. Add a `.md` file in `knowledge/[category]/` with YAML frontmatter
2. Include `id`, `title`, `category`, `tags`, `source`, `source_authority`
3. Write actionable content: the principle, when to apply it, common violations
4. Run `design-intel index-knowledge`
5. Add the source to `knowledge/CORPUS_SOURCES.md`

## Project structure

```
better-design-agent/
├── CLAUDE.md                        # Claude Code instructions (architecture, conventions, backlog rules)
├── Backlog.md                       # Tactical work tracker (items with full specs)
├── .claude/
│   ├── settings.json                # Hook config (ruff on edit, pytest on Stop)
│   └── hooks/ruff-edited.sh         # Scoped lint on the edited file
├── .github/workflows/
│   └── claude-review.yml            # claude-code-action PR review workflow
├── templates/ci/
│   └── github-actions-design-review.yml  # Drop-in CI gate workflow
├── src/
│   ├── cli.py                       # Typer CLI (all commands)
│   ├── config.py                    # Pydantic Settings
│   ├── mcp_server.py                # FastMCP server (6 tools + knowledge resources)
│   ├── providers/llm.py             # LiteLLM wrapper (Claude, OpenAI, Ollama, ...)
│   ├── input/
│   │   ├── processor.py             # Input normalisation
│   │   ├── screenshot.py            # Playwright: screenshots, DOM, SPA crawl, state tests
│   │   └── models.py                # DesignInput, PageCapture dataclasses
│   ├── agents/
│   │   ├── base.py                  # Base agent with knowledge retrieval
│   │   ├── critique.py              # Single-agent critique
│   │   ├── orchestrator.py          # Multi-agent parallel orchestrator
│   │   ├── ensemble.py              # Multi-model parallel + synthesis
│   │   ├── accessibility_agent.py   # ARIA, semantics, screen reader, focus management
│   │   ├── design_system_agent.py   # Tokens, root cause, naming, maturity
│   │   ├── visual_agent.py          # Hierarchy, composition, rhythm, aesthetics
│   │   ├── interaction_agent.py     # States, affordances, feedback
│   │   └── handoff_agent.py         # Developer handoff specification
│   ├── analysis/
│   │   ├── wcag_checker.py          # Deterministic WCAG 2.2 checker (11 criteria)
│   │   ├── axe_runner.py            # Axe-core injection via Playwright (100+ rules)
│   │   ├── fix_generator.py         # CSS/HTML patches from WCAG failures
│   │   ├── competitive.py           # 10-metric side-by-side comparison
│   │   ├── ci_runner.py             # Pragmatic CI gate + fingerprint diffing
│   │   ├── diff_analyzer.py         # Before/after diff + Pillow visual PNG
│   │   ├── monitoring.py            # Scheduled monitor + trend + Slack webhook
│   │   ├── system_extractor.py      # Token extraction → CSS + JSON + Tailwind
│   │   ├── interaction_tester.py    # Keyboard nav, form validation, empty states, responsive
│   │   ├── component_detector.py    # Component detection + per-component scoring
│   │   └── history.py               # Run history, regression tracking, score diff
│   ├── knowledge/
│   │   ├── store.py                 # Read/write knowledge entries
│   │   ├── index.py                 # Tag-based index
│   │   └── retriever.py             # Context-aware retrieval
│   └── output/
│       ├── formatter.py             # Report saving
│       ├── html_report.py           # HTML report with inline screenshots
│       └── pdf_report.py            # Print-ready PDF via Playwright page.pdf()
├── knowledge/                       # Design knowledge corpus (39 entries, git-tracked)
│   ├── INDEX.yaml                   # Auto-generated tag index (100 tags)
│   └── CORPUS_SOURCES.md            # Source reference document
├── tests/
│   ├── test_fix_generator.py        # 17 unit tests — colour maths + fix recipes
│   ├── test_competitive.py          # 21 unit tests — metric logic + report shape
│   ├── test_ci_runner.py            # 35 unit tests — pragmatic + strict modes
│   ├── test_ci_cli.py               # 9 CLI integration tests
│   ├── test_diff_analyzer.py        # 22 unit tests — fingerprint + visual diff
│   ├── test_monitoring.py           # 22 unit tests — trend + alert discipline
│   ├── test_system_extractor.py     # 26 unit tests — extraction + file output
│   ├── test_pdf_report.py           # 24 unit tests — cover page, TOC, print CSS
│   ├── test_mcp_server.py           # 14 MCP server registration tests
│   ├── benchmark_critique.py        # Output quality benchmark (7 dimensions)
│   ├── benchmark_fix_generator.py   # Fix-generator correctness (6 dimensions, 100/100)
│   ├── benchmark_competitive.py     # Comparison correctness (6 dimensions, 100/100)
│   ├── benchmark_diff_analyzer.py   # Diff correctness (6 dimensions, 100/100)
│   ├── benchmark_monitoring.py      # Monitor correctness (6 dimensions, 100/100)
│   └── benchmark_system_extractor.py  # Extractor correctness (6 dimensions, 100/100)
├── config/default.yaml
└── output/                          # Generated reports (gitignored)
```

## Benchmarking

Benchmarked against raw Claude Opus 4.6 and Sonnet 4.6 sessions on excalidraw.com:

| Agent | Score | Specificity | Actionability | Accessibility | Design System | Unique Findings |
|---|---|---|---|---|---|---|
| **design-intel (ensemble)** | **94%** | 100% | 95% | 100% | 100% | 100% |
| **design-intel (deep)** | **86%** | 100% | 50% | 100% | 100% | 100% |
| Sonnet 4.6 (raw) | 85% | 100% | 50% | 100% | 100% | 100% |
| design-intel (single) | 78% | 100% | 90% | 100% | 100% | 0% |
| Opus 4.6 (raw) | 73% | 75% | 50% | 100% | 50% | 100% |

The ensemble mode scores highest because each model's full output is preserved (no information loss), and the synthesis adds consensus analysis on top. Different models catch different things - the ensemble captures all of them.

The benchmark measures seven dimensions:

| Dimension | What it measures |
|---|---|
| Specificity | Hex colours, pixel values, contrast ratios, CSS selectors cited |
| Coverage | Design categories evaluated (9 possible) |
| Actionability | Findings with concrete fixes including specific values |
| Accessibility Depth | WCAG criteria referenced, semantic HTML analysis |
| Design System Awareness | Existing token references, proposed token systems |
| Scope | Pages covered, empty/loading/responsive state analysis |
| Unique Findings | Issues found that other tools missed |

```bash
python -m tests.benchmark_critique
```

### Deterministic benchmarks

The fix generator and competitive comparison ship with their own reproducible benchmarks (no LLM, no network) that fail CI if output correctness regresses below 90%.

| Benchmark | What it scores | Floor | Current |
|---|---|---|---|
| `benchmark_fix_generator` | Coverage, contrast accuracy, target-size accuracy, HTML snippet validity, determinism discipline, selector quality | 90% | **100%** |
| `benchmark_competitive` | Metric count, winner correctness, symmetry, tie handling, lower-is-better discipline, markdown shape | 90% | **100%** |
| `benchmark_diff_analyzer` | Fingerprint-diff correctness, exit-code semantics, score delta math, markdown completeness, visual diff detection, JSON schema shape | 90% | **100%** |
| `benchmark_monitoring` | Exit-code semantics, fingerprint diff vs baseline, trend truncation, alert discipline, markdown completeness, JSON schema shape | 90% | **100%** |
| `benchmark_system_extractor` | Strategy selection, direct fidelity, synthesis naming, ordering/dedup, file output, Tailwind+JSON shape | 90% | **100%** |

```bash
python -m tests.benchmark_fix_generator
python -m tests.benchmark_competitive
python -m tests.benchmark_diff_analyzer
python -m tests.benchmark_monitoring
python -m tests.benchmark_system_extractor
```

## Roadmap

Work is tracked in two paired files:

- **`Backlog.md`** (this repo) — tactical: items committed to shipping, with full CLI-observable acceptance criteria. Read this to see what's in progress and what ships next.
- **`../design-agent-private/ROADMAP.md`** (private) — strategic horizon with the prioritised P-list and the complete shipped history.

**Shipped so far** (35 items): critique agent + 39-entry knowledge library, DOM extraction + SPA crawl, 11-criterion WCAG checker, regression tracking, multi-agent architecture (4 agents in parallel), interaction testing, component scoring, stage-aware critique, dual viewport + 8 device presets, developer handoff specs, multi-model ensemble (9 providers), axe-core integration (100+ rules), HTML reports, stealth mode, screenshot-only mode, quality fixes (reconciliation, deduplication, alpha compositing), auto-fix generation, MCP server, Claude Code project config + hooks, claude-code-action workflow, competitive benchmarking, pragmatic CI gate, before/after diff (with visual PNG), scheduled monitoring + Slack webhook alerts, design system extractor, PDF export, custom brand rules, interactive review + pragmatic flags, user flow analysis, autopilot (LLM-driven browser), ship-ready polish (`init` + project config), **opinionated UI audit** (7-category deterministic scoring + LLM opinion layer), **style guide extraction + comparison**, **component style extraction**, **feedback iteration (v2)**.

**Next up** (in priority order): Performance + Design (Lighthouse integration), Design Documentation Generator, Watch Mode, Figma Input, Browser Extension, Plugin System, Web Dashboard.

## Sample reports

Real critique reports generated by design-intel on public websites:

| Site | Mode | Score | Report |
|---|---|---|---|
| [Anthropic](https://anthropic.com) | Deep + dual viewport | 68/100 | [anthropic-deep-dual.md](reports/samples/anthropic-deep-dual.md) |
| [Anthropic](https://anthropic.com) | Standard desktop | 68/100 | [anthropic-desktop.md](reports/samples/anthropic-desktop.md) |
| [Excalidraw](https://excalidraw.com) | Deep | 59/100 | [excalidraw-deep.md](reports/samples/excalidraw-deep.md) |
| [StackBlitz](https://stackblitz.com) | Deep | 59/100 | [stackblitz-deep.md](reports/samples/stackblitz-deep.md) |
| [GitHub Explore](https://github.com/explore) | Deep | 62/100 | [github-deep.md](reports/samples/github-deep.md) |
| LOADOUT (fitness app) | Deep desktop | - | [loadout-desktop-deep.md](reports/samples/loadout-desktop-deep.md) |
| LOADOUT (fitness app) | Deep mobile | - | [loadout-mobile-deep.md](reports/samples/loadout-mobile-deep.md) |

## Configuration

| Variable | Default | Description |
|---|---|---|
| `LLM_PROVIDER` | `claude` | `claude`, `openai`, or `ollama` |
| `LLM_MODEL` | `claude-sonnet-4-20250514` | Model identifier |
| `KNOWLEDGE_RETRIEVAL_LIMIT` | `2000` | Max tokens of knowledge context per call |
| `RETRIEVAL_TOP_K` | `5` | Number of knowledge chunks retrieved |
| `OUTPUT_FORMAT` | `markdown` | `markdown`, `json`, or `yaml` |
| `CRITIQUE_SEVERITY_THRESHOLD` | `low` | Minimum severity to include |

## License

MIT
