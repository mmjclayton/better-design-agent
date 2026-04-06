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

app = typer.Typer(name="design-intel", help="Design Intelligence Agent", invoke_without_command=True)
console = Console()


def _warn_if_login_page(design_input, url: str) -> None:
    """Print a friendly warning if the captured page looks like a login screen."""
    from src.analysis.login_detection import detect_login_page
    from src.input.processor import DEFAULT_AUTH_PATH as _auth_path

    if not url or not url.startswith(("http://", "https://")):
        return
    if _auth_path.exists():
        return  # Already authenticated — the user knows what they're doing.

    detection = detect_login_page(
        design_input.dom_data, url, design_input.page_text or "",
    )
    if detection.is_login_page:
        console.print()
        console.print(
            f"[yellow]⚠  Login screen detected[/yellow] "
            f"[dim]({', '.join(detection.signals)})[/dim]"
        )
        console.print(
            "   Your review will only cover this login page, not the app behind it."
        )
        console.print(
            "   To review the authenticated app: "
            "[cyan]design-intel auth --url " + url + "[/cyan] "
            "then re-run this command.\n"
        )


def _friendly_exit(exc: BaseException, exit_code: int = 2) -> None:
    """Render an exception as a friendly message and exit."""
    from src.errors import friendly_error
    fe = friendly_error(exc)
    stderr_console = Console(stderr=True)
    stderr_console.print(f"\n[red bold]{fe.headline}[/red bold]")
    stderr_console.print(f"{fe.detail}")
    stderr_console.print(f"\n[bold]What to do:[/bold] {fe.next_action}")
    stderr_console.print(f"\n[dim]Original error: {fe.original}[/dim]\n")
    raise typer.Exit(exit_code)


@app.callback()
def _default_entry(ctx: typer.Context) -> None:
    """Launch the guided wizard when no subcommand is given."""
    if ctx.invoked_subcommand is None:
        from src.cli_wizard import run_wizard
        run_wizard()
        raise typer.Exit(0)


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
    pdf: bool = typer.Option(False, "--pdf", help="Also export a print-ready PDF (requires --save)"),
    pragmatic: bool = typer.Option(False, "--pragmatic", help="Pragmatic mode: top 3–5 findings per section, severity ≥ 2, skip AAA"),
    html_only: bool = typer.Option(False, "--html-only", help="Skip the .md file, save only the HTML report (requires --save)"),
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

        # Warn if the landing page looks like a login screen.
        _warn_if_login_page(di, url or "")

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

        with console.status("[bold]Running 4 specialist agents in parallel[/bold] [dim](typically 2-3 minutes)[/dim]..."):
            result = run_multi_agent_critique(design_input, context=combined_context)

        # Append deterministic reports
        if interaction_report:
            result += "\n\n---\n\n" + interaction_report.to_markdown()
        if component_report and component_report.components:
            result += "\n\n---\n\n" + component_report.to_markdown()
    else:
        with console.status("[bold]Asking the AI to critique[/bold] [dim](typically 60-90 seconds)[/dim]..."):
            agent = CritiqueAgent(tone=tone, pragmatic=pragmatic)
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
            with console.status("[Mobile] [bold]Asking the AI to critique[/bold] [dim](typically 60-90s)[/dim]..."):
                agent = CritiqueAgent(tone=tone, pragmatic=pragmatic)
                mobile_result = agent.run(di_mobile, context=mobile_ctx)

        # In `deep` mode the multi-agent orchestrator already embeds its own
        # WCAG section in `result`/`mobile_result`; prepending the WCAG report
        # again would duplicate it. For ensemble/default modes the agent
        # outputs don't include WCAG, so we prepend it there.
        def _strip_inner_title(md: str) -> str:
            # Remove the orchestrator's "# Design Critique Report ..." H1 and
            # its subtitle paragraph — the wrapping "# Desktop/Mobile Analysis"
            # H1 is enough context, and two H1s break heading hierarchy.
            import re as _re
            return _re.sub(
                r"^# Design Critique Report \(Multi-Agent Analysis\)\n+"
                r"This report was produced by four specialized agents[^\n]*\n+",
                "", md, count=1, flags=_re.MULTILINE,
            )

        if deep:
            # Label the embedded mobile WCAG section with its viewport suffix
            # (only rename the FIRST occurrence to avoid touching the body).
            mobile_result = mobile_result.replace(
                "## WCAG 2.2 Automated Audit",
                "## WCAG 2.2 Automated Audit (Mobile - iPhone 14 Pro, 393x852)",
                1,
            )
            result = (
                "# Desktop Analysis (1440x900)\n\n"
                + _strip_inner_title(result)
                + "\n\n---\n\n"
                + "# Mobile Analysis (iPhone 14 Pro, 393x852)\n\n"
                + _strip_inner_title(mobile_result)
            )
        else:
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
        if not html_only:
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

        # Optional PDF export
        if pdf:
            from src.output.pdf_report import save_pdf_report
            with console.status("Rendering PDF..."):
                pdf_path = save_pdf_report(
                    md_content=result,
                    url=url or "",
                    device=device_str,
                    image_paths=image_paths,
                    page_labels=page_labels,
                )
            if pdf_path:
                console.print(f"PDF report: {pdf_path}")
            else:
                console.print("[yellow]PDF generation skipped (see warning above)[/yellow]")

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
    pragmatic: bool = typer.Option(False, "--pragmatic", help="High-signal view: A/AA failures + axe critical/serious only"),
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

    result = report.to_pragmatic_markdown() if pragmatic else report.to_markdown()

    # Add axe-core results if available (filtered to critical+serious in pragmatic mode)
    axe_data = design_input.dom_data.get("axe_results", {})
    if axe_data and not axe_data.get("error"):
        from src.analysis.axe_runner import AxeResult
        violations = axe_data.get("violations", [])
        if pragmatic:
            violations = [
                v for v in violations
                if v.get("impact") in ("critical", "serious")
            ]
        axe = AxeResult(
            violations=violations,
            passes=[] if pragmatic else [{"id": p} for p in axe_data.get("passes", [])],
            incomplete=[] if pragmatic else axe_data.get("incomplete", []),
        )
        if violations or not pragmatic:
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
    pragmatic: bool = typer.Option(False, "--pragmatic", help="High-signal view: components below 60% only"),
):
    """Detect and score individual UI components."""
    with console.status("Analysing components..."):
        design_input = process_input(url=url, crawl=crawl, max_pages=max_pages)

    with console.status("Scoring components..."):
        if design_input.pages and len(design_input.pages) > 1:
            report = detect_and_score_multi(design_input.pages)
        else:
            report = detect_and_score_components(design_input.dom_data)

    result = report.to_pragmatic_markdown() if pragmatic else report.to_markdown()
    console.print(Markdown(result))

    if save:
        path = save_report(result, "components")
        console.print(f"\nSaved to {path}")


@app.command(name="ui-audit")
def ui_audit(
    url: str = typer.Option(..., "--url", "-u", help="URL to audit"),
    crawl: bool = typer.Option(False, "--crawl", help="Crawl the app and audit every page found"),
    max_pages: int = typer.Option(10, "--max-pages", help="Max pages to crawl"),
    device: Optional[str] = typer.Option(None, "--device", help=f"Device preset: {', '.join(DEVICE_PRESETS.keys())}"),
    responsive: bool = typer.Option(False, "--responsive", "-r", help="Audit at mobile/tablet/desktop breakpoints"),
    style_guide: Optional[str] = typer.Option(None, "--style-guide", "-g", help="Compare against a saved style guide (name or path)"),
    save: bool = typer.Option(False, "--save", "-s", help="Save report to output/"),
    format: str = typer.Option("markdown", "--format", "-f", help="Output format: markdown, json"),
    no_llm: bool = typer.Option(False, "--no-llm", help="Skip LLM opinion layer — deterministic results only"),
    stealth: bool = typer.Option(False, "--stealth", help="Stealth mode: bypass bot detection"),
):
    """Opinionated UI quality audit — typography, colour, spacing, interactivity, hierarchy."""
    if stealth:
        from src.input.screenshot import set_stealth_mode
        set_stealth_mode(True)

    import json as json_mod
    from src.analysis.ui_review import run_ui_review

    try:
        if responsive:
            # Multi-breakpoint audit
            from src.analysis.ui_review import BREAKPOINTS, ResponsiveReport
            responsive_report = ResponsiveReport()

            for bp_name, bp in BREAKPOINTS.items():
                bp_label = bp["label"]
                with console.status(f"Capturing {bp_label}..."):
                    di = process_input(url=url, viewport_width=bp["width"], viewport_height=bp["height"])
                with console.status(f"Reviewing {bp_label}..."):
                    report = run_ui_review(di.dom_data)
                responsive_report.breakpoint_reports[bp_name] = report
                console.print(f"  {bp_label}: {report.overall_score}/100")

            if format == "json":
                output = json_mod.dumps(responsive_report.to_dict(), indent=2)
                console.print(output)
            else:
                console.print(Markdown(responsive_report.to_markdown()))
                # Also print the desktop report detail
                desktop_report = responsive_report.breakpoint_reports.get("desktop")
                if desktop_report:
                    console.print(Markdown(desktop_report.to_markdown()))

            if save:
                fmt = "json" if format == "json" else "md"
                content = (
                    json_mod.dumps(responsive_report.to_dict(), indent=2) if format == "json"
                    else responsive_report.to_markdown()
                )
                path = save_report(content, "ui-audit-responsive", format=fmt)
                console.print(f"\nSaved to {path}")
        else:
            # Single or crawl viewport audit
            vw, vh = 1440, 900
            if device:
                preset = DEVICE_PRESETS.get(device)
                if not preset:
                    console.print(f"[red]Unknown device: {device}. Options: {', '.join(DEVICE_PRESETS.keys())}[/red]")
                    raise typer.Exit(1)
                vw, vh = preset["width"], preset["height"]
                console.print(f"Using device: {preset['label']} ({vw}x{vh})")

            status_msg = "Crawling app..." if crawl else "Capturing page..."
            with console.status(status_msg):
                design_input = process_input(
                    url=url, crawl=crawl, max_pages=max_pages,
                    viewport_width=vw, viewport_height=vh,
                )

            _warn_if_login_page(design_input, url)

            # Multi-page crawl review
            if crawl and design_input.pages and len(design_input.pages) > 1:
                from src.analysis.ui_review import CrawlReviewReport
                crawl_report = CrawlReviewReport()
                for i, page in enumerate(design_input.pages):
                    label = page.label or page.url
                    console.print(f"  [{i+1}/{len(design_input.pages)}] Reviewing {label}...")
                    page_review = run_ui_review(page.dom_data)
                    crawl_report.page_reports.append({
                        "url": page.url,
                        "label": label,
                        "report": page_review,
                    })

                if format == "json":
                    output = json_mod.dumps(crawl_report.to_dict(), indent=2)
                    console.print(output)
                else:
                    console.print(Markdown(crawl_report.to_markdown()))

                if save:
                    fmt = "json" if format == "json" else "md"
                    content = (
                        json_mod.dumps(crawl_report.to_dict(), indent=2) if format == "json"
                        else crawl_report.to_markdown()
                    )
                    path = save_report(content, "ui-audit-crawl", format=fmt)
                    console.print(f"\nSaved to {path}")
                return

            with console.status("Running UI review..."):
                report = run_ui_review(design_input.dom_data)

            if not no_llm:
                with console.status("Getting design suggestions..."):
                    from src.analysis.ui_review import get_llm_suggestions
                    report.llm_suggestions = get_llm_suggestions(
                        report, design_input.image_path, design_input.dom_data,
                    )

            # Style guide comparison
            guide_comparison = None
            if style_guide:
                with console.status("Comparing against style guide..."):
                    from src.analysis.style_guide import resolve_guide, load_guide, compare_against_guide
                    guide_path = resolve_guide(style_guide)
                    loaded_guide = load_guide(guide_path)
                    guide_comparison = compare_against_guide(design_input.dom_data, loaded_guide)

            if format == "json":
                result_dict = report.to_dict()
                if guide_comparison:
                    result_dict["style_guide_comparison"] = guide_comparison.to_dict()
                output = json_mod.dumps(result_dict, indent=2)
                console.print(output)
            else:
                result = report.to_markdown()
                if guide_comparison:
                    result += "\n\n---\n\n" + guide_comparison.to_markdown()
                console.print(Markdown(result))

            if save:
                fmt = "json" if format == "json" else "md"
                if format == "json":
                    result_dict = report.to_dict()
                    if guide_comparison:
                        result_dict["style_guide_comparison"] = guide_comparison.to_dict()
                    content = json_mod.dumps(result_dict, indent=2)
                else:
                    content = report.to_markdown()
                    if guide_comparison:
                        content += "\n\n---\n\n" + guide_comparison.to_markdown()
                path = save_report(content, "ui-audit", format=fmt)
                console.print(f"\nSaved to {path}")

    except Exception as exc:
        _friendly_exit(exc)


@app.command(name="extract-style")
def extract_style(
    url: str = typer.Option(..., "--url", "-u", help="URL to extract style guide from"),
    name: str = typer.Option(..., "--name", "-n", help="Name for the style guide"),
    guide_dir: Optional[str] = typer.Option(None, "--guide-dir", help="Directory to save guides (default: .design-intel/guides/)"),
    device: Optional[str] = typer.Option(None, "--device", help=f"Device preset: {', '.join(DEVICE_PRESETS.keys())}"),
    stealth: bool = typer.Option(False, "--stealth", help="Stealth mode: bypass bot detection"),
):
    """Extract a design style guide from a reference site."""
    if stealth:
        from src.input.screenshot import set_stealth_mode
        set_stealth_mode(True)

    vw, vh = 1440, 900
    if device:
        preset = DEVICE_PRESETS.get(device)
        if preset:
            vw, vh = preset["width"], preset["height"]
            console.print(f"Using device: {preset['label']} ({vw}x{vh})")

    try:
        with console.status(f"Capturing {url}..."):
            design_input = process_input(url=url, viewport_width=vw, viewport_height=vh)

        _warn_if_login_page(design_input, url)

        with console.status("Extracting style guide..."):
            from src.analysis.style_guide import extract_style_guide, save_guide
            from pathlib import Path
            guide = extract_style_guide(design_input.dom_data, url, name)

        save_dir = Path(guide_dir) if guide_dir else None
        path = save_guide(guide, save_dir)

        console.print(Markdown(guide.to_markdown()))
        console.print(f"\nStyle guide saved to [bold]{path}[/bold]")
        console.print(f"Use with: [cyan]design-intel ui-audit --url <your-site> --style-guide {name}[/cyan]")

    except Exception as exc:
        _friendly_exit(exc)


@app.command(name="list-styles")
def list_styles(
    guide_dir: Optional[str] = typer.Option(None, "--guide-dir", help="Directory to search"),
):
    """List saved style guides."""
    from src.analysis.style_guide import list_guides, load_guide
    from pathlib import Path

    directory = Path(guide_dir) if guide_dir else None
    guides = list_guides(directory)

    if not guides:
        console.print("No style guides found. Create one with: design-intel extract-style --url <url> --name <name>")
        return

    console.print(f"\n[bold]{len(guides)} style guide(s) found:[/bold]\n")
    for path in guides:
        try:
            guide = load_guide(path)
            console.print(f"  [cyan]{guide.name}[/cyan] — {guide.source_url} ({guide.extracted_at})")
            comp_counts = []
            for comp_name, comp_list in [("buttons", guide.buttons), ("inputs", guide.inputs),
                                          ("links", guide.links), ("cards", guide.cards)]:
                if comp_list:
                    comp_counts.append(f"{len(comp_list)} {comp_name}")
            if comp_counts:
                console.print(f"    Components: {', '.join(comp_counts)}")
        except Exception:
            console.print(f"  [dim]{path.stem}[/dim] — (unable to read)")
    console.print()


@app.command()
def handoff(
    url: str = typer.Option(..., "--url", "-u", help="URL to generate handoff for"),
    crawl: bool = typer.Option(False, "--crawl", help="Crawl multiple pages"),
    max_pages: int = typer.Option(10, "--max-pages", help="Max pages to crawl"),
    device: Optional[str] = typer.Option(None, "--device", help="Device preset"),
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
def fix(
    url: Optional[str] = typer.Option(None, "--url", "-u", help="URL to generate fixes for"),
    crawl: bool = typer.Option(False, "--crawl", help="Crawl multiple pages"),
    max_pages: int = typer.Option(10, "--max-pages", help="Max pages to crawl"),
    device: Optional[str] = typer.Option(None, "--device", help=f"Device preset: {', '.join(DEVICE_PRESETS.keys())}"),
    save: bool = typer.Option(True, "--save/--no-save", help="Write fixes.css and fixes.md to output/"),
):
    """Generate CSS/HTML fixes for deterministic WCAG failures."""
    from src.analysis.fix_generator import generate_fixes

    if not url:
        console.print("[red]fix requires --url[/red]")
        raise typer.Exit(1)

    vw, vh = 1440, 900
    if device:
        preset = DEVICE_PRESETS.get(device)
        if not preset:
            console.print(f"[red]Unknown device: {device}[/red]")
            raise typer.Exit(1)
        vw, vh = preset["width"], preset["height"]
        console.print(f"Using device: {preset['label']} ({vw}x{vh})")

    with console.status("Crawling and analysing..." if crawl else "Analysing..."):
        design_input = process_input(
            url=url, crawl=crawl, max_pages=max_pages,
            viewport_width=vw, viewport_height=vh,
        )

    with console.status("Running WCAG checks..."):
        if design_input.pages and len(design_input.pages) > 1:
            wcag_report = run_wcag_check_multi(design_input.pages)
        else:
            wcag_report = run_wcag_check(design_input.dom_data)

    with console.status("Generating fixes..."):
        fix_set = generate_fixes(wcag_report)

    console.print(
        f"\nGenerated [bold]{len(fix_set.css_fixes)}[/bold] CSS fixes and "
        f"[bold]{len(fix_set.html_fixes)}[/bold] HTML/structural fixes."
    )
    if fix_set.skipped:
        console.print(f"[dim]{len(fix_set.skipped)} issues skipped (no deterministic recipe).[/dim]")

    console.print(Markdown(fix_set.to_markdown()))

    if save and fix_set.total > 0:
        from datetime import datetime
        from pathlib import Path
        from src.config import settings

        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        out_dir = Path(settings.output_directory)
        out_dir.mkdir(parents=True, exist_ok=True)
        css_path = out_dir / f"fixes-{ts}.css"
        md_path = out_dir / f"fixes-{ts}.md"
        css_path.write_text(fix_set.to_css_file())
        md_path.write_text(fix_set.to_markdown())
        console.print(f"\nSaved CSS to {css_path}")
        console.print(f"Saved report to {md_path}")


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


# extract-style command is defined above (line ~716) — replaced Phase 2 placeholder


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


REVIEW_MODES = {
    "pragmatic-audit": {
        "label": "Pragmatic audit (no LLM, fastest)",
        "description": "WCAG A/AA failures + axe critical/serious + components below 60%",
    },
    "pragmatic-critique": {
        "label": "Pragmatic critique (LLM, focused)",
        "description": "LLM critique with top 3–5 findings per section, severity ≥ 2, skips AAA/polish",
    },
    "deep-critique": {
        "label": "Deep multi-agent critique (LLM, full)",
        "description": "4 specialised agents in parallel, full findings, no filtering",
    },
    "brand-compliance": {
        "label": "Brand compliance (no LLM)",
        "description": "Validate against .design-intel/rules.yaml (font, colour, tokens)",
    },
    "everything": {
        "label": "Everything (LLM, exhaustive)",
        "description": "Deep critique + full WCAG + components + interactions, no filtering",
    },
}

OUTPUT_FORMATS = {
    "terminal": "Terminal only",
    "html-only": "HTML only (auto-opens in browser, no .md file)",
    "markdown": "Save markdown to output/",
    "html": "Save markdown + HTML",
    "pdf": "Save markdown + HTML + PDF",
}


def _detect_target_type(target: str) -> tuple[str, Optional[str]]:
    """Return (kind, error_msg). kind is 'url' | 'image' | 'unknown'."""
    from pathlib import Path as _Path
    t = target.strip()
    if not t:
        return "unknown", "Empty target"
    if t.startswith(("http://", "https://")):
        return "url", None
    path = _Path(t)
    if path.exists() and path.is_file():
        if path.suffix.lower() in {".png", ".jpg", ".jpeg"}:
            return "image", None
        return "unknown", f"File type not supported: {path.suffix}"
    return "unknown", f"Not a URL and file not found: {t}"


def _resolve_review_plan(
    mode: str, target: str, target_kind: str,
    output_format: str, context: Optional[str],
) -> list[str]:
    """Translate mode + inputs into a design-intel command argv list."""
    save_flags = []
    if output_format == "markdown":
        save_flags = ["--save"]
    elif output_format == "html-only":
        save_flags = ["--save", "--html-only"]
    elif output_format == "html":
        save_flags = ["--save"]
    elif output_format == "pdf":
        save_flags = ["--save", "--pdf"]

    target_flag = ["--url", target] if target_kind == "url" else ["--image", target]
    ctx_flag = ["--context", context] if context else []

    if mode == "pragmatic-audit":
        return ["wcag", *target_flag, "--pragmatic"]
    if mode == "pragmatic-critique":
        return ["critique", *target_flag, "--pragmatic", *save_flags, *ctx_flag]
    if mode == "deep-critique":
        return ["critique", *target_flag, "--deep", *save_flags, *ctx_flag]
    if mode == "brand-compliance":
        return ["brand-check", *target_flag]
    if mode == "everything":
        return ["critique", *target_flag, "--deep", *save_flags, *ctx_flag]
    return []


@app.command()
def review(
    non_interactive: bool = typer.Option(
        False, "--non-interactive",
        help="Skip prompts; requires --mode and --target.",
    ),
    mode: Optional[str] = typer.Option(None, "--mode", help=f"One of: {', '.join(REVIEW_MODES.keys())}"),
    target: Optional[str] = typer.Option(None, "--target", help="URL or local image path"),
    output_format: str = typer.Option("terminal", "--format", help="terminal | markdown | html | pdf"),
    context_arg: Optional[str] = typer.Option(None, "--context", help="Optional context about the target"),
):
    """Interactive review — asks what, how, where, and runs the right tool."""
    from rich.prompt import Prompt

    if non_interactive:
        if not mode or not target:
            console.print("[red]--non-interactive requires --mode and --target[/red]")
            raise typer.Exit(2)
        if mode not in REVIEW_MODES:
            console.print(f"[red]Unknown mode: {mode}. Choose from: {', '.join(REVIEW_MODES.keys())}[/red]")
            raise typer.Exit(2)
        resolved_mode = mode
        resolved_target = target
        resolved_format = output_format
        resolved_context = context_arg
    else:
        console.print("\n[bold]design-intel review[/bold] — 4 questions, then I'll run the right tool.\n")

        resolved_target = Prompt.ask(
            "[bold]1.[/bold] What should I review? (URL or local image path)",
        ).strip()
        kind, err = _detect_target_type(resolved_target)
        if err:
            console.print(f"[red]{err}[/red]")
            raise typer.Exit(2)
        console.print(f"   → detected: [cyan]{kind}[/cyan]\n")

        console.print("[bold]2.[/bold] Which mode?")
        mode_keys = list(REVIEW_MODES.keys())
        for i, key in enumerate(mode_keys, 1):
            info = REVIEW_MODES[key]
            console.print(f"   {i}. [bold]{info['label']}[/bold]")
            console.print(f"      [dim]{info['description']}[/dim]")
        from src.cli_wizard import ask_numbered_choice
        mode_choice = ask_numbered_choice(
            "   Choose", len(mode_keys), default="1",
        )
        resolved_mode = mode_keys[int(mode_choice) - 1]
        console.print(f"   → [cyan]{resolved_mode}[/cyan]\n")

        console.print("[bold]3.[/bold] Output format?")
        fmt_keys = list(OUTPUT_FORMATS.keys())
        for i, key in enumerate(fmt_keys, 1):
            console.print(f"   {i}. {OUTPUT_FORMATS[key]}")
        fmt_choice = ask_numbered_choice(
            "   Choose", len(fmt_keys), default="1",
        )
        resolved_format = fmt_keys[int(fmt_choice) - 1]
        console.print(f"   → [cyan]{resolved_format}[/cyan]\n")

        resolved_context = Prompt.ask(
            "[bold]4.[/bold] Any context about this project? (press enter to skip)",
            default="",
        ).strip() or None
        if resolved_context:
            console.print(f"   → {resolved_context}\n")

    kind, err = _detect_target_type(resolved_target)
    if err:
        console.print(f"[red]{err}[/red]")
        raise typer.Exit(2)

    argv = _resolve_review_plan(
        resolved_mode, resolved_target, kind,
        resolved_format, resolved_context,
    )

    cmd_str = "design-intel " + " ".join(argv)
    console.print(f"\n[bold]I'll run:[/bold] [cyan]{cmd_str}[/cyan]")

    if not non_interactive:
        if not typer.confirm("\nRun this?", default=True):
            console.print("[yellow]Cancelled.[/yellow]")
            raise typer.Exit(0)

    console.print("")
    app(argv, standalone_mode=False)

    if resolved_mode == "pragmatic-audit" and kind == "url":
        console.print("\n[dim]--- running components ---[/dim]\n")
        app(
            ["components", "--url", resolved_target, "--pragmatic"],
            standalone_mode=False,
        )


@app.command()
def autopilot(
    url: Optional[str] = typer.Option(None, "--url", "-u", help="Starting URL"),
    goal: Optional[str] = typer.Option(None, "--goal", "-g", help="Natural-language goal (e.g. 'review the signup + dashboard')"),
    mode: Optional[str] = typer.Option(None, "--mode", help="pragmatic-audit | pragmatic-critique | deep-critique"),
    max_steps: int = typer.Option(20, "--max-steps", help="Cap on autopilot navigation steps"),
    device: Optional[str] = typer.Option(None, "--device", help=f"Device preset: {', '.join(DEVICE_PRESETS.keys())}"),
):
    """LLM drives the browser: screenshot → pick action → execute → repeat.

    Claude watches the page, clicks through your app, captures every
    screen, then runs the usual synthesis. Log in manually first in the
    browser window, then press Enter to hand off to Claude.
    """
    from pathlib import Path as _Path
    from datetime import datetime as _dt
    from rich.prompt import Prompt
    from src.analysis.autopilot import run_autopilot_sync, render_action_log
    from src.analysis.interactive_session import validate_mode, finalise_session
    from src.cli_wizard import REVIEW_DEPTHS
    from src.config import settings

    # Load project config defaults
    from src.project_config import load_project_config
    project_config = load_project_config()
    if not url and project_config.default_url:
        url = project_config.default_url
    if not mode and project_config.default_mode:
        mode = project_config.default_mode
    if not device and project_config.default_device:
        device = project_config.default_device

    # ── Welcome screen + fill-in-the-blanks prompts ──
    console.print()
    console.print("[bold cyan]design-intel autopilot[/bold cyan]")
    if project_config.exists:
        console.print(f"[dim]Using project config: {project_config.loaded_from}[/dim]")
    console.print(
        "I'll drive a browser autonomously to review your app. "
        "You log in once (if needed), I do the rest."
    )
    console.print()
    console.print("[bold]Here's what will happen:[/bold]")
    console.print("  1. A Chrome window opens at your starting URL")
    console.print("  2. You log in manually (if the app needs it) and navigate to your starting screen")
    console.print("  3. You press Enter — I take over")
    console.print("  4. I click / navigate / fill forms to accomplish your goal")
    console.print("  5. Every page I visit gets captured + reviewed")
    console.print("  6. At the end you get a prioritised report + action log")
    console.print()

    # Collect missing inputs interactively
    if not url:
        url = Prompt.ask("[bold]What URL should I start at?[/bold]").strip()
        if not url:
            console.print("[red]A starting URL is required.[/red]")
            raise typer.Exit(2)
    if not goal:
        console.print(
            "[bold]What should I try to accomplish?[/bold] "
            "[dim](e.g. 'tour the dashboard, programs, and settings')[/dim]"
        )
        goal = Prompt.ask("  Goal").strip()
        if not goal:
            console.print("[red]A goal is required.[/red]")
            raise typer.Exit(2)
    if not mode:
        console.print("\n[bold]Which review mode per page?[/bold]")
        for i, depth in enumerate(REVIEW_DEPTHS, 1):
            console.print(
                f"  {i}. [bold]{depth['label']}[/bold] "
                f"[dim]({depth['time']})[/dim]"
            )
            console.print(f"     [dim]{depth['detail']}[/dim]")
        from src.cli_wizard import ask_numbered_choice
        choice = ask_numbered_choice("  Pick one", len(REVIEW_DEPTHS), default="1")
        mode = REVIEW_DEPTHS[int(choice) - 1]["key"]
        console.print()

    try:
        validate_mode(mode)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(2)

    vw, vh = 1440, 900
    if device:
        preset = DEVICE_PRESETS.get(device)
        if preset:
            vw, vh = preset["width"], preset["height"]

    ts = _dt.now().strftime("%Y%m%d-%H%M%S")
    output_dir = _Path(settings.output_directory) / f"autopilot-{ts}"

    console.print("[bold]Plan:[/bold]")
    console.print(f"  URL:       [cyan]{url}[/cyan]")
    console.print(f"  Goal:      [cyan]{goal}[/cyan]")
    console.print(f"  Mode:      [cyan]{mode}[/cyan]")
    console.print(f"  Max steps: {max_steps}")
    console.print(f"  Output:    [dim]{output_dir}[/dim]")
    console.print()

    try:
        captures, action_log = run_autopilot_sync(
            start_url=url, goal=goal, mode=mode, max_steps=max_steps,
            viewport_width=vw, viewport_height=vh, output_dir=output_dir,
        )
    except Exception as exc:
        _friendly_exit(exc)

    # Write the action log
    log_path = output_dir / "actions.md"
    log_path.write_text(render_action_log(action_log, goal))

    # Synthesis
    if captures:
        console.print("\n[dim]Synthesising priorities...[/dim]")
        with console.status("Building combined report + prioritised synthesis..."):
            summary = finalise_session(captures, output_dir, mode)

        console.print(
            f"\n[bold green]Autopilot complete.[/bold green] "
            f"{len(captures)} page(s) captured in {len(action_log)} step(s).\n"
        )
        console.print("[bold]Your reports:[/bold]")
        if summary.priorities_report:
            console.print(f"  [cyan]{summary.priorities_report}[/cyan]  [dim]← start here[/dim]")
        if summary.combined_report:
            console.print(f"  [cyan]{summary.combined_report}[/cyan]  [dim](everything)[/dim]")
        console.print(f"  [cyan]{log_path}[/cyan]  [dim](what Claude did)[/dim]")
        console.print(
            f"\n[dim]Open the priorities file first:[/dim] "
            f"[cyan]open {summary.priorities_report or output_dir}[/cyan]\n"
        )
    else:
        console.print("\n[yellow]No pages captured.[/yellow]")
        console.print(f"Action log: {log_path}")


@app.command()
def init(
    force: bool = typer.Option(
        False, "--force", "-f",
        help="Overwrite existing files instead of preserving them.",
    ),
):
    """First-run bootstrap — creates .env, .design-intel/, and a project
    config template in the current directory.

    Safe to re-run: existing files are left alone unless --force is set.
    """
    from pathlib import Path as _Path
    from src.project_config import EXAMPLE_CONFIG, CONFIG_RELATIVE

    cwd = _Path.cwd()
    actions = []

    # .design-intel/ directory
    intel_dir = cwd / ".design-intel"
    intel_dir.mkdir(exist_ok=True)
    if intel_dir.exists():
        actions.append((".design-intel/", "ready"))

    # config.yaml template
    config_path = cwd / CONFIG_RELATIVE
    if config_path.exists() and not force:
        actions.append((f"{CONFIG_RELATIVE}", "exists, left alone"))
    else:
        config_path.write_text(EXAMPLE_CONFIG)
        actions.append((f"{CONFIG_RELATIVE}", "created"))

    # .env from .env.example (if the example is nearby)
    env_path = cwd / ".env"
    if env_path.exists() and not force:
        actions.append((".env", "exists, left alone"))
    else:
        # Look for .env.example in the current dir first, then the project root
        # (design-agent/.env.example) if this is being run from somewhere else.
        example_candidates = [
            cwd / ".env.example",
            _Path(__file__).parent.parent / ".env.example",
        ]
        example = next((p for p in example_candidates if p.exists()), None)
        if example is not None:
            env_path.write_text(example.read_text())
            actions.append((".env", f"created from {example.name}"))
        else:
            env_path.write_text(
                "# Add your LLM API key here.\n"
                "ANTHROPIC_API_KEY=sk-ant-...\n"
            )
            actions.append((".env", "created (template, add your API key)"))

    # output/ directory (referenced by every save command)
    output_dir = cwd / "output"
    output_dir.mkdir(exist_ok=True)
    actions.append(("output/", "ready"))

    # Print the summary
    console.print("\n[bold]design-intel init[/bold] — bootstrapping this project\n")
    for path, status in actions:
        marker = "✓" if "ready" in status or "created" in status else "·"
        console.print(f"  {marker} [cyan]{path}[/cyan] [dim]— {status}[/dim]")
    console.print()

    # Next-step guidance
    console.print("[bold]Next:[/bold]")
    if "created" in dict(actions).get(".env", ""):
        console.print("  1. Open [cyan].env[/cyan] and add your [bold]ANTHROPIC_API_KEY[/bold]")
        console.print(f"  2. Edit [cyan]{CONFIG_RELATIVE}[/cyan] to set default_url etc. (optional)")
        console.print("  3. Run [cyan]design-intel[/cyan] to start the wizard")
    else:
        console.print(f"  1. Edit [cyan]{CONFIG_RELATIVE}[/cyan] to set default_url etc.")
        console.print("  2. Run [cyan]design-intel[/cyan] to start the wizard")
    console.print()


@app.command()
def interactive(
    url: str = typer.Option(..., "--url", "-u", help="Starting URL (usually your app's login page or home)"),
    mode: str = typer.Option(
        "pragmatic-audit", "--mode",
        help="pragmatic-audit (no AI, fast) | pragmatic-critique (AI, focused) | deep-critique (AI, full)",
    ),
    device: Optional[str] = typer.Option(None, "--device", help=f"Device preset: {', '.join(DEVICE_PRESETS.keys())}"),
):
    """Open a browser, log in + navigate, press Enter to review each page.

    Single browser stays open the whole time. No saved-session files, no
    reopening. Best for authenticated SPAs where you want to review
    multiple pages in one sitting.
    """
    from pathlib import Path as _Path
    from datetime import datetime as _dt
    from src.analysis.interactive_session import (
        run_interactive_sync, validate_mode, finalise_session,
    )
    from src.config import settings

    try:
        validate_mode(mode)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(2)

    vw, vh = 1440, 900
    if device:
        preset = DEVICE_PRESETS.get(device)
        if preset:
            vw, vh = preset["width"], preset["height"]

    ts = _dt.now().strftime("%Y%m%d-%H%M%S")
    output_dir = _Path(settings.output_directory) / f"interactive-{ts}"

    console.print(f"\n[bold]Interactive review[/bold] — mode: [cyan]{mode}[/cyan]")
    console.print(f"[dim]Reports will be saved to {output_dir}[/dim]")

    try:
        captures = run_interactive_sync(
            start_url=url, mode=mode,
            viewport_width=vw, viewport_height=vh,
            output_dir=output_dir,
        )
    except Exception as exc:
        _friendly_exit(exc)

    # Finalise: write combined report + prioritised synthesis
    if captures:
        console.print("\n[dim]Synthesising priorities across all pages...[/dim]")
        with console.status("Building combined report + prioritised synthesis..."):
            summary = finalise_session(captures, output_dir, mode)

        console.print(f"\n[bold green]Review complete.[/bold green] "
                      f"{summary.capture_count} page(s) reviewed.\n")
        console.print("[bold]Your reports:[/bold]")
        if summary.priorities_report:
            console.print(
                f"  [cyan]{summary.priorities_report}[/cyan]  "
                "[dim]← start here (prioritised across all pages)[/dim]"
            )
        if summary.combined_report:
            console.print(
                f"  [cyan]{summary.combined_report}[/cyan]  "
                "[dim](everything in one file)[/dim]"
            )
        console.print(
            f"  [dim]{len(summary.per_page_reports)} per-page report(s) in "
            f"{summary.output_dir}[/dim]"
        )
        console.print(
            f"\n[dim]Open the priorities file first:[/dim] "
            f"[cyan]open {summary.priorities_report or summary.output_dir}[/cyan]\n"
        )
    else:
        console.print("\n[yellow]No pages captured in this session.[/yellow]")


@app.command()
def auth(
    url: str = typer.Option(..., "--url", "-u", help="URL to start at (usually your app's login page)"),
    output: str = typer.Option(
        ".design-intel/auth.json", "--output", "-o",
        help="Where to save the captured session (default: .design-intel/auth.json, auto-detected by other commands)",
    ),
):
    """Capture an authenticated browser session so later commands can review the signed-in app.

    Opens a visible Chromium window at the URL you provide. Log in manually,
    navigate to wherever you want design-intel to start reviewing from, then
    close the browser window. Your session (cookies + localStorage) is saved
    to the output file.

    Every subsequent command that hits a URL will automatically use that file
    if it exists. To disable: set `DESIGN_INTEL_NO_AUTH=1` env var, delete
    the file, or point `DESIGN_INTEL_AUTH` at a different path.
    """
    from src.input.screenshot import save_auth

    console.print(
        "\n[bold]Opening a browser window.[/bold] Log in to your app, "
        "navigate around to make sure the session works, then [bold]close "
        "the window[/bold] when you're ready.\n"
    )
    console.print(f"[dim]Target URL: {url}[/dim]\n")

    try:
        summary = save_auth(url, output)
    except Exception as exc:
        console.print(f"[red]Failed to capture session: {exc}[/red]")
        raise typer.Exit(2)

    if summary.get("cookies", 0) == 0 and not summary.get("origins"):
        console.print(
            "[yellow]No cookies or origins captured. "
            "Did you close the browser before logging in? Try again.[/yellow]"
        )
        raise typer.Exit(1)

    console.print(
        f"\n[green]Session saved[/green] to [bold]{summary['output_path']}[/bold]"
    )
    console.print(f"  {summary['cookies']} cookie(s)  |  {len(summary['origins'])} origin(s)")
    if summary["origins"]:
        console.print("  Origins: " + ", ".join(summary["origins"][:5]))
    console.print(
        "\nFrom now on, every command that hits a URL will use this session "
        "automatically. Set DESIGN_INTEL_NO_AUTH=1 to skip."
    )


@app.command()
def flow(
    flow_path: str = typer.Option(..., "--flow", help="Path to the flow YAML file"),
    base_url: str = typer.Option(..., "--base-url", help="Base URL (navigate steps with relative URLs are resolved against this)"),
    format: str = typer.Option("text", "--format", help="Output format: text | json"),
    save: bool = typer.Option(False, "--save", "-s", help="Save markdown report + screenshots to output/"),
):
    """Execute a multi-step user flow and emit a step-by-step report."""
    from datetime import datetime
    from pathlib import Path as _Path
    from src.analysis.flow_analyzer import (
        EXIT_TECHNICAL_ERROR, FlowLoadError, execute_flow, load_flow,
    )
    from src.config import settings

    stderr_console = Console(stderr=True)

    try:
        flow_def = load_flow(_Path(flow_path))
    except FlowLoadError as exc:
        stderr_console.print(f"[red]{exc}[/red]")
        raise typer.Exit(EXIT_TECHNICAL_ERROR)

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    flow_output_dir = _Path(settings.output_directory) / f"flow-{ts}"

    with console.status(f"Executing {len(flow_def.steps)} steps..."):
        report = execute_flow(flow_def, base_url, flow_output_dir)

    if format == "json":
        print(report.to_json())
        stderr_console.print(report.to_markdown())
    else:
        console.print(Markdown(report.to_markdown()))

    if save:
        md_path = flow_output_dir / "report.md"
        md_path.write_text(report.to_markdown())
        console.print(f"\nReport saved to {md_path}")
        console.print(f"Screenshots in {flow_output_dir}")

    raise typer.Exit(report.exit_code)


@app.command()
def brand_check(
    url: str = typer.Option(..., "--url", "-u", help="URL to validate"),
    rules_path: Optional[str] = typer.Option(
        None, "--rules", help="Path to rules YAML (default: .design-intel/rules.yaml)",
    ),
    format: str = typer.Option("text", "--format", help="Output format: text | json"),
    device: Optional[str] = typer.Option(None, "--device", help=f"Device preset: {', '.join(DEVICE_PRESETS.keys())}"),
    save: bool = typer.Option(False, "--save", "-s", help="Save report to output/"),
):
    """Validate a URL against project-local brand rules (.design-intel/rules.yaml)."""
    from pathlib import Path as _Path
    from src.analysis.brand_rules import (
        DEFAULT_RULES_PATH, RulesLoadError,
        evaluate_rules, load_rules,
        EXIT_TECHNICAL_ERROR,
    )

    stderr_console = Console(stderr=True)
    resolved_path = _Path(rules_path) if rules_path else DEFAULT_RULES_PATH

    try:
        rules = load_rules(resolved_path)
    except RulesLoadError as exc:
        stderr_console.print(f"[red]{exc}[/red]")
        raise typer.Exit(EXIT_TECHNICAL_ERROR)

    vw, vh = 1440, 900
    if device:
        preset = DEVICE_PRESETS.get(device)
        if preset:
            vw, vh = preset["width"], preset["height"]

    try:
        design_input = process_input(url=url, viewport_width=vw, viewport_height=vh)
    except Exception as exc:
        stderr_console.print(f"[red]Failed to load {url}: {exc}[/red]")
        raise typer.Exit(EXIT_TECHNICAL_ERROR)

    if design_input.dom_data.get("_blocked"):
        stderr_console.print(f"[red]Site blocked automated access: {url}[/red]")
        raise typer.Exit(EXIT_TECHNICAL_ERROR)

    report = evaluate_rules(rules, design_input.dom_data, url, str(resolved_path))

    if format == "json":
        print(report.to_json())
        stderr_console.print(report.to_markdown())
    else:
        console.print(Markdown(report.to_markdown()))

    if save:
        path = save_report(report.to_markdown(), "brand-check")
        console.print(f"\nSaved report to {path}")

    raise typer.Exit(report.exit_code)


@app.command()
def extract_system(
    url: str = typer.Option(..., "--url", "-u", help="URL to extract design system from"),
    output: str = typer.Option("./design-system", "--output", "-o", help="Output directory"),
    format: str = typer.Option("text", "--format", help="Output format: text | json"),
    device: Optional[str] = typer.Option(None, "--device", help=f"Device preset: {', '.join(DEVICE_PRESETS.keys())}"),
):
    """Reverse-engineer a complete design-token system from a live URL."""
    from pathlib import Path as _Path
    from src.analysis.system_extractor import extract_system, write_system_to_dir

    stderr_console = Console(stderr=True)

    vw, vh = 1440, 900
    if device:
        preset = DEVICE_PRESETS.get(device)
        if preset:
            vw, vh = preset["width"], preset["height"]

    try:
        design_input = process_input(url=url, viewport_width=vw, viewport_height=vh)
    except Exception as exc:
        stderr_console.print(f"[red]Failed to load {url}: {exc}[/red]")
        raise typer.Exit(2)

    if design_input.dom_data.get("_blocked"):
        stderr_console.print(f"[red]Site blocked automated access: {url}[/red]")
        raise typer.Exit(2)

    system = extract_system(design_input.dom_data, url)
    result = write_system_to_dir(system, _Path(output))

    if format == "json":
        print(result.to_json())
    else:
        console.print(
            f"\n[green]Extracted {result.strategy} design system[/green] "
            f"from [bold]{url}[/bold]"
        )
        console.print(f"Output: {result.output_dir}\n")
        for cat, n in result.counts.items():
            if n > 0:
                console.print(f"  {cat}: {n}")
        console.print("\nFiles written:")
        for p in result.files_written:
            console.print(f"  - {p.name}")


@app.command()
def monitor(
    url: str = typer.Option(..., "--url", "-u", help="URL to monitor"),
    alert_webhook: Optional[str] = typer.Option(
        None, "--alert-webhook",
        help="Slack-compatible webhook URL. Posts {\"text\": \"...\"} on regression.",
    ),
    trend_window: int = typer.Option(
        10, "--trend-window", help="Number of recent runs to include in the trend table.",
    ),
    score_tolerance: float = typer.Option(
        2.0, "--score-tolerance",
        help="Allowed WCAG score drop before flagging a regression (pp).",
    ),
    format: str = typer.Option("text", "--format", help="Output format: text | json"),
    device: Optional[str] = typer.Option(None, "--device", help=f"Device preset: {', '.join(DEVICE_PRESETS.keys())}"),
    save: bool = typer.Option(False, "--save", "-s", help="Save markdown report to output/"),
):
    """Scheduled monitoring — run audit, diff vs history, alert on regression."""
    from src.analysis.monitoring import build_monitor_report, EXIT_TECHNICAL_ERROR
    from src.analysis.history import get_previous_run, load_history

    stderr_console = Console(stderr=True)

    vw, vh = 1440, 900
    if device:
        preset = DEVICE_PRESETS.get(device)
        if preset:
            vw, vh = preset["width"], preset["height"]

    try:
        design_input = process_input(url=url, viewport_width=vw, viewport_height=vh)
    except Exception as exc:
        stderr_console.print(f"[red]Failed to load {url}: {exc}[/red]")
        raise typer.Exit(EXIT_TECHNICAL_ERROR)

    blocked = design_input.dom_data.get("_blocked", False)
    if blocked:
        stderr_console.print(f"[red]Site blocked automated access: {url}[/red]")
        raise typer.Exit(EXIT_TECHNICAL_ERROR)

    wcag_report = run_wcag_check(design_input.dom_data)
    history = load_history(url)
    previous = get_previous_run(url)

    report = build_monitor_report(
        url=url,
        wcag_report=wcag_report,
        dom_data=design_input.dom_data,
        history=history,
        previous_run=previous,
        trend_window=trend_window,
        score_tolerance=score_tolerance,
        alert_webhook=alert_webhook,
    )

    # Persist this run with fingerprints so the next monitor has a baseline.
    device_name = device or "desktop"
    fingerprint_issues = report.new_violations + [
        {"criterion": fp["criterion"], "element": fp["element"],
         "issue": fp["issue"], "details": fp["issue"]}
        for fp in [
            {"criterion": str(v.get("criterion", "")),
             "element": str(v.get("element", "")),
             "issue": str(v.get("issue", ""))}
            for v in (
                # Reuse the diff report's persistent set — compute inline.
                []
            )
        ]
    ]
    # Simpler: build the full fingerprint set from the current run.
    from src.analysis.monitoring import _fingerprints_now
    current_fps = _fingerprints_now(wcag_report, design_input.dom_data)
    fingerprint_issues = [
        {"criterion": fp.criterion, "element": fp.element,
         "issue": fp.issue, "details": fp.issue}
        for fp in current_fps
    ]
    record = build_run_record(
        url=url, device=device_name,
        pages_crawled=1,
        score=int(report.score),
        wcag_report=wcag_report,
        issues=fingerprint_issues,
    )
    save_run(record)

    if format == "json":
        print(report.to_json())
        stderr_console.print(report.to_markdown())
    else:
        console.print(Markdown(report.to_markdown()))

    if save:
        path = save_report(report.to_markdown(), "monitor")
        console.print(f"\nSaved report to {path}")

    raise typer.Exit(report.exit_code)


@app.command()
def diff(
    before: Optional[str] = typer.Option(None, "--before", help="Before side: URL or local image path"),
    after: str = typer.Option(..., "--after", help="After side: URL or local image path"),
    baseline: Optional[str] = typer.Option(
        None, "--baseline",
        help="If 'history', use the most recent saved run for --after URL as the before baseline.",
    ),
    format: str = typer.Option("text", "--format", help="Output format: text | json"),
    device: Optional[str] = typer.Option(None, "--device", help=f"Device preset: {', '.join(DEVICE_PRESETS.keys())}"),
    save: bool = typer.Option(False, "--save", "-s", help="Save markdown report + visual diff PNG to output/"),
):
    """Before/after diff — compare two designs (URLs, images, or URL vs history)."""
    from datetime import datetime
    from pathlib import Path as _Path
    from src.analysis.diff_analyzer import build_diff_report, EXIT_TECHNICAL_ERROR
    from src.analysis.history import get_previous_run
    from src.config import settings

    stderr_console = Console(stderr=True)

    vw, vh = 1440, 900
    if device:
        preset = DEVICE_PRESETS.get(device)
        if preset:
            vw, vh = preset["width"], preset["height"]

    # Resolve the --baseline history shorthand.
    errors: list[str] = []
    if baseline == "history":
        if not after.startswith(("http://", "https://")):
            stderr_console.print("[red]--baseline history requires --after to be a URL[/red]")
            raise typer.Exit(EXIT_TECHNICAL_ERROR)
        prev = get_previous_run(after)
        if prev is None:
            stderr_console.print(f"[red]No history baseline found for {after}[/red]")
            raise typer.Exit(EXIT_TECHNICAL_ERROR)
        before_label = f"history: {prev.timestamp}"
        # We can't recover DOM data from history, so run fresh WCAG on after-URL
        # against the stored score + issues.
        class _HistWcag:
            score_percentage = prev.wcag_score
            pass_count = prev.wcag_pass
            fail_count = prev.wcag_fail
            warning_count = prev.wcag_warning
            total_violations = prev.total_violations
            results = []
        before_wcag_obj = _HistWcag()
        before_dom_data: dict = {"_history_issues": prev.issues}
        before_image: _Path | None = None
    elif before is None:
        stderr_console.print("[red]--before is required unless --baseline history is set[/red]")
        raise typer.Exit(EXIT_TECHNICAL_ERROR)
    else:
        before_wcag_obj = None
        before_dom_data = {}
        before_image = None
        before_label = before

    # Analyse the "before" side (unless already set by --baseline history).
    if baseline != "history":
        if before.startswith(("http://", "https://")):
            try:
                with console.status(f"Analysing before: {before}..."):
                    before_input = process_input(url=before, viewport_width=vw, viewport_height=vh)
            except Exception as exc:
                errors.append(f"Failed to load before URL: {exc}")
                before_input = None
            if before_input:
                before_wcag_obj = run_wcag_check(before_input.dom_data)
                before_dom_data = before_input.dom_data
                before_image = _Path(before_input.image_path) if before_input.image_path else None
        else:
            path = _Path(before)
            if not path.exists():
                errors.append(f"Before image not found: {before}")
            before_image = path

    # Analyse the "after" side.
    after_wcag_obj = None
    after_dom_data: dict = {}
    after_image: _Path | None = None
    after_label = after
    if after.startswith(("http://", "https://")):
        try:
            with console.status(f"Analysing after: {after}..."):
                after_input = process_input(url=after, viewport_width=vw, viewport_height=vh)
            after_wcag_obj = run_wcag_check(after_input.dom_data)
            after_dom_data = after_input.dom_data
            after_image = _Path(after_input.image_path) if after_input.image_path else None
        except Exception as exc:
            errors.append(f"Failed to load after URL: {exc}")
    else:
        path = _Path(after)
        if not path.exists():
            errors.append(f"After image not found: {after}")
        after_image = path

    # Resolve visual diff output path.
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = _Path(settings.output_directory)
    visual_path = out_dir / f"diff-{ts}.png" if save else (out_dir / f".diff-{ts}-preview.png")

    # Override issue-diff for the history branch — pull stored issues.
    if baseline == "history":
        from src.analysis.ci_runner import ViolationFingerprint
        # Construct fingerprints from stored issues.
        stored_fps = []
        for issue in before_dom_data.get("_history_issues", []):
            stored_fps.append(ViolationFingerprint(
                criterion=str(issue.get("criterion", "")),
                element=str(issue.get("element", "")),
                issue=str(issue.get("details", issue.get("issue", ""))),
            ))

        # Build the report with custom before fingerprints.
        from src.analysis.diff_analyzer import (
            fingerprints_from_side, diff_fingerprints,
            DiffReport, _compute_visual_diff, SCHEMA_VERSION,
            DEFAULT_SCORE_TOLERANCE, EXIT_PASS, EXIT_THRESHOLD_FAILED,
        )
        after_fps = fingerprints_from_side(after_wcag_obj, after_dom_data)
        issue_diff = diff_fingerprints(stored_fps, after_fps)
        score_before = before_wcag_obj.score_percentage if before_wcag_obj else None
        score_after = after_wcag_obj.score_percentage if after_wcag_obj else None
        score_delta = (
            round(score_after - score_before, 1)
            if score_before is not None and score_after is not None else None
        )
        regions = 0
        diff_path_str: Optional[str] = None
        if save and after_image is not None:
            regions, diff_path_str = _compute_visual_diff(
                None, after_image, visual_path,
            )
        if errors:
            exit_code = EXIT_TECHNICAL_ERROR
        elif issue_diff.new:
            exit_code = EXIT_THRESHOLD_FAILED
        elif score_delta is not None and score_delta < -DEFAULT_SCORE_TOLERANCE:
            exit_code = EXIT_THRESHOLD_FAILED
        else:
            exit_code = EXIT_PASS
        report = DiffReport(
            schema_version=SCHEMA_VERSION,
            before_label=before_label, after_label=after_label,
            score_before=score_before, score_after=score_after, score_delta=score_delta,
            issues=issue_diff, visual_diff_path=diff_path_str,
            visual_diff_regions=regions, exit_code=exit_code, errors=errors,
        )
    else:
        report = build_diff_report(
            before_label=before_label, after_label=after_label,
            before_wcag=before_wcag_obj, before_dom=before_dom_data,
            before_image=before_image,
            after_wcag=after_wcag_obj, after_dom=after_dom_data,
            after_image=after_image,
            visual_diff_output=visual_path if save else None,
            errors=errors,
        )

    if format == "json":
        print(report.to_json())
        stderr_console.print(report.to_markdown())
    else:
        console.print(Markdown(report.to_markdown()))

    if save:
        path = save_report(report.to_markdown(), "diff")
        console.print(f"\nSaved report to {path}")
        if report.visual_diff_path:
            console.print(f"Visual diff: {report.visual_diff_path}")

    raise typer.Exit(report.exit_code)


@app.command()
def ci(
    url: str = typer.Option(..., "--url", "-u", help="URL to audit"),
    strict: bool = typer.Option(
        False, "--strict",
        help="Disable pragmatic mode. Fail on any A/AA violation or any score drop. "
             "Default is pragmatic: gates only on NEW critical/serious violations "
             "introduced vs the baseline.",
    ),
    min_score: Optional[float] = typer.Option(
        None, "--min-score",
        help="Hard floor — fail if WCAG score below this percentage (works in both modes).",
    ),
    severity: str = typer.Option(
        "serious", "--severity",
        help="Minimum axe severity that gates in pragmatic mode: "
             "minor | moderate | serious | critical. Default: serious.",
    ),
    score_tolerance: float = typer.Option(
        2.0, "--score-tolerance",
        help="Allowed WCAG score drop in pragmatic mode (percentage points). Default: 2.0.",
    ),
    format: str = typer.Option("text", "--format", help="Output format: text | json"),
    device: Optional[str] = typer.Option(None, "--device", help=f"Device preset: {', '.join(DEVICE_PRESETS.keys())}"),
):
    """CI gate — deterministic audit that fails PRs on design regressions.

    Pragmatic mode (default): grandfathers pre-existing violations and only
    fails the build when a PR introduces new critical/serious issues or drops
    the score by more than the tolerance. Designed to be dropped into CI
    without becoming noise.

    Pass `--strict` to disable pragmatic mode and gate on every A/AA violation
    and any score drop (zero-tolerance behaviour).
    """
    from src.analysis.ci_runner import evaluate, PragmaticConfig
    from src.analysis.history import get_previous_run

    vw, vh = 1440, 900
    if device:
        preset = DEVICE_PRESETS.get(device)
        if preset:
            vw, vh = preset["width"], preset["height"]

    stderr_console = Console(stderr=True)
    try:
        design_input = process_input(url=url, viewport_width=vw, viewport_height=vh)
    except Exception as exc:
        stderr_console.print(f"[red]Failed to load {url}: {exc}[/red]")
        raise typer.Exit(2)

    blocked = design_input.dom_data.get("_blocked", False)
    wcag_report = run_wcag_check(design_input.dom_data) if not blocked else None
    previous = get_previous_run(url)

    cfg = PragmaticConfig(
        enabled=not strict,
        severity_floor=severity,
        score_tolerance=score_tolerance,
    )

    result = evaluate(
        url=url,
        wcag_report=wcag_report,
        dom_data=design_input.dom_data,
        previous_run=previous,
        min_score=min_score,
        pragmatic=cfg,
        strict=strict,
        blocked=blocked,
    )

    # Save this run with per-violation fingerprints so the next run can diff.
    if wcag_report and not blocked:
        device_name = device or "desktop"
        fingerprint_issues = (
            result.new_violations + result.pre_existing_violations
        )
        # RunRecord expects a 'details' field; copy issue→details for fingerprint match.
        for fp in fingerprint_issues:
            fp.setdefault("details", fp.get("issue", ""))
        record = build_run_record(
            url=url, device=device_name,
            pages_crawled=1,
            score=int(result.score),
            wcag_report=wcag_report,
            issues=fingerprint_issues,
        )
        save_run(record)

    if format == "json":
        print(result.to_json())
        stderr_console.print(result.to_human())
    else:
        console.print(result.to_human())

    raise typer.Exit(result.exit_code)


@app.command()
def compare(
    url: str = typer.Option(..., "--url", "-u", help="Your URL"),
    competitor: str = typer.Option(..., "--competitor", "-c", help="Competitor URL"),
    device: Optional[str] = typer.Option(None, "--device", help=f"Device preset: {', '.join(DEVICE_PRESETS.keys())}"),
    save: bool = typer.Option(False, "--save", "-s", help="Save report to output/"),
):
    """Run a side-by-side competitive benchmark against another URL."""
    from src.analysis.competitive import build_comparison

    vw, vh = 1440, 900
    if device:
        preset = DEVICE_PRESETS.get(device)
        if not preset:
            console.print(f"[red]Unknown device: {device}[/red]")
            raise typer.Exit(1)
        vw, vh = preset["width"], preset["height"]
        console.print(f"Using device: {preset['label']} ({vw}x{vh})")

    with console.status(f"Analysing {url}..."):
        your_input = process_input(url=url, viewport_width=vw, viewport_height=vh)
    with console.status(f"Analysing {competitor}..."):
        their_input = process_input(url=competitor, viewport_width=vw, viewport_height=vh)

    with console.status("Running WCAG checks..."):
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

    result = report.to_markdown()
    console.print(Markdown(result))

    if save:
        path = save_report(result, "compare")
        console.print(f"\nSaved to {path}")


@app.command()
def mcp():
    """Launch the MCP server over stdio for editor/agent integration."""
    from src.mcp_server import run
    run()


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
