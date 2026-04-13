# design-intel: Backlog

Single source of truth for work items. Never delete without trace: update in place, mark superseded, or archive.

## Tag Taxonomy

Status (first): `[OPEN]` | `[IN PROGRESS]` | `[BLOCKED]` | `[SHIPPED - YYYY-MM-DD]` | `[VERIFIED - YYYY-MM-DD]` | `[WON'T]`
Type (second): `[Feature]` | `[Iteration]` | `[Bug]` | `[Refactor]` | `[Infra]`

**Tag rules:**
- Status first, type second. Never reverse.
- `[WON'T]` requires inline reason: `[WON'T] [Type] Reason: [explanation or superseding P-number]`
- `[VERIFIED]` = tested in production or confirmed accurate
- P-numbers are sequential, never reused, do not imply priority
- Acceptance criteria must be CLI-observable (commands, flags, files, exit codes, stdout patterns)
- Status changes ship in the same commit as the code
- Never delete items. Move to Shipped Archive when Backlog exceeds ~2,000 lines (items >90 days old).

## P-Numbered Items

Items ordered: In Progress > Blocked > Open > Shipped (most recent first).

---

## [SHIPPED - 2026-04-08] [Feature] Quick Score Command — design-intel check

**Summary.** Zero-config, no-LLM command that prints a single design quality
score line to stdout. Pipe-friendly with `--json` and `--threshold` flags.

**Acceptance criteria.**
1. `design-intel check https://example.com` prints `<url> <score>/100 (<categories>)` to stdout.
2. `--json` outputs parseable JSON with url, score, and categories.
3. `--threshold N` exits 0 if score >= N, exits 1 if below.
4. `--device <preset>` selects viewport. Unknown devices exit 2.
5. All status/progress output goes to stderr (pipe-clean stdout).
6. 8 unit tests pass in `tests/test_check.py`.

---

## [SHIPPED - 2026-04-08] [Infra] Version and Doctor Commands

**Summary.** `design-intel --version` prints version. `design-intel version`
prints version + Python + Playwright info. `design-intel doctor` validates
environment: Python version, Playwright, Chromium, API keys, .design-intel/
directory, network connectivity.

**Acceptance criteria.**
1. `design-intel --version` prints `design-intel <version>` and exits 0.
2. `design-intel version` prints version, Python version, Playwright version.
3. `design-intel doctor` checks 7 items: Python, design-intel, Playwright,
   Chromium, API keys, .design-intel/, network. Exits 0 if all pass, 1 if warnings.
4. 6 unit tests pass across `tests/test_version.py` and `tests/test_doctor.py`.

---

## [SHIPPED - 2026-04-08] [Infra] Community Scaffolding

**Summary.** Community contribution infrastructure: CONTRIBUTING.md,
CHANGELOG.md, GitHub issue templates (bug report, feature request), PR template.

**Acceptance criteria.**
1. `CONTRIBUTING.md` exists with dev setup, test commands, and how-to-add-an-analyser guide.
2. `CHANGELOG.md` exists with retroactive 0.1.0 entry and unreleased section.
3. `.github/ISSUE_TEMPLATE/bug_report.md` and `feature_request.md` exist.
4. `.github/PULL_REQUEST_TEMPLATE.md` exists.

---

## [SHIPPED - 2026-04-08] [Feature] Framework Rule Templates + CI Templates

**Summary.** Pre-built `rules.yaml` templates for Tailwind, Material Design,
Bootstrap, and Shadcn/ui. CI pipeline templates for GitLab and Bitbucket.
`design-intel init --framework <name>` copies the matching template.

**Acceptance criteria.**
1. `templates/rules/tailwind-default.yaml`, `material-design.yaml`,
   `bootstrap.yaml`, `shadcn-ui.yaml` exist with correct brand rules.
2. `templates/ci/gitlab-ci-design-review.yml` and
   `bitbucket-pipelines-design-review.yml` exist.
3. `templates/ci/README.md` documents all templates.
4. `design-intel init --framework tailwind` copies the template to
   `.design-intel/rules.yaml`.

---

## P3 [OPEN] [Feature] GitHub PR Comment Integration

**Summary.** `design-intel ci --url X --github-comment` posts a structured PR
comment with score, violation table, and inline fix suggestions using the
GitHub API.

**Context.** The current CI gate uploads a JSON artifact. Developers don't
read artifacts — they read PR comments. ESLint, Lighthouse CI, and Codecov
all post PR comments; this is the pattern that makes CI gates visible.

**Acceptance criteria.**
1. `--github-comment` flag on `ci` command posts a markdown comment to the
   current PR via GitHub API using `$GITHUB_TOKEN`.
2. Comment includes: overall score, new/fixed/persistent violation counts,
   top 5 violations with fix suggestions, pass/fail verdict.
3. Requires `GITHUB_TOKEN` env var; skips with a warning if not set.
4. Works in GitHub Actions (reads PR number from `$GITHUB_EVENT_PATH`).
5. Unit tests mock the GitHub API call and verify comment formatting.

---

## P4 [OPEN] [Feature] Published GitHub Action

**Summary.** `uses: mmjclayton/design-intel-action@v1` — a published GitHub
Action that reduces CI setup from 8+ lines to 3.

**Context.** The current GitHub Actions template requires manual Python setup,
pip install, and Playwright browser installation. A published action removes
all friction. pa11y and Lighthouse both have published actions.

**Acceptance criteria.**
1. `action.yml` with inputs: url, mode, min-score, github-token.
2. Dockerfile or composite action that installs design-intel + Chromium.
3. Posts PR comment when github-token is provided.
4. Published to GitHub Marketplace.
5. README section with 3-line usage example.

---

## P6 [OPEN] [Feature] Violation Explainer: design-intel explain

**Summary.** `design-intel explain 1.4.3` returns what the WCAG criterion
means, why it matters, how to fix it, and spec links. Optionally scoped to a
URL to show specific affected elements.

**Context.** When CI gates fail, developers Google the criterion ID. This
command gives a contextualized answer using the existing 39-entry knowledge
library, saving a round-trip to the spec.

**Acceptance criteria.**
1. `design-intel explain 1.4.3` prints criterion explanation, user impact,
   fix guidance, and WCAG spec link.
2. `design-intel explain "target size"` fuzzy-matches criterion by name.
3. `--url X` adds the specific elements on that page that violate the criterion.
4. Uses knowledge library entries; falls back to LLM for criteria not covered.
5. Unit tests verify lookup, fuzzy matching, and output formatting.

---

## P7 [OPEN] [Feature] Framework-Aware Fix Suggestions: design-intel suggest

**Summary.** Extends `fix` with framework translation: instead of raw CSS,
emits Tailwind classes, React/JSX diffs, or Bootstrap class changes.

**Context.** `design-intel fix` generates raw CSS patches. Most frontend
developers write Tailwind or React, not raw CSS. Bridging this gap makes
fixes immediately actionable.

**Acceptance criteria.**
1. `design-intel suggest --url X --framework tailwind` maps hex values to
   nearest Tailwind color class and emits class-based fixes.
2. `--framework react` emits JSX diffs.
3. `--framework bootstrap` emits Bootstrap class changes.
4. Auto-detects framework from DOM heuristics when `--framework` is omitted.
5. Unit tests verify translation for each framework.

---

## [SHIPPED - 2026-04-06] [Feature] Opinionated UI Review — design-intel ui-audit

**Summary.** New `review` subcommand that performs an opinionated UI/UX
quality audit on a live URL. Combines deterministic CSS/DOM analysis
(typography consistency, spacing discipline, color palette coherence,
interactive element polish) with an LLM opinion layer that synthesises
findings into prioritised, actionable improvement suggestions.

**Context.** The existing `critique` command gives an LLM-driven impression
from a screenshot. The `wcag` command checks accessibility compliance.
Neither answers the builder's core question: "is my UI consistent, legible,
and well-crafted?" This command grounds design feedback in real computed
CSS values — when it says "you have 14 font sizes", it lists them.

**Current state.**
- DOM extraction already captures: font sizes/families (with counts),
  spacing values (with counts), text/background colors (with counts),
  interactive elements (dimensions, labels), contrast pairs, heading
  structure, CSS tokens, state tests (hover/focus), layout metadata.
- `system_extractor.py` extracts design tokens but doesn't evaluate quality.
- `component_detector.py` scores components but not design consistency.
- No command evaluates typography scale, spacing grid, or color discipline.

**Target state.**
- `design-intel ui-audit --url <url>` runs a layered analysis and emits a
  structured report with per-category scores and concrete fix suggestions.

**Acceptance criteria.**
1. `design-intel ui-audit --url <url>` captures the page and runs the full
   analysis pipeline. No `--image` support in v1 (needs live DOM).
2. Deterministic layer scores five categories (each 0-100):
   - **Typography**: font-family count (fewer = better), font-size count
     vs ideal scale, line-height range, heading hierarchy gaps.
   - **Color**: distinct color count, palette clustering, text/bg diversity.
   - **Spacing**: distinct spacing value count, adherence to a base grid
     (4px/8px), scatter metric.
   - **Interactive**: touch-target compliance %, hover-state coverage %,
     consistent sizing of similar elements.
   - **Visual hierarchy**: heading level usage, single H1, logical order,
     CTA prominence (largest interactive element exists).
3. Each category finding includes: what was found, why it matters, and a
   specific recommendation.
4. LLM opinion layer receives: the deterministic scores, the raw findings,
   and the page screenshot. It produces 3-5 prioritised improvement
   suggestions with rationale — things the deterministic checks can't
   catch (layout balance, visual flow, clarity of purpose).
5. Overall score is a weighted average of the five category scores.
6. `--format json` emits a structured JSON document with all scores,
   findings, and LLM suggestions.
7. `--save` writes the report to `output/review-<timestamp>/`.
8. `--no-llm` flag skips the LLM layer and emits only deterministic results.
9. Report markdown includes a summary table, per-category detail sections,
   and the LLM suggestions section.
10. Unit tests cover: all scoring functions with synthetic DOM data,
    category score calculations, overall score weighting, report rendering,
    JSON schema shape. LLM layer tested via mock.

**Technical notes.**
- Analyser lives at `src/analysis/ui_review.py` — pure data transformation
  for the deterministic layer, same pattern as `wcag_checker.py`.
- LLM opinion uses the existing litellm provider abstraction.
- Reuses `process_input()` for URL capture — same flow as `critique`.
- Category weights: typography 25, color 20, spacing 20, interactive 20,
  hierarchy 15.

**Out of scope (v1).**
- Responsive multi-breakpoint audit (future item).
- Component pattern heuristics (future item — "your form has too many fields").
- Design system generation / cleanup proposals (future item).
- Framework-aware suggestions (Tailwind classes etc.) — future item.
- Copy/microcopy review — future item.
- Alignment / grid analysis (needs DOM extraction extension) — future item.

**Open questions.** None — ship it.

---

## [SHIPPED - 2026-04-05] [Feature] User Flow Analysis — design-intel flow

**Summary.** New `flow` subcommand that executes a multi-step user journey
(signup, checkout, onboarding) via Playwright, captures screenshots + DOM
data at each step, and emits a step-by-step report with timings + industry
benchmark comparison. No LLM for v1 — deterministic scoring against
known-good step counts.

**Context.** Page-level critiques miss flow problems. A single page can
score 80/100, but the signup flow it's embedded in could be 7 steps when
industry norm is 2-3. No current command measures that.

**Design decision: structured step YAML, not natural language.**
Natural-language step parsing ("click Sign Up") is lossy and unreliable.
Users write explicit selectors in a YAML file — same pattern as Cypress /
Playwright test fixtures. Maintainable, debuggable, no LLM dependency.

**Current state.**
- Playwright is already a dep for DOM extraction + axe-core.
- `src/input/screenshot.py` has reusable browser-launch patterns.
- `src/analysis/interaction_tester.py` does single-page interaction
  testing but isn't flow-aware.
- No multi-step execution engine.

**Target state.**
- `design-intel flow --flow flows/signup.yaml --base-url https://x.com`
  loads a YAML file defining steps, executes them sequentially, and
  emits a markdown report with per-step outcomes, timings, and overall
  verdict.

**Acceptance criteria.**
1. `design-intel flow --flow <path>.yaml --base-url <url>` loads the YAML,
   launches Playwright, executes steps sequentially against the base URL.
2. YAML schema supports four action types per step:
   `navigate` (go to URL), `click` (CSS selector), `fill` (selector + value),
   `assert_text` (text presence on page). Each step also has a `name`.
3. Each step records: outcome (pass/fail), duration_ms, optional error
   message, screenshot path (captured after action).
4. Report includes: flow name, total step count, total duration, per-step
   table, industry-benchmark comparison (signup ≤ 3, checkout ≤ 5, login
   ≤ 2), and an overall verdict.
5. `--flow-type` flag (signup|checkout|login|onboarding|other) picks the
   benchmark. Defaults to `other` (no benchmark comparison).
6. Exit codes: `0` all steps passed + within benchmark; `1` step failed
   OR step count exceeds benchmark; `2` technical error (YAML missing/
   malformed, Playwright launch failure).
7. `--format json` emits a schema-v1 document with flow metadata + step
   results array + benchmark comparison.
8. `--save` writes the markdown report + a screenshots subdirectory to
   `output/flow-<timestamp>/`.
9. An example flow YAML is committed at `examples/flow-example.yaml`.
10. Unit tests cover: YAML schema validation (all action types, missing
    required fields, unknown action type), step-result aggregation,
    benchmark comparison logic, exit code paths, report rendering, JSON
    schema shape. Playwright execution itself is integration-tested
    manually (same pattern as `pdf_report.py`).

**Technical notes.**
- YAML load via `pyyaml` (already a dep).
- Playwright launch: reuse the `sync_playwright` pattern from
  `pdf_report.py` for the sync execution model.
- Step timeouts: 10s per action (configurable via YAML).
- `fill` actions: wait for the selector to be visible, then type the
  value (Playwright's `page.fill` handles the waiting).
- `assert_text`: uses `page.wait_for_selector(f"text={value}")` with
  timeout. Failure marks the step (and flow) as failed.
- Industry benchmarks hardcoded for v1 — can become config later.
- Screenshots: `page.screenshot(path=...)` after each step, stored in
  the flow's output dir.

**Out of scope.**
- Natural-language step parsing (e.g. "click the signup button").
- Conditional steps / loops / retries.
- Cognitive-load heuristics (needs LLM judgment — follow-up feature).
- Error-recovery analysis (needs intentional-failure runs).
- Form-validation coverage (already handled by `test-interactions`).
- Cross-browser flow testing (Chromium only in v1).
- Authentication flows that require 2FA / CAPTCHA.
- Network mocking / fixture data injection.

**Open questions.** None blocking.

**Reference materials.**
- `src/input/screenshot.py` — Playwright launch + screenshot patterns.
- `src/analysis/interaction_tester.py` — single-page test harness.
- `src/output/pdf_report.py` — two-layer split (pure logic + Playwright
  integration) for testability.
- ROADMAP.md P1 (source of this spec).

---

## [SHIPPED - 2026-04-05] [Infra] Ship-ready polish — init command + project config + README quickstart

**Summary.** Trivial-but-impactful pre-distribution polish: a first-run
`init` command, project-local `.design-intel/config.yaml` with env-var
expansion, 60-second quickstart + table of contents at the top of the
README. All in service of getting the tool ready to show strangers.

**Acceptance criteria (all met).**
1. `design-intel init` bootstraps `.env` (from `.env.example`), creates
   `.design-intel/`, writes a `config.yaml` template, ensures `output/`
   exists. Safe to re-run (`--force` to overwrite).
2. `src/project_config.py` loads `.design-intel/config.yaml` walking up
   the directory tree. Supports default_url, default_mode, default_device,
   default_context, plus ci: {} and monitor: {} subsections.
3. Env-var references in YAML string values (`$VAR` and `${VAR}`) are
   expanded at read time.
4. `autopilot` command reads project config defaults for URL/mode/device
   when flags not provided; prints the loaded config path.
5. README has a 60-second quickstart at the top (install → init → run)
   and a 16-link table of contents covering every major section.
6. 15 unit tests for the config loader (walks-up-tree, malformed YAML
   fallback, env expansion, missing var preservation, subsection loading,
   non-mapping rejection).

**Technical notes.**
- `find_config_file()` walks up parent directories so commands run from
  subdirectories still pick up the project config.
- Malformed YAML silently falls back to empty config — never crashes.
- Env-var expansion uses `os.path.expandvars` (keeps unexpanded vars
  literal when env var is missing).

---

## [SHIPPED - 2026-04-05] [Feature] Autopilot — LLM-driven autonomous review

**Summary.** New `autopilot` subcommand that lets Claude drive the browser
autonomously: user provides a URL + a natural-language goal, design-intel
screenshots the page, asks Claude for the next action, executes it in
Playwright, repeats until the goal is met. After navigation, runs the
standard synthesis pipeline over every captured page.

**Context.** Interactive mode (human-driven) works well when the user
knows their app. Autopilot adds the "point-and-walk-away" capability for
unknown apps, competitor research, or batch/unattended review. The user
explicitly asked for the choice between modes.

**Current state.**
- Interactive mode keeps a human in the loop (press Enter per page).
- `_capture_page()` + synthesis pipeline ready to reuse.
- `call_llm()` with image support already in `src/providers/llm.py`.
- No LLM-action-loop code yet.

**Target state.**
- `design-intel autopilot --url X --goal "review signup + dashboard"`
  launches a visible Chromium, drives it step-by-step via Claude, and
  outputs the same kind of session-combined + session-priorities report
  as interactive mode.

**Acceptance criteria.**
1. `design-intel autopilot --url <url> --goal "<text>"` runs a loop:
   capture → LLM action → execute → capture again.
2. The LLM chooses from a fixed action vocabulary: `CLICK`, `FILL`,
   `NAVIGATE`, `SCROLL`, `DONE`, `STOP`. No other verbs accepted.
3. `--max-steps N` caps the loop (default 20). Exceeding the cap ends
   the session gracefully (not an error).
4. Every step captures a screenshot + DOM data + runs the selected
   analysis mode (same three modes as interactive: pragmatic-audit,
   pragmatic-critique, deep-critique).
5. After the loop: run `finalise_session()` to emit
   `session-combined.md` + `session-priorities.md`.
6. `--mode` flag matches interactive (pragmatic-audit | pragmatic-critique
   | deep-critique). Default: pragmatic-audit.
7. Action log written to `output/autopilot-<ts>/actions.md` showing
   each step's action + reasoning.
8. Unreachable goal or STOP action → exit cleanly, keep whatever was
   captured.
9. Unit tests cover action parsing (valid verbs, malformed strings),
   action validation, step-count enforcement, goal-completion
   detection, session-summary integration. Browser loop tested
   manually.

**Technical notes.**
- LLM action prompt is strict: one action per response, fixed format.
  Malformed responses → STOP action (fail safe).
- Action history (last 3 steps) included in every prompt so the LLM
  doesn't repeat itself in loops.
- No form-submit safety for v1 — users testing their own apps. Add
  confirmations later if needed.
- Reuses `_capture_page()` for screenshots + DOM extraction.
- Reuses `finalise_session()` + `synthesise_session()` unchanged.
- Vision model required (Claude Sonnet 4 / Opus 4). Check at startup.

**Out of scope.**
- OAuth / 2FA / CAPTCHA handling.
- File uploads, drag-and-drop, keyboard shortcuts.
- Dropdown option selection beyond basic FILL.
- Budget enforcement ($ per run).
- Cross-browser / mobile autopilot.
- Pausing for human review mid-run.

**Open questions.** None blocking.

---

## [SHIPPED - 2026-04-05] [Feature] UX sweep — login detection, friendly errors, progress, shim

**Summary.** Four coordinated UX improvements shipped together: auto-detect
when a URL returns a login page, translate technical errors into plain
English, show per-stage progress during long critique runs, and a one-shot
shim installer so `design-intel` works without the `.venv/bin/` prefix.

**Context.** The guided wizard covers discoverability. This round covers
the failure modes and long-wait pain points: users hit cryptic errors,
crawl runs against login pages unknowingly, critique sits silent for 90
seconds, and they have to type `.venv/bin/design-intel` every invocation.

**Acceptance criteria.**
1. **Login-page detection:** after any URL command captures a page, a
   pure `detect_login_page()` function inspects the DOM + URL + text.
   Flags pages with any of: title/heading containing login signals
   ("sign in", "log in", "login"), a password input, URL path containing
   `/login` or `/signin`. If detected AND no auth session is active, the
   command prints a friendly "this looks like a login screen — want to
   set up login access?" message before continuing.
2. **Friendly errors:** new `src/errors.py` module maps common exceptions
   (Playwright launch failures, chromium-not-installed, DNS errors, 403s,
   file-not-found, missing API keys) to plain-language messages with a
   concrete next action. Wired into `process_input` callsites.
3. **Progress feedback:** critique command shows a live stage name via
   `console.status()` updating through: extracting DOM → running WCAG →
   asking AI → finalising. No more 90 seconds of silence.
4. **Shim installer:** a `scripts/install-shim.sh` that creates a symlink
   `/usr/local/bin/design-intel` → the project's venv binary. Users run
   once, then can type `design-intel` from anywhere.
5. Unit tests cover: login-page detection on fixtures (true for a
   password-form page, false for a dashboard, true for a URL ending in
   /signin), error-message mapping (per exception type), shim script
   exists and is executable.

**Technical notes.**
- Login detection is DOM-shape-based. No LLM, no network.
- Error friendliness uses type-dispatched mapping; unknown exceptions
  keep their original message with a generic "open an issue" footer.
- Progress uses rich's existing `console.status()` context manager —
  no new dependencies.
- Shim script is bash, uses `$(cd ... && pwd)` for stable absolute
  paths, idempotent (replaces existing symlink).

**Out of scope.**
- LLM-driven login detection (DOM heuristics are enough for v1).
- Auto-login (user still logs in manually via `auth`).
- Streaming LLM output during critique (progress only, not content).
- Windows shim (bash only in v1; WSL users covered).

**Open questions.** None blocking.

---

## [SHIPPED - 2026-04-05] [Feature] Interactive review + pragmatic-mode flags

**Summary.** Two connected additions: (1) a `--pragmatic` flag on the
review commands (`critique`, `wcag`, `components`) that filters output to
the highest-signal findings, and (2) an interactive `review` command that
prompts the user for target + mode + output format and runs the right
underlying tool, so non-technical users don't have to memorise flag
combinations.

**Context.** Today's review commands output everything: full WCAG audits
with 11 criteria + passes + warnings + AAA aspirational findings; critique
reports that list every trivial polish issue. When a user just wants to
know "what should I fix next," the signal is buried in noise. The CI gate
already has a pragmatic mode — extend the same concept to ad-hoc review,
and make it discoverable via an interactive command.

**Out-of-roadmap rationale.** This isn't in the current P-list, but it's a
usability win that compounds every other review run. Justified as a UX
polish pass on the tools we already shipped.

**Current state.**
- `critique --url X` runs full 4-agent (or single) analysis, no filtering.
- `wcag --url X` prints every criterion including passes, warnings, AAA.
- `components --url X` lists every detected component and score.
- No interactive entry point; users must know flag combinations.

**Target state.**
- `--pragmatic` flag on `critique`, `wcag`, `components`: filters output
  to high-signal findings (severity ≥ serious, A/AA only, below-threshold
  components only).
- `design-intel review` launches an interactive 4-question flow that
  picks the right command + flags, confirms the plan, then runs it.

**Acceptance criteria.**
1. `design-intel wcag --url X --pragmatic` emits a report showing ONLY
   failing A/AA custom criteria + axe critical/serious violations. Drops
   passes, warnings, AAA criteria, na rows. No axe "passes" list.
2. `design-intel components --url X --pragmatic` emits only components
   scoring below 60%. Header shows "N components below threshold".
3. `design-intel critique --url X --pragmatic` injects a "pragmatic mode"
   instruction into the critique agent's context: limit to top 3–5
   findings per section, skip AAA/aspirational, skip trivial polish.
4. `design-intel review` launches interactive mode and asks 4 questions:
   (a) what to review — URL / image path / text description, auto-detected
   from the input format; (b) which mode — numbered list of 5 modes with
   one-line descriptions; (c) output format — terminal / md / md+html /
   md+html+pdf; (d) optional context.
5. After question 4, the `review` command **prints the resolved command**
   (e.g. `critique --url X --pragmatic --save`) and prompts "Run this?
   [Y/n]" before executing.
6. The five modes map to concrete command invocations:
   `pragmatic-audit` → `wcag --pragmatic` + `components --pragmatic`;
   `pragmatic-critique` → `critique --pragmatic`;
   `deep-critique` → `critique --deep`;
   `brand-compliance` → `brand-check`;
   `everything` → `critique --deep` + wcag + components + interactions.
7. `review --non-interactive --mode <name> --target <input>` runs without
   prompts (for scripting / testing).
8. Unit tests cover: pragmatic filtering for wcag + components, prompt
   injection for critique, input auto-detection (URL vs path), mode →
   command mapping, non-interactive path.

**Technical notes.**
- Use `rich.prompt.Prompt` for questions + `typer.confirm` for the run
  confirmation.
- Input auto-detection: starts with `http://` or `https://` → URL; file
  path exists and has image suffix → screenshot; everything else →
  rejected with clear error.
- Mode → command mapping is a lookup dict in `src/cli.py` so future
  modes are easy to add.
- The `--pragmatic` flag on `wcag` filters the existing `WcagReport` —
  no changes to the underlying analyser, just a new markdown-rendering
  path.
- Don't touch dual-viewport or crawl behaviour — they're orthogonal.

**Out of scope.**
- Folder-of-images batch review (URL or single image only in v1).
- Pragmatic mode for handoff, fix, compare, diff (only review commands).
- Auto-detect desktop vs mobile from user context in question 1.
- Saving interactive answers as a "review profile" for repeat runs.
- Nested mode configuration beyond the 5 presets.

**Open questions.** None blocking.

**Reference materials.**
- `src/analysis/wcag_checker.py` — existing WcagReport rendering.
- `src/analysis/component_detector.py` — existing component scoring.
- `src/agents/critique.py` — critique agent prompt construction.
- Rich's `Prompt.ask()` + Typer's `confirm()` for the interactive flow.

---

## [SHIPPED - 2026-04-05] [Feature] Custom Design Rules — design-intel brand-check

**Summary.** New `brand-check` subcommand that reads a `.design-intel/rules.yaml`
file from the project, validates the live site's DOM against it, and emits
a "Brand Compliance" report. Deterministic — no LLM involved.

**Context.** Teams need to enforce brand-specific standards that sit *above*
generic WCAG compliance: "we only ship Inter and Menlo, only these 8 hex
colours, never below 14px body text, must reference `--color-brand-primary`
everywhere." Currently there's no way to encode those rules machine-readably.

**Current state.**
- DOM extraction already captures every font family, font size, colour,
  and CSS custom property in use.
- `history.py` already uses `.design-intel/` as the project-local config dir.
- No rule engine, no YAML config loader, no brand-compliance report.

**Target state.**
- `design-intel brand-check --url X` reads `.design-intel/rules.yaml` and
  emits a pass/fail report per rule.
- Five rule types cover the roadmap ask: allowed fonts, allowed colours
  (by context: text/background), min font size, required tokens, forbidden
  tokens.
- Exit codes match the CI/monitor pattern (0 pass, 1 violation, 2 error)
  so brand-check drops into CI.

**Acceptance criteria.**
1. `design-intel brand-check --url <url>` runs, loads
   `.design-intel/rules.yaml` from the CWD, validates the live site's DOM
   against each rule, and prints a markdown compliance report.
2. `--rules <path>` accepts an explicit path to a rules file, overriding
   the default location.
3. The YAML schema supports five rule types: `allowed_fonts` (list),
   `allowed_colours.text` / `allowed_colours.background` (lists of hex),
   `min_font_size` (integer px), `required_tokens` (list of CSS var names),
   `forbidden_tokens` (list of CSS var names). All keys optional — only
   supplied rules are checked.
4. Report includes per-rule pass/fail + the specific violations (e.g.
   "font family 'Comic Sans' found but not in allowed_fonts").
5. Exit codes: `0` all rules passed, `1` one or more violations, `2`
   technical error (rules file missing/malformed, URL unreachable).
6. `--format json` emits a schema-v1 document with rule results, violation
   lists, and overall pass/fail.
7. `--save` writes the markdown report to `output/`.
8. An example rules file is committed at
   `examples/brand-rules-example.yaml` so users have a reference.
9. Missing rules file returns exit code 2 with a friendly "create
   .design-intel/rules.yaml" message pointing at the example.
10. Unit tests cover: each rule type in isolation (pass + violation
    cases), combined rules, missing rules file, malformed YAML, exit
    codes, JSON schema shape, and the schema-key vocabulary.

**Technical notes.**
- YAML loading via `pyyaml` (already a dep).
- Colour comparison: normalise to lowercase hex, strip leading `#`.
  Accept both `#fff` and `#ffffff` in the rules file.
- Font family comparison: case-insensitive substring match against the
  first family in each declaration's family stack ("Inter, sans-serif"
  → "Inter").
- Token checks run against `css_tokens` entries (names only; values
  aren't policed in v1).
- Keep scope tight — no regex rules, no per-element overrides, no "this
  rule applies to buttons only" targeting in v1.

**Out of scope.**
- Non-colour/non-font rules (shadow, radius, motion tokens).
- LLM-driven rule generation ("infer our brand standards from an existing
  page"). User writes the YAML manually for v1.
- Per-component rule targeting.
- Automatic rule suggestion from the `extract-system` output (possible
  follow-up, not v1).
- Severity levels (every violation equally weighted in v1).

**Open questions.** None blocking.

**Reference materials.**
- `src/input/screenshot.py` — DOM data shape (colors, fonts, css_tokens).
- `src/analysis/system_extractor.py` — token extraction reference.
- ROADMAP.md P1 (source of this spec).

---

## [SHIPPED - 2026-04-05] [Feature] PDF Export — `--pdf` flag on saved reports

**Summary.** Extend the existing HTML report pipeline so critiques can be
exported as a polished PDF (cover page, table of contents, page numbers,
print CSS) using Playwright's `page.pdf()`. Triggered via a new `--pdf`
flag alongside `--save` on the `critique` command.

**Context.** `design-intel critique --save` already writes markdown + HTML.
Stakeholders routinely want a shareable PDF for decks, printing, or
non-technical reviewers. Playwright is already in the stack, so PDF
generation adds no new dependencies.

**Current state.**
- `src/output/html_report.py` produces a self-contained HTML file with
  inline screenshots, score dashboard, and styled sections.
- Playwright is already imported for DOM extraction + axe-core.
- No PDF generation code exists.

**Target state.**
- `design-intel critique --url X --save --pdf` writes a third artefact
  alongside .md and .html: a print-ready PDF with cover page, TOC, and
  page numbers.
- HTML augmentation is a pure function (testable without Playwright).
- Playwright render is an integration point, tested with a single smoke
  test that can be skipped if Playwright isn't available.

**Acceptance criteria.**
1. `design-intel critique --url X --save --pdf` writes a `.pdf` file to
   `output/` in addition to the existing .md and .html artefacts.
2. The PDF has a **cover page** with report title, URL, device, date,
   overall score (if extracted), and a "design-intel" footer.
3. The PDF has an **auto-generated table of contents** with links to each
   h2 section in the body.
4. The PDF has **page numbers** in the footer (via CSS `@page`).
5. Print CSS avoids page breaks mid-heading, mid-table-row, and
   mid-screenshot (via `break-inside: avoid`).
6. `build_pdf_html()` is a pure function that takes the base HTML and
   returns augmented HTML — testable without Playwright.
7. `save_pdf_report()` uses Playwright to render; failures are caught
   and surfaced as a warning, never crash the critique run.
8. Unit tests cover: TOC generation from h2 headings, cover-page
   content, print CSS presence, graceful degradation when Playwright
   isn't available or render fails.

**Technical notes.**
- Playwright `page.pdf()` supports `format: "A4"`, `printBackground: True`,
  `displayHeaderFooter: True`, custom header/footer templates.
- TOC: parse h2 elements from the body HTML (already converted from
  markdown), emit anchor links + targets.
- Cover page = `<div class="cover-page">` with `break-after: page`.
- Don't spawn a full browser for the test suite — test `build_pdf_html()`
  directly with fixture HTML.

**Out of scope.**
- PDF export for handoff, wcag, fix, compare, monitor reports (critique
  first; extend to others if users ask).
- Custom cover-page branding (fixed template for v1).
- Multi-page layout tuning beyond basic break-avoidance.
- Watermarks / headers on every page.

**Open questions.** None blocking.

**Reference materials.**
- `src/output/html_report.py` — HTML generator this wraps.
- `src/input/screenshot.py` — existing Playwright usage pattern.
- ROADMAP.md P1 (source of this spec).

---

## [SHIPPED - 2026-04-05] [Feature] Design System Extractor — design-intel extract-system

**Summary.** New `extract-system` subcommand that reverse-engineers a
complete design-token system from a live URL and writes CSS, JSON, and
Tailwind config files ready to drop into another project.

**Context.** The DOM extractor already captures CSS custom properties (if
the site defines them), plus usage-counted colours, font families, font
sizes, and spacing values. Today that data lives inside audit reports —
users can't pull it out as a reusable token set. The "point at Stripe, get
a complete system in 30 seconds" promise needs dedicated code.

**Current state.**
- `handoff` generates a markdown table of tokens but it isn't importable.
- `css_tokens` in DOM data is shaped as
  `{color, spacing, radius, font, other}` lists of `{name, value}`.
- `colors.text`, `colors.background`, `fonts.sizes`, `fonts.families`,
  `spacing_values` are all available as usage-counted raw values.

**Target state.**
- `design-intel extract-system --url X --output ./design-system/` creates
  a directory with drop-in CSS + JSON + Tailwind config.
- Two-strategy extraction: prefer the site's own CSS tokens; synthesise
  from usage-counted raw values when tokens aren't defined.
- Output is self-documenting (README.md in the output dir explains source,
  date, counts).

**Acceptance criteria.**
1. `design-intel extract-system --url <url> --output <dir>` creates the
   output directory (recursively) and writes files.
2. When the site defines CSS tokens (`css_tokens` populated), uses them
   verbatim — same names, same values.
3. When no tokens exist, synthesises names from usage-counted values:
   top colours → `--color-1..N`, font families → `--font-sans|serif|mono`,
   font sizes → `--font-size-xs|sm|base|lg|xl|2xl` ordered by size,
   spacing values → `--space-1..N`.
4. Writes six files: `tokens.css`, `colours.css`, `typography.css`,
   `spacing.css`, `tokens.json`, `README.md` (plus `tailwind.config.js`
   when tokens were extracted).
5. `tokens.json` uses a Figma-Variables-compatible shape: an array of
   `{name, value, type}` entries (`type` ∈ `color | dimension | string`).
6. `tailwind.config.js` emits a CommonJS module with a `theme.extend`
   block mapping extracted colour tokens to `colors.*` entries and
   spacing tokens to `spacing.*`.
7. `README.md` in the output dir includes: source URL, extraction date,
   token counts per category, extraction strategy used (`direct` or
   `synthesised`).
8. Exits 2 on unreachable or blocked URLs.
9. `--format json` prints a summary to stdout after writing files (file
   paths + counts) so CI pipelines can parse it.
10. Unit tests cover: direct extraction from pre-existing tokens,
    synthesis from raw values, file generation using `tmp_path`, the
    Figma JSON shape, Tailwind config shape, README content.

**Technical notes.**
- Reuse `src/input/processor.py` for the URL fetch; no new scraping code.
- Strategy detection: direct if any of `css_tokens.color/spacing/font`
  has entries, synthesised otherwise.
- Synthesised font-size names use a fixed scale
  (`xs|sm|base|lg|xl|2xl|3xl|4xl`) mapped in size order.
- Synthesised font-family names: first match for sans/serif/mono in the
  family string, else `font-1|2|3`.
- Tailwind config skipped when synthesised output is empty (no tokens
  to export).
- Write files atomically-ish: write to the output dir after
  `mkdir(parents=True, exist_ok=True)`.

**Out of scope.**
- Tailwind v4 CSS-first `@theme` config (generates v3 JS config only).
- Full component extraction into a component library (handoff already
  does the per-component inventory).
- Styled-components / Emotion / CSS-in-JS theme export.
- Shadow/motion/easing token extraction (v1 handles colour + typography +
  spacing + radius only).

**Open questions.** None blocking.

**Reference materials.**
- `src/input/screenshot.py` — DOM extractor `tokenCategories` shape.
- `src/input/processor.py` — URL fetch entry point.
- Figma Variables REST API shape (public docs) — guides `tokens.json`.
- ROADMAP.md P1 (source of this spec).

---

## [SHIPPED - 2026-04-05] [Feature] Scheduled Monitoring — design-intel monitor subcommand

**Summary.** New `monitor` subcommand that runs an audit, compares against
history, detects regressions, emits a trend-aware report, and optionally
posts to a Slack-compatible webhook. Scheduling is the user's responsibility
(GitHub Actions template provided); we don't embed a daemon.

**Context.** CI gates catch PR-introduced regressions, but don't catch silent
degradation from upstream deps, dynamic content, A/B tests, or third-party
embeds shifting over time. Teams need a set-and-forget signal when design
quality drifts between active changes.

**Current state.**
- `design-intel history --url X` prints a text trend for one URL.
- `design-intel ci` gates PRs but isn't trend-aware.
- `design-intel diff` compares two known inputs.
- No unified monitoring output, no alerting hook, no scheduler template.

**Target state.**
- `design-intel monitor --url X` runs an audit, appends to history, emits
  a trend + regression report.
- `--alert-webhook <url>` posts a Slack-compatible payload on regression.
- Exit codes mirror the CI gate.
- `templates/ci/github-actions-monitoring.yml` runs the monitor weekly.

**Design philosophy.** No embedded scheduler / daemon. Scheduling stays
decoupled (GitHub Actions, cron, any scheduler) so the tool remains a
stateless CLI that does one thing. Alerts are fire-and-forget HTTP POSTs.

**Acceptance criteria.**
1. `design-intel monitor --url <url>` runs a full audit and produces a
   markdown report with current score, trend over recent runs, new
   violations (via CI fingerprints), and improvement callouts.
2. `--trend-window N` caps the trend table at the last N history runs
   (default: 10).
3. `--alert-webhook <url>` POSTs a JSON payload
   (`{"text": "<summary>"}`) when the exit code would be non-zero.
   Webhook call failures do NOT crash the command — they're logged to
   stderr and noted in the report.
4. Exit codes: `0` stable/improving; `1` regression detected (new
   critical/serious violations OR score dropped > 2pp vs previous run);
   `2` technical error (URL unreachable, blocked, no history + webhook
   requested).
5. `--format json` emits schema_version 1 with: `url`, `timestamp`,
   `score`, `score_previous`, `score_delta`, `trend` (array of
   `{timestamp, score}`), `new_violations`, `fixed_violations`,
   `alert_fired`, `alert_payload`, `exit_code`.
6. `--save` writes the markdown report to `output/` and the JSON payload
   too when both flags are combined with `--format json`.
7. `--severity` + `--score-tolerance` knobs match the CI gate defaults
   (`serious`, `2.0`) and accept the same values.
8. `templates/ci/github-actions-monitoring.yml` provides a weekly cron
   workflow that installs design-intel, runs `monitor`, uploads the
   report artefact, and optionally posts to Slack via repo secret.
9. Each monitor run persists fingerprinted violations in history (same
   shape as `ci`) so the next run has a baseline.
10. Unit tests cover: report assembly with 0/1/many history entries,
    trend-window truncation, exit code paths (stable, regression, tech
    error), Slack payload shape, webhook call (mocked), JSON schema
    shape, fingerprint diffing vs history baseline.

**Technical notes.**
- Reuse `src/analysis/history.py` for storage and baseline loading.
- Reuse `src/analysis/ci_runner.py` fingerprint extractors so what counts
  as a violation stays consistent across ci/diff/monitor.
- Slack webhook: use `httpx` (already a dep). Post with a short timeout
  (5s) and catch exceptions so webhook failure doesn't fail the job.
- Trend table sorted oldest-first, rendered as a plain markdown table.

**Out of scope.**
- Email alerting (Slack webhook only in v1; email is workflow concern).
- Embedded daemon / long-running process.
- Multi-URL fleet monitoring (single URL per invocation; GitHub Actions
  matrix handles multiple URLs).
- Historical chart rendering as PNG (markdown table for v1).
- PagerDuty / Teams / Discord payload formats (Slack-compatible JSON is
  the lingua franca; most receivers accept `{"text": "..."}`).

**Open questions.** None blocking.

**Reference materials.**
- `src/analysis/history.py` — run persistence + `get_previous_run`.
- `src/analysis/ci_runner.py` — fingerprint dataclass + extractors.
- `src/analysis/diff_analyzer.py` — `diff_fingerprints` helper.
- ROADMAP.md P1 (source of this spec).

---

## [SHIPPED - 2026-04-05] [Feature] Before/After Diff — design-intel diff subcommand

**Summary.** New `diff` subcommand that compares two designs (URLs,
screenshots, or a URL vs its history baseline) and produces a visual diff,
score delta, and issue diff. Answers "what changed between v1 and v2?"

**Context.** Redesigns and PRs need to quantify change. Today the tool can
regression-track one URL over time via `history`, and can score two sites
as peers via `compare`, but can't answer "did this specific change improve
things?" for arbitrary input pairs.

**Naming rationale.** `compare` is already taken by competitive benchmarking
(peers A vs B). Using `diff` keeps the semantics distinct — `diff` is the
natural word for old vs new. ROADMAP.md entry used `compare --before/--after`
originally; renamed on promotion.

**Current state.**
- `design-intel compare --url X --competitor Y` scores peers.
- `design-intel history --url X` lists runs for a single URL over time.
- `design-intel ci` already fingerprints and diffs violations vs the most
  recent baseline — reusable for the issue-diff logic here.
- No cross-pair image diff exists.

**Target state.**
- `design-intel diff --before <path-or-url> --after <path-or-url>` emits a
  markdown report with a visual diff, score delta, and issue diff.
- Accepts three input pairs: two URLs, two screenshots, or URL vs its
  stored history baseline.
- Visual diff is a PNG with changed regions boxed (Pillow pixel comparison).

**Acceptance criteria.**
1. `design-intel diff --before <input> --after <input>` runs and produces a
   markdown report; both inputs can be a URL or a local image path.
2. `--baseline history` substitutes "before" with the most recent saved run
   for the `--after` URL (URL mode only; exits 2 if no history exists).
3. For URL inputs, DOM extraction + WCAG check runs on each side; violation
   fingerprints are reused from the CI runner module.
4. Score delta section shows overall WCAG score before → after + percentage
   delta; per-criterion pass/fail change is listed when both sides ran WCAG.
5. Issue diff section lists three buckets: `fixed` (in before, not after),
   `new` (in after, not before), `persistent` (in both).
6. Visual diff PNG is generated when both inputs resolve to a raster source
   (URL screenshots or provided images). Changed regions are outlined with
   bounding boxes drawn on the "after" image. Skipped with a one-line note
   if only one side produced a screenshot.
7. Exit code: `0` if no new issues + score didn't drop > 2pp; `1` if new
   issues or score dropped beyond tolerance; `2` on technical error
   (unreachable URL, missing file, missing history baseline). Matches CI
   gate semantics so this can also be used as a gating tool.
8. `--save` writes the markdown report + visual diff PNG into `output/`.
9. `--format json` emits a structured document with `schema_version: 1`,
   `score_before`, `score_after`, `score_delta`, `new_issues`,
   `fixed_issues`, `persistent_issues`, and a `visual_diff_path` field.
10. Unit tests cover: URL/URL pair, screenshot/screenshot pair, URL vs
    history baseline, issue-diff logic (all three buckets populated from a
    fixture), pixel-diff on synthesised images (identical → no diff,
    modified → bounding box emitted), exit codes for pass/fail/error paths.

**Technical notes.**
- Reuse `src/analysis/ci_runner.py`:`ViolationFingerprint` + fingerprint
  extractors (`_fingerprint_wcag_violations`, `_fingerprint_axe_violations`)
  for the issue-diff logic. Don't duplicate.
- Visual diff: Pillow `ImageChops.difference` → threshold → bounding boxes
  of connected non-zero regions → draw rectangles on the after image.
- For URL inputs, wcag score comes from `run_wcag_check`; for screenshots,
  score_delta reports "n/a (no DOM data)".
- `--baseline history` path reads from the existing `history.py` store
  (no new persistence).

**Out of scope.**
- Side-by-side HTML preview (just the PNG overlay for now).
- Semantic DOM-tree diff (structure change summary).
- LLM-generated narrative summary of what changed.
- Animating between states / video diff.

**Open questions.** None blocking.

**Reference materials.**
- `src/analysis/ci_runner.py` — fingerprint dataclass + extractors.
- `src/analysis/history.py` — for `--baseline history` support.
- Pillow `ImageChops.difference` + `getbbox()` for pixel diffing.
- ROADMAP.md P1 entry (source of this spec; renamed subcommand on promotion).

---

## [SHIPPED - 2026-04-05] [Feature] CI/CD Integration — design-intel ci subcommand

**Summary.** Add a `ci` subcommand that runs a deterministic design audit on a
URL and exits non-zero based on configured thresholds, so CI pipelines can
gate PRs on design quality.

**Context.** Existing commands (`critique`, `wcag`, `compare`, `fix`) always
exit 0 regardless of findings. There's no way to fail a build when a PR
introduces contrast violations or drops the design score. Machine-readable
output is also missing — no JSON mode for parsing in automation.

**Current state.**
- `design-intel wcag --url X` prints markdown, exits 0.
- History module (`src/analysis/history.py`) already tracks runs per URL and
  exposes `get_previous_run` + `compute_diff`.
- No JSON output format anywhere in the CLI.

**Target state.**
- `design-intel ci --url X` runs WCAG + score calculation.
- **Default pragmatic mode** grandfathers pre-existing violations so teams
  can drop the gate into CI without every PR nagging about the backlog.
- `--strict` toggles zero-tolerance gating.
- `--format json` prints a stable, versioned schema to stdout for CI parsing.
- A ready-to-drop GitHub Actions workflow template ships in `templates/ci/`.

**Pragmatic-mode rules (all default-on, all toggleable):**
- **New-only gating.** Per-violation fingerprints diffed vs. baseline; only
  violations not present before can fail the build.
- **Severity floor.** Only axe-core `critical` + `serious` gate by default
  (`--severity` knob: `minor|moderate|serious|critical`).
- **Score-drop tolerance.** ±2pp noise band on the WCAG score
  (`--score-tolerance N`).
- **AAA excluded** from gating (already excluded from scoring).

**Acceptance criteria.**
1. `design-intel ci --url <url>` runs in pragmatic mode by default, saves a
   baseline on first run, exits 0 when nothing new is introduced.
2. `--strict` disables pragmatic mode and fails on any A/AA violation and any
   score drop.
3. `--min-score N` adds a hard floor in either mode — fails if score < N.
4. `--severity {minor|moderate|serious|critical}` lowers/raises the pragmatic
   severity floor (default: `serious`).
5. `--score-tolerance N` widens the pragmatic score-drop band (default: 2.0).
6. `--format json` emits a `schema_version: 2` JSON document to stdout with:
   URL, mode, current + previous + delta scores, violation counts, separate
   buckets for `new_violations` / `fixed_violations` /
   `pre_existing_violations`, each threshold's pass/fail, overall exit,
   pragmatic config (or `null` in strict mode). Human output goes to stderr.
7. Exit codes: `0` all thresholds passed, `1` one or more thresholds failed,
   `2` technical error (site blocked, network failure).
8. `templates/ci/github-actions-design-review.yml` provides a copy-paste
   workflow: installs design-intel, runs `ci` in pragmatic mode by default,
   uploads the JSON report as an artefact. Header comments explain both
   modes and the override flags.
9. Each CI run persists per-violation fingerprints to history so the next
   run has a baseline to diff against.
10. Unit tests cover: first-run baseline capture, new-violation gating,
    pre-existing grandfathering, severity floor filtering, score tolerance
    band, strict mode gating, min-score in both modes, blocked-site exit 2,
    JSON schema shape (v2 keys + config field), strict-mode config omission.

**Technical notes.**
- Violation fingerprint: `(criterion, element, issue)` tuple — stable across
  runs because content of the issue field shouldn't change for the same root
  cause.
- Baseline = the most recent RunRecord for the URL, with `issues` list
  containing stored fingerprints. First CI run on a fresh URL exits 0
  ("baseline-captured" threshold).
- JSON schema bumped to v2 — the v1 shape never shipped, so no back-compat
  concerns.
- `--strict` mode excludes the `pragmatic_config` key from the JSON output
  to keep the strict contract minimal.

**Out of scope.**
- GitLab CI template — add only if a user requests it.
- Posting PR comments from the CLI itself (workflow responsibility).
- Per-criterion custom thresholds (single severity floor for v1).
- Scheduled monitoring — separate roadmap item.
- `--baseline <path>` to compare against an external baseline file.

**Open questions.** *(Resolved.)* Using most-recent-run as baseline; external
baseline files can be added later if users request them.

**Reference materials.**
- `src/analysis/history.py` — existing regression tracking primitives.
- `src/analysis/wcag_checker.py` — score percentage + violation counts.
- `../design-agent-private/ROADMAP.md` P1 entry (source of this spec).

---

## [SHIPPED - 2026-04-05] [Feature] Competitive Benchmarking

**Shipped.** `design-intel compare --url X --competitor Y` scores both sites
across 10 deterministic metrics (WCAG score, violations, contrast pass rate,
target-size pass rate, landmarks, heading hierarchy validity, design tokens,
font discipline, palette size, axe critical/serious) and returns a verdict
with category winners, biggest gaps, and where you lead. Also exposed as an
MCP tool. 18 unit tests + dedicated benchmark (100/100: metric count, winner
correctness, symmetry, tie handling, lower-is-better discipline, markdown
shape).

## [SHIPPED - 2026-04-05] [Infra] claude-code-action workflow

**Shipped.** `.github/workflows/claude-review.yml` triggers on `@claude`
mentions in PR comments, PR review comments, PR reviews, and issue
bodies/titles/comments. Uses `anthropics/claude-code-action@v1`. One-time
repo setup required: `ANTHROPIC_API_KEY` secret + enable Actions PR-creation
permission.

## [SHIPPED - 2026-04-05] [Infra] Claude Code project config

**Shipped.** `CLAUDE.md` at repo root (architecture map, venv path, roadmap
pointer, update protocol) + `.claude/settings.json` hooks: scoped ruff
auto-fix on edited `.py` files (via `.claude/hooks/ruff-edited.sh`), pytest on
Stop. Ruff target bumped `py311 → py312` to match the f-string syntax already
in use. First run auto-fixed 11 pre-existing lint issues.

## [SHIPPED - 2026-04-05] [Feature] MCP Server

**Shipped.** FastMCP server over stdio exposing 6 tools
(`critique`, `wcag`, `components`, `handoff`, `fix`, `compare`) and the
39-entry knowledge library as resources (`design-intel://knowledge/{cat}/{slug}`
+ a static index resource). Launched via `design-intel mcp`. 11 registration
tests + path-traversal guard. Usable from any MCP client (Claude Code, Cursor,
Windsurf).

## [SHIPPED - 2026-04-05] [Feature] Auto-Fix Generation

**Shipped.** `design-intel fix --url X` emits CSS/HTML patches for
deterministic WCAG failures: colour-adjusted contrast rules (binary-search
darkens/lightens text to hit the required ratio), min-width/min-height +
padding for target-size violations, and HTML snippets for lang, skip link,
landmarks, heading hierarchy, form labels. Non-deterministic failures (e.g.
1.4.1 Use of Color) go to `FixSet.skipped` — never speculative patches.
12 unit tests + dedicated benchmark (100/100: coverage, contrast accuracy,
target-size accuracy, HTML snippet validity, determinism discipline,
selector quality).

---

## Shipped Archive

*Items shipped or verified. Never removed. Move items here when Backlog exceeds ~2,000 lines and items >90 days old.*

*(no items archived yet, Backlog is under 2,000 lines)*
