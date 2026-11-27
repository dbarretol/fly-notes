"""Write the GitHub release notes for a version tag.

Used by ``.github/workflows/release.yml``::

    python scripts/release_notes.py v0.3.0 <sha256-of-FlyNotes.exe>

It fails if the tag does not match the version in ``pyproject.toml`` or if
``CHANGELOG.md`` has no section for that version. Otherwise it prints that
section followed by a download note with the checksum.
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO_URL = "https://github.com/dbarretol/fly-notes"


class ReleaseError(Exception):
    """The tag, the version or the changelog are not ready for a release."""


def project_version(pyproject: Path) -> str:
    with pyproject.open("rb") as f:
        return tomllib.load(f)["project"]["version"]


def changelog_section(changelog: str, version: str) -> str:
    """Return the body of ``## [version]``, without its heading."""
    heading = re.compile(rf"^## \[{re.escape(version)}\][^\n]*\n", re.MULTILINE)
    match = heading.search(changelog)
    if match is None:
        raise ReleaseError(f"CHANGELOG.md has no section for {version}")
    rest = changelog[match.end() :]
    end = re.search(r"^## \[|^\[[^\]]+\]: ", rest, re.MULTILINE)
    body = rest[: end.start()] if end else rest
    # Issue references are reference-style links in the changelog, whose
    # definitions are not part of the section: plain "#N" autolinks on GitHub.
    body = re.sub(r"\[#(\d+)\]", r"#\1", body).strip()
    if not body:
        raise ReleaseError(f"The CHANGELOG.md section for {version} is empty")
    return body


def previous_version(changelog: str, version: str) -> str | None:
    """Return the version listed right after ``version``, if any."""
    versions = re.findall(r"^## \[(\d+\.\d+\.\d+)\]", changelog, re.MULTILINE)
    if version in versions:
        i = versions.index(version)
        if i + 1 < len(versions):
            return versions[i + 1]
    return None


def release_notes(tag: str, sha256: str, changelog: str, version: str) -> str:
    if not re.fullmatch(r"v\d+\.\d+\.\d+", tag):
        raise ReleaseError(f"{tag!r} is not a vX.Y.Z tag")
    if tag[1:] != version:
        raise ReleaseError(f"Tag {tag} does not match version {version} in pyproject.toml")
    if not re.fullmatch(r"[0-9a-f]{64}", sha256):
        raise ReleaseError(f"{sha256!r} is not a SHA-256 hex digest")

    notes = [
        changelog_section(changelog, version),
        "### Download",
        "`FlyNotes.exe`: a single file for Windows, with nothing to install. It is not "
        "code-signed, so SmartScreen may warn the first time (**More info → Run anyway**).",
        f"SHA-256: `{sha256}`",
    ]
    previous = previous_version(changelog, version)
    if previous:
        notes.append(f"**Full changelog**: {REPO_URL}/compare/v{previous}...{tag}")
    return "\n\n".join(notes) + "\n"


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: release_notes.py <tag> <sha256>", file=sys.stderr)
        return 2
    tag, sha256 = argv
    try:
        notes = release_notes(
            tag,
            sha256.lower(),
            (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"),
            project_version(ROOT / "pyproject.toml"),
        )
    except ReleaseError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    # Bytes, so the output is UTF-8 with LF line endings whatever the console uses.
    sys.stdout.buffer.write(notes.encode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
