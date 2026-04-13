"""
Login-page detection.

After a URL capture, we want to warn the user if they've landed on a login
screen without realising it — otherwise their critique is just reviewing
the login form, not the app.

Pure function, no LLM, no network. Uses three deterministic signals:

  1. URL path contains /login, /signin, /auth, /sso, etc.
  2. DOM has an <input type="password">
  3. Page title or main heading contains common login-page copy

Two or more signals → definitely a login page. One signal → probably.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse


LOGIN_PATH_MARKERS = (
    "/login", "/signin", "/sign-in", "/signup", "/sign-up",
    "/auth/", "/sso/", "/authenticate",
)

LOGIN_COPY_MARKERS = (
    "sign in", "log in", "login", "sign up", "welcome back",
    "enter your password", "enter your email",
)


@dataclass
class LoginDetection:
    is_login_page: bool
    signals: list[str]
    confidence: str  # "high" | "medium" | "none"

    def to_message(self) -> str:
        if not self.is_login_page:
            return ""
        reason = " + ".join(self.signals)
        return (
            f"This looks like a login screen ({reason}). "
            "Your review will only cover the login page itself, not the "
            "app behind it. To review the authenticated app: close this, "
            "run `design-intel auth --url <your-url>`, log in, close the "
            "browser, then re-run your review."
        )


def detect_login_page(
    dom_data: dict,
    url: str,
    page_text: str = "",
) -> LoginDetection:
    """Inspect a captured page; return a detection verdict."""
    signals: list[str] = []

    # Signal 1: URL path
    path = (urlparse(url).path or "").lower()
    if any(marker in path for marker in LOGIN_PATH_MARKERS):
        signals.append("URL path")

    # Signal 2: password input present
    interactive = dom_data.get("interactive_elements", []) or []
    if any(
        "password" in str(el.get("element", "")).lower()
        for el in interactive
    ):
        signals.append("password field")

    # Signal 3: title / heading copy
    html = dom_data.get("html_structure", {}) or {}
    title = str(html.get("title", "") or "").lower()
    headings = html.get("headings", []) or []
    heading_text = " ".join(
        str(h.get("text", "") or "") for h in headings
    ).lower()
    combined = f"{title} {heading_text}"
    copy_matches = [m for m in LOGIN_COPY_MARKERS if m in combined]
    if copy_matches:
        signals.append(f"page copy: '{copy_matches[0]}'")

    # Signal 4 (weak): small page with a form-only body (helps SPAs where
    # the URL doesn't contain /login but the landing page is a login form)
    forms = html.get("forms", {}) or {}
    total_inputs = (
        len(forms.get("inputs_without_labels", []))
        + sum(
            1 for el in interactive
            if str(el.get("element", "")).startswith(("input", "select"))
        )
    )
    button_count = sum(
        1 for el in interactive
        if str(el.get("element", "")).startswith("button")
    )
    if total_inputs <= 4 and button_count <= 3 and total_inputs >= 2 and "password field" in signals:
        # Tight login form — bolsters the password-field signal.
        signals.append("login-shaped form")

    # Confidence: 2+ signals = high, 1 = medium, 0 = none.
    count = len(signals)
    if count >= 2:
        confidence = "high"
    elif count == 1:
        confidence = "medium"
    else:
        confidence = "none"

    return LoginDetection(
        is_login_page=(count >= 1),
        signals=signals,
        confidence=confidence,
    )
