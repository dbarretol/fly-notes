"""Tests for scripts/release_notes.py, which builds the GitHub release notes."""

import importlib.util
import sys
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parent.parent / "scripts" / "release_notes.py"
_spec = importlib.util.spec_from_file_location("release_notes", _PATH)
assert _spec is not None and _spec.loader is not None
release_notes = importlib.util.module_from_spec(_spec)
sys.modules["release_notes"] = release_notes
_spec.loader.exec_module(release_notes)

SHA = "ab" * 32

CHANGELOG = """\
# Changelog

## [Unreleased]

### Added

- Something not released yet. ([#40])

## [0.3.0] - 2026-11-27

Speed release.

### Changed

- Faster list. ([#25], [#26])

## [0.2.0] - 2026-11-26

### Added

- Undo. ([#9])

[Unreleased]: https://github.com/dbarretol/fly-notes/compare/v0.3.0...HEAD
[#25]: https://github.com/dbarretol/fly-notes/issues/25
"""


def test_notes_have_the_section_download_and_compare_link():
    notes = release_notes.release_notes("v0.3.0", SHA, CHANGELOG, "0.3.0")

    assert notes.startswith("Speed release.\n\n### Changed\n\n- Faster list. (#25, #26)\n")
    assert "Undo" not in notes
    assert "Something not released" not in notes
    assert f"SHA-256: `{SHA}`" in notes
    assert notes.endswith(
        "**Full changelog**: https://github.com/dbarretol/fly-notes/compare/v0.2.0...v0.3.0\n"
    )


def test_last_section_stops_at_the_link_definitions():
    notes = release_notes.release_notes("v0.2.0", SHA, CHANGELOG, "0.2.0")

    assert notes.startswith("### Added\n\n- Undo. (#9)\n\n### Download")
    assert "issues/25" not in notes
    assert "Full changelog" not in notes  # no earlier version to compare with


@pytest.mark.parametrize(
    ("tag", "sha", "version", "message"),
    [
        ("v0.3.1", SHA, "0.3.0", "does not match"),
        ("0.3.0", SHA, "0.3.0", "not a vX.Y.Z tag"),
        ("v0.3.0-rc1", SHA, "0.3.0", "not a vX.Y.Z tag"),
        ("v0.3.0", "abc", "0.3.0", "not a SHA-256"),
        ("v0.4.0", SHA, "0.4.0", "no section for 0.4.0"),
    ],
)
def test_rejects_a_release_that_is_not_ready(tag, sha, version, message):
    with pytest.raises(release_notes.ReleaseError, match=message):
        release_notes.release_notes(tag, sha, CHANGELOG, version)


def test_rejects_an_empty_section():
    changelog = "## [0.4.0] - 2026-12-01\n\n## [0.3.0] - 2026-11-27\n\n- x\n"

    with pytest.raises(release_notes.ReleaseError, match="empty"):
        release_notes.release_notes("v0.4.0", SHA, changelog, "0.4.0")


def test_real_changelog_has_a_section_for_the_current_version():
    root = _PATH.parent.parent
    version = release_notes.project_version(root / "pyproject.toml")
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")

    assert release_notes.changelog_section(changelog, version)


def test_main_prints_notes_and_fails_on_a_wrong_tag(capsysbinary):
    version = release_notes.project_version(_PATH.parent.parent / "pyproject.toml")

    assert release_notes.main([f"v{version}", SHA.upper()]) == 0
    out = capsysbinary.readouterr().out.decode("utf-8")
    assert f"SHA-256: `{SHA}`" in out
    assert "\r\n" not in out

    assert release_notes.main(["v99.0.0", SHA]) == 1
    assert release_notes.main([]) == 2
