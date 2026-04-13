"""Tests for authenticated-session resolution.

The actual Playwright session-capture is integration-tested manually —
this file covers the path-resolution logic that every URL command relies on.
"""


import pytest

from src.input.processor import DEFAULT_AUTH_PATH, resolve_auth_path


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Ensure no stale env vars leak between tests."""
    monkeypatch.delenv("DESIGN_INTEL_NO_AUTH", raising=False)
    monkeypatch.delenv("DESIGN_INTEL_AUTH", raising=False)


def test_no_auth_env_var_disables_detection(tmp_path, monkeypatch):
    auth_file = tmp_path / "auth.json"
    auth_file.write_text("{}")
    monkeypatch.setenv("DESIGN_INTEL_NO_AUTH", "1")
    assert resolve_auth_path(str(auth_file)) is None


def test_explicit_path_used_when_exists(tmp_path):
    auth_file = tmp_path / "custom.json"
    auth_file.write_text("{}")
    assert resolve_auth_path(str(auth_file)) == str(auth_file)


def test_explicit_path_missing_returns_none(tmp_path):
    missing = tmp_path / "missing.json"
    assert resolve_auth_path(str(missing)) is None


def test_env_override_used_when_exists(tmp_path, monkeypatch):
    auth_file = tmp_path / "env-override.json"
    auth_file.write_text("{}")
    monkeypatch.setenv("DESIGN_INTEL_AUTH", str(auth_file))
    assert resolve_auth_path() == str(auth_file)


def test_env_override_missing_returns_none(tmp_path, monkeypatch):
    monkeypatch.setenv("DESIGN_INTEL_AUTH", str(tmp_path / "no.json"))
    assert resolve_auth_path() is None


def test_explicit_path_beats_env_override(tmp_path, monkeypatch):
    env_file = tmp_path / "env.json"
    env_file.write_text("{}")
    explicit_file = tmp_path / "explicit.json"
    explicit_file.write_text("{}")
    monkeypatch.setenv("DESIGN_INTEL_AUTH", str(env_file))
    assert resolve_auth_path(str(explicit_file)) == str(explicit_file)


def test_default_path_used_when_no_explicit_or_env(tmp_path, monkeypatch):
    # Simulate the default by pointing DEFAULT_AUTH_PATH at a temp file.
    fake_default = tmp_path / "auth.json"
    fake_default.write_text("{}")
    monkeypatch.setattr("src.input.processor.DEFAULT_AUTH_PATH", fake_default)
    assert resolve_auth_path() == str(fake_default)


def test_default_path_absent_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "src.input.processor.DEFAULT_AUTH_PATH", tmp_path / "nope.json",
    )
    assert resolve_auth_path() is None


def test_no_auth_env_var_overrides_everything(tmp_path, monkeypatch):
    """DESIGN_INTEL_NO_AUTH wins even when explicit + env + default all exist."""
    env_file = tmp_path / "env.json"
    env_file.write_text("{}")
    explicit_file = tmp_path / "explicit.json"
    explicit_file.write_text("{}")
    fake_default = tmp_path / "default.json"
    fake_default.write_text("{}")
    monkeypatch.setenv("DESIGN_INTEL_NO_AUTH", "1")
    monkeypatch.setenv("DESIGN_INTEL_AUTH", str(env_file))
    monkeypatch.setattr("src.input.processor.DEFAULT_AUTH_PATH", fake_default)
    assert resolve_auth_path(str(explicit_file)) is None


def test_default_auth_path_is_project_local():
    """The default lives in .design-intel/ — matches where history.py writes."""
    assert str(DEFAULT_AUTH_PATH).endswith(".design-intel/auth.json")
