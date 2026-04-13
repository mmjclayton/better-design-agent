"""
Friendly error translation.

Turns exception tracebacks into plain-English messages with concrete
next actions. Non-technical users shouldn't have to read a Python
stack trace to understand "your API key is missing" or "the site
blocked the browser."

Pure functions — caller decides how to render the output.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FriendlyError:
    headline: str  # One-line summary
    detail: str  # What went wrong, plain English
    next_action: str  # The concrete thing to do
    original: str  # Truncated original error for debugging

    def to_markdown(self) -> str:
        return (
            f"**{self.headline}**\n\n"
            f"{self.detail}\n\n"
            f"**What to do:** {self.next_action}\n\n"
            f"_Original error: {self.original}_"
        )


def friendly_error(exc: BaseException) -> FriendlyError:
    """Map any exception to a FriendlyError."""
    msg = str(exc)
    msg_lower = msg.lower()
    exc_type = type(exc).__name__

    # Playwright / browser failures
    if "executable doesn't exist" in msg_lower or "please run" in msg_lower and "install" in msg_lower:
        return FriendlyError(
            headline="Playwright's browser isn't installed",
            detail=(
                "design-intel uses Playwright to drive a real browser, "
                "but the Chromium browser hasn't been downloaded yet."
            ),
            next_action=(
                "Run `.venv/bin/playwright install chromium` in the "
                "design-agent folder, then try your command again."
            ),
            original=_truncate(msg),
        )

    if "timeout" in msg_lower and ("goto" in msg_lower or "navigation" in msg_lower):
        return FriendlyError(
            headline="The page took too long to load",
            detail=(
                "The browser waited 30 seconds for the page to settle, "
                "but it kept loading. This can happen on slow servers, "
                "large SPAs, or pages that never finish network activity."
            ),
            next_action=(
                "Try again. If it keeps failing, try a more specific URL "
                "(e.g. /dashboard instead of /) or take a screenshot "
                "manually and use `--image ./screenshot.png`."
            ),
            original=_truncate(msg),
        )

    if "net::err_name_not_resolved" in msg_lower or "dns" in msg_lower:
        return FriendlyError(
            headline="Can't reach that URL",
            detail=(
                "The address couldn't be resolved. Either the URL is "
                "typed wrong, or your internet connection is down."
            ),
            next_action="Double-check the URL and your internet, then retry.",
            original=_truncate(msg),
        )

    if "net::err_connection_refused" in msg_lower or "err_connection" in msg_lower:
        return FriendlyError(
            headline="The server refused the connection",
            detail=(
                "The URL resolved, but nothing is listening on it. "
                "If it's a local dev server, it might not be running."
            ),
            next_action=(
                "Check that the server is up. For localhost: start your "
                "dev server first (e.g. `npm run dev`)."
            ),
            original=_truncate(msg),
        )

    if "net::err_cert" in msg_lower or "ssl" in msg_lower and "error" in msg_lower:
        return FriendlyError(
            headline="HTTPS certificate problem",
            detail="The site's security certificate isn't valid or trusted.",
            next_action=(
                "If this is a dev server with a self-signed cert, use "
                "`http://` instead of `https://`."
            ),
            original=_truncate(msg),
        )

    # Blocked sites (bot protection)
    if "403" in msg or "blocked" in msg_lower or "cloudflare" in msg_lower:
        return FriendlyError(
            headline="The site blocked the browser",
            detail=(
                "The site uses bot protection (Cloudflare, Akamai, etc.) "
                "and rejected the automated browser."
            ),
            next_action=(
                "Try adding `--stealth` to the command. If that fails, "
                "take a screenshot manually and use `--image <path.png>` "
                "instead of `--url`."
            ),
            original=_truncate(msg),
        )

    # File not found (image input)
    if isinstance(exc, FileNotFoundError) or "no such file" in msg_lower:
        return FriendlyError(
            headline="File not found",
            detail="design-intel couldn't find the file at that path.",
            next_action=(
                "Double-check the path. Relative paths are resolved from "
                "the folder you ran the command in."
            ),
            original=_truncate(msg),
        )

    # Missing API key
    if "api" in msg_lower and "key" in msg_lower and ("missing" in msg_lower or "not set" in msg_lower or "invalid" in msg_lower):
        return FriendlyError(
            headline="LLM API key missing or invalid",
            detail=(
                "The AI-driven commands need an API key for your LLM "
                "provider (Anthropic, OpenAI, etc.)."
            ),
            next_action=(
                "Add `ANTHROPIC_API_KEY=sk-ant-...` to your `.env` file "
                "in the design-agent folder. Get a key at "
                "console.anthropic.com."
            ),
            original=_truncate(msg),
        )

    if "authentication" in msg_lower and "failed" in msg_lower:
        return FriendlyError(
            headline="LLM authentication failed",
            detail="The API key was rejected by the LLM provider.",
            next_action=(
                "Verify the key in .env is correct and still active. "
                "For Anthropic: check console.anthropic.com for the "
                "exact key and that it has credits."
            ),
            original=_truncate(msg),
        )

    # Rate limits
    if "rate limit" in msg_lower or "429" in msg:
        return FriendlyError(
            headline="LLM rate limit hit",
            detail="You've sent too many requests to the LLM in a short window.",
            next_action="Wait a minute and try again, or switch to a different model.",
            original=_truncate(msg),
        )

    # Fallback
    return FriendlyError(
        headline=f"Unexpected error ({exc_type})",
        detail=(
            "Something went wrong that design-intel doesn't have a "
            "specific fix for yet."
        ),
        next_action=(
            "Look at the original error below for clues. If it's not "
            "obvious, open an issue at "
            "github.com/mmjclayton/design-intel with this message."
        ),
        original=_truncate(msg),
    )


def _truncate(msg: str, max_chars: int = 200) -> str:
    first_line = msg.split("\n")[0]
    if len(first_line) <= max_chars:
        return first_line
    return first_line[:max_chars] + "…"
