"""Smoke tests for the shim installer script."""

import os
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).parent.parent
SHIM_PATH = PROJECT_ROOT / "scripts" / "install-shim.sh"


def test_shim_script_exists():
    assert SHIM_PATH.exists()


def test_shim_script_is_executable():
    assert os.access(SHIM_PATH, os.X_OK)


def test_shim_script_has_shebang():
    first_line = SHIM_PATH.read_text().split("\n")[0]
    assert first_line.startswith("#!")


def test_shim_script_help_flag_works():
    result = subprocess.run(
        [str(SHIM_PATH), "--help"],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0
    assert "Usage:" in result.stdout
    assert "--prefix" in result.stdout
    assert "--name" in result.stdout


def test_shim_script_rejects_unknown_arg():
    result = subprocess.run(
        [str(SHIM_PATH), "--bogus"],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode != 0
    assert "Unknown argument" in result.stderr


def test_shim_script_rejects_missing_venv(tmp_path):
    """Running the script from a copied location without a .venv fails cleanly."""
    fake_script = tmp_path / "scripts"
    fake_script.mkdir()
    copied = fake_script / "install-shim.sh"
    copied.write_text(SHIM_PATH.read_text())
    copied.chmod(0o755)
    # tmp_path has no .venv/bin/design-intel
    result = subprocess.run(
        [str(copied), "--prefix", str(tmp_path)],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode != 0
    assert "can't find" in result.stderr.lower() or "python3 -m venv" in result.stderr
