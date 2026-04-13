"""
MCP server for design-intel.

Exposes the design analysis toolset over the Model Context Protocol so any
MCP-compatible client (Claude Code, Cursor, Windsurf, etc.) can call it as
native tools. Transport is stdio — the server is launched as a child process
by the MCP client.

Tools:
  - critique:  LLM-driven design critique of a URL
  - wcag:      deterministic WCAG 2.2 audit (no LLM)
  - components: per-component detection and scoring
  - handoff:   developer handoff spec generation
  - fix:       CSS/HTML patches for deterministic WCAG failures

Resources:
  - design-intel://knowledge/{category}/{slug}
    39 knowledge library entries, exposed as readable resources.
"""

from __future__ import annotations

from pathlib import Path

from mcp.server.fastmcp import FastMCP

from src.input.processor import process_input
from src.agents.critique import CritiqueAgent
from src.agents.handoff_agent import HandoffAgent
from src.analysis.wcag_checker import run_wcag_check, run_wcag_check_multi
from src.analysis.component_detector import (
    detect_and_score_components,
    detect_and_score_multi,
)
from src.analysis.competitive import build_comparison
from src.analysis.diff_analyzer import build_diff_report
from src.analysis.fix_generator import generate_fixes


KNOWLEDGE_ROOT = Path(__file__).parent.parent / "knowledge"

mcp = FastMCP("design-intel")


# ── Helpers ──


def _resolve_viewport(device: str | None) -> tuple[int, int]:
    presets = {
        "iphone-12": (390, 844),
        "iphone-14-pro": (393, 852),
        "iphone-15": (393, 852),
        "iphone-se": (375, 667),
        "pixel-7": (412, 915),
        "ipad": (820, 1180),
        "ipad-pro": (1024, 1366),
        "desktop": (1440, 900),
    }
    return presets.get(device or "", (1440, 900))


def _run_wcag(design_input) -> object:
    if design_input.pages and len(design_input.pages) > 1:
        return run_wcag_check_multi(design_input.pages)
    return run_wcag_check(design_input.dom_data)


# ── Tools ──


@mcp.tool()
def critique(
    url: str,
    tone: str = "opinionated",
    device: str | None = None,
    stage: str = "production",
    crawl: bool = False,
    max_pages: int = 10,
) -> str:
    """Run a design critique on a live URL.

    Returns a markdown report covering visual hierarchy, typography, colour,
    spacing, accessibility, interaction, and consistency. Use `tone` to tune
    the voice (opinionated | balanced | gentle). Use `stage` to adjust depth
    for wireframe | mockup | production designs. Set `crawl=True` to analyse
    multiple pages of an SPA.
    """
    vw, vh = _resolve_viewport(device)
    design_input = process_input(
        url=url, crawl=crawl, max_pages=max_pages,
        viewport_width=vw, viewport_height=vh,
    )
    agent = CritiqueAgent(tone=tone)
    return agent.run(design_input, context=f"Stage: {stage}")


@mcp.tool()
def wcag(
    url: str,
    device: str | None = None,
    crawl: bool = False,
    max_pages: int = 10,
) -> str:
    """Run a deterministic WCAG 2.2 audit on a URL.

    No LLM involved — produces a pass/fail report against 11 programmatic
    criteria (contrast, target size, landmarks, heading hierarchy, form
    labels, language, bypass blocks, etc.) plus any axe-core violations
    surfaced by the DOM extractor.
    """
    vw, vh = _resolve_viewport(device)
    design_input = process_input(
        url=url, crawl=crawl, max_pages=max_pages,
        viewport_width=vw, viewport_height=vh,
    )
    report = _run_wcag(design_input)
    return report.to_markdown()


@mcp.tool()
def components(
    url: str,
    crawl: bool = False,
    max_pages: int = 10,
) -> str:
    """Detect and score UI components on a URL.

    Identifies buttons, inputs, cards, navs, and other components, then grades
    each against its pattern standard (touch target, label, state coverage,
    contrast). Returns a markdown component inventory.
    """
    design_input = process_input(url=url, crawl=crawl, max_pages=max_pages)
    if design_input.pages and len(design_input.pages) > 1:
        report = detect_and_score_multi(design_input.pages)
    else:
        report = detect_and_score_components(design_input.dom_data)
    return report.to_markdown()


@mcp.tool()
def handoff(
    url: str,
    device: str | None = None,
    crawl: bool = False,
    max_pages: int = 10,
) -> str:
    """Generate a developer handoff specification from a live site.

    Extracts design tokens, computed styles, layout specs, interactive element
    dimensions, and interaction states, then produces a markdown handoff
    document suitable for a front-end implementer.
    """
    vw, vh = _resolve_viewport(device)
    design_input = process_input(
        url=url, crawl=crawl, max_pages=max_pages,
        viewport_width=vw, viewport_height=vh,
    )
    agent = HandoffAgent()
    return agent.run(design_input)


@mcp.tool()
def fix(
    url: str,
    device: str | None = None,
    crawl: bool = False,
    max_pages: int = 10,
) -> str:
    """Generate CSS/HTML patches for deterministic WCAG failures.

    Runs the WCAG audit and emits concrete fixes: corrected contrast colours,
    min-width/min-height rules for target-size violations, and HTML snippets
    for labels, landmarks, skip links, and lang attributes. Only fixes
    issues with a mechanical correct answer — subjective failures are
    skipped and listed.
    """
    vw, vh = _resolve_viewport(device)
    design_input = process_input(
        url=url, crawl=crawl, max_pages=max_pages,
        viewport_width=vw, viewport_height=vh,
    )
    wcag_report = _run_wcag(design_input)
    fix_set = generate_fixes(wcag_report)

    parts = [fix_set.to_markdown()]
    if fix_set.css_fixes:
        parts.append("\n## Generated Stylesheet\n\n```css\n" + fix_set.to_css_file() + "\n```")
    return "\n".join(parts)


@mcp.tool()
def compare(
    url: str,
    competitor: str,
    device: str | None = None,
) -> str:
    """Side-by-side competitive benchmark of your URL vs a competitor URL.

    Scores both sites across 10 deterministic dimensions (WCAG score,
    violations, contrast pass rate, target size, landmarks, heading
    hierarchy, design tokens, font discipline, colour palette size, axe
    critical/serious issues) and returns a markdown report with a verdict,
    category winners, biggest gaps, and where you lead.
    """
    vw, vh = _resolve_viewport(device)
    your_input = process_input(url=url, viewport_width=vw, viewport_height=vh)
    their_input = process_input(url=competitor, viewport_width=vw, viewport_height=vh)
    your_wcag = run_wcag_check(your_input.dom_data)
    their_wcag = run_wcag_check(their_input.dom_data)
    report = build_comparison(
        your_url=url,
        competitor_url=competitor,
        your_dom=your_input.dom_data,
        competitor_dom=their_input.dom_data,
        your_wcag=your_wcag,
        competitor_wcag=their_wcag,
    )
    return report.to_markdown()


@mcp.tool()
def diff(
    url: str,
    before: str,
    device: str | None = None,
) -> str:
    """Before/after diff of two URLs.

    `url` is the "after" side (current state), `before` is the baseline URL
    you want to compare against. Returns a markdown report with score delta,
    issue diff (new/fixed/persistent violations), and overall exit-code
    verdict (exits 1-semantics if the change introduced regressions).
    """
    vw, vh = _resolve_viewport(device)
    before_input = process_input(url=before, viewport_width=vw, viewport_height=vh)
    after_input = process_input(url=url, viewport_width=vw, viewport_height=vh)
    before_wcag = run_wcag_check(before_input.dom_data)
    after_wcag = run_wcag_check(after_input.dom_data)
    report = build_diff_report(
        before_label=before, after_label=url,
        before_wcag=before_wcag, before_dom=before_input.dom_data,
        after_wcag=after_wcag, after_dom=after_input.dom_data,
    )
    return report.to_markdown()


# ── Resources: knowledge library ──


def _iter_knowledge_entries():
    """Yield (category, slug, path) for every knowledge entry on disk."""
    if not KNOWLEDGE_ROOT.exists():
        return
    for category_dir in sorted(KNOWLEDGE_ROOT.iterdir()):
        if not category_dir.is_dir() or category_dir.name.startswith("."):
            continue
        if category_dir.name == "pending":
            continue
        for entry in sorted(category_dir.glob("*.md")):
            yield category_dir.name, entry.stem, entry


@mcp.resource("design-intel://knowledge/{category}/{slug}")
def knowledge_entry(category: str, slug: str) -> str:
    """Read a single knowledge library entry by category and slug."""
    path = KNOWLEDGE_ROOT / category / f"{slug}.md"
    if not path.exists() or not path.is_file():
        return f"Knowledge entry not found: {category}/{slug}"
    # Guard against path traversal — resolved path must stay inside KNOWLEDGE_ROOT.
    try:
        path.resolve().relative_to(KNOWLEDGE_ROOT.resolve())
    except ValueError:
        return "Invalid knowledge path"
    return path.read_text()


@mcp.resource("design-intel://knowledge/index")
def knowledge_index() -> str:
    """List all available knowledge entries with their URIs."""
    lines = ["# design-intel Knowledge Library\n"]
    current_category = None
    for category, slug, _path in _iter_knowledge_entries():
        if category != current_category:
            lines.append(f"\n## {category}\n")
            current_category = category
        lines.append(f"- design-intel://knowledge/{category}/{slug}")
    return "\n".join(lines)


def run() -> None:
    """Launch the MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":
    run()
