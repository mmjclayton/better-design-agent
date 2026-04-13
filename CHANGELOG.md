# Changelog

All notable changes to design-intel are documented here.

## [Unreleased]

### Added
- `design-intel check` — one-line quick design quality score, pipe-friendly
- `design-intel doctor` — environment diagnostic checklist
- `design-intel version` — runtime environment info
- `--version` / `-V` flag on all commands
- CONTRIBUTING.md with development setup and contribution guide
- GitLab CI and Bitbucket Pipelines templates
- Pre-built brand rule templates for Tailwind, Material Design, Bootstrap, Shadcn/ui
- GitHub issue and PR templates

## [0.1.0] - 2026-04-08

### Initial Release

35 features shipped including:

- **Critique agent** with 39-entry knowledge library across 10 domains
- **Multi-agent ensemble** across 9 LLM providers (Anthropic, OpenAI, Google, Groq, DeepSeek, Mistral, Together AI, OpenRouter, Ollama)
- **WCAG 2.2 checker** — 11 deterministic criteria, no LLM
- **axe-core integration** — 100+ WCAG rules via Playwright injection
- **Auto-fix generation** — CSS/HTML patches for contrast, target size, labels, landmarks
- **Component scoring** — per-component detection and grading (nav, forms, buttons, lists, cards)
- **UI audit** — 7-category deterministic scoring (typography, color, spacing, interactive, hierarchy, patterns, copy)
- **Brand compliance** — validate against custom YAML rules (fonts, colours, tokens)
- **User flow analysis** — multi-step journey testing with industry benchmarks
- **Design system extraction** — reverse-engineer tokens to CSS, JSON, and Tailwind config
- **Competitive benchmarking** — 10-metric comparison between two sites
- **Before/after diff** — score delta, issue buckets, visual diff PNG
- **CI gate** — pragmatic mode (grandfathers pre-existing violations) or strict
- **Scheduled monitoring** — trend tracking with Slack webhook alerts
- **Autopilot** — LLM-driven browser exploration
- **Interactive review** — human-in-loop page-by-page capture with synthesis
- **MCP server** — 6 tools + knowledge resources for Claude Code, Cursor, Windsurf
- **PDF export** — print-ready reports with cover page, TOC, page numbers
- **Developer handoff** — token tables, layout specs, component inventory
- **HTML reports** — inline screenshots, score dashboard
