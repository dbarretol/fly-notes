"""
Self‑contained Tk widget for a single task row.

Responsibilities
────────────────
* Render checkbox + label + delete button.
* Expose drag callbacks to the parent for reorder.
* Track its own ``task_id`` so the parent can map back to the data layer
  without fragile index arithmetic.
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional

from .config import config


class TaskItem(tk.Frame):
    """Visual representation of one task in the scrollable list."""

    def __init__(
        self,
        master: tk.Widget,
        task_id: str,
        text: str,
        completed: bool = False,
        on_status_change: Optional[Callable[[TaskItem], None]] = None,
        on_delete: Optional[Callable[[TaskItem], None]] = None,
        on_drag_start: Optional[Callable[[TaskItem, tk.Event], None]] = None,
        on_drag_do: Optional[Callable[[TaskItem, tk.Event], None]] = None,
        on_drag_stop: Optional[Callable[[TaskItem, tk.Event], None]] = None,
        **kwargs,
    ) -> None:
        super().__init__(master, bg=config.item_bg, **kwargs)

        # Identity -------------------------------------------------------
        self.task_id: str = task_id
        self.text: str = text

        # Callbacks -------------------------------------------------------
        self._on_status_change = on_status_change
        self._on_delete = on_delete
        self._on_drag_start = on_drag_start
        self._on_drag_do = on_drag_do
        self._on_drag_stop = on_drag_stop

        # Widgets ---------------------------------------------------------
        self.completed_var = tk.BooleanVar(value=completed)

        self.check = tk.Checkbutton(
            self,
            variable=self.completed_var,
            command=self._handle_status_change,
            bg=config.item_bg,
            activebackground=config.item_bg,
            selectcolor="white",
            fg=config.text_color,
        )
        self.check.pack(side="left", padx=5)

        self.label = tk.Label(
            self,
            text=text,
            fg=config.text_color,
            bg=config.item_bg,
            font=config.font_body,
            anchor="w",
        )
        self.label.pack(side="left", fill="x", expand=True)

        self.delete_btn = tk.Button(
            self,
            text="✕",
            command=self._handle_delete,
            bg=config.item_bg,
            fg="#D2691E",
            bd=0,
            activebackground=config.content_bg,
            activeforeground="#FF4500",
            cursor="hand2",
        )
        self.delete_btn.pack(side="right", padx=5)

        # Drag bindings on frame + label ----------------------------------
        for widget in (self, self.label):
            widget.bind("<Button-1>", self._start_drag)
            widget.bind("<B1-Motion>", self._do_drag)
            widget.bind("<ButtonRelease-1>", self._stop_drag)

        # Initial styling
        self._update_style()

    # ── Internal handlers ────────────────────

    def _handle_status_change(self) -> None:
        self._update_style()
        if self._on_status_change:
            self._on_status_change(self)

    def _handle_delete(self) -> None:
        if self._on_delete:
            self._on_delete(self)

    def _start_drag(self, event: tk.Event) -> None:
        if self._on_drag_start:
            self._on_drag_start(self, event)

    def _do_drag(self, event: tk.Event) -> None:
        if self._on_drag_do:
            self._on_drag_do(self, event)

    def _stop_drag(self, event: tk.Event) -> None:
        if self._on_drag_stop:
            self._on_drag_stop(self, event)

    # ── Visual helpers ───────────────────────

    def _update_style(self) -> None:
        if self.completed_var.get():
            self.label.config(font=config.font_body_strike, fg=config.strike_color)
        else:
            self.label.config(font=config.font_body, fg=config.text_color)

    def set_bg(self, color: str) -> None:
        """Change background of the entire row (used during drag)."""
        for w in (self, self.label, self.check, self.delete_btn):
            w.config(bg=color)
        self.check.config(activebackground=color)