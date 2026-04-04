from typing import Optional

import typer
from rich.console import Console
from rich.markdown import Markdown

import re

from src.input.processor import process_input
from src.agents.critique import CritiqueAgent
from src.agents.orchestrator import run_multi_agent_critique
from src.agents.ensemble import EnsembleRunner, get_ensemble_models
from src.analysis.wcag_checker import run_wcag_check, run_wcag_check_multi
from src.analysis.interaction_tester import run_interaction_tests
from src.analysis.component_detector import detect_and_score_components, detect_and_score_multi
from src.providers.llm import get_model_display_name
from src.analysis.history import (
    build_run_record, save_run, get_previous_run, compute_diff, load_history,
)
from src.knowledge.index import build_index
from src.output.formatter import save_report

app = typer.Typer(name="design-intel", help="Design Intelligence Agent")
console = Console()


DEVICE_PRESETS = {
    "iphone-12": {"width": 390, "height": 844, "label": "iPhone 12"},
    "iphone-14-pro": {"width": 393, "height": 852, "label": "iPhone 14 Pro"},
    "iphone-15": {"width": 393, "height": 852, "label": "iPhone 15"},
    "iphone-se": {"width": 375, "height": 667, "label": "iPhone SE"},
    "pixel-7": {"width": 412, "height": 915, "label": "Pixel 7"},
    "ipad": {"width": 820, "height": 1180, "label": "iPad (10th gen)"},
    "ipad-pro": {"width": 1024, "height": 1366, "label": "iPad Pro 12.9"},
    "desktop": {"width": 1440, "height": 900, "label": "Desktop"},
}


@app.command()
def critique(
    image: Optional[str] = typer.Option(None, "--image", "-i", help="Path to screenshot"),
    url: Optional[str] = typer.Option(None, "--url", "-u", help="URL to critique"),
    describe: Optional[str] = typer.Option(None, "--describe", "-d", help="Text description"),
    context: Optional[str] = typer.Option(None, "--context", "-c", help="Additional context"),
    tone: str = typer.Option("opinionated", "--tone", "-t", help="Tone: opinionated, balanced, gentle"),
    crawl: bool = typer.Option(False, "--crawl", help="Crawl app and critique multiple pages"),
    max_pages: int = typer.Option(10, "--max-pages", help="Max pages to crawl (with --crawl)"),
    device: Optional[str] = typer.Option(None, "--device", help=f"Device preset: {', '.join(DEVICE_PRESETS.keys())}"),
    viewport_width: Optional[int] = typer.Option(None, "--viewport-width", help="Custom viewport width in px"),
    viewport_height: Optional[int] = typer.Option(None, "--viewport-height", help="Custom viewport height in px"),
    stage: str = typer.Option("production", "--stage", help="Design stage: wireframe, mockup, production"),
    deep: bool = typer.Option(False, "--deep", help="Multi-agent deep analysis (4 specialized agents in parallel)"),
    ensemble: bool = typer.Option(False, "--ensemble", help="Run multiple models and synthesise findings"),
    ensemble_models: Optional[str] = typer.Option(None, "--models", help="Comma-separated model list (overrides ENSEMBLE_MODELS env var)"),
    stealth: bool = typer.Option(False, "--stealth", help="Stealth mode: bypass bot detection on protected sites"),
    save: bool = typer.Option(False, "--save", "-s", help="Save report to output/"),
):
    """Run a design critique on a screenshot, URL, or description."""
    # Activate stealth mode if requested
    if stealth:
        from src.input.screenshot import set_stealth_mode
        set_stealth_mode(True)
        console.print("Stealth mode: enabled (bypassing bot detection)")

    STAGE_CONTEXT = {
        "wireframe": (
            "This is an early-stage WIREFRAME. Focus on information architecture, "
            "content hierarchy, user flow, and layout structure. Do NOT critique "
            "visual polish, colour choices, typography details, or pixel-level spacing. "
            "Flag structural issues: missing content, unclear navigation, wrong IA."
        ),
        "mockup": (
            "This is a MID-FIDELITY MOCKUP. Focus on visual hierarchy, typography "
            "scale, colour system, spacing rhythm, and component consistency. Flag "
            "interaction patterns that need definition. Light touch on accessibility "
            "- note obvious issues but don't deep-audit WCAG compliance yet."
        ),
        "production": "",
    }

    # Determine if we should run dual viewport (desktop + mobile)
    explicit_device = device or viewport_width or viewport_height
    is_url_input = url is not None
    run_dual = is_url_input and not explicit_device and not image and not describe

    # Resolve viewport
    vw, vh = 1440, 900
    device_label = None
    if device:
        preset = DEVICE_PRESETS.get(device)
        if not preset:
            console.print(f"[red]Unknown device: {device}. Options: {', '.join(DEVICE_PRESETS.keys())}[/red]")
            raise typer.Exit(1)
        vw, vh = preset["width"], preset["height"]
        device_label = preset["label"]
        console.print(f"Using device: {device_label} ({vw}x{vh})")
    if viewport_width:
        vw = viewport_width
    if viewport_height:
        vh = viewport_height

    def _build_context(device_label_str=None, viewport_dims=None):
        parts = []
        if device_label_str and viewport_dims:
            parts.append(f"This is a mobile view ({device_label_str}, {viewport_dims[0]}x{viewport_dims[1]}px). Evaluate against mobile design patterns: thumb zone placement, bottom navigation, touch targets (44pt iOS / 48dp Android), and responsive layout behaviour.")
        stage_ctx = STAGE_CONTEXT.get(stage, "")
        if stage_ctx:
            parts.append(stage_ctx)
        return "\n".join(filter(None, [context or ""] + parts)).strip()

    if stage != "production":
        console.print(f"Stage: {stage} (adjusting critique depth)")

    def _check_blocked(di):
        """Check if the site blocked access. Returns True if blocked."""
        blocked = di.dom_data.get("_blocked", False)
        if not blocked and di.pages:
            blocked = any(p.dom_data.get("_blocked", False) for p in di.pages)
        return blocked

    def _run_single_viewport(vw_, vh_, device_label_, device_name_):
        """Run a complete critique for one viewport."""
        ctx = _build_context(device_label_, (vw_, vh_) if device_label_ else None)

        status_msg = "Crawling app..." if crawl else "Processing input..."
        with console.status(f"[{device_name_}] {status_msg}"):
            di = process_input(
                image=image, url=url, describe=describe,
                crawl=crawl, max_pages=max_pages,
                viewport_width=vw_, viewport_height=vh_,
            )

        if crawl and di.pages:
            console.print(f"[{device_name_}] Captured {len(di.pages)} pages")

        with console.status(f"[{device_name_}] Running WCAG checks..."):
            if di.pages and len(di.pages) > 1:
                wcag = run_wcag_check_multi(di.pages)
            else:
                wcag = run_wcag_check(di.dom_data)

        return di, wcag, ctx

    if run_dual:
        console.print("Running dual viewport analysis: Desktop (1440x900) + Mobile (393x852)")

        # Desktop
        di_desktop, wcag_desktop, ctx_desktop = _run_single_viewport(1440, 900, None, "Desktop")

        # Check for blocked access
        if _check_blocked(di_desktop):
            console.print("\n[red bold]Access Denied[/red bold]\n")
            console.print(f"The site [bold]{url}[/bold] blocked automated access.")
            console.print("\nThis typically means the site uses bot protection (Cloudflare, Akamai, etc.)")
            console.print("that prevents automated browsers from loading the real page.\n")
            console.print("[yellow]Options:[/yellow]")
            console.print("  1. Try [bold]--stealth[/bold] mode: design-intel critique --url X --stealth")
            console.print("  2. Take a manual screenshot and use: design-intel critique --image ./screenshot.png")
            console.print("  3. Use a site without bot protection\n")
            if save:
                blocked_report = (
                    f"# Access Denied\n\n"
                    f"**URL:** {url}\n\n"
                    f"The site blocked automated access. Bot protection (Cloudflare, Akamai, etc.) "
                    f"prevented the agent from loading the real page.\n\n"
                    f"## What to do\n\n"
                    f"1. Try `--stealth` mode to bypass basic bot detection\n"
                    f"2. Take a manual screenshot and use `--image ./screenshot.png`\n"
                    f"3. If the site uses CAPTCHA or JavaScript challenges, automated review is not possible\n"
                )
                path = save_report(blocked_report, "blocked")
                console.print(f"Saved to {path}")
            return

        # Mobile
        di_mobile, wcag_mobile, ctx_mobile = _run_single_viewport(393, 852, "iPhone 14 Pro", "Mobile")

        # Use desktop as primary input, append mobile findings
        design_input = di_desktop
        wcag_report = wcag_desktop

        # Run the critique on desktop
        combined_context = ctx_desktop
    else:
        combined_context = _build_context(device_label, (vw, vh) if device_label else None)

        status_msg = "Crawling app..." if crawl else "Processing input..."
        with console.status(status_msg):
            design_input = process_input(
                image=image, url=url, describe=describe,
                crawl=crawl, max_pages=max_pages,
                viewport_width=vw, viewport_height=vh,
            )

        if crawl and design_input.pages:
            console.print(f"Captured {len(design_input.pages)} pages:")
            for p in design_input.pages:
                console.print(f"  - {p.label} ({p.url})")

        # Check for blocked access
        if _check_blocked(design_input):
            console.print("\n[red bold]Access Denied[/red bold]\n")
            console.print(f"The site [bold]{url}[/bold] blocked automated access.")
            console.print("\nThis typically means the site uses bot protection (Cloudflare, Akamai, etc.)")
            console.print("that prevents automated browsers from loading the real page.\n")
            console.print("[yellow]Options:[/yellow]")
            console.print("  1. Try [bold]--stealth[/bold] mode: design-intel critique --url X --stealth")
            console.print("  2. Take a manual screenshot and use: design-intel critique --image ./screenshot.png")
            console.print("  3. Use a site without bot protection\n")
            if save:
                blocked_report = (
                    f"# Access Denied\n\n"
                    f"**URL:** {url}\n\n"
                    f"The site blocked automated access.\n\n"
                    f"## What to do\n\n"
                    f"1. Try `--stealth` mode\n"
                    f"2. Take a manual screenshot and use `--image ./screenshot.png`\n"
                )
                path = save_report(blocked_report, "blocked")
                console.print(f"Saved to {path}")
            return

        with console.status("Running WCAG checks..."):
            if design_input.pages and len(design_input.pages) > 1:
                wcag_report = run_wcag_check_multi(design_input.pages)
            else:
                wcag_report = run_wcag_check(design_input.dom_data)

    if ensemble:
        # Ensemble mode: run multiple models in parallel, then synthesise
        models = ensemble_models.split(",") if ensemble_models else get_ensemble_models()
        models = [m.strip() for m in models if m.strip()]

        if len(models) < 2:
            console.print("[yellow]Ensemble mode needs at least 2 models. Add more to ENSEMBLE_MODELS in .env[/yellow]")
            console.print("[yellow]Example: ENSEMBLE_MODELS=anthropic/claude-sonnet-4-20250514,openai/gpt-4o-mini[/yellow]")
            console.print(f"[yellow]Currently configured: {', '.join(models)}[/yellow]")
            raise typer.Exit(1)

        console.print(f"Ensemble mode: {len(models)} models")
        for m in models:
            console.print(f"  - {get_model_display_name(m)}")

        with console.status(f"Running {len(models)} models in parallel..."):
            runner = EnsembleRunner(models=models, tone=tone)
            result = runner.run(design_input, context=combined_context)

    elif deep:
        # Run interaction tests and component scoring alongside agents
        interaction_report = None
        component_report = None
        if url:
            with console.status("Running interaction tests..."):
                try:
                    interaction_report = run_interaction_tests(url, viewport_width=vw, viewport_height=vh)
                except Exception:
                    pass
            with console.status("Detecting and scoring components..."):
                try:
                    if design_input.pages and len(design_input.pages) > 1:
                        component_report = detect_and_score_multi(design_input.pages)
                    else:
                        component_report = detect_and_score_components(design_input.dom_data)
                except Exception:
                    pass

        with console.status("Running multi-agent deep analysis (4 agents in parallel)..."):
            result = run_multi_agent_critique(design_input, context=combined_context)

        # Append deterministic reports
        if interaction_report:
            result += "\n\n---\n\n" + interaction_report.to_markdown()
        if component_report and component_report.components:
            result += "\n\n---\n\n" + component_report.to_markdown()
    else:
        with console.status("Generating critique..."):
            agent = CritiqueAgent(tone=tone)
            result = agent.run(design_input, context=combined_context)

    # Append mobile analysis if running dual viewport
    if run_dual:
        mobile_ctx = _build_context("iPhone 14 Pro", (393, 852))

        if deep:
            with console.status("[Mobile] Running multi-agent deep analysis..."):
                mobile_result = run_multi_agent_critique(di_mobile, context=mobile_ctx)
        elif ensemble:
            models = ensemble_models.split(",") if ensemble_models else get_ensemble_models()
            models = [m.strip() for m in models if m.strip()]
            with console.status(f"[Mobile] Running {len(models)} models in parallel..."):
                runner = EnsembleRunner(models=models, tone=tone)
                mobile_result = runner.run(di_mobile, context=mobile_ctx)
        else:
            with console.status("[Mobile] Generating mobile critique..."):
                agent = CritiqueAgent(tone=tone)
                mobile_result = agent.run(di_mobile, context=mobile_ctx)

        # Combine desktop + mobile WCAG
        mobile_wcag_md = wcag_mobile.to_markdown().replace(
            "## WCAG 2.2 Automated Audit",
            "## WCAG 2.2 Automated Audit (Mobile - iPhone 14 Pro, 393x852)"
        )

        result = (
            "# Desktop Analysis (1440x900)\n\n"
            + result
            + "\n\n---\n\n"
            + "# Mobile Analysis (iPhone 14 Pro, 393x852)\n\n"
            + mobile_wcag_md
            + "\n\n"
            + mobile_result
        )

    # Extract score from critique output (handles **bold** markdown)
    score = 0
    score_match = re.search(r"(\d+)\s*/\s*100", result)
    if score_match:
        score = int(score_match.group(1))

    # Save run to history and show regression diff
    if url:
        device_name = device or "desktop"
        record = build_run_record(
            url=url,
            device=device_name,
            pages_crawled=len(design_input.pages) if design_input.pages else 1,
            score=score,
            wcag_report=wcag_report,
        )

        previous = get_previous_run(url)
        save_run(record)

        if previous:
            diff = compute_diff(previous, record)
            console.print(Markdown(diff.to_markdown()))

    console.print(Markdown(result))

    if save:
        path = save_report(result, "critique")
        console.print(f"\nSaved to {path}")

        # Also generate HTML report
        from src.output.html_report import save_html_report
        image_paths = []
        page_labels = []

        # Desktop screenshots
        if design_input.pages:
            for p in design_input.pages:
                if p.image_path:
                    image_paths.append(p.image_path)
                    page_labels.append(f"Desktop: {p.label}")
        elif design_input.image_path:
            image_paths.append(design_input.image_path)
            page_labels.append("Desktop: Main")

        # Mobile screenshots (if dual viewport)
        if run_dual and di_mobile:
            if di_mobile.pages:
                for p in di_mobile.pages:
                    if p.image_path:
                        image_paths.append(p.image_path)
                        page_labels.append(f"Mobile: {p.label}")
            elif di_mobile.image_path:
                image_paths.append(di_mobile.image_path)
                page_labels.append("Mobile: Main")

        device_str = "Desktop + Mobile" if run_dual else (device or "desktop")
        html_path = save_html_report(
            md_content=result,
            url=url or "",
            device=device_str,
            image_paths=image_paths,
            page_labels=page_labels,
        )
        console.print(f"HTML report: {html_path}")

        # Auto-open HTML report
        import subprocess
        subprocess.run(["open", str(html_path)], check=False)


@app.command()
def wcag(
    url: Optional[str] = typer.Option(None, "--url", "-u", help="URL to audit"),
    image: Optional[str] = typer.Option(None, "--image", "-i", help="Not supported for WCAG audit"),
    crawl: bool = typer.Option(False, "--crawl", help="Crawl app and audit multiple pages"),
    max_pages: int = typer.Option(10, "--max-pages", help="Max pages to crawl"),
    device: Optional[str] = typer.Option(None, "--device", help=f"Device preset: {', '.join(DEVICE_PRESETS.keys())}"),
    save: bool = typer.Option(False, "--save", "-s", help="Save report to output/"),
):
    """Run a standalone WCAG 2.2 audit (no LLM, deterministic)."""
    if not url:
        console.print("[red]WCAG audit requires --url[/red]")
        raise typer.Exit(1)

    vw, vh = 1440, 900
    if device:
        preset = DEVICE_PRESETS.get(device)
        if preset:
            vw, vh = preset["width"], preset["height"]
            console.print(f"Using device: {preset['label']} ({vw}x{vh})")

    with console.status("Crawling and analysing..." if crawl else "Analysing..."):
        design_input = process_input(
            url=url, crawl=crawl, max_pages=max_pages,
            viewport_width=vw, viewport_height=vh,
        )

    with console.status("Running WCAG checks..."):
        if design_input.pages and len(design_input.pages) > 1:
            report = run_wcag_check_multi(design_input.pages)
        else:
            report = run_wcag_check(design_input.dom_data)

    result = report.to_markdown()

    # Add axe-core results if available
    axe_data = design_input.dom_data.get("axe_results", {})
    if axe_data and not axe_data.get("error"):
        from src.analysis.axe_runner import AxeResult
        axe = AxeResult(
            violations=axe_data.get("violations", []),
            passes=[{"id": p} for p in axe_data.get("passes", [])],
            incomplete=axe_data.get("incomplete", []),
        )
        result += "\n\n---\n\n" + axe.to_markdown()

    console.print(Markdown(result))

    if save:
        path = save_report(result, "wcag-audit")
        console.print(f"\nSaved to {path}")


@app.command()
def test_interactions(
    url: str = typer.Option(..., "--url", "-u", help="URL to test"),
    device: Optional[str] = typer.Option(None, "--device", help=f"Device preset: {', '.join(DEVICE_PRESETS.keys())}"),
    save: bool = typer.Option(False, "--save", "-s", help="Save report to output/"),
):
    """Run interaction tests - keyboard nav, form validation, empty states, responsive."""
    vw, vh = 1440, 900
    if device:
        preset = DEVICE_PRESETS.get(device)
        if preset:
            vw, vh = preset["width"], preset["height"]
            console.print(f"Using device: {preset['label']} ({vw}x{vh})")

    with console.status("Running interaction tests..."):
        report = run_interaction_tests(url, viewport_width=vw, viewport_height=vh)

    result = report.to_markdown()
    console.print(Markdown(result))

    if save:
        path = save_report(result, "interaction-tests")
        console.print(f"\nSaved to {path}")


@app.command()
def components(
    url: str = typer.Option(..., "--url", "-u", help="URL to analyse"),
    crawl: bool = typer.Option(False, "--crawl", help="Crawl multiple pages"),
    max_pages: int = typer.Option(10, "--max-pages", help="Max pages to crawl"),
    save: bool = typer.Option(False, "--save", "-s", help="Save report to output/"),
):
    """Detect and score individual UI components."""
    with console.status("Analysing components..."):
        design_input = process_input(url=url, crawl=crawl, max_pages=max_pages)

    with console.status("Scoring components..."):
        if design_input.pages and len(design_input.pages) > 1:
            report = detect_and_score_multi(design_input.pages)
        else:
            report = detect_and_score_components(design_input.dom_data)

    result = report.to_markdown()
    console.print(Markdown(result))

    if save:
        path = save_report(result, "components")
        console.print(f"\nSaved to {path}")


@app.command()
def handoff(
    url: str = typer.Option(..., "--url", "-u", help="URL to generate handoff for"),
    crawl: bool = typer.Option(False, "--crawl", help="Crawl multiple pages"),
    max_pages: int = typer.Option(10, "--max-pages", help="Max pages to crawl"),
    device: Optional[str] = typer.Option(None, "--device", help=f"Device preset"),
    save: bool = typer.Option(False, "--save", "-s", help="Save report to output/"),
):
    """Generate developer handoff specs from a live site."""
    from src.agents.handoff_agent import HandoffAgent

    vw, vh = 1440, 900
    if device:
        preset = DEVICE_PRESETS.get(device)
        if preset:
            vw, vh = preset["width"], preset["height"]
            console.print(f"Using device: {preset['label']} ({vw}x{vh})")

    with console.status("Extracting design data..."):
        design_input = process_input(
            url=url, crawl=crawl, max_pages=max_pages,
            viewport_width=vw, viewport_height=vh,
        )

    with console.status("Generating handoff specification..."):
        agent = HandoffAgent()
        result = agent.run(design_input)

    console.print(Markdown(result))

    if save:
        path = save_report(result, "handoff")
        console.print(f"\nSaved to {path}")


@app.command()
def history(
    url: str = typer.Option(..., "--url", "-u", help="URL to view history for"),
):
    """View run history for a URL."""
    runs = load_history(url)
    if not runs:
        console.print(f"No history found for {url}")
        return

    console.print(f"\n[bold]Run History for {url}[/bold] ({len(runs)} runs)\n")
    console.print(f"{'#':<4} {'Date':<22} {'Score':<8} {'WCAG':<8} {'Pages':<7} {'Device':<15} {'Violations'}")
    console.print("-" * 85)
    for i, run in enumerate(runs):
        ts = run.timestamp[:19].replace("T", " ")
        console.print(
            f"{i+1:<4} {ts:<22} {run.score:<8} {run.wcag_score:<8} "
            f"{run.pages_crawled:<7} {run.device:<15} {run.total_violations}"
        )

    # Show trend
    if len(runs) >= 2:
        first, last = runs[0], runs[-1]
        delta = last.score - first.score
        console.print(f"\nTrend: {first.score} → {last.score} ({'+' if delta >= 0 else ''}{delta} points)")


@app.command()
def generate_style(
    brief: str = typer.Option(..., "--brief", "-b", help="Design brief"),
):
    """Generate a style guide from a brief. (Phase 2)"""
    console.print("[yellow]Style Guide Generator is not yet implemented (Phase 2).[/yellow]")


@app.command()
def extract_style(
    url: Optional[str] = typer.Option(None, "--url", "-u", help="URL to extract from"),
    image: Optional[str] = typer.Option(None, "--image", "-i", help="Screenshot to extract from"),
):
    """Extract a style guide from a live site. (Phase 2)"""
    console.print("[yellow]Style Guide Extractor is not yet implemented (Phase 2).[/yellow]")


@app.command()
def write_spec(
    feature: str = typer.Option(..., "--feature", "-f", help="Feature description"),
):
    """Write a design specification. (Phase 3)"""
    console.print("[yellow]Design Spec Writer is not yet implemented (Phase 3).[/yellow]")


@app.command()
def curate():
    """Run knowledge curator to discover new entries. (Phase 4)"""
    console.print("[yellow]Knowledge Curator is not yet implemented (Phase 4).[/yellow]")


@app.command()
def index_knowledge():
    """Rebuild the knowledge index."""
    with console.status("Building knowledge index..."):
        index = build_index()
    categories = len(index.get("categories", {}))
    tags = len(index.get("tags", {}))
    console.print(f"Index built: {categories} categories, {tags} tags")


@app.command()
def add_knowledge():
    """Manually add a knowledge entry. (Phase 4)"""
    console.print("[yellow]Manual knowledge addition is not yet implemented (Phase 4).[/yellow]")


if __name__ == "__main__":
    app()
