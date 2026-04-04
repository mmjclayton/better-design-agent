"""
Multi-agent orchestrator — runs specialized sub-agents in parallel
and merges their outputs into a unified critique report.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed

from src.agents.accessibility_agent import AccessibilityAgent
from src.agents.design_system_agent import DesignSystemAgent
from src.agents.visual_agent import VisualDesignAgent
from src.agents.interaction_agent import InteractionAgent
from src.analysis.wcag_checker import run_wcag_check, run_wcag_check_multi
from src.input.models import DesignInput


def run_multi_agent_critique(design_input: DesignInput, context: str = "") -> str:
    """Run all four specialized agents in parallel and merge results."""

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

    # Merge into unified report
    return _merge_reports(wcag_report, results)


def _merge_reports(wcag_report, agent_results: dict) -> str:
    """Merge WCAG checker and agent outputs into a unified report."""

    sections = []

    # Header
    sections.append("# Design Critique Report (Multi-Agent Analysis)\n")
    sections.append(
        "This report was produced by four specialized agents analysing the design "
        "in parallel, plus a deterministic WCAG 2.2 checker. Each section represents "
        "a different analytical lens.\n"
    )

    # WCAG Checker (deterministic)
    sections.append("---\n")
    sections.append(wcag_report.to_markdown())

    # Visual Design
    if "visual" in agent_results:
        sections.append("---\n")
        sections.append("## Visual Design Analysis\n")
        sections.append(agent_results["visual"])

    # Accessibility Deep Dive
    if "accessibility" in agent_results:
        sections.append("\n---\n")
        sections.append("## Accessibility Deep Dive\n")
        sections.append(agent_results["accessibility"])

    # Design System
    if "design_system" in agent_results:
        sections.append("\n---\n")
        sections.append("## Design System Analysis\n")
        sections.append(agent_results["design_system"])

    # Interaction Quality
    if "interaction" in agent_results:
        sections.append("\n---\n")
        sections.append("## Interaction Quality Analysis\n")
        sections.append(agent_results["interaction"])

    return "\n".join(sections)
