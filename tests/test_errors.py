"""Tests for friendly error translation."""

from src.errors import FriendlyError, friendly_error


# ── Error type dispatching ──


def test_playwright_not_installed():
    exc = Exception(
        "Executable doesn't exist at /path/to/chromium. "
        "Please run `playwright install chromium`"
    )
    fe = friendly_error(exc)
    assert "Playwright" in fe.headline
    assert "playwright install chromium" in fe.next_action


def test_navigation_timeout():
    exc = Exception("Timeout 30000ms exceeded during goto")
    fe = friendly_error(exc)
    assert "too long" in fe.headline.lower()
    assert "--image" in fe.next_action


def test_dns_error():
    exc = Exception("net::ERR_NAME_NOT_RESOLVED at https://nope.example")
    fe = friendly_error(exc)
    assert "reach" in fe.headline.lower()


def test_connection_refused():
    exc = Exception("net::ERR_CONNECTION_REFUSED")
    fe = friendly_error(exc)
    assert "refused" in fe.headline.lower()
    assert "dev server" in fe.next_action.lower()


def test_403_blocked():
    exc = Exception("403 Forbidden: Cloudflare challenge")
    fe = friendly_error(exc)
    assert "blocked" in fe.headline.lower()
    assert "--stealth" in fe.next_action


def test_file_not_found():
    exc = FileNotFoundError("No such file: ./nope.png")
    fe = friendly_error(exc)
    assert "File not found" in fe.headline


def test_missing_api_key():
    exc = Exception("ANTHROPIC_API_KEY is not set")
    fe = friendly_error(exc)
    assert "API key" in fe.headline
    assert "ANTHROPIC_API_KEY" in fe.next_action


def test_api_key_invalid():
    exc = Exception("authentication failed: invalid API key")
    fe = friendly_error(exc)
    assert "authentication" in fe.headline.lower() or "api key" in fe.headline.lower()


def test_rate_limit():
    exc = Exception("429 Rate limit exceeded")
    fe = friendly_error(exc)
    assert "rate limit" in fe.headline.lower()


def test_unknown_exception_has_fallback():
    exc = RuntimeError("Something entirely unexpected")
    fe = friendly_error(exc)
    assert "Unexpected" in fe.headline
    assert "RuntimeError" in fe.headline
    assert "open an issue" in fe.next_action.lower()


# ── Structure ──


def test_friendly_error_has_all_fields():
    exc = Exception("a test error")
    fe = friendly_error(exc)
    assert isinstance(fe, FriendlyError)
    assert fe.headline
    assert fe.detail
    assert fe.next_action
    assert fe.original


def test_to_markdown_renders_all_sections():
    exc = Exception("test")
    fe = friendly_error(exc)
    md = fe.to_markdown()
    assert fe.headline in md
    assert "What to do:" in md
    assert "Original error:" in md


def test_long_original_error_truncated():
    long_msg = "x" * 500
    exc = Exception(long_msg)
    fe = friendly_error(exc)
    assert len(fe.original) <= 205  # 200 + ellipsis
    assert fe.original.endswith("…")


def test_multiline_original_error_uses_first_line():
    exc = Exception("first line\nsecond line\nthird line")
    fe = friendly_error(exc)
    assert "first line" in fe.original
    assert "second line" not in fe.original
