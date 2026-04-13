"""CLI tests for `design-intel version` and `--version` flag."""

from typer.testing import CliRunner

from src.cli import app

runner = CliRunner(mix_stderr=False)


def test_version_flag():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "design-intel" in result.stdout


def test_version_command():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    combined = result.stdout + result.stderr
    assert "design-intel" in combined
    assert "Python" in combined
    assert "Playwright" in combined
