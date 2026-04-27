"""
Borderless-window controller — dragging, 8-direction resizing, taskbar proxy.

Handles all platform-specific quirks for a frameless, always-on-top
Tk window that still appears in the OS taskbar.
"""

from __future__ import annotations

import sys
import tkinter as tk
from typing import Callable, Optional

from .config import config

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

# Edge → (dx_sign_for_width, dy_sign_for_height, moves_x, moves_y)
_EDGE_EFFECTS = {
    "n":  (False, True,  False, True),
    "s":  (False, True,  False, False),
    "e":  (True,  False, False, False),
    "w":  (True,  False, True,  False),
    "ne": (True,  True,  False, True),
    "nw": (True,  True,  True,  True),
    "se": (True,  True,  False, False),
    "sw": (True,  True,  True,  False),
}


class WindowController:
    """Manages borderless-window dragging, 8-direction resizing and taskbar proxy.

    Usage::

        ctrl = WindowController(root, on_resize_callback=my_callback)
        ctrl.bind_drag(header_widget)
        ctrl.setup_resize_handles(bg_color)
    """

    _GRIP = 6

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

        # Resize grip widgets (tracked for cleanup)
        self._grip_widgets: list[tk.Frame] = []

        # Taskbar proxy
        self._was_minimized: bool = False
        self._proxy_programmatic: bool = False
        self._proxy: Optional[tk.Toplevel] = None
        self._setup_taskbar_proxy()

    # ── Dragging ─────────────────────────────

    def bind_drag(self, widget: tk.Widget) -> None:
        """Make *widget* a drag handle for the root window."""
        widget.bind("<Button-1>", self._start_move)
        widget.bind("<B1-Motion>", self._do_move)

    def _start_move(self, event: tk.Event) -> None:
        self._offset_x = event.x
        self._offset_y = event.y

    def _do_move(self, event: tk.Event) -> None:
        x = self.root.winfo_x() + event.x - self._offset_x
        y = self.root.winfo_y() + event.y - self._offset_y
        self.root.geometry(f"+{x}+{y}")

    # ── 8-direction resizing ─────────────────

    def setup_resize_handles(self, bg_color: str) -> None:
        """Create invisible grip frames around the window edges."""
        # Destroy old grips if re-called
        for grip in self._grip_widgets:
            try:
                grip.destroy()
            except tk.TclError:
                pass
        self._grip_widgets.clear()

        g = self._GRIP
        specs = [
            ("n",  dict(x=0, y=0, relwidth=1.0, height=g)),
            ("s",  dict(x=0, rely=1.0, y=-g, relwidth=1.0, height=g)),
            ("e",  dict(rely=0, relx=1.0, x=-g, width=g, relheight=1.0)),
            ("w",  dict(x=0, y=0, width=g, relheight=1.0)),
            ("ne", dict(relx=1.0, x=-g, y=0, width=g, height=g)),
            ("nw", dict(x=0, y=0, width=g, height=g)),
            ("se", dict(relx=1.0, x=-g, rely=1.0, y=-g, width=g, height=g)),
            ("sw", dict(x=0, rely=1.0, y=-g, width=g, height=g)),
        ]
        for edge, place_kw in specs:
            grip = tk.Frame(self.root, bg=bg_color, cursor=_CURSOR_MAP[edge])
            grip.place(**place_kw)
            grip.bind("<Button-1>", lambda e, ed=edge: self._start_resize(ed, e))
            grip.bind("<B1-Motion>", self._do_resize)
            grip.bind("<ButtonRelease-1>", self._stop_resize)
            self._grip_widgets.append(grip)

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

        new_x, new_y = self._start_win_x, self._start_win_y
        new_w, new_h = self._start_w, self._start_h

        affects_w, affects_h, moves_x, moves_y = _EDGE_EFFECTS[edge]

        if affects_w:
            if moves_x:
                # West edge: growing = negative dx
                proposed_w = self._start_w - dx
                if proposed_w >= config.min_width:
                    new_w = proposed_w
                    new_x = self._start_win_x + dx
                else:
                    new_w = config.min_width
                    new_x = self._start_win_x + (self._start_w - config.min_width)
            else:
                # East edge: growing = positive dx
                new_w = max(config.min_width, self._start_w + dx)

        if affects_h:
            if moves_y:
                # North edge: growing = negative dy
                proposed_h = self._start_h - dy
                if proposed_h >= config.min_height:
                    new_h = proposed_h
                    new_y = self._start_win_y + dy
                else:
                    new_h = config.min_height
                    new_y = self._start_win_y + (self._start_h - config.min_height)
            else:
                # South edge: growing = positive dy
                new_h = max(config.min_height, self._start_h + dy)

        self.root.geometry(f"{new_w}x{new_h}+{new_x}+{new_y}")

        if self.on_resize_callback:
            self.on_resize_callback()

    def _stop_resize(self, event: tk.Event) -> None:
        self._is_resizing = False
        self._resize_edge = ""

    # ── Taskbar proxy ────────────────────────

    def _setup_taskbar_proxy(self) -> None:
        """Create a hidden proxy window that represents the app in the taskbar.

        This is only meaningful on platforms where ``overrideredirect(True)``
        removes the window from the taskbar (primarily Windows).
        """
        self._proxy = tk.Toplevel(self.root)
        self._proxy.title(config.string("app_title"))
        self._proxy.geometry("1x1+-32000+-32000")
        self._proxy.resizable(False, False)
        self._proxy.protocol("WM_DELETE_WINDOW", self._on_proxy_close)
        self._proxy.bind("<Map>", self._proxy_restore)
        self._proxy.bind("<FocusIn>", self._proxy_restore)
        self._proxy.withdraw()

    def _on_proxy_close(self) -> None:
        """Handle close from the taskbar proxy — destroy main window."""
        self.root.destroy()

    def _proxy_restore(self, _event: Optional[tk.Event] = None) -> None:
        """Restore main window when the user clicks the taskbar icon."""
        if self._proxy_programmatic or not self._was_minimized:
            return
        self._was_minimized = False
        try:
            self._proxy.withdraw()
        except tk.TclError:
            return
        self.root.deiconify()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.lift()
        self.root.focus_force()

    def minimize_window(self) -> None:
        """Minimize to taskbar via the proxy window."""
        self._was_minimized = True
        self.root.withdraw()
        self._proxy_programmatic = True
        try:
            self._proxy.deiconify()
            self._proxy.after_idle(self._proxy.iconify)
            self._proxy.after(300, self._clear_proxy_flag)
        except tk.TclError:
            self._proxy_programmatic = False

    def _clear_proxy_flag(self) -> None:
        self._proxy_programmatic = False