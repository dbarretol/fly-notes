"""Title bar: drag area, always-on-top pin, minimize and close buttons."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from typing import Any

from ..config import config


class HeaderBar(tk.Frame):
    """Title bar with drag, always-on-top pin, minimize, and close buttons."""

    def __init__(
        self,
        master: tk.Widget,
        on_close: callable,
        on_minimize: callable,
        on_toggle_pin: Callable[[], None] | None = None,
        pinned: bool = True,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            master,
            bg=config.header_bg,
            height=config.header_height,
            highlightthickness=0,
            bd=0,
            **kwargs,
        )
        self.pack_propagate(False)

        self._title_lbl = tk.Label(
            self,
            text=config.string("app_title"),
            fg=config.text_on_header,
            bg=config.header_bg,
            font=config.font_header,
        )
        self._title_lbl.pack(side="left", padx=config.spacing_lg, pady=config.spacing_md)

        # Close
        self._close_btn = tk.Button(
            self,
            text=config.string("btn_close"),
            command=on_close,
            bg=config.header_bg,
            fg=config.text_on_header,
            bd=0,
            activebackground=config.btn_close_hover_bg,
            activeforeground="#FFFFFF",
            padx=config.spacing_lg,
            font=config.font_header,
            cursor="hand2",
            relief="flat",
        )
        self._close_btn.pack(side="right", fill="y")
        self._close_btn.bind(
            "<Enter>", lambda e: self._close_btn.config(bg=config.btn_close_hover_bg)
        )
        self._close_btn.bind("<Leave>", lambda e: self._close_btn.config(bg=config.header_bg))

        # Minimize
        self._min_btn = tk.Button(
            self,
            text=config.string("btn_minimize"),
            command=on_minimize,
            bg=config.header_bg,
            fg=config.text_on_header,
            bd=0,
            activebackground=config.btn_header_hover_bg,
            activeforeground="#FFFFFF",
            padx=config.spacing_lg,
            font=config.font_header,
            cursor="hand2",
            relief="flat",
        )
        self._min_btn.pack(side="right", fill="y")
        self._min_btn.bind("<Enter>", lambda e: self._min_btn.config(bg=config.btn_header_hover_bg))
        self._min_btn.bind("<Leave>", lambda e: self._min_btn.config(bg=config.header_bg))

        # Always-on-top pin
        self._pin_btn = tk.Button(
            self,
            command=on_toggle_pin,
            bg=config.header_bg,
            fg=config.text_on_header,
            bd=0,
            activebackground=config.btn_header_hover_bg,
            activeforeground="#FFFFFF",
            padx=config.spacing_md,
            font=config.font_header,
            cursor="hand2",
            relief="flat",
        )
        self._pin_btn.pack(side="right", fill="y")
        self._pin_btn.bind("<Enter>", lambda e: self._pin_btn.config(bg=config.btn_header_hover_bg))
        self._pin_btn.bind("<Leave>", lambda e: self._pin_btn.config(bg=config.header_bg))
        self.set_pinned(pinned)

    def set_pinned(self, pinned: bool) -> None:
        """Show whether the window currently stays on top."""
        self._pin_btn.config(text=config.string("btn_pin_on" if pinned else "btn_pin_off"))

    @property
    def pin_text(self) -> str:
        return self._pin_btn.cget("text")

    @property
    def draggable_widgets(self) -> list[tk.Widget]:
        """Widgets that should initiate window drag."""
        return [self, self._title_lbl]
