# design-intel

**The measurement, memory, and composability layer that LLMs don't have.** A CLI and MCP server for UX/UI design review that combines deterministic analysis (WCAG, axe-core, component scoring, fix generation, brand rules), multi-agent LLM critique, and an autonomous review loop driven by a real browser via Playwright.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-637_passing-success.svg)](#testing)
[![Benchmark](https://img.shields.io/badge/ensemble_score-94%25-brightgreen.svg)](#benchmarking)
[![MCP](https://img.shields.io/badge/MCP-compatible-orange.svg)](#mcp-server)

Outperforms raw Claude Opus 4.6 and Sonnet 4.6 sessions on structured design critique benchmarks (94% ensemble vs 73-85% raw model) by combining deterministic measurement, multi-agent architecture, and multi-model ensemble synthesis.

Not trying to replace an LLM. Designed to sit *between* a website and an LLM, catching the things LLMs can't see — exact pixel measurements, alpha-composited contrast, cross-page patterns, regressions vs baseline — and handing the LLM grounded facts it can reason about.

---

## Contents

- [What makes this different](#what-makes-this-different)
- [Quickstart](#quickstart)
- [Performance vs raw Claude](#performance-vs-raw-claude)
- [When to use this vs a raw LLM](#when-to-use-this-vs-a-raw-llm)
- [Commands](#commands)
- [CI/CD integration](#cicd-integration)
- [Feature highlights](#feature-highlights)
- [MCP server](#mcp-server)
- [Architecture](#architecture)
- [WCAG coverage](#wcag-coverage)
- [LLM providers](#llm-providers)
- [Benchmarking](#benchmarking)
- [Sample reports](#sample-reports)
- [Configuration](#configuration)
- [Contributing](#contributing)

---

## What makes this different

| Capability | Raw LLM session | design-intel |
|---|---|---|
| Contrast ratios | Approximated, sometimes wrong | Deterministic, exact (alpha-composited) |
| Touch target measurements | Estimated ("~40px") | Exact ("36×36px, 13×13px") |
| Token detection | Manual inspection | Automated 3-strategy extraction |
| WCAG compliance | LLM interpretation | Programmatic checker (10 criteria, 11 checks) + axe-core (100+ rules) |
| Run history | None | Score trend, issue-level diff |
| Hover / focus states | "Not tested" | Playwright-verified with before/after |
| Multi-page analysis | Manual navigation | Automated SPA crawl |
| Component scoring | Not available | Per-component pass/fail |
| Keyboard navigation | "Test with real AT" | Automated tab order mapping |
| Auto-fix generation | "Roughly what to change" | CSS rules with verified target ratios |
| Competitive benchmarking | Manual side-by-side read | 10 deterministic metrics + winner callouts |
| CI/CD gate | None | Pragmatic-by-default; only fails on NEW issues |
| Editor integration | Copy/paste prompts | MCP server: 6 tools to any MCP client |
| Cross-page synthesis | You reading 13 tabs | Ranked priorities + "fix once, resolve N pages" |

---

## Quickstart

```bash
# 1. Install (Python 3.11+)
git clone https://github.com/mmjclayton/design-intel.git
cd design-intel
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/playwright install chromium

# 2. Configure
.venv/bin/design-intel init    # creates .env + .design-intel/ + output/
# Edit .env and add your key: ANTHROPIC_API_KEY=sk-ant-...

# 3. Run the wizard or jump straight in
.venv/bin/design-intel                                          # interactive menu
.venv/bin/design-intel check https://stripe.com                 # one-line score
.venv/bin/design-intel critique --url https://example.com --save
```

**Put it on your PATH** (optional):
```bash
scripts/install-shim.sh
design-intel check https://stripe.com
```

**One-line scoring** for CI gates and pipe-friendly use:
```bash
design-intel check https://stripe.com
# stripe.com 82.5/100 (typography:78 color:85 spacing:74 interactive:88 hierarchy:90 patterns:80 copy:85)

design-intel check https://stripe.com --json | jq .score
design-intel check https://stripe.com --threshold 80    # CI gate: exit 0/1
```

**Environment check** if anything breaks:
```bash
design-intel doctor
```

---

## Performance vs raw Claude

*Last benchmarked: 2026-04-06. Model: Claude Opus 4.6, post-feedback iteration with token audit, hover media detection, and WCAG integration.*

### Benchmark scores against production sites

| Site | Score | Key findings | What standard Claude misses |
|---|---|---|---|
| HST Tracker (auth app) | 93.6/100 | Hover states gated behind `@media (hover: hover)` correctly detected; 11 spacing values on 73% grid | Can't measure grid adherence, detect media queries, count token usage |
| Linear.app | 79.8/100 | 15 text colours, 15 bg colours (palette sprawl); generic "More" button; unlabelled element | Can't count distinct computed colours or detect unlabelled elements |
| Notion.com | 75.9/100 | 408 tokens on `:root`; 12 hardcoded values flagged; 14 font sizes; WCAG 62.5% | Can't read 408 CSS custom properties or detect token-system bypasses |
| Stripe.com | 75.0/100 | 14 bg colours, 20 unlabelled links (`a.hds-link`), no hover states detected | Can't detect that 20 links lack programmatic labels |
| Hacker News | 79.2/100 | No H1, no headings, no landmarks, 30 links all under 24px, 13px body font | Can't measure that every link is 16px tall or that body text is 13.3px |

### What this agent does that standard Claude cannot

1. **Measures real CSS values.** Extracts computed styles from the DOM: exact font sizes, hex colours, spacing in pixels, border-radius, transitions. When it says "15 font sizes" it lists them with usage counts.
2. **Detects invisible issues.** `@media (hover: hover)` gated styles, missing ARIA labels, heading level gaps, unlabelled form inputs, absent landmarks. Invisible in a screenshot but measurable in the DOM.
3. **Scores reproducibly.** The deterministic layer produces the same score every time. 7-category scoring (typography, color, spacing, interactive, hierarchy, patterns, copy) is comparable across pages and over time.
4. **Crawls and aggregates.** Navigates an entire app via Playwright, reviews every page, and surfaces systemic issues (findings appearing on 50%+ of pages).
5. **Audits against existing tokens.** Reads the site's `:root` custom properties and flags hardcoded values that should use existing tokens.
6. **Compares against reference sites.** Extract a style guide from Linear or Stripe, then score your app against it.
7. **Composites alpha-blended backgrounds for true contrast.** Walks the DOM tree compositing semi-transparent layers to get the actually-rendered background colour, then computes the real ratio.
8. **Tracks regressions across runs.** Stores fingerprints per URL and gates CI specifically on NEW violations introduced by a PR. Grandfathers pre-existing issues.

### Honest limitations

- **Hover detection is incomplete.** Playwright's headless mode doesn't activate `@media (hover: hover)` rules. The agent now detects the media query and reports it correctly, but can't verify the actual hover styles fire.
- **Colour dominance metrics are approximate.** We count distinct colours, not visual area.
- **Component pattern heuristics are shallow.** "Form has 14 fields" is a useful flag but doesn't understand grouping or conditional fields.
- **The LLM opinion layer is only as good as the model.** It sometimes repeats what the deterministic layer already said. The `--no-llm` flag exists for a reason.
- **Genuinely novel UIs** (custom game UIs, VR, chart-heavy dashboards) confuse the component detectors.

---

## When to use this vs a raw LLM

### Where design-intel clearly wins

**Deterministic measurements.** Ask an LLM "what's the contrast on this?" and you get `~4.2:1` or whatever looks right. design-intel reads the DOM, alpha-composites overlays, and computes the exact ratio. Same for target sizes, spacing, type scale, palette counts. LLMs approximate; design-intel measures.

**Cross-page patterns.** Review a 13-page app with an LLM and you get 13 separate critiques. design-intel deduplicates findings across pages (*"`button.top-nav-tab` fails 1.4.3 across 7 pages, fix once"*).

**Regression tracking.** LLMs have no memory. design-intel stores per-URL fingerprints and gates CI specifically on NEW violations. The difference between "every PR yells about 20 contrast problems" and "this PR introduced one."

**axe-core for free.** 100+ industry-standard accessibility rules running in Playwright against the live DOM, not vibes-checked from a screenshot.

**Auto-fix patches.** LLMs say "darken the text colour." design-intel outputs `.button { color: #333; }` with the specific hex that achieves 4.5:1 on the actual background, verified by re-running the contrast calc.

### Where raw LLM clearly wins

**Quick gut check on a single screenshot.** Paste → 20 seconds → $0.02. design-intel needs Playwright, a browser, venv setup.

**Conversational iteration.** "What if we moved the CTA above the fold?" is natural in chat. design-intel's critique is one-shot batch.

**Truly novel UIs.** Custom game UIs, VR interfaces, chart-heavy dashboards: an LLM treats everything as a design surface; the component detectors don't.

### Tool selection cheat sheet

| Situation | Tool |
|---|---|
| Quick gut check on a screenshot | Just ask Claude directly |
| How does my dashboard compare to Linear's? | `design-intel compare --url X --competitor Y` |
| Catch accessibility regressions in CI | `design-intel ci --url X` |
| Audit my entire app at once | `design-intel interactive` (authenticated) |
| Generate a design token system from a site | `design-intel extract-system` |
| Write the CSS to fix contrast issues | `design-intel fix --url X` |
| Is my brand consistency enforced? | `design-intel brand-check` |
| What changed between v1 and v2? | `design-intel diff --before A --after B` |
| Tour an unknown app autonomously | `design-intel autopilot` |
| Have a conversation about my designs | Claude / ChatGPT directly |

---

## Commands

| Command | Description | LLM? |
|---|---|---|
| `check <url>` | One-line quick score; `--json`, `--threshold` for CI gates | No |
| `critique --url X` | Dual viewport critique (desktop + mobile) | Yes |
| `critique --url X --deep` | Multi-agent deep analysis (4 agents in parallel) | Yes (×4) |
| `critique --url X --ensemble` | Multi-model ensemble + consensus synthesis | Yes (N+1) |
| `critique --url X --crawl` | Multi-page SPA crawl + cross-page analysis | Yes |
| `critique --url X --pragmatic` | Top 3-5 findings per section, skip AAA/polish | Yes |
| `critique --url X --stage wireframe` | Stage-adjusted critique depth | Yes |
| `critique --url X --device iphone-14-pro` | Single-viewport critique on a device preset | Yes |
| `critique --url X --save --pdf` | Print-ready PDF export alongside .md and .html | Yes |
| `critique --image ./screenshot.png` | Screenshot-only visual critique (no code claims) | Yes |
| `wcag --url X` | WCAG 2.2 audit (custom checker + axe-core) | No |
| `wcag --url X --pragmatic` | A/AA failures + axe critical/serious only | No |
| `components --url X` | Component detection + per-component scoring | No |
| `components --url X --pragmatic` | Only components scoring below 60% | No |
| `test-interactions --url X` | Keyboard nav, forms, empty states, responsive | No |
| `handoff --url X` | Developer handoff specification | Yes |
| `history --url X` | Run history + score trend | No |
| `ci --url X` | CI gate: pragmatic by default, `--strict` for zero-tolerance | No |
| `compare --url X --competitor Y` | Side-by-side competitive benchmark (10 metrics) | No |
| `diff --before A --after B` | Before/after diff: score delta + issue buckets + visual PNG | No |
| `monitor --url X` | Scheduled monitoring + trend + Slack webhook alerts | No |
| `extract-system --url X` | Extract complete CSS/JSON/Tailwind token system | No |
| `fix --url X` | Auto-generate CSS/HTML patches for WCAG failures | No |
| `flow --flow X.yaml --base-url Y` | Multi-step user journey + industry step-count benchmark | No |
| `interactive --url X` | Browser stays open; press Enter per page | Mode-dep |
| `autopilot --url X --goal "..."` | LLM drives the browser autonomously | Yes |
| `brand-check --url X` | Validate against `.design-intel/rules.yaml` | No |
| `review` | Interactive: asks 4 questions, runs the right tool | Mode-dep |
| `init --framework tailwind` | Bootstrap project + framework brand rules | No |
| `doctor` | Diagnose environment: Python, Playwright, API keys, network | No |
| `version` | Runtime info; also `--version` flag on all commands | No |
| `mcp` | Launch MCP server over stdio (Claude Code, Cursor, etc.) | No |
| `index-knowledge` | Rebuild the knowledge library index | No |

---

## CI/CD integration

`design-intel ci --url X` is designed to drop into a GitHub Actions / GitLab CI / Bitbucket workflow without becoming noise. By default it runs in **pragmatic mode**:

- **Grandfathers pre-existing violations.** First run saves a baseline; the gate only fails on *new* regressions.
- **Severity-filtered.** Only axe-core `critical` + `serious` gate the build (tune with `--severity`). Moderate/minor surface in the report but don't fail CI.
- **Score-drop tolerance.** Allows ±2pp flicker on the WCAG score to absorb crawl/timing noise.
- **AAA ignored.** AAA criteria stay aspirational.

```bash
# Pragmatic (default)
design-intel ci --url https://preview.example.com

# Strict: gate on every A/AA violation and any score drop
design-intel ci --url https://preview.example.com --strict

# Hard score floor (works in both modes)
design-intel ci --url https://preview.example.com --min-score 70
```

Exit codes: `0` pass · `1` threshold failed · `2` technical error. Use `--format json` for machine-readable output.

**Drop-in CI templates:**

| Platform | Template |
|---|---|
| GitHub Actions | `templates/ci/github-actions-design-review.yml` |
| GitHub Actions (monitoring) | `templates/ci/github-actions-monitoring.yml` |
| GitLab CI | `templates/ci/gitlab-ci-design-review.yml` |
| Bitbucket Pipelines | `templates/ci/bitbucket-pipelines-design-review.yml` |

See `templates/ci/README.md` for setup instructions.

---

## Feature highlights

### Auto-fix generation

`design-intel fix --url X` turns deterministic WCAG failures into concrete CSS and HTML patches. No LLM; only emits fixes for issues with a mechanical correct answer. Binary-searches a corrected text colour that hits the required ratio on the actual background, verified after emission. Generates target-size rules, non-text contrast borders, missing landmarks, form labels, and `lang` attributes. Subjective failures land in `FixSet.skipped` with no speculative patches. Outputs `fixes-{ts}.css` + `fixes-{ts}.md`.

### Competitive benchmarking

`design-intel compare --url X --competitor Y` scores two sites side-by-side across 10 deterministic metrics: WCAG score, A/AA violation count, contrast pass rate, target-size pass rate, landmark coverage, heading hierarchy, design-token count, font-family discipline, palette size, axe critical+serious count. Report shows per-metric winners, "biggest gaps" where the competitor leads, and "where you lead." Lower-is-better is tracked per metric, so "fewer violations" correctly wins.

### Before / after diff

`design-intel diff --before X --after Y` quantifies what changed between two designs. Accepts URLs, local images, or a URL vs its stored history baseline. Produces score delta, three issue buckets (`new`, `fixed`, `persistent`), and a Pillow-based visual diff PNG with bounding boxes around changed regions. Exit codes match the CI gate so it's drop-in usable as a PR gate.

### Design system extractor

`design-intel extract-system --url X --output ./design-system/` reverse-engineers a complete design token system from a live site. Two strategies, auto-selected: **direct** (uses the site's own CSS custom properties) or **synthesised** (generates tokens from usage-counted raw values). Emits `tokens.css`, category-specific files, `tokens.json` (Figma Variables compatible), `tailwind.config.js`, and a README documenting source URL, date, strategy, and counts.

### User flow analysis

`design-intel flow --flow signup.yaml --base-url X` executes a multi-step Playwright journey, captures screenshots at each step, and benchmarks step count against industry norms (signup ≤ 3, login ≤ 2, checkout ≤ 5, onboarding ≤ 5). Structured YAML, not natural-language step parsing — flows live in version control alongside your code.

### Autopilot: LLM drives the browser

`design-intel autopilot --url X --goal "review the signup + dashboard flow"` launches a visible browser, screenshots each page, and asks Claude what to do next. Claude picks one action at a time (CLICK / FILL / NAVIGATE / SCROLL / DONE / STOP). Loop detection (identical action twice → graceful STOP), 3 consecutive failed actions → STOP, max-steps cap (default 20). Each action logged for audit. ~$0.30 in Anthropic credits for a 15-step journey. Output structure matches `interactive`: per-page reports + cross-page synthesis + `actions.md`.

### Scheduled monitoring

`design-intel monitor --url X` runs an audit, persists to history, diffs against the last baseline, emits a trend-aware report, and optionally posts to a Slack-compatible webhook on regression. **No embedded scheduler** — delegates timing to GitHub Actions, cron, etc. A weekly workflow template ships at `templates/ci/github-actions-monitoring.yml`. Webhook failures are recorded but never crash the job.

### Interactive review + pragmatic flags

**New to the project? Run `design-intel review`.** It asks four questions (target, mode, output format, optional context), shows the command it's about to run, confirms, then executes. Five modes: `pragmatic-audit` (no LLM, fastest), `pragmatic-critique` (top findings, severity ≥ 2), `deep-critique` (4 agents, no filtering), `brand-compliance` (rules.yaml), `everything` (deep + WCAG + components + interactions, no filtering).

---

## MCP server

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

Once wired, you can ask your coding agent to "run WCAG on localhost:3000" or "critique the staging deploy" from inside the editor. Knowledge entries are citeable as context via the `design-intel://knowledge/{category}/{slug}` URI template.

---

## Architecture

### Data pipeline

```
URL / Screenshot / Description
    ↓
[Input Processor]      Playwright screenshots, DOM extraction, SPA crawl
    ↓
[Deterministic Analysis]  WCAG checker, axe-core, components, fixes (no LLM)
    ↓
[Knowledge Retrieval]  Context-aware tag matching from 39-entry library
    ↓
[LLM Agents]           Single-agent · 4 specialised agents · N-model ensemble
    ↓
[Reconciliation]       Cross-checks sub-agent findings, removes contradictions
    ↓
[Synthesis]            (ensemble only) Cross-model consensus
    ↓
[Output]               Markdown · HTML · PDF · JSON · regression diff · history
```

### What the deterministic layer catches

Pure analysis over DOM data, no LLM calls. The WCAG checker runs 11 checks across 10 criteria deterministically — same input, same output, every run. Alpha-composited contrast handles semi-transparent backgrounds. Off-screen elements (skip links) excluded from touch target checks. Multi-page violations deduplicated by unique element. AA and AAA target-size rows stay separated to prevent double-counting. The state-test harness falls back from `networkidle` to `domcontentloaded` on sites with persistent analytics so hover/focus tests run instead of silently timing out.

### What the LLM adds

Subjective judgement that code can't do: visual hierarchy and composition quality, typography rhythm, component intent vs semantics (is a checkbox being used where a toggle button would be correct?), ARIA pattern correctness against WAI-ARIA APG, screen-reader experience narrative, design-system maturity assessment, and root-cause analysis (which token maps to the failing contrast value?).

### Regression tracking

Every run is stored in `.design-intel/` with score, WCAG results, and issue inventory. Subsequent runs show a regression report with `Fixed`, `Persistent`, and `New` buckets and a signed score delta. Same fingerprinting powers the CI gate, the `diff` command, and the `monitor` trend report — one definition of "what counts as a regression" across all tools.

---

## WCAG coverage

The deterministic checker runs 11 reproducible checks across 10 WCAG 2.2 criteria. Plus axe-core for 100+ additional industry-standard rules.

| Criterion | Level | What it checks |
|---|---|---|
| 1.3.1 Info and Relationships | A | Landmarks (`main`, `nav`, `header`, `footer`) + heading hierarchy |
| 1.4.1 Use of Color | A | Flagged for manual review |
| 1.4.3 Contrast (Minimum) | AA | Text/background pairs vs 4.5:1 (and 3:1 for large) |
| 1.4.11 Non-text Contrast | AA | UI component boundaries vs 3:1 |
| 2.4.1 Bypass Blocks | A | Skip link presence |
| 2.4.7 Focus Visible | AA | Stylesheet scan for `:focus-visible` rules |
| 2.5.8 Target Size (Minimum) | AA | 24×24px minimum |
| 2.5.5 Target Size (Enhanced) | AAA | 44×44px (aspirational) |
| 3.1.1 Language of Page | A | `lang` attribute on `html` |
| 4.1.2 Name, Role, Value | A | Form inputs with programmatic labels |

The report separates A/AA failures (must fix for compliance) from AAA (aspirational). WCAG score is calculated on A/AA only.

Grounded in: WCAG 2.2 AA, Nielsen's 10 Heuristics + Severity Scale (0–4), Gestalt principles, Fitts's Law. Findings reference specific criteria by number and heuristic by name.

---

## LLM providers

Works with any LLM provider via [LiteLLM](https://github.com/BerriAI/litellm). Configure in `.env`.

| Provider | Models | Cost | Vision? |
|---|---|---|---|
| Anthropic | `claude-sonnet-4-20250514`, `claude-opus-4-20250514` | Paid | Yes |
| OpenAI | `gpt-4o`, `gpt-4o-mini` | Paid | Yes |
| Google | `gemini-2.5-pro`, `gemini-2.5-flash` | Paid (flash has free tier) | Yes |
| Groq | `llama-3.3-70b-versatile`, `llama-3.2-90b-vision-preview` | Free tier | Partial |
| DeepSeek | `deepseek-chat` | Very low cost | No |
| Mistral | `mistral-large-latest`, `mistral-small-latest` | Paid | No |
| Together AI | `meta-llama/Llama-3.3-70B-Instruct-Turbo` | Low cost | No |
| OpenRouter | 100+ models | Varies (some free) | Varies |
| Ollama | `llama3.2-vision`, `gemma3`, any local model | Free (local) | Yes |

**Recommended ensemble for best coverage vs cost:**
```env
ENSEMBLE_MODELS=anthropic/claude-sonnet-4-20250514,openai/gpt-4o-mini,groq/llama-3.3-70b-versatile
```

**Single-provider example (Anthropic, default):**
```env
LLM_PROVIDER=claude
LLM_MODEL=claude-sonnet-4-20250514
ANTHROPIC_API_KEY=sk-ant-...
```

---

## Benchmarking

### Output quality vs raw Claude (excalidraw.com)

| Agent | Score | Specificity | Actionability | A11y | Design System | Unique |
|---|---|---|---|---|---|---|
| **design-intel (ensemble)** | **94%** | 100% | 95% | 100% | 100% | 100% |
| **design-intel (deep)** | **86%** | 100% | 50% | 100% | 100% | 100% |
| Sonnet 4.6 (raw) | 85% | 100% | 50% | 100% | 100% | 100% |
| design-intel (single) | 78% | 100% | 90% | 100% | 100% | 0% |
| Opus 4.6 (raw) | 73% | 75% | 50% | 100% | 50% | 100% |

Ensemble mode wins because each model's full output is preserved (no information loss) and the synthesis adds consensus analysis on top. Different models catch different things — the ensemble captures all of them.

```bash
.venv/bin/python -m tests.benchmark_critique
```

### Deterministic benchmarks (no LLM, reproducible)

The deterministic analysers ship with their own correctness benchmarks that fail CI if output regresses below 90%.

| Benchmark | What it scores | Floor | Current |
|---|---|---|---|
| `benchmark_fix_generator` | Coverage, contrast accuracy, target-size accuracy, HTML validity, determinism, selector quality | 90% | **100%** |
| `benchmark_competitive` | Metric count, winner correctness, symmetry, tie handling, lower-is-better discipline, markdown shape | 90% | **100%** |
| `benchmark_diff_analyzer` | Fingerprint-diff correctness, exit codes, score delta math, markdown completeness, visual diff, JSON shape | 90% | **100%** |
| `benchmark_monitoring` | Exit codes, fingerprint diff vs baseline, trend truncation, alert discipline, JSON shape | 90% | **100%** |
| `benchmark_system_extractor` | Strategy selection, direct fidelity, synthesis naming, dedup, file output, Tailwind+JSON shape | 90% | **100%** |
| `benchmark_brand_rules` | Rule loading, validation correctness, framework template parity | 90% | **100%** |
| `benchmark_flow_analyzer` | Step execution, screenshot capture, industry-norm benchmarking | 90% | **100%** |

```bash
.venv/bin/python -m tests.benchmark_fix_generator
```

### Testing

637 unit and integration tests across all modules, plus the deterministic benchmarks above.

```bash
.venv/bin/python -m pytest tests/ -q \
  --ignore=tests/benchmark_critique.py \
  --ignore=tests/benchmark_fix_generator.py
```

---

## Sample reports

Real critique reports generated by design-intel on public websites:

| Site | Mode | Score | Report |
|---|---|---|---|
| [Anthropic](https://anthropic.com) | Deep + dual viewport | 68/100 | [anthropic-deep-dual.md](reports/samples/anthropic-deep-dual.md) |
| [Anthropic](https://anthropic.com) | Standard desktop | 68/100 | [anthropic-desktop.md](reports/samples/anthropic-desktop.md) |
| [Excalidraw](https://excalidraw.com) | Deep | 59/100 | [excalidraw-deep.md](reports/samples/excalidraw-deep.md) |
| [StackBlitz](https://stackblitz.com) | Deep | 59/100 | [stackblitz-deep.md](reports/samples/stackblitz-deep.md) |
| [GitHub Explore](https://github.com/explore) | Deep | 62/100 | [github-deep.md](reports/samples/github-deep.md) |

---

## Configuration

| Variable | Default | Description |
|---|---|---|
| `LLM_PROVIDER` | `claude` | `claude`, `openai`, `ollama`, etc. |
| `LLM_MODEL` | `claude-sonnet-4-20250514` | Model identifier |
| `ENSEMBLE_MODELS` | (unset) | Comma-separated list for `--ensemble` |
| `KNOWLEDGE_RETRIEVAL_LIMIT` | `2000` | Max tokens of knowledge context per call |
| `RETRIEVAL_TOP_K` | `5` | Number of knowledge chunks retrieved |
| `OUTPUT_FORMAT` | `markdown` | `markdown`, `json`, or `yaml` |
| `CRITIQUE_SEVERITY_THRESHOLD` | `low` | Minimum severity to include |

See `.env.example` for the full list.

---

## Knowledge library

39 entries across 10 domains, sourced from authoritative references (WCAG, Nielsen, Apple HIG, Material Design, Carbon, etc.):

```
knowledge/
  accessibility/   heuristics/   typography/   colour/      layout/
  interaction/     systems/      critique/     motion/      mobile/
```

Context-aware retrieval selects relevant entries based on what's actually in the DOM (dark theme detected → dark mode guidelines loaded; forms detected → form design patterns loaded). To add an entry, see [CONTRIBUTING.md](CONTRIBUTING.md).

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, test commands, and how to add new analysers, knowledge entries, or framework brand-rule templates. Bug reports, feature requests, and PRs welcome.

Brand rule templates for popular frameworks live in `templates/rules/` (Tailwind, Material Design, Bootstrap, Shadcn/ui).

---

## License

[MIT](LICENSE) © 2026 Matt Clayton
