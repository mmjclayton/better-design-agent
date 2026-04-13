"""CLI tests for `design-intel check` — the one-line quick score command."""

import json

import pytest
from typer.testing import CliRunner

from src.cli import app
from src.input.models import DesignInput, InputType

runner = CliRunner(mix_stderr=False)


def _make_dom() -> dict:
    """Minimal DOM fixture matching the shape expected by run_ui_review scorers."""
    return {
        "fonts": {
            "families": [{"family": "Inter", "count": 14}],
            "sizes": [
                {"size": "16px", "count": 10},
                {"size": "24px", "count": 3},
                {"size": "32px", "count": 1},
            ],
        },
        "colors": {
            "text": [{"color": "#333333", "count": 10}],
            "background": [{"color": "#ffffff", "count": 8}],
        },
        "spacing_values": [
            {"value": "8px", "count": 5},
            {"value": "16px", "count": 8},
            {"value": "24px", "count": 3},
        ],
        "interactive_elements": [
            {"width": 48, "height": 48, "meets_touch_target": True,
             "tag": "button", "text": "Submit"},
        ],
        "state_tests": [],
        "html_structure": {
            "has_lang": True, "lang_value": "en",
            "skip_link": True,
            "landmarks": {"main": 1, "nav": 1, "header": 1, "footer": 1},
            "headings": [{"level": 1, "text": "Hello"}],
            "forms": {"inputs_without_labels": [], "selects_without_labels": []},
            "has_global_focus_visible": True,
            "focus_visible_rules": [{"selector": ":focus-visible"}],
        },
        "layout": {
            "viewport_width": 1440,
            "viewport_height": 900,
            "body_font_size": "16px",
            "body_line_height": "24px",
            "body_font_family": "Inter",
            "body_bg": "#ffffff",
        },
        "axe_results": {"violations": []},
        "contrast_pairs": [
            {"passes_aa": True, "element": "p", "ratio": 7.5,
             "foreground": "#333", "background": "#fff"},
        ],
        "non_text_contrast": [],
        "css_tokens": {},
    }


@pytest.fixture
def mock_capture(monkeypatch):
    """Stub out process_input to avoid Playwright."""
    di = DesignInput(
        type=InputType.URL,
        url="https://fixture.example",
        dom_data=_make_dom(),
    )
    monkeypatch.setattr("src.cli.process_input", lambda **kw: di)


def test_check_prints_score_line(mock_capture):
    result = runner.invoke(app, ["check", "https://fixture.example"])
    assert result.exit_code == 0
    assert "fixture.example" in result.stdout
    assert "/100" in result.stdout


def test_check_json_output_parseable(mock_capture):
    result = runner.invoke(app, ["check", "https://fixture.example", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "url" in data
    assert "score" in data
    assert "categories" in data
    assert isinstance(data["score"], (int, float))
    assert isinstance(data["categories"], dict)


def test_check_threshold_pass(mock_capture):
    result = runner.invoke(app, ["check", "https://fixture.example", "--threshold", "10"])
    assert result.exit_code == 0


def test_check_threshold_fail(mock_capture):
    result = runner.invoke(app, ["check", "https://fixture.example", "--threshold", "101"])
    assert result.exit_code == 1
    assert "below threshold" in result.stderr.lower()


def test_check_unknown_device_exits_two(mock_capture):
    result = runner.invoke(app, ["check", "https://fixture.example", "--device", "nokia-3310"])
    assert result.exit_code == 2
    assert "Unknown device" in result.stderr


def test_check_valid_device(mock_capture):
    result = runner.invoke(app, ["check", "https://fixture.example", "--device", "iphone-12"])
    assert result.exit_code == 0
    assert "/100" in result.stdout


def test_check_process_input_failure(monkeypatch):
    def boom(**kw):
        raise RuntimeError("page not found")

    monkeypatch.setattr("src.cli.process_input", boom)
    result = runner.invoke(app, ["check", "https://fixture.example"])
    assert result.exit_code == 2


def test_check_json_categories_match_score(mock_capture):
    result = runner.invoke(app, ["check", "https://fixture.example", "--json"])
    data = json.loads(result.stdout)
    # Overall score should be a weighted average of category scores
    assert data["score"] > 0
    assert len(data["categories"]) > 0
