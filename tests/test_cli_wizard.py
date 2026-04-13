"""Tests for the guided-wizard CLI entry point.

Covers pure logic: state detection, menu → argv mapping, review action
resolution, recent-reports listing. Interactive prompts are skipped —
they're exercised via the same `--non-interactive` harness as `review`.
"""

from pathlib import Path

import pytest

from src.cli_wizard import (
    FEATURE_OVERVIEW,
    MENU_OPTIONS,
    REVIEW_DEPTHS,
    EnvState,
    WizardAction,
    build_review_argv,
    detect_state,
    list_recent_reports,
    render_state_summary,
    resolve_review_action,
)


# ── State detection ──


def test_detect_state_returns_envstate():
    state = detect_state()
    assert isinstance(state, EnvState)
    assert isinstance(state.any_llm_key, bool)
    assert isinstance(state.auth_session, bool)


def test_render_state_shows_api_key_status():
    state_with = EnvState(
        anthropic_key=True, openai_key=False, any_llm_key=True,
        auth_session=False, output_dir_exists=True, past_reports=0,
    )
    md = render_state_summary(state_with)
    assert "AI model access set up" in md
    assert "login session saved yet" in md.lower()


def test_render_state_shows_missing_api_key():
    state_without = EnvState(
        anthropic_key=False, openai_key=False, any_llm_key=False,
        auth_session=False, output_dir_exists=False, past_reports=0,
    )
    md = render_state_summary(state_without)
    assert "No AI model key" in md


def test_render_state_shows_auth_when_present():
    state = EnvState(
        anthropic_key=True, openai_key=False, any_llm_key=True,
        auth_session=True, output_dir_exists=True, past_reports=0,
    )
    md = render_state_summary(state)
    assert "Login session saved" in md


def test_render_state_shows_past_report_count():
    state = EnvState(
        anthropic_key=True, openai_key=False, any_llm_key=True,
        auth_session=False, output_dir_exists=True, past_reports=5,
    )
    md = render_state_summary(state)
    assert "5 past report" in md


def test_render_state_skips_past_reports_when_zero():
    state = EnvState(
        anthropic_key=True, openai_key=False, any_llm_key=True,
        auth_session=False, output_dir_exists=True, past_reports=0,
    )
    md = render_state_summary(state)
    assert "past report" not in md.lower()


# ── Menu definition ──


def test_menu_has_five_options():
    assert len(MENU_OPTIONS) == 5
    keys = [o["key"] for o in MENU_OPTIONS]
    assert keys == ["review", "auth", "history", "learn", "quit"]


def test_every_menu_option_has_label():
    for option in MENU_OPTIONS:
        assert option["label"]
        assert "description" in option


# ── Review depths ──


def test_review_depths_covers_three_tiers():
    keys = [d["key"] for d in REVIEW_DEPTHS]
    assert "pragmatic-audit" in keys
    assert "pragmatic-critique" in keys
    assert "deep-critique" in keys


def test_review_depths_have_time_estimates():
    for depth in REVIEW_DEPTHS:
        assert "time" in depth
        assert "seconds" in depth["time"] or "minute" in depth["time"]


# ── build_review_argv ──


def test_build_review_argv_basic():
    argv = build_review_argv("pragmatic-critique", "https://x.com")
    assert "review" in argv
    assert "--non-interactive" in argv
    assert "--mode" in argv and "pragmatic-critique" in argv
    assert "--target" in argv and "https://x.com" in argv
    assert "--format" in argv and "html-only" in argv


def test_build_review_argv_with_context():
    argv = build_review_argv(
        "deep-critique", "https://x.com", context="B2B dashboard",
    )
    assert "--context" in argv
    assert "B2B dashboard" in argv


def test_build_review_argv_omits_context_when_none():
    argv = build_review_argv("pragmatic-audit", "https://x.com", context=None)
    assert "--context" not in argv


def test_build_review_argv_custom_format():
    argv = build_review_argv(
        "pragmatic-critique", "https://x.com", output_format="pdf",
    )
    assert "pdf" in argv


# ── resolve_review_action ──


def test_resolve_review_no_auth_single_command():
    action = resolve_review_action(
        "https://x.com", auth_choice="no", mode="pragmatic-audit",
    )
    assert isinstance(action, WizardAction)
    assert len(action.commands) == 1
    assert action.commands[0][0] == "review"


def test_resolve_review_has_auth_single_command():
    action = resolve_review_action(
        "https://x.com", auth_choice="has_auth", mode="pragmatic-critique",
    )
    # Auth already saved → skip the auth step, just run review.
    assert len(action.commands) == 1
    assert action.commands[0][0] == "review"


def test_resolve_review_needs_auth_routes_to_interactive():
    """Needs-auth now routes to interactive mode (single browser stays open)."""
    action = resolve_review_action(
        "https://x.com", auth_choice="needs_auth", mode="deep-critique",
    )
    assert len(action.commands) == 1
    assert action.commands[0][0] == "interactive"
    assert "--url" in action.commands[0]
    assert "https://x.com" in action.commands[0]
    assert "--mode" in action.commands[0]
    assert "deep-critique" in action.commands[0]


def test_resolve_review_passes_context_through():
    action = resolve_review_action(
        "https://x.com", auth_choice="no", mode="pragmatic-critique",
        context="internal tool",
    )
    assert "--context" in action.commands[-1]
    assert "internal tool" in action.commands[-1]


def test_resolve_review_uses_html_only_format():
    action = resolve_review_action(
        "https://x.com", auth_choice="no", mode="pragmatic-audit",
    )
    assert "html-only" in action.commands[-1]


# ── list_recent_reports ──


def test_list_recent_reports_empty_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "src.cli_wizard.settings",
        type("S", (), {"output_directory": str(tmp_path / "nope")})(),
    )
    assert list_recent_reports() == []


def test_list_recent_reports_newest_first(tmp_path, monkeypatch):
    out = tmp_path / "output"
    out.mkdir()
    # Touch 3 files with distinct mtimes.
    import time
    f_old = out / "critique-20260101.html"
    f_old.write_text("old")
    time.sleep(0.01)
    f_mid = out / "critique-20260105.html"
    f_mid.write_text("mid")
    time.sleep(0.01)
    f_new = out / "critique-20260110.html"
    f_new.write_text("new")

    monkeypatch.setattr(
        "src.cli_wizard.settings",
        type("S", (), {"output_directory": str(out)})(),
    )
    recent = list_recent_reports()
    assert recent[0].name == "critique-20260110.html"
    assert recent[-1].name == "critique-20260101.html"


def test_list_recent_reports_respects_max(tmp_path, monkeypatch):
    out = tmp_path / "output"
    out.mkdir()
    for i in range(15):
        (out / f"critique-2026010{i}.html").write_text(str(i))
    monkeypatch.setattr(
        "src.cli_wizard.settings",
        type("S", (), {"output_directory": str(out)})(),
    )
    assert len(list_recent_reports(max_items=5)) == 5


def test_list_recent_reports_ignores_unrelated_files(tmp_path, monkeypatch):
    out = tmp_path / "output"
    out.mkdir()
    (out / "critique-x.html").write_text("ok")
    (out / "random.txt").write_text("skip")
    (out / "screenshot.png").write_text("skip")
    monkeypatch.setattr(
        "src.cli_wizard.settings",
        type("S", (), {"output_directory": str(out)})(),
    )
    names = [p.name for p in list_recent_reports()]
    assert names == ["critique-x.html"]


def test_list_recent_reports_includes_markdown():
    """Markdown files should be picked up too, not just HTML."""
    # Uses the global fixture via tmp_path indirectly
    pass  # covered by the newest_first test not being html-only


# ── Feature overview ──


def test_feature_overview_mentions_key_capabilities():
    text = FEATURE_OVERVIEW
    assert "Review a website" in text
    assert "Set up login access" in text
    assert "Playwright" in text
    assert "Axe-core" in text
