"""Tests for project-local config loading."""

from pathlib import Path

import pytest

from src.project_config import (
    EXAMPLE_CONFIG,
    ProjectConfig,
    find_config_file,
    load_project_config,
)


# ── find_config_file ──


def test_find_returns_none_when_absent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert find_config_file() is None


def test_find_locates_config_in_cwd(tmp_path, monkeypatch):
    config = tmp_path / ".design-intel" / "config.yaml"
    config.parent.mkdir()
    config.write_text("default_url: https://x.com")
    monkeypatch.chdir(tmp_path)
    assert find_config_file() == config


def test_find_walks_up_tree(tmp_path, monkeypatch):
    # Create config at root, cd into deep nested dir
    config = tmp_path / ".design-intel" / "config.yaml"
    config.parent.mkdir()
    config.write_text("default_url: https://x.com")
    deep = tmp_path / "a" / "b" / "c"
    deep.mkdir(parents=True)
    monkeypatch.chdir(deep)
    assert find_config_file() == config


# ── load_project_config ──


def test_load_empty_returns_default_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = load_project_config()
    assert cfg.exists is False
    assert cfg.default_url is None
    assert cfg.default_mode is None


def test_load_populated_config(tmp_path):
    config = tmp_path / ".design-intel" / "config.yaml"
    config.parent.mkdir()
    config.write_text(
        "default_url: https://x.com\n"
        "default_mode: pragmatic-critique\n"
        "default_device: iphone-14-pro\n"
        "default_context: B2B dashboard\n"
    )
    cfg = load_project_config(config)
    assert cfg.exists is True
    assert cfg.default_url == "https://x.com"
    assert cfg.default_mode == "pragmatic-critique"
    assert cfg.default_device == "iphone-14-pro"
    assert cfg.default_context == "B2B dashboard"
    assert cfg.loaded_from == config


def test_load_ci_monitor_subsections(tmp_path):
    config = tmp_path / "config.yaml"
    config.write_text(
        "ci:\n"
        "  min_score: 70\n"
        "  severity: serious\n"
        "monitor:\n"
        "  url: https://x.com\n"
        "  trend_window: 12\n"
    )
    cfg = load_project_config(config)
    assert cfg.ci == {"min_score": 70, "severity": "serious"}
    assert cfg.monitor == {"url": "https://x.com", "trend_window": 12}


def test_load_malformed_yaml_returns_empty_config(tmp_path):
    config = tmp_path / "config.yaml"
    config.write_text("not: [valid: yaml")
    cfg = load_project_config(config)
    # Malformed → silently fall back to empty config, don't crash
    assert cfg.exists is False


def test_load_nonexistent_path_returns_empty_config(tmp_path):
    cfg = load_project_config(tmp_path / "missing.yaml")
    assert cfg.exists is False


def test_load_non_mapping_returns_empty_config(tmp_path):
    config = tmp_path / "config.yaml"
    config.write_text("- just a list\n- not a mapping")
    cfg = load_project_config(config)
    assert cfg.exists is False


# ── Env var expansion ──


def test_env_var_expansion_in_string_values(tmp_path, monkeypatch):
    monkeypatch.setenv("MY_SLACK_URL", "https://hooks.slack.com/services/ABC")
    config = tmp_path / "config.yaml"
    config.write_text(
        'monitor:\n'
        '  alert_webhook: "$MY_SLACK_URL"\n'
    )
    cfg = load_project_config(config)
    assert cfg.monitor["alert_webhook"] == "https://hooks.slack.com/services/ABC"


def test_env_var_expansion_handles_braces(tmp_path, monkeypatch):
    monkeypatch.setenv("HOOK_URL", "https://example.com")
    config = tmp_path / "config.yaml"
    config.write_text('monitor:\n  alert_webhook: "${HOOK_URL}/notify"')
    cfg = load_project_config(config)
    assert cfg.monitor["alert_webhook"] == "https://example.com/notify"


def test_env_var_missing_leaves_reference_literal(tmp_path, monkeypatch):
    monkeypatch.delenv("DEFINITELY_NOT_SET", raising=False)
    config = tmp_path / "config.yaml"
    config.write_text('monitor:\n  alert_webhook: "$DEFINITELY_NOT_SET"')
    cfg = load_project_config(config)
    # os.path.expandvars keeps unexpanded vars as-is
    assert cfg.monitor["alert_webhook"] == "$DEFINITELY_NOT_SET"


# ── Example config content ──


def test_example_config_has_placeholders_for_key_fields():
    assert "default_url" in EXAMPLE_CONFIG
    assert "default_mode" in EXAMPLE_CONFIG
    assert "ci:" in EXAMPLE_CONFIG
    assert "monitor:" in EXAMPLE_CONFIG


def test_example_config_is_valid_yaml_when_uncommented():
    """All lines are either blank, comments, or uncommented yaml."""
    import yaml as _yaml
    # The template ships with everything commented — loading it as YAML
    # should succeed and produce None (all comments) or an empty dict.
    result = _yaml.safe_load(EXAMPLE_CONFIG)
    assert result is None or result == {}


# ── ProjectConfig dataclass ──


def test_project_config_defaults():
    cfg = ProjectConfig()
    assert cfg.default_url is None
    assert cfg.ci == {}
    assert cfg.monitor == {}
    assert cfg.exists is False
