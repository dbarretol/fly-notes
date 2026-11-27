"""
Remembered window state — no Tkinter dependency.

The window's size and position, and whether it stays on top, are stored in
``state.json`` next to the tasks file when the app closes. The geometry is
restored on the next start unless the saved spot is no longer reachable on
any connected monitor (e.g. a laptop undocked from an external screen).
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

STATE_FILENAME = "state.json"

# How much of the window's top edge (where the drag handle lives) must be on
# a monitor for the saved position to count as reachable.
MIN_VISIBLE_WIDTH = 80
MIN_VISIBLE_HEIGHT = 20

_TK_GEOMETRY = re.compile(r"^(\d+)x(\d+)([+-]-?\d+)([+-]-?\d+)$")


@dataclass(frozen=True)
class Rect:
    left: int
    top: int
    right: int
    bottom: int


@dataclass(frozen=True)
class WindowGeometry:
    width: int
    height: int
    x: int
    y: int

    def to_tk(self) -> str:
        return f"{self.width}x{self.height}{self.x:+d}{self.y:+d}"

    @classmethod
    def from_tk(cls, geometry: str) -> WindowGeometry:
        """Parse a Tk geometry string such as ``"320x480+100+-20"``."""
        match = _TK_GEOMETRY.match(geometry.strip())
        if not match:
            raise ValueError(f"Not a Tk geometry string: {geometry!r}")
        w, h, x, y = match.groups()
        # Tk writes a negative offset as "+-20"; int() needs the sign folded.
        return cls(int(w), int(h), int(x.replace("+-", "-")), int(y.replace("+-", "-")))


def state_file_for(tasks_file: str) -> str:
    """``state.json`` in the same folder as *tasks_file*."""
    return os.path.join(os.path.dirname(os.path.abspath(tasks_file)), STATE_FILENAME)


def load_geometry(path: str) -> WindowGeometry | None:
    """Return the saved geometry, or ``None`` if absent or unreadable."""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        window = data["window"]
        values = [window[k] for k in ("width", "height", "x", "y")]
    except FileNotFoundError:
        return None
    except (OSError, ValueError, KeyError, TypeError):
        logger.warning("Ignoring unreadable window state in %s", path, exc_info=True)
        return None
    if not all(isinstance(v, int) and not isinstance(v, bool) for v in values):
        logger.warning("Ignoring window state with non-integer values in %s", path)
        return None
    geometry = WindowGeometry(*values)
    if geometry.width <= 0 or geometry.height <= 0:
        return None
    return geometry


def save_geometry(path: str, geometry: WindowGeometry) -> None:
    """Write *geometry* atomically, keeping any other keys already in the file."""
    _update_state(
        path,
        "window",
        {"width": geometry.width, "height": geometry.height, "x": geometry.x, "y": geometry.y},
    )


def load_always_on_top(path: str) -> bool | None:
    """The saved always-on-top choice, or ``None`` if absent or invalid."""
    value = _read_state(path).get("always_on_top")
    return value if isinstance(value, bool) else None


def save_always_on_top(path: str, always_on_top: bool) -> None:
    """Write the always-on-top choice, keeping any other keys already in the file."""
    _update_state(path, "always_on_top", bool(always_on_top))


def _read_state(path: str) -> dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _update_state(path: str, key: str, value: Any) -> None:
    data = _read_state(path)
    data[key] = value

    dir_name = os.path.dirname(path) or "."
    os.makedirs(dir_name, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        os.replace(tmp_path, path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def is_reachable(geometry: WindowGeometry, monitors: list[Rect]) -> bool:
    """True if enough of the window's top edge lies on one monitor to grab it."""
    need_w = min(MIN_VISIBLE_WIDTH, geometry.width)
    need_h = min(MIN_VISIBLE_HEIGHT, geometry.height)
    left, top = geometry.x, geometry.y
    right, bottom = left + geometry.width, top + need_h
    for m in monitors:
        overlap_w = min(right, m.right) - max(left, m.left)
        overlap_h = min(bottom, m.bottom) - max(top, m.top)
        if overlap_w >= need_w and overlap_h >= need_h:
            return True
    return False


def choose_geometry(
    saved: WindowGeometry | None,
    default: WindowGeometry,
    monitors: list[Rect],
    min_width: int,
    min_height: int,
) -> WindowGeometry:
    """The saved geometry (with at least the minimum size) if reachable, else *default*."""
    if saved is None:
        return default
    restored = WindowGeometry(
        max(min_width, saved.width), max(min_height, saved.height), saved.x, saved.y
    )
    if not is_reachable(restored, monitors):
        logger.info("Saved window position %s is off-screen; using the default", saved)
        return default
    return restored


def monitor_work_areas() -> list[Rect]:
    """Work areas (screen minus taskbar) of every connected monitor.

    Windows only; returns an empty list elsewhere or if the query fails, so
    the caller can fall back to the primary screen size from Tk.
    """
    if sys.platform != "win32":
        return []
    try:
        import ctypes  # noqa: PLC0415 -- Windows-only, inside the guard
        from ctypes import wintypes  # noqa: PLC0415 -- Windows-only, inside the guard

        class MONITORINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT),
                ("dwFlags", wintypes.DWORD),
            ]

        user32 = ctypes.windll.user32
        areas: list[Rect] = []

        monitor_enum_proc = ctypes.WINFUNCTYPE(
            wintypes.BOOL,
            wintypes.HMONITOR,
            wintypes.HDC,
            ctypes.POINTER(wintypes.RECT),
            wintypes.LPARAM,
        )

        def _collect(hmonitor, _hdc, _rect, _data):
            info = MONITORINFO()
            info.cbSize = ctypes.sizeof(MONITORINFO)
            if user32.GetMonitorInfoW(hmonitor, ctypes.byref(info)):
                r = info.rcWork
                areas.append(Rect(r.left, r.top, r.right, r.bottom))
            return True

        if not user32.EnumDisplayMonitors(None, None, monitor_enum_proc(_collect), 0):
            return []
        return areas
    except Exception:
        logger.warning("Could not list monitors", exc_info=True)
        return []
