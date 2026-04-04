# Better Design Agent

An agent-based CLI that delivers expert-level UX/UI design critique, developer handoff specs, and accessibility audits - powered by deterministic analysis, multi-agent architecture, and a knowledge library of 39 design principles across 10 domains.

Outperforms raw Claude Opus and Sonnet sessions on structured design critique benchmarks (94% ensemble vs 73% Opus / 85% Sonnet) by combining deterministic analysis, multi-agent architecture, and multi-model ensemble synthesis.

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
| `design-intel critique --image ./screenshot.png` | Screenshot-only visual critique (no code claims) | Yes |
| `design-intel wcag --url X` | WCAG 2.2 audit (custom checker + axe-core, 100+ rules) | No |
| `design-intel test-interactions --url X` | Keyboard nav, forms, empty states, responsive | No |
| `design-intel components --url X` | Component detection + per-component scoring | No |
| `design-intel handoff --url X` | Developer handoff specification | Yes |
| `design-intel history --url X` | View run history + score trend | No |
| `design-intel index-knowledge` | Rebuild knowledge index | No |

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
├── src/
│   ├── cli.py                       # Typer CLI (all commands)
│   ├── config.py                    # Pydantic Settings
│   ├── providers/llm.py             # LiteLLM wrapper (Claude, OpenAI, Ollama)
│   ├── input/
│   │   ├── processor.py             # Input normalisation
│   │   ├── screenshot.py            # Playwright: screenshots, DOM extraction, SPA crawl,
│   │   │                            #   state testing, image compression
│   │   └── models.py                # DesignInput, PageCapture dataclasses
│   ├── agents/
│   │   ├── base.py                  # Base agent with knowledge retrieval
│   │   ├── critique.py              # Single-agent critique
│   │   ├── orchestrator.py          # Multi-agent parallel orchestrator
│   │   ├── accessibility_agent.py   # ARIA, semantics, screen reader, focus management
│   │   ├── design_system_agent.py   # Tokens, root cause, naming, maturity
│   │   ├── visual_agent.py          # Hierarchy, composition, rhythm, aesthetics
│   │   ├── interaction_agent.py     # States, affordances, feedback
│   │   └── handoff_agent.py         # Developer handoff specification
│   ├── analysis/
│   │   ├── wcag_checker.py          # Deterministic WCAG 2.2 checker (11 criteria)
│   │   ├── interaction_tester.py    # Keyboard nav, form validation, empty states, responsive
│   │   ├── component_detector.py    # Component detection + per-component scoring
│   │   └── history.py               # Run history, regression tracking, score diff
│   ├── knowledge/
│   │   ├── store.py                 # Read/write knowledge entries
│   │   ├── index.py                 # Tag-based index
│   │   └── retriever.py             # Context-aware retrieval
│   └── output/
│       └── formatter.py             # Report saving
├── knowledge/                       # Design knowledge corpus (39 entries, git-tracked)
│   ├── INDEX.yaml                   # Auto-generated tag index (100 tags)
│   └── CORPUS_SOURCES.md            # Source reference document
├── tests/
│   └── benchmark_critique.py        # Output quality benchmark (7 dimensions)
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

## Roadmap

- [x] **Phase 1** - Critique Agent + knowledge library (39 entries, 10 domains)
- [x] **Phase 1.5** - DOM extraction, HTML audit, multi-page SPA crawl
- [x] **Batch 1** - Deterministic WCAG 2.2 checker (11 criteria, no LLM)
- [x] **Batch 2** - Regression tracking with run history and issue-level diff
- [x] **Batch 3** - Multi-agent architecture (4 specialized agents in parallel)
- [x] **Batch 4** - Real interaction testing (keyboard, forms, empty states, responsive)
- [x] **Batch 5** - Component-level detection and scoring
- [x] **Extra** - Stage-aware critique, device presets, developer handoff, image compression
- [x] **Ensemble** - Multi-model parallel analysis with consensus synthesis (94% benchmark)
- [x] **Step 1** - Axe-core integration (100+ WCAG rules via Playwright)
- [x] **Step 2** - HTML reports with inline screenshots and score dashboard
- [x] **Quality** - Stealth mode, access denied detection, screenshot-only mode, viewport detection, sub-agent reconciliation, AA/AAA separation, deduplication
- [ ] **Step 3** - Comparative mode (before/after visual diff)
- [ ] **Step 4** - CI/CD integration (exit codes, GitHub Actions template)
- [ ] **Step 5** - PDF export
- [ ] **Step 6** - Custom design rules (.design-intel/rules.yaml)
- [ ] **Step 7** - Figma input support
- [ ] **Step 8** - Watch mode (live feedback during dev)
- [ ] **Step 9** - Plugin system
- [ ] **Step 10** - Web dashboard

Full build plan: [docs/BUILD_PLAN.md](docs/BUILD_PLAN.md)

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
