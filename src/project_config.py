"""
Project-local config loader.

Reads `.design-intel/config.yaml` from the current directory (walks up
until it finds one) and exposes defaults commands can fall back on when
flags aren't provided.

Schema (all keys optional):

  default_url: https://myapp.com
  default_mode: pragmatic-audit      # for review / autopilot / interactive
  default_device: desktop            # device preset
  default_context: "B2B dashboard"   # injected into LLM critiques
  ci:
    min_score: 70
    score_tolerance: 2.0
    severity: serious
  monitor:
    url: https://myapp.com
    trend_window: 12
    alert_webhook: "$SLACK_WEBHOOK_URL"  # env var reference

Env-var references in string values are expanded at read time.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


CONFIG_RELATIVE = ".design-intel/config.yaml"


@dataclass
class ProjectConfig:
    """Typed view over the project config YAML."""
    default_url: str | None = None
    default_mode: str | None = None
    default_device: str | None = None
    default_context: str | None = None
    ci: dict = field(default_factory=dict)
    monitor: dict = field(default_factory=dict)
    loaded_from: Path | None = None

    @property
    def exists(self) -> bool:
        return self.loaded_from is not None


def find_config_file(start: Path | None = None) -> Path | None:
    """Walk up from `start` (or cwd) looking for .design-intel/config.yaml."""
    current = (start or Path.cwd()).resolve()
    for candidate_root in [current, *current.parents]:
        candidate = candidate_root / CONFIG_RELATIVE
        if candidate.exists():
            return candidate
    return None


def _expand_env(value):
    """Expand $VAR or ${VAR} references inside a scalar string."""
    if isinstance(value, str):
        return os.path.expandvars(value)
    return value


def _expand_env_recursive(obj):
    if isinstance(obj, dict):
        return {k: _expand_env_recursive(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_expand_env_recursive(v) for v in obj]
    return _expand_env(obj)


def load_project_config(path: Path | None = None) -> ProjectConfig:
    """Load the project config. Returns an empty config if none is found."""
    config_path = path if path is not None else find_config_file()
    if config_path is None:
        return ProjectConfig()
    if not config_path.exists():
        return ProjectConfig()
    try:
        raw = yaml.safe_load(config_path.read_text()) or {}
    except Exception:
        return ProjectConfig()

    expanded = _expand_env_recursive(raw)
    if not isinstance(expanded, dict):
        return ProjectConfig()

    return ProjectConfig(
        default_url=expanded.get("default_url"),
        default_mode=expanded.get("default_mode"),
        default_device=expanded.get("default_device"),
        default_context=expanded.get("default_context"),
        ci=expanded.get("ci") or {},
        monitor=expanded.get("monitor") or {},
        loaded_from=config_path,
    )


EXAMPLE_CONFIG = """\
# design-intel project config — commit this to your repo.
# All keys are optional; commands fall back to their built-in defaults
# when a value isn't set here.

# URL to review by default (most commands accept --url to override).
# default_url: https://your-app.com

# Which review mode to use by default.
# Options: pragmatic-audit | pragmatic-critique | deep-critique
# default_mode: pragmatic-audit

# Device preset. Options: iphone-12, iphone-14-pro, iphone-15, iphone-se,
# pixel-7, ipad, ipad-pro, desktop
# default_device: desktop

# Free-text context injected into LLM critiques.
# default_context: "B2B dashboard for finance teams"

# CI-gate defaults (used by `design-intel ci`).
# ci:
#   min_score: 70
#   score_tolerance: 2.0
#   severity: serious

# Scheduled-monitor defaults (used by `design-intel monitor`).
# monitor:
#   url: https://your-app.com
#   trend_window: 12
#   alert_webhook: "$SLACK_WEBHOOK_URL"
"""
