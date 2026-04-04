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


@app.command()
def critique(
    image: Optional[str] = typer.Option(None, "--image", "-i", help="Path to screenshot"),
    url: Optional[str] = typer.Option(None, "--url", "-u", help="URL to critique"),
    describe: Optional[str] = typer.Option(None, "--describe", "-d", help="Text description"),
    context: Optional[str] = typer.Option(None, "--context", "-c", help="Additional context"),
    tone: str = typer.Option("opinionated", "--tone", "-t", help="Tone: opinionated, balanced, gentle"),
    crawl: bool = typer.Option(False, "--crawl", help="Crawl app and critique multiple pages"),
    max_pages: int = typer.Option(10, "--max-pages", help="Max pages to crawl (with --crawl)"),
    save: bool = typer.Option(False, "--save", "-s", help="Save report to output/"),
):
    """Run a design critique on a screenshot, URL, or description."""
    status_msg = "Crawling app..." if crawl else "Processing input..."
    with console.status(status_msg):
        design_input = process_input(
            image=image, url=url, describe=describe,
            crawl=crawl, max_pages=max_pages,
        )

    if crawl and design_input.pages:
        console.print(f"Captured {len(design_input.pages)} pages:")
        for p in design_input.pages:
            console.print(f"  - {p.label} ({p.url})")

    with console.status("Generating critique..."):
        agent = CritiqueAgent(tone=tone)
        result = agent.run(design_input, context=context or "")

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
