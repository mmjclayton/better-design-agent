"""CLI tests for `design-intel doctor` diagnostic command."""

from typer.testing import CliRunner

from src.cli import app

runner = CliRunner(mix_stderr=False)


def test_doctor_runs_without_crash():
    """Doctor should always complete, even with missing deps or keys."""
    result = runner.invoke(app, ["doctor"])
    # Should produce output with checklist items
    combined = result.stdout + result.stderr
    assert "doctor" in combined.lower() or "[ok]" in combined or "[warn]" in combined


def test_doctor_checks_python_version():
    result = runner.invoke(app, ["doctor"])
    combined = result.stdout + result.stderr
    assert "Python" in combined


def test_doctor_checks_playwright():
    result = runner.invoke(app, ["doctor"])
    combined = result.stdout + result.stderr
    assert "Playwright" in combined


def test_doctor_checks_design_intel_version():
    result = runner.invoke(app, ["doctor"])
    combined = result.stdout + result.stderr
    assert "design-intel" in combined
