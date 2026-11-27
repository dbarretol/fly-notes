import tomllib
from pathlib import Path

import fly_notes
from fly_notes.__main__ import main

ROOT = Path(__file__).resolve().parent.parent


def test_version_matches_pyproject():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert fly_notes.__version__ == pyproject["project"]["version"]


def test_console_script_points_at_package_main():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["scripts"]["fly-notes"] == "fly_notes.__main__:main"
    assert callable(main)


def test_build_spec_and_license_are_present():
    assert (ROOT / "FlyNotes.spec").is_file()
    assert (ROOT / "LICENSE").read_text(encoding="utf-8").startswith("MIT License")
