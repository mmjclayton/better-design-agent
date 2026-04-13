# Contributing to design-intel

Thanks for your interest in contributing. This guide covers how to set up your
development environment, run the test suite, and submit changes.

## Development Setup

```bash
# Clone the repo
git clone https://github.com/mmjclayton/design-intelligence.git
cd design-intelligence

# Create a virtual environment and install in editable mode
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Install Playwright browsers
playwright install chromium
```

Verify the setup:

```bash
design-intel doctor
design-intel --version
```

## Running Tests

```bash
# Full unit test suite (excludes benchmarks)
.venv/bin/python -m pytest tests/ -q \
  --ignore=tests/benchmark_critique.py \
  --ignore=tests/benchmark_fix_generator.py

# Specific test file
.venv/bin/python -m pytest tests/test_check.py -v

# Benchmarks (deterministic, scored — run separately)
.venv/bin/python -m tests.benchmark_fix_generator
.venv/bin/python -m tests.benchmark_critique
```

## Code Style

This project uses [ruff](https://docs.astral.sh/ruff/) for linting and formatting.
Ruff runs automatically via Claude Code hooks on save, but you can run it manually:

```bash
ruff check src/ tests/
ruff format src/ tests/
```

Key conventions:

- Python 3.11+, type annotations on all function signatures
- Deterministic analysers (WCAG checker, fix generator, component detector) contain
  no LLM calls. Keep it that way.
- Prefer `dataclass(frozen=True)` or `NamedTuple` for data containers
- Files under 800 lines, functions under 50 lines
- Immutable patterns — create new objects, don't mutate existing ones

## Project Workflow

This project uses `Backlog.md` as its single source of truth for work tracking.
No GitHub Issues, no external trackers.

1. **Check the Backlog** — read `Backlog.md` before starting any work
2. **Claim an item** — change status from `[OPEN]` to `[IN PROGRESS]`
3. **Write tests first** — follow TDD: write failing test, implement, verify
4. **Ship the code + status update** — mark `[DONE - YYYY-MM-DD]` in the same
   commit as the code change

## How to Add a New Analyser

The simplest way to contribute is adding a new deterministic analyser. Follow the
pattern established by `src/analysis/wcag_checker.py`:

1. Create `src/analysis/your_analyser.py`
2. Write a pure function that takes `dom_data: dict` and returns a typed result
3. Add tests in `tests/test_your_analyser.py`
4. Wire it into a CLI command in `src/cli.py`
5. Optionally add a benchmark in `tests/benchmark_your_analyser.py`

Key rule: deterministic analysers must not call any LLM. They operate on DOM data
extracted by Playwright and return reproducible results.

## How to Add a Knowledge Entry

The knowledge library lives in `knowledge/` with 39 entries across 10 categories.
To add one:

1. Create a markdown file in the appropriate `knowledge/<category>/` directory
2. Add frontmatter with `title`, `category`, and `tags`
3. Run `design-intel index-knowledge` to rebuild the index
4. The entry will automatically be available via the MCP server and critique agents

## Pull Request Checklist

- [ ] Tests pass: `pytest tests/ -q`
- [ ] Ruff passes: `ruff check src/ tests/`
- [ ] New functionality has tests
- [ ] Backlog item linked (if applicable)
- [ ] No hardcoded secrets or API keys
