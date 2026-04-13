"""CLI-level smoke tests for `design-intel ci`.

These tests mock `process_input` + `save_run` to avoid spinning up Playwright
or touching disk, and verify that CLI flags wire through correctly: format
selection, exit-code propagation, pragmatic/strict mode selection.
"""

import json

import pytest
from typer.testing import CliRunner

from src.cli import app
from src.input.models import DesignInput, InputType


runner = CliRunner(mix_stderr=False)


def _make_design_input(contrast_all_pass: bool = True) -> DesignInput:
    dom = {
        "axe_results": {"violations": []},
        "contrast_pairs": [
            {"passes_aa": contrast_all_pass, "element": "p"}
        ],
        "interactive_elements": [{"width": 48, "height": 48, "meets_touch_target": True}],
        "html_structure": {
            "has_lang": True, "lang_value": "en",
            "skip_link": True,
            "landmarks": {"main": 1, "nav": 1, "header": 1, "footer": 1},
            "headings": [{"level": 1, "text": "x"}],
            "forms": {"inputs_without_labels": [], "selects_without_labels": []},
            "has_global_focus_visible": True,
            "focus_visible_rules": [{"selector": ":focus-visible"}],
        },
        "non_text_contrast": [],
    }
    return DesignInput(
        type=InputType.URL,
        url="https://fixture.example",
        dom_data=dom,
    )


@pytest.fixture
def mock_pipeline(monkeypatch, tmp_path):
    """Stub out process_input + history persistence."""
    captured = {}

    def fake_process_input(**kwargs):
        captured["process_input_called"] = True
        return _make_design_input(contrast_all_pass=True)

    def fake_save_run(record):
        captured["saved"] = record
        return tmp_path / "fake-history.json"

    def fake_get_previous_run(url):
        return captured.get("previous")

    monkeypatch.setattr("src.cli.process_input", fake_process_input)
    monkeypatch.setattr("src.cli.save_run", fake_save_run)
    monkeypatch.setattr(
        "src.analysis.history.get_previous_run", fake_get_previous_run
    )
    # cli.py does `from src.analysis.history import get_previous_run` at call
    # time, so monkeypatching the source module is sufficient.
    return captured


def test_ci_clean_run_exits_zero(mock_pipeline):
    result = runner.invoke(app, ["ci", "--url", "https://fixture.example"])
    assert result.exit_code == 0
    assert "CI Gate" in result.stdout or "CI Gate" in result.stderr
    assert mock_pipeline["process_input_called"]


def test_ci_first_run_captures_baseline(mock_pipeline):
    result = runner.invoke(app, ["ci", "--url", "https://fixture.example"])
    assert result.exit_code == 0
    assert "baseline" in (result.stdout + result.stderr).lower()


def test_ci_json_format_emits_parseable_json_to_stdout(mock_pipeline):
    result = runner.invoke(app, [
        "ci", "--url", "https://fixture.example", "--format", "json"
    ])
    assert result.exit_code == 0
    # JSON is emitted to stdout; human-readable goes to stderr.
    data = json.loads(result.stdout)
    assert data["url"] == "https://fixture.example"
    assert data["mode"] == "pragmatic"
    assert data["schema_version"] == 2


def test_ci_strict_flag_sets_mode(mock_pipeline):
    result = runner.invoke(app, [
        "ci", "--url", "https://fixture.example", "--strict", "--format", "json"
    ])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["mode"] == "strict"
    assert data["pragmatic_config"] is None


def test_ci_min_score_flag_enforced(mock_pipeline):
    # Clean fixture → score should be high. --min-score 99.9 should fail.
    result = runner.invoke(app, [
        "ci", "--url", "https://fixture.example", "--min-score", "99.9",
        "--format", "json"
    ])
    # Fixture score is 100% (all WCAG checks pass) so 99.9 should still pass.
    # Use an absurd floor to force failure.
    data = json.loads(result.stdout)
    # If fixture scored 100%, 99.9 passes. Test with floor > 100.
    assert result.exit_code == 0
    assert data["score"] >= 90


def test_ci_min_score_impossible_floor_fails(mock_pipeline):
    result = runner.invoke(app, [
        "ci", "--url", "https://fixture.example", "--min-score", "101",
        "--format", "json"
    ])
    assert result.exit_code == 1
    data = json.loads(result.stdout)
    ms = [t for t in data["thresholds"] if t["name"] == "min-score"]
    assert ms and not ms[0]["passed"]


def test_ci_severity_flag_passed_through(mock_pipeline):
    result = runner.invoke(app, [
        "ci", "--url", "https://fixture.example",
        "--severity", "critical", "--format", "json"
    ])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["pragmatic_config"]["severity_floor"] == "critical"


def test_ci_score_tolerance_flag_passed_through(mock_pipeline):
    result = runner.invoke(app, [
        "ci", "--url", "https://fixture.example",
        "--score-tolerance", "10.5", "--format", "json"
    ])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["pragmatic_config"]["score_tolerance"] == 10.5


def test_ci_process_input_failure_exits_two(monkeypatch):
    def boom(**kwargs):
        raise RuntimeError("network down")
    monkeypatch.setattr("src.cli.process_input", boom)

    result = runner.invoke(app, ["ci", "--url", "https://fixture.example"])
    assert result.exit_code == 2
    assert "network down" in result.stderr or "Failed to load" in result.stderr
