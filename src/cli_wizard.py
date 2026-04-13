"""
Guided wizard — the default entry when `design-intel` is run with no
subcommand. Walks non-technical users through setup + review without
requiring them to know the flag syntax.

Design principles:
- Plain language. No jargon words like "fingerprint" or "schema_version".
- Detect state before asking. Don't ask "do you have auth?" when
  .design-intel/auth.json is already there.
- Chain sub-commands. If the user picks "review a login-protected app"
  without auth, run auth first automatically.
- Show the equivalent CLI at the end so power users graduate naturally.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.prompt import Prompt


def ask_numbered_choice(message: str, count: int, default: str = "1") -> str:
    """Prompt for a number 1..count. Uses plain input() to bypass Rich's
    Prompt validation, which can mis-read the first keystroke on some
    terminals and print a bogus 'Please select one of the available
    options' message before accepting the real input.
    """
    choices_str = "/".join(str(i) for i in range(1, count + 1))
    prompt_line = f"{message} [{choices_str}] ({default}): "
    while True:
        try:
            raw = input(prompt_line).strip()
        except EOFError:
            return default
        if not raw:
            return default
        if raw.isdigit() and 1 <= int(raw) <= count:
            return raw
        print(f"  Pick a number between 1 and {count}.")

from src.config import settings
from src.input.processor import DEFAULT_AUTH_PATH


console = Console()


# ── State detection ──


@dataclass
class EnvState:
    anthropic_key: bool
    openai_key: bool
    any_llm_key: bool
    auth_session: bool
    output_dir_exists: bool
    past_reports: int


def detect_state() -> EnvState:
    """Check what's set up so the wizard can skip redundant questions."""
    anthropic = bool(settings.anthropic_api_key)
    openai = bool(settings.openai_api_key)
    any_key = any([
        anthropic, openai,
        settings.google_api_key, settings.groq_api_key,
        settings.mistral_api_key, settings.deepseek_api_key,
        settings.together_api_key, settings.openrouter_api_key,
    ])
    output_dir = Path(settings.output_directory)
    past_reports = 0
    if output_dir.exists():
        past_reports = len(
            list(output_dir.glob("critique-*.html"))
            + list(output_dir.glob("critique-*.md"))
        )
    return EnvState(
        anthropic_key=anthropic,
        openai_key=openai,
        any_llm_key=any_key,
        auth_session=DEFAULT_AUTH_PATH.exists(),
        output_dir_exists=output_dir.exists(),
        past_reports=past_reports,
    )


def render_state_summary(state: EnvState) -> str:
    """Plain-English state summary for the welcome screen."""
    lines = []
    if state.any_llm_key:
        lines.append("  [green]✓[/green] AI model access set up")
    else:
        lines.append("  [yellow]✗[/yellow] No AI model key found (add one to .env for LLM features)")
    if state.auth_session:
        lines.append("  [green]✓[/green] Login session saved (will use automatically)")
    else:
        lines.append("  [dim]-[/dim] No login session saved yet")
    if state.past_reports > 0:
        lines.append(f"  [green]✓[/green] {state.past_reports} past report(s) in output/")
    return "\n".join(lines)


# ── Menu definition ──


MENU_OPTIONS = [
    {
        "key": "review",
        "label": "Review a website",
        "description": "quick check or deep design analysis",
    },
    {
        "key": "auth",
        "label": "Set up login access",
        "description": "capture a browser session for private apps",
    },
    {
        "key": "history",
        "label": "View past reports",
        "description": "open a previous critique from output/",
    },
    {
        "key": "learn",
        "label": "Learn what this does",
        "description": "a short tour of the features",
    },
    {
        "key": "quit",
        "label": "Quit",
        "description": "",
    },
]


# ── Review sub-flow ──


REVIEW_DEPTHS = [
    {
        "key": "pragmatic-audit",
        "label": "Quick check",
        "time": "~20 seconds, no AI",
        "detail": "WCAG accessibility + top component issues",
    },
    {
        "key": "pragmatic-critique",
        "label": "Focused review",
        "time": "~60 seconds, uses AI",
        "detail": "top 3-5 findings per area, skips nice-to-haves",
    },
    {
        "key": "deep-critique",
        "label": "Deep analysis",
        "time": "~3 minutes, uses AI",
        "detail": "full 4-agent critique, all findings",
    },
]


def build_review_argv(
    mode: str, target: str, output_format: str = "html-only",
    context: str | None = None,
) -> list[str]:
    """Translate wizard answers into a concrete `review` argv."""
    argv = [
        "review", "--non-interactive",
        "--mode", mode, "--target", target,
        "--format", output_format,
    ]
    if context:
        argv += ["--context", context]
    return argv


# ── Sub-flow handlers ──


def choose_review_depth() -> str:
    """Prompt the user to pick a review depth. Returns the mode key."""
    console.print("[bold]How deep should I look?[/bold]")
    for i, depth in enumerate(REVIEW_DEPTHS, 1):
        console.print(
            f"  {i}. [bold]{depth['label']}[/bold] "
            f"[dim]({depth['time']})[/dim]"
        )
        console.print(f"     [dim]{depth['detail']}[/dim]")
    choice = ask_numbered_choice("  Pick one", len(REVIEW_DEPTHS), default="2")
    return REVIEW_DEPTHS[int(choice) - 1]["key"]


def needs_auth_prompt() -> str:
    """Ask whether the target is login-protected. Returns 'no' | 'has_auth' | 'needs_auth'."""
    console.print("[bold]Is the website behind a login screen?[/bold]")
    console.print("  1. [bold]No[/bold] — it's public")
    console.print("  2. [bold]Yes[/bold], and I already have login access saved")
    console.print("  3. [bold]Yes[/bold] — let's log in together now "
                  "[dim](browser stays open, you press Enter to review each page)[/dim]")
    choice = ask_numbered_choice("  Pick one", 3, default="1")
    return {"1": "no", "2": "has_auth", "3": "needs_auth"}[choice]


def print_equivalent_command(argv: list[str]) -> None:
    """Show the user the direct CLI command for next time."""
    cmd = "design-intel " + " ".join(
        f'"{a}"' if " " in a else a for a in argv
    )
    console.print("\n[dim]Next time, skip the menu:[/dim]")
    console.print(f"[cyan]  {cmd}[/cyan]\n")


# ── Resolver: map wizard answers to a concrete action ──


@dataclass
class WizardAction:
    """A chain of CLI commands the wizard wants to run, plus UX text."""
    commands: list[list[str]]  # each inner list is an argv
    post_message: str = ""


def resolve_review_action(
    url: str, auth_choice: str, mode: str, context: str | None = None,
) -> WizardAction:
    """Compose the command chain for the review flow.

    - auth_choice='no' → single review command
    - auth_choice='has_auth' → single review command (uses saved session)
    - auth_choice='needs_auth' → interactive mode: browser stays open,
      user logs in + navigates + reviews each page
    """
    if auth_choice == "needs_auth":
        # Route to interactive mode — no saved session, no reopening.
        return WizardAction(commands=[[
            "interactive", "--url", url, "--mode", mode,
        ]])
    commands = [
        build_review_argv(mode, url, output_format="html-only", context=context)
    ]
    return WizardAction(commands=commands)


# ── History list helpers ──


def list_recent_reports(max_items: int = 10) -> list[Path]:
    """Return the most recent report files in output/, newest first."""
    out = Path(settings.output_directory)
    if not out.exists():
        return []
    files = [
        *out.glob("critique-*.html"),
        *out.glob("critique-*.md"),
    ]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files[:max_items]


# ── Learn / overview content ──


FEATURE_OVERVIEW = """
[bold]What design-intel can do[/bold]

[bold]Review a website[/bold]
  Critique the design, score it against WCAG accessibility, detect and
  score individual components, suggest improvements. Can run fast (no AI,
  deterministic rules) or deep (AI-driven analysis across 4 specialist
  agents).

[bold]Set up login access[/bold]
  Capture a browser session so all commands can review your app while
  signed in. One-time setup, session reused automatically.

[bold]Export + share[/bold]
  Reports come as terminal output, markdown, HTML (opens in browser), or
  PDF. HTML is the friendliest format for non-technical reviewers.

[bold]Compare + diff[/bold]
  Side-by-side against a competitor (`compare`), before/after when you
  change something (`diff`), or monitor over time with Slack alerts
  (`monitor`).

[bold]Under the hood[/bold]
  Playwright drives a real browser. Axe-core runs 100+ accessibility
  checks. Knowledge library of 39 design principles guides the AI.
  Deterministic checks never hallucinate.
"""


# ── Main wizard loop ──


def print_banner(state: EnvState) -> None:
    console.print()
    console.print("[bold cyan]design-intel[/bold cyan]")
    console.print("Review your website's design quality\n")
    console.print("[bold]I can see:[/bold]")
    console.print(render_state_summary(state))
    console.print()


def print_main_menu() -> str:
    console.print("[bold]What would you like to do?[/bold]")
    for i, option in enumerate(MENU_OPTIONS, 1):
        desc = f" [dim]— {option['description']}[/dim]" if option["description"] else ""
        console.print(f"  {i}. [bold]{option['label']}[/bold]{desc}")
    choice = ask_numbered_choice("  Pick one", len(MENU_OPTIONS), default="1")
    return MENU_OPTIONS[int(choice) - 1]["key"]


def run_learn_flow() -> None:
    console.print(FEATURE_OVERVIEW)
    Prompt.ask("\n[dim]Press enter to go back[/dim]", default="")


def run_history_flow() -> None:
    files = list_recent_reports()
    if not files:
        console.print(
            "[yellow]No past reports found in output/. "
            "Run a review first.[/yellow]"
        )
        return
    console.print("[bold]Recent reports:[/bold]")
    for i, path in enumerate(files, 1):
        console.print(f"  {i}. [cyan]{path.name}[/cyan]")
    choice = Prompt.ask(
        "\n  Open which one? (number, or enter to skip)",
        default="",
    )
    if not choice.strip():
        return
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(files):
            import subprocess
            subprocess.run(["open", str(files[idx])], check=False)
            console.print(f"[green]Opened {files[idx].name}[/green]")
    except (ValueError, IndexError):
        console.print("[yellow]Not a valid number, skipping.[/yellow]")


def prompt_url_input() -> str:
    target = Prompt.ask(
        "[bold]What URL should I look at?[/bold] "
        "(or a local image path)"
    ).strip()
    if not target:
        console.print("[yellow]No URL given. Going back.[/yellow]")
        return ""
    return target


def prompt_context() -> str | None:
    context = Prompt.ask(
        "[bold]Any context about this site?[/bold] "
        "[dim](optional, press enter to skip)[/dim]",
        default="",
    ).strip()
    return context or None


def dispatch_action(action: WizardAction) -> None:
    """Run each command in the action chain against the app."""
    # Import here to avoid circular imports.
    from src.cli import app
    for argv in action.commands:
        try:
            app(argv, standalone_mode=False)
        except SystemExit:
            # typer.Exit propagates as SystemExit — swallow so the wizard
            # continues after a sub-command finishes.
            pass
    if action.post_message:
        console.print(action.post_message)


def run_wizard() -> None:
    """Top-level entry. One pass through the menu, then exits."""
    state = detect_state()
    print_banner(state)

    while True:
        choice = print_main_menu()
        console.print()

        if choice == "quit":
            console.print("[dim]Goodbye.[/dim]")
            return

        if choice == "learn":
            run_learn_flow()
            console.print()
            continue

        if choice == "history":
            run_history_flow()
            console.print()
            continue

        if choice == "auth":
            url = prompt_url_input()
            if not url:
                continue
            dispatch_action(WizardAction(commands=[["auth", "--url", url]]))
            print_equivalent_command(["auth", "--url", url])
            return

        if choice == "review":
            url = prompt_url_input()
            if not url:
                continue
            console.print()

            # Auth path
            auth_choice = "no"
            if url.startswith(("http://", "https://")):
                auth_choice = needs_auth_prompt()
                console.print()

            if auth_choice == "has_auth" and not state.auth_session:
                console.print(
                    "[yellow]No login session found at .design-intel/auth.json. "
                    "Switching to 'set up now'.[/yellow]\n"
                )
                auth_choice = "needs_auth"

            # Depth
            mode = choose_review_depth()
            console.print()

            # Context
            context = prompt_context()
            console.print()

            # Sanity-check: the AI-driven modes require a key
            if mode in ("pragmatic-critique", "deep-critique") and not state.any_llm_key:
                console.print(
                    "[yellow]The AI-driven modes need an LLM API key. "
                    "Add ANTHROPIC_API_KEY to .env and rerun.[/yellow]"
                )
                return

            action = resolve_review_action(url, auth_choice, mode, context)
            console.print("[bold]I'll run these commands for you:[/bold]")
            for argv in action.commands:
                console.print(f"  [cyan]design-intel {' '.join(argv)}[/cyan]")
            console.print()

            dispatch_action(action)
            # Show the equivalent single command for next time (the review one).
            print_equivalent_command(action.commands[-1])
            return
