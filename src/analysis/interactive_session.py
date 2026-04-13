"""
Interactive review session — single browser, user-driven navigation.

The user logs in + navigates + captures from the SAME browser window that
stays open throughout. No storage-state juggling, no reopening browsers,
no race conditions.

Flow:
  1. Launch visible Chromium at start URL
  2. Loop:
       prompt user: navigate, then press Enter (or q to quit)
       capture current page (URL + screenshot + DOM)
       run selected analysis mode
       display result
  3. Exit on 'q' or browser close.

This is the right pattern for authenticated-SPA review. The existing `auth`
command stays for batch/CI scenarios where you want a saved session reused
over multiple non-interactive runs.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class CaptureResult:
    """Result of a single capture cycle."""
    index: int
    url: str
    screenshot_path: str
    report_markdown: str
    mode: str
    label: str = ""  # derived from <title>/<h1>; empty → fall back to "Page N"


@dataclass
class SessionSummary:
    """End-of-session artefacts + path references for user messaging."""
    output_dir: Path
    per_page_reports: list[Path]
    combined_report: Path | None
    priorities_report: Path | None
    capture_count: int
    mode: str


async def _capture_current_page(
    page, output_dir: Path, index: int,
) -> tuple[str, str, dict]:
    """Capture screenshot + extract DOM from whatever page is currently open."""
    from src.input.screenshot import _capture_page

    shot_path = output_dir / f"capture-{index:02d}.png"
    text, dom_data = await _capture_page(page, str(shot_path))
    return str(shot_path), text, dom_data


def derive_page_label(dom_data: dict, index: int) -> str:
    """Pick a short, distinguishing label for this capture.

    Preference order:
      1. First <h1> text
      2. <title> tag (stripped of common " — Site Name" suffixes)
      3. Fallback to "Page N"
    """
    html = dom_data.get("html_structure", {}) or {}
    headings = html.get("headings", []) or []
    for h in headings:
        if h.get("level") == 1:
            text = str(h.get("text", "") or "").strip()
            if text:
                return _shorten_label(text)

    title = str(html.get("title", "") or "").strip()
    if title:
        # Trim "Page Name — App Name" or "Page Name | App Name" patterns.
        for sep in (" — ", " | ", " - ", " – "):
            if sep in title:
                title = title.split(sep)[0].strip()
                break
        if title:
            return _shorten_label(title)

    return f"Page {index}"


def _shorten_label(text: str, max_chars: int = 50) -> str:
    text = " ".join(text.split())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def _run_analysis(mode: str, dom_data: dict, text: str, url: str,
                  screenshot_path: str) -> str:
    """Run the selected analysis mode against captured page data."""
    if mode == "pragmatic-audit":
        return _run_pragmatic_audit(dom_data)
    if mode == "pragmatic-critique":
        return _run_pragmatic_critique(dom_data, text, url, screenshot_path)
    if mode == "deep-critique":
        return _run_deep_critique(dom_data, text, url, screenshot_path)
    return "Unknown mode."


def _run_pragmatic_audit(dom_data: dict) -> str:
    from src.analysis.wcag_checker import run_wcag_check
    from src.analysis.component_detector import detect_and_score_components
    from src.analysis.fix_generator import generate_fixes
    wcag = run_wcag_check(dom_data)
    components = detect_and_score_components(dom_data)
    fixes = generate_fixes(wcag)
    parts = [wcag.to_pragmatic_markdown()]
    if components.components:
        parts.append(components.to_pragmatic_markdown())
    if fixes.total > 0:
        parts.append(_render_fixes_inline(fixes))
    return "\n\n---\n\n".join(parts)


def _render_fixes_inline(fix_set) -> str:
    """Render auto-generated fixes as a report section."""
    lines = [
        "## Auto-fix suggestions\n",
        f"_{fix_set.total} mechanical fix(es) available — "
        "review before applying._\n",
    ]
    if fix_set.css_fixes:
        lines.append("### CSS patches")
        lines.append("")
        lines.append("```css")
        for fix in fix_set.css_fixes[:10]:
            lines.append(f"/* {fix.criterion}: {fix.reason} */")
            lines.append(f"{fix.selector} {{")
            for prop, val in fix.declarations.items():
                lines.append(f"  {prop}: {val};")
            lines.append("}")
            lines.append("")
        if len(fix_set.css_fixes) > 10:
            lines.append(f"/* … +{len(fix_set.css_fixes) - 10} more — "
                         f"run `design-intel fix` for the complete set */")
        lines.append("```")
        lines.append("")
    if fix_set.html_fixes:
        lines.append("### HTML/structural fixes")
        lines.append("")
        for fix in fix_set.html_fixes[:5]:
            lines.append(f"**{fix.title}** ({fix.criterion})")
            if fix.after:
                lines.append("```html")
                lines.append(fix.after)
                lines.append("```")
            if fix.notes:
                lines.append(f"_{fix.notes}_")
            lines.append("")
    if fix_set.skipped:
        lines.append("### Skipped (need manual review)")
        lines.append("")
        for s in fix_set.skipped[:5]:
            lines.append(f"- {s}")
    return "\n".join(lines)


def _build_design_input(dom_data: dict, text: str, url: str, screenshot_path: str):
    from src.input.models import DesignInput, InputType
    return DesignInput(
        type=InputType.URL,
        url=url,
        image_path=screenshot_path,
        page_text=text,
        dom_data=dom_data,
    )


def _run_pragmatic_critique(dom_data, text, url, screenshot_path) -> str:
    from src.agents.critique import CritiqueAgent
    design_input = _build_design_input(dom_data, text, url, screenshot_path)
    agent = CritiqueAgent(tone="opinionated", pragmatic=True)
    return agent.run(design_input)


def _run_deep_critique(dom_data, text, url, screenshot_path) -> str:
    from src.agents.orchestrator import run_multi_agent_critique
    design_input = _build_design_input(dom_data, text, url, screenshot_path)
    return run_multi_agent_critique(design_input)


# ── Main interactive loop (async) ──


async def run_interactive_session(
    start_url: str,
    mode: str = "pragmatic-audit",
    viewport_width: int = 1440,
    viewport_height: int = 900,
    output_dir: Path | None = None,
    prompt_fn=None,
) -> list[CaptureResult]:
    """Launch a browser, loop on user input, capture + analyse each page.

    `prompt_fn` is injected for testability — defaults to stdin input().
    """
    from playwright.async_api import async_playwright

    if prompt_fn is None:
        prompt_fn = input

    if output_dir is None:
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_dir = Path("output") / f"interactive-{ts}"
    output_dir.mkdir(parents=True, exist_ok=True)

    captures: list[CaptureResult] = []
    index = 0

    # Auto-load any saved auth session so interactive can start authenticated.
    from src.input.processor import resolve_auth_path
    storage_state = resolve_auth_path()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context_kwargs = {
            "viewport": {"width": viewport_width, "height": viewport_height},
            "locale": "en-AU",
        }
        if storage_state:
            context_kwargs["storage_state"] = storage_state
            print(f"[interactive] Using saved session from {storage_state}")
        context = await browser.new_context(**context_kwargs)
        page = await context.new_page()
        try:
            await page.goto(start_url, wait_until="domcontentloaded", timeout=30000)
        except Exception:
            pass  # User can navigate manually

        print(
            "\n→ The browser is open. Log in and navigate to the page you "
            "want reviewed.\n"
        )

        while browser.is_connected():
            try:
                choice = await asyncio.to_thread(
                    prompt_fn,
                    "Press Enter to capture + review the current page, "
                    "or type 'q' then Enter to quit: ",
                )
            except (EOFError, KeyboardInterrupt):
                break

            if choice.strip().lower() in {"q", "quit", "exit"}:
                break

            if not browser.is_connected():
                print("\n(Browser closed — stopping.)")
                break

            index += 1
            current_url = page.url
            print(f"\n[{index}] Capturing {current_url} ...")
            try:
                shot, text, dom_data = await _capture_current_page(
                    page, output_dir, index,
                )
            except Exception as exc:
                print(f"  Capture failed: {exc}")
                continue

            label = derive_page_label(dom_data, index)
            print(f"    → Identified as: {label}")
            print(f"    Running {mode} analysis...")
            try:
                report_md = _run_analysis(mode, dom_data, text, current_url, shot)
            except Exception as exc:
                print(f"  Analysis failed: {exc}")
                continue

            captures.append(CaptureResult(
                index=index, url=current_url, label=label,
                screenshot_path=shot, report_markdown=report_md, mode=mode,
            ))

            # Save per-capture report
            report_path = output_dir / f"capture-{index:02d}.md"
            report_path.write_text(report_md)
            print(f"    Report saved: {report_path}")
            print()

        # Close cleanly
        try:
            await browser.close()
        except Exception:
            pass

    return captures


def run_interactive_sync(start_url: str, mode: str, **kwargs) -> list[CaptureResult]:
    """Sync wrapper around the async session."""
    return asyncio.run(run_interactive_session(start_url, mode, **kwargs))


def finalise_session(
    captures: list[CaptureResult],
    output_dir: Path,
    mode: str,
    synthesise: bool = True,
) -> SessionSummary:
    """Write combined + priorities reports after the session ends.

    Returns a SessionSummary with all artefact paths so the CLI can show
    the user exactly where to find everything.
    """
    from src.analysis.session_synthesis import (
        CaptureRef, synthesise_session,
    )

    per_page_paths = [
        output_dir / f"capture-{c.index:02d}.md" for c in captures
    ]

    combined_path: Path | None = None
    priorities_path: Path | None = None

    if captures and synthesise:
        refs = [
            CaptureRef(
                index=c.index, url=c.url, report_markdown=c.report_markdown,
                label=c.label,
            )
            for c in captures
        ]
        combined, priorities = synthesise_session(refs, mode)
        combined_path = output_dir / "session-combined.md"
        combined_path.write_text(combined)
        priorities_path = output_dir / "session-priorities.md"
        priorities_path.write_text(priorities)

    return SessionSummary(
        output_dir=output_dir,
        per_page_reports=per_page_paths,
        combined_report=combined_path,
        priorities_report=priorities_path,
        capture_count=len(captures),
        mode=mode,
    )


# ── Pure helpers (testable without Playwright) ──


VALID_MODES = {"pragmatic-audit", "pragmatic-critique", "deep-critique"}


def validate_mode(mode: str) -> str:
    if mode not in VALID_MODES:
        raise ValueError(
            f"Unknown mode '{mode}'. Choose from: {sorted(VALID_MODES)}"
        )
    return mode


def summary_markdown(captures: list[CaptureResult]) -> str:
    """Render an index of captures from a session."""
    if not captures:
        return "# Interactive session\n\n_No pages captured._"
    lines = [
        f"# Interactive session — {len(captures)} page(s) reviewed",
        "",
        f"**Mode:** {captures[0].mode}",
        "",
        "## Captures",
        "",
    ]
    for c in captures:
        name = c.label or c.url
        lines.append(
            f"{c.index}. **{name}** — `{Path(c.screenshot_path).name}`  \n"
            f"   [dim]{c.url}[/dim]"
        )
    return "\n".join(lines)
