"""Tests for login-page detection."""

from src.analysis.login_detection import detect_login_page


def _dom(
    *,
    interactive=None,
    title="",
    headings=None,
    forms_unlabelled=None,
) -> dict:
    return {
        "interactive_elements": interactive or [],
        "html_structure": {
            "title": title,
            "headings": headings or [],
            "forms": {
                "inputs_without_labels": forms_unlabelled or [],
                "selects_without_labels": [],
            },
        },
    }


# ── URL-path signal ──


def test_url_path_login_triggers_signal():
    detection = detect_login_page(_dom(), "https://example.com/login")
    assert detection.is_login_page
    assert "URL path" in detection.signals


def test_url_path_signin_triggers_signal():
    detection = detect_login_page(_dom(), "https://example.com/signin")
    assert detection.is_login_page


def test_url_path_auth_triggers_signal():
    detection = detect_login_page(_dom(), "https://example.com/auth/callback")
    assert detection.is_login_page


def test_url_path_dashboard_does_not_trigger():
    detection = detect_login_page(_dom(), "https://example.com/dashboard")
    assert not detection.is_login_page


# ── Password-field signal ──


def test_password_input_triggers_signal():
    dom = _dom(interactive=[
        {"element": 'input[type="password"]'},
        {"element": "button.submit"},
    ])
    detection = detect_login_page(dom, "https://example.com/")
    assert detection.is_login_page
    assert any("password" in s.lower() for s in detection.signals)


def test_no_password_input_no_signal():
    dom = _dom(interactive=[
        {"element": "input.search"},
        {"element": "button.submit"},
    ])
    detection = detect_login_page(dom, "https://example.com/")
    assert not detection.is_login_page


# ── Page copy signal ──


def test_title_sign_in_triggers_signal():
    dom = _dom(title="Sign in — My App")
    detection = detect_login_page(dom, "https://example.com/")
    assert detection.is_login_page
    assert any("copy" in s.lower() for s in detection.signals)


def test_heading_log_in_triggers_signal():
    dom = _dom(headings=[{"level": 1, "text": "Log in to continue"}])
    detection = detect_login_page(dom, "https://example.com/")
    assert detection.is_login_page


def test_welcome_back_triggers_signal():
    dom = _dom(headings=[{"level": 1, "text": "Welcome back"}])
    detection = detect_login_page(dom, "https://example.com/")
    assert detection.is_login_page


def test_title_dashboard_does_not_trigger():
    dom = _dom(title="Dashboard — My App")
    detection = detect_login_page(dom, "https://example.com/dashboard")
    assert not detection.is_login_page


# ── Confidence ──


def test_two_signals_high_confidence():
    dom = _dom(
        interactive=[
            {"element": 'input[type="password"]'},
            {"element": "input.email"},
            {"element": "button.submit"},
        ],
        title="Sign in",
    )
    detection = detect_login_page(dom, "https://example.com/login")
    assert detection.confidence == "high"
    assert len(detection.signals) >= 2


def test_one_signal_medium_confidence():
    dom = _dom(headings=[{"level": 1, "text": "Log in"}])
    detection = detect_login_page(dom, "https://example.com/")
    assert detection.confidence == "medium"
    assert len(detection.signals) == 1


def test_no_signals_confidence_none():
    dom = _dom(
        interactive=[{"element": "button.cta"}],
        title="Home",
        headings=[{"level": 1, "text": "Welcome home"}],
    )
    # "welcome home" doesn't match "welcome back"
    detection = detect_login_page(dom, "https://example.com/home")
    assert detection.confidence == "none"
    assert not detection.is_login_page


# ── Login-shaped form bolster ──


def test_tight_login_form_adds_signal():
    """A small form with 2-4 inputs including a password adds a signal."""
    dom = _dom(
        interactive=[
            {"element": 'input[type="email"]'},
            {"element": 'input[type="password"]'},
            {"element": "button.submit"},
        ],
    )
    detection = detect_login_page(dom, "https://example.com/")
    assert detection.is_login_page
    # Should have both "password field" and "login-shaped form"
    assert len(detection.signals) >= 2


def test_large_form_with_password_no_bolster():
    """A page with 10 inputs + a password is NOT login-shaped."""
    dom = _dom(
        interactive=[
            {"element": f"input.field-{i}"} for i in range(8)
        ] + [{"element": 'input[type="password"]'}, {"element": "button.save"}],
    )
    detection = detect_login_page(dom, "https://example.com/profile")
    # Still flags as login (password field), but no "login-shaped form" signal.
    assert "login-shaped form" not in " ".join(detection.signals)


# ── to_message ──


def test_to_message_empty_when_not_login():
    detection = detect_login_page(_dom(), "https://example.com/home")
    assert detection.to_message() == ""


def test_to_message_has_call_to_action():
    dom = _dom(
        interactive=[{"element": 'input[type="password"]'}],
        title="Sign in",
    )
    detection = detect_login_page(dom, "https://example.com/login")
    msg = detection.to_message()
    assert "login" in msg.lower()
    assert "design-intel auth" in msg
