"""
Borderless‑window utilities: dragging, resizing and a taskbar proxy.

Key fixes over the original
───────────────────────────
* ``is_resizing`` is properly **reset** on ``<ButtonRelease‑1>``.
* The resize handle set now covers **all four edges and four corners**.
* The taskbar‑proxy timing has been made more robust with flag guards.
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional

from .config import config

# Edge identifiers — combinations of these characters
_EDGES = {
    "n", "s", "e", "w",
    "ne", "nw", "se", "sw",
}

# Cursor map per edge
_CURSOR_MAP = {
    "n":  "sb_v_double_arrow",
    "s":  "sb_v_double_arrow",
    "e":  "sb_h_double_arrow",
    "w":  "sb_h_double_arrow",
    "ne": "size_ne_sw",
    "nw": "size_nw_se",
    "se": "size_nw_se",
    "sw": "size_ne_sw",
}


class WindowController:
    """Manages borderless‑window dragging, 8‑direction resizing and taskbar proxy."""

    _GRIP = 6  # px thickness of invisible edge grips

    def __init__(
        self,
        root: tk.Tk,
        on_resize_callback: Optional[Callable[[], None]] = None,
    ) -> None:
        self.root = root
        self.on_resize_callback = on_resize_callback

        # Drag state
        self._offset_x: int = 0
        self._offset_y: int = 0

        # Resize state
        self._is_resizing: bool = False
        self._resize_edge: str = ""
        self._start_x: int = 0
        self._start_y: int = 0
        self._start_w: int = 0
        self._start_h: int = 0
        self._start_win_x: int = 0
        self._start_win_y: int = 0

        # Taskbar proxy
        self._was_minimized: bool = False
        self._proxy_programmatic: bool = False
        self._setup_taskbar_proxy()

    # ── Window dragging ──────────────────────

    def bind_drag(self, widget: tk.Widget) -> None:
        widget.bind("<Button-1>", self._start_move)
        widget.bind("<B1-Motion>", self._do_move)

    def _start_move(self, event: tk.Event) -> None:
        self._offset_x = event.x
        self._offset_y = event.y

    def _do_move(self, event: tk.Event) -> None:
        x = self.root.winfo_x() + event.x - self._offset_x
        y = self.root.winfo_y() + event.y - self._offset_y
        self.root.geometry(f"+{x}+{y}")

    # ── 8‑direction resizing ─────────────────

    def setup_resize_handles(self, bg_color: str) -> None:
        """Create invisible edge/corner grips around the window."""
        g = self._GRIP

        # fmt: off
        specs = [
            # edge   place kwargs
            ("n",  dict(x=0, y=0, relwidth=1.0, height=g)),
            ("s",  dict(x=0, rely=1.0, y=-g, relwidth=1.0, height=g)),
            ("e",  dict(rely=0, relx=1.0, x=-g, width=g, relheight=1.0)),
            ("w",  dict(x=0, y=0, width=g, relheight=1.0)),
            ("ne", dict(relx=1.0, x=-g, y=0, width=g, height=g)),
            ("nw", dict(x=0, y=0, width=g, height=g)),
            ("se", dict(relx=1.0, x=-g, rely=1.0, y=-g, width=g, height=g)),
            ("sw", dict(x=0, rely=1.0, y=-g, width=g, height=g)),
        ]
        # fmt: on

        for edge, place_kw in specs:
            grip = tk.Frame(self.root, bg=bg_color, cursor=_CURSOR_MAP[edge])
            grip.place(**place_kw)
            grip.bind("<Button-1>", lambda e, ed=edge: self._start_resize(ed, e))
            grip.bind("<B1-Motion>", self._do_resize)
            grip.bind("<ButtonRelease-1>", self._stop_resize)

    def _start_resize(self, edge: str, event: tk.Event) -> None:
        self._is_resizing = True
        self._resize_edge = edge
        self._start_x = event.x_root
        self._start_y = event.y_root
        self._start_w = self.root.winfo_width()
        self._start_h = self.root.winfo_height()
        self._start_win_x = self.root.winfo_x()
        self._start_win_y = self.root.winfo_y()

    def _do_resize(self, event: tk.Event) -> None:
        if not self._is_resizing:
            return

        dx = event.x_root - self._start_x
        dy = event.y_root - self._start_y
        edge = self._resize_edge

        new_x = self._start_win_x
        new_y = self._start_win_y
        new_w = self._start_w
        new_h = self._start_h

        if "e" in edge:
            new_w = max(config.min_width, self._start_w + dx)
        if "w" in edge:
            proposed_w = self._start_w - dx
            if proposed_w >= config.min_width:
                new_w = proposed_w
                new_x = self._start_win_x + dx
        if "s" in edge:
            new_h = max(config.min_height, self._start_h + dy)
        if "n" in edge:
            proposed_h = self._start_h - dy
            if proposed_h >= config.min_height:
                new_h = proposed_h
                new_y = self._start_win_y + dy

        self.root.geometry(f"{new_w}x{new_h}+{new_x}+{new_y}")

        if self.on_resize_callback:
            self.on_resize_callback()

    def _stop_resize(self, event: tk.Event) -> None:
        """Reset resize state — critical fix over original code."""
        self._is_resizing = False
        self._resize_edge = ""

    # ── Taskbar proxy (Windows) ──────────────

    def _setup_taskbar_proxy(self) -> None:
        self._proxy = tk.Toplevel(self.root)
        self._proxy.title("Fly Notes")
        self._proxy.geometry("1x1+-32000+-32000")
        self._proxy.resizable(False, False)
        self._proxy.protocol("WM_DELETE_WINDOW", self.root.destroy)
        self._proxy.bind("<Map>", self._proxy_restore)
        self._proxy.bind("<FocusIn>", self._proxy_restore)
        self._proxy.withdraw()

    def _proxy_restore(self, _event: Optional[tk.Event] = None) -> None:
        if self._proxy_programmatic or not self._was_minimized:
            return
        self._was_minimized = False
        self._proxy.withdraw()
        self.root.deiconify()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.lift()
        self.root.focus_force()

    def minimize_window(self) -> None:
        self._was_minimized = True
        self.root.withdraw()
        self._proxy_programmatic = True
        self._proxy.deiconify()
        self._proxy.after_idle(self._proxy.iconify)
        self._proxy.after(300, self._clear_proxy_flag)

    def _clear_proxy_flag(self) -> None:
        self._proxy_programmatic = False