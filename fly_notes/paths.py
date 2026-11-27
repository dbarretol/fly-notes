"""
Resolution of where Fly Notes reads its configuration and stores its data.

Three modes:

- **Source** (``python main.py`` / ``uv run``): everything lives in the
  project root, next to ``main.py`` — unchanged from earlier versions.
- **Installed executable** (PyInstaller build): user data goes to
  ``%APPDATA%\\FlyNotes``. The executable's own directory is not used for
  data because a *onefile* build runs from a temporary extraction folder
  (``sys._MEIPASS``) that is deleted when the app exits.
- **Portable executable**: if a ``config.json`` or ``tasks.json`` sits next
  to ``FlyNotes.exe``, that directory is used instead, so the app can run
  from a USB stick or a synced folder.

Bundled read-only assets (the window icon) always come from
``sys._MEIPASS`` when frozen, and from the project root otherwise.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

APP_DIR_NAME = "FlyNotes"
CONFIG_FILENAME = "config.json"
TASKS_FILENAME = "tasks.json"

_SOURCE_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class AppPaths:
    """Resolved locations for one run of the app."""

    mode: str  # "source" | "installed" | "portable"
    data_dir: Path
    assets_dir: Path

    @property
    def config_file(self) -> Path:
        return self.data_dir / CONFIG_FILENAME

    @property
    def tasks_file(self) -> Path:
        return self.data_dir / TASKS_FILENAME

    @property
    def icon_file(self) -> Path:
        return self.assets_dir / "assets" / "fly_notes.ico"

    def resolve_data_path(self, value: str) -> Path:
        """Resolve a user-supplied path: relative paths are taken from ``data_dir``."""
        path = Path(os.path.expandvars(os.path.expanduser(value)))
        return path if path.is_absolute() else self.data_dir / path


def resolve_paths(
    *,
    frozen: bool,
    executable: Path,
    meipass: Path | None,
    appdata: str | None,
    home: Path,
    source_root: Path = _SOURCE_ROOT,
) -> AppPaths:
    """Pure path resolution, with every environment input passed explicitly."""
    if not frozen:
        return AppPaths(mode="source", data_dir=source_root, assets_dir=source_root)

    exe_dir = executable.resolve().parent
    assets_dir = meipass if meipass is not None else exe_dir

    if (exe_dir / CONFIG_FILENAME).exists() or (exe_dir / TASKS_FILENAME).exists():
        return AppPaths(mode="portable", data_dir=exe_dir, assets_dir=assets_dir)

    base = Path(appdata) if appdata else home / "AppData" / "Roaming"
    return AppPaths(mode="installed", data_dir=base / APP_DIR_NAME, assets_dir=assets_dir)


def current_paths() -> AppPaths:
    """Resolve paths for the running process."""
    meipass = getattr(sys, "_MEIPASS", None)
    return resolve_paths(
        frozen=bool(getattr(sys, "frozen", False)),
        executable=Path(sys.executable),
        meipass=Path(meipass) if meipass else None,
        appdata=os.environ.get("APPDATA"),
        home=Path.home(),
    )


APP_PATHS = current_paths()
