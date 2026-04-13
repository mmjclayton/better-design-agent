"""
Multi-agent orchestrator — runs specialized sub-agents in parallel,
reconciles contradictions, and merges into a unified report.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed

from src.agents.accessibility_agent import AccessibilityAgent
from src.agents.design_system_agent import DesignSystemAgent
from src.agents.visual_agent import VisualDesignAgent
from src.agents.interaction_agent import InteractionAgent
from src.analysis.wcag_checker import run_wcag_check, run_wcag_check_multi
from src.input.models import DesignInput
from src.providers.llm import call_llm


RECONCILIATION_PROMPT = """\
You are a technical editor reviewing a design critique report produced by \
four independent sub-agents. Your ONLY job is to find and fix contradictions \
between sections. Do NOT add new findings or change the substance.

Fix these specific problems:
1. If one section says "no active state" but another confirms active states \
exist with specific CSS changes, remove the false claim.
2. If one section says "no focus styles" but another documents focus styles \
working, remove the false claim.
3. If counts are impossible (e.g. "13/10 inputs missing labels"), fix the \
denominator to match the actual count.
4. If colours are described as "pure black #000000" or "pure white #FFFFFF" \
but the DOM data shows different values (#0f1117, #e1e4ed), use the DOM values.
5. If the same element appears multiple times as separate violations, \
deduplicate to count unique elements only.

Output the complete corrected report. Preserve all formatting, sections, and \
findings that are NOT contradictory. Only change what is factually inconsistent \
between sections.

CRITICAL formatting rules:
- Preserve heading levels EXACTLY as given. Do not promote H3s to H2s or \
demote H2s to H3s. If the input has `### Foo` leave it as `### Foo`.
- Preserve section order exactly.
- Do not add new section headers that weren't in the original.
"""


def run_multi_agent_critique(design_input: DesignInput, context: str = "") -> str:
    """Run all four specialized agents in parallel, reconcile, and merge."""

    agents = {
        "accessibility": AccessibilityAgent(),
        "design_system": DesignSystemAgent(),
        "visual": VisualDesignAgent(),
        "interaction": InteractionAgent(),
    }

    # Run WCAG checker (deterministic, instant)
    if design_input.pages and len(design_input.pages) > 1:
        wcag_report = run_wcag_check_multi(design_input.pages)
    else:
        wcag_report = run_wcag_check(design_input.dom_data)

    # Run all agents in parallel
    results = {}

    def _run_agent(name, agent):
        return name, agent.run(design_input, context)

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(_run_agent, name, agent): name
            for name, agent in agents.items()
        }
        for future in as_completed(futures):
            name, output = future.result()
            results[name] = output

    # Merge into draft report
    draft = _merge_reports(wcag_report, results)

    # Reconciliation pass — fix contradictions between sub-agents
    reconciled = _reconcile(draft)

    # Post-reconciliation heading enforcement: the LLM sometimes restores
    # H2s that should be H3s. Demote any H2 that isn't in our fixed
    # section-header whitelist.
    reconciled = _enforce_section_headers(reconciled)

    return reconciled


def _merge_reports(wcag_report, agent_results: dict) -> str:
    """Merge WCAG checker and agent outputs into a unified report."""

    sections = []

    # Header
    sections.append("# Design Critique Report (Multi-Agent Analysis)\n")
    sections.append(
        "This report was produced by four specialized agents analysing the design "
        "in parallel, plus a deterministic WCAG 2.2 checker.\n"
    )

    # WCAG Checker (deterministic)
    sections.append("---\n")
    sections.append(wcag_report.to_markdown())

    # Visual Design
    if "visual" in agent_results:
        sections.append("---\n")
        sections.append("## Visual Design Analysis\n")
        sections.append(_clean_agent_output(agent_results["visual"], "Visual"))

    # Accessibility Deep Dive
    if "accessibility" in agent_results:
        sections.append("\n---\n")
        sections.append("## Accessibility Deep Dive\n")
        sections.append(_clean_agent_output(agent_results["accessibility"], "Accessibility"))

    # Design System
    if "design_system" in agent_results:
        sections.append("\n---\n")
        sections.append("## Design System Analysis\n")
        sections.append(_clean_agent_output(agent_results["design_system"], "Design System"))

    # Interaction Quality
    if "interaction" in agent_results:
        sections.append("\n---\n")
        sections.append("## Interaction Quality Analysis\n")
        sections.append(_clean_agent_output(agent_results["interaction"], "Interaction"))

    return "\n".join(sections)


# The orchestrator emits exactly these H2 section headers. Anything else
# at H2 level in the body was the LLM "fixing" our demoted headings, and
# should be pushed back down to H3.
ALLOWED_H2_HEADERS = {
    "WCAG 2.2 Automated Audit",
    "Visual Design Analysis",
    "Accessibility Deep Dive",
    "Design System Analysis",
    "Interaction Quality Analysis",
    "Component Inventory & Scoring",
}


def _enforce_section_headers(markdown: str) -> str:
    """Demote any H2 heading whose title isn't one of our allowed sections.

    The LLM reconciliation pass sometimes re-promotes body H3s back to H2s.
    This pass walks the output and forces every H2 not in the whitelist to
    H3, keeping the section structure clean.
    """
    import re as _re

    def _maybe_demote(match: _re.Match) -> str:
        title = match.group(1).strip()
        # The WCAG audit mobile variant includes " (Mobile - ..." suffix; match prefix.
        title_base = title.split(" (")[0].strip()
        if title_base in ALLOWED_H2_HEADERS or title in ALLOWED_H2_HEADERS:
            return match.group(0)
        return "### " + title

    return _re.sub(
        r"^## (.+?)$", _maybe_demote, markdown, flags=_re.MULTILINE,
    )


def _clean_agent_output(markdown: str, section_keyword: str) -> str:
    """Strip redundant leading title headings + demote remaining ones.

    Sub-agents often open their response with their own `# Title` or
    `## Title` that duplicates the orchestrator's section header (the
    title may not exactly match the section name — e.g. the interaction
    agent writes "# State Audit Results"). This function:
      1. Strips the FIRST heading from the output if it's at H1 or H2
         level. The orchestrator already provides the section's H2.
      2. Demotes every remaining heading by one level so the section's
         original H2 stays the only H2 in the block.

    `section_keyword` is kept for future heuristics but not currently
    used — the "strip first H1/H2 unconditionally" rule matches real
    agent-output patterns more reliably.
    """
    import re as _re

    lines = markdown.lstrip("\n").split("\n")

    # Strip the first heading if it's an H1 or H2 (agents shouldn't emit
    # top-level titles — their content should start at H3 or prose).
    if lines and _re.match(r"^#{1,2}\s", lines[0]):
        lines = lines[1:]
        while lines and not lines[0].strip():
            lines = lines[1:]

    cleaned = "\n".join(lines)

    def _shift(match):
        hashes = match.group(1)
        if len(hashes) >= 6:
            return match.group(0)
        return "#" + hashes

    return _re.sub(r"^(#{1,5})(?=\s)", _shift, cleaned, flags=_re.MULTILINE)


def _reconcile(draft: str) -> str:
    """Run a reconciliation pass to fix contradictions between sub-agents."""
    try:
        return call_llm(
            system_prompt=RECONCILIATION_PROMPT,
            user_prompt=draft,
            max_tokens=8000,
        )
    except Exception:
        # If reconciliation fails, return the draft as-is
        return draft
