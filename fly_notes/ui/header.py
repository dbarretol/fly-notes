"""Title bar: drag area, always-on-top pin, minimize and close buttons."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from typing import Any

from ..config import AppConfig


class HeaderBar(tk.Frame):
    """Title bar with drag, always-on-top pin, minimize, and close buttons."""

    def __init__(
        self,
        master: tk.Misc,
        cfg: AppConfig,
        on_close: Callable[[], None],
        on_minimize: Callable[[], None],
        on_toggle_pin: Callable[[], None] | None = None,
        pinned: bool = True,
        **kwargs: Any,
    ) -> None:
        self._cfg = cfg
        super().__init__(
            master,
            bg=self._cfg.colors.header_bg,
            height=self._cfg.settings.header_height,
            highlightthickness=0,
            bd=0,
            **kwargs,
        )
        self.pack_propagate(False)

        self._title_lbl = tk.Label(
            self,
            text=self._cfg.string("app_title"),
            fg=self._cfg.colors.text_on_header,
            bg=self._cfg.colors.header_bg,
            font=self._cfg.fonts.header,
        )
        self._title_lbl.pack(side="left", padx=self._cfg.spacing.lg, pady=self._cfg.spacing.md)

        # Close
        self._close_btn = tk.Button(
            self,
            text=self._cfg.string("btn_close"),
            command=on_close,
            bg=self._cfg.colors.header_bg,
            fg=self._cfg.colors.header_icon,
            bd=0,
            activebackground=self._cfg.colors.btn_close_hover_bg,
            activeforeground="#FFFFFF",
            padx=self._cfg.spacing.lg,
            font=self._cfg.fonts.header,
            cursor="hand2",
            relief="flat",
        )
        self._close_btn.pack(side="right", fill="y")
        self._close_btn.bind(
            "<Enter>",
            lambda e: self._close_btn.config(bg=self._cfg.colors.btn_close_hover_bg, fg="#FFFFFF"),
        )
        self._close_btn.bind(
            "<Leave>",
            lambda e: self._close_btn.config(
                bg=self._cfg.colors.header_bg, fg=self._cfg.colors.header_icon
            ),
        )

        # Minimize
        self._min_btn = tk.Button(
            self,
            text=self._cfg.string("btn_minimize"),
            command=on_minimize,
            bg=self._cfg.colors.header_bg,
            fg=self._cfg.colors.header_icon,
            bd=0,
            activebackground=self._cfg.colors.btn_header_hover_bg,
            activeforeground=self._cfg.colors.header_icon,
            padx=self._cfg.spacing.lg,
            font=self._cfg.fonts.header,
            cursor="hand2",
            relief="flat",
        )
        self._min_btn.pack(side="right", fill="y")
        self._min_btn.bind(
            "<Enter>", lambda e: self._min_btn.config(bg=self._cfg.colors.btn_header_hover_bg)
        )
        self._min_btn.bind("<Leave>", lambda e: self._min_btn.config(bg=self._cfg.colors.header_bg))

        # Always-on-top pin
        self._pin_btn = tk.Button(
            self,
            command=on_toggle_pin or "",
            bg=self._cfg.colors.header_bg,
            fg=self._cfg.colors.header_icon,
            bd=0,
            activebackground=self._cfg.colors.btn_header_hover_bg,
            activeforeground=self._cfg.colors.header_icon,
            padx=self._cfg.spacing.md,
            font=self._cfg.fonts.header,
            cursor="hand2",
            relief="flat",
        )
        self._pin_btn.pack(side="right", fill="y")
        self._pin_btn.bind(
            "<Enter>", lambda e: self._pin_btn.config(bg=self._cfg.colors.btn_header_hover_bg)
        )
        self._pin_btn.bind("<Leave>", lambda e: self._pin_btn.config(bg=self._cfg.colors.header_bg))
        self.set_pinned(pinned)

    def set_pinned(self, pinned: bool) -> None:
        """Show whether the window currently stays on top."""
        self._pin_btn.config(text=self._cfg.string("btn_pin_on" if pinned else "btn_pin_off"))

    @property
    def pin_text(self) -> str:
        return self._pin_btn.cget("text")

    @property
    def draggable_widgets(self) -> list[tk.Widget]:
        """Widgets that should initiate window drag."""
        return [self, self._title_lbl]
