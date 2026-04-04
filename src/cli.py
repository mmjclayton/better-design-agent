from typing import Optional

import typer
from rich.console import Console
from rich.markdown import Markdown

from src.input.processor import process_input
from src.agents.critique import CritiqueAgent
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
    save: bool = typer.Option(False, "--save", "-s", help="Save report to output/"),
):
    """Run a design critique on a screenshot, URL, or description."""
    # Resolve viewport from device preset or custom values
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

    # Add device context to the critique
    device_context = ""
    if device_label:
        device_context = f"This is a mobile view ({device_label}, {vw}x{vh}px). Evaluate against mobile design patterns: thumb zone placement, bottom navigation, touch targets (44pt iOS / 48dp Android), and responsive layout behaviour."

    combined_context = f"{context or ''}\n{device_context}".strip() if (context or device_context) else ""

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

    with console.status("Generating critique..."):
        agent = CritiqueAgent(tone=tone)
        result = agent.run(design_input, context=combined_context)

    console.print(Markdown(result))

    if save:
        path = save_report(result, "critique")
        console.print(f"\nSaved to {path}")


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
