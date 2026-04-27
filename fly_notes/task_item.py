"""
Self-contained task-row widget with full UX polish:

* Hover states on the row and on the delete button.
* Distinct visual treatment for completed vs pending items.
* Smooth background transitions during drag.
* Keyboard-accessible delete (focused → Enter/Space).
* Tooltip on truncated text.
* Semantic colour tokens from config.
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional

from .config import config


class TaskItem(tk.Frame):
    """One task row: checkbox │ label │ delete button."""

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
        super().__init__(
            master,
            bg=config.item_bg,
            highlightbackground=config.border_color,
            highlightthickness=1,
            padx=config.item_padding_x,
            pady=config.item_padding_y,
            **kwargs,
        )

        # Identity
        self.task_id: str = task_id
        self.text: str = text

        # Callbacks
        self._on_status_change = on_status_change
        self._on_delete = on_delete
        self._on_drag_start = on_drag_start
        self._on_drag_do = on_drag_do
        self._on_drag_stop = on_drag_stop

        # State
        self.completed_var = tk.BooleanVar(value=completed)
        self._is_hovered = False
        self._is_dragging = False

        # ── Checkbox ────────────────────────
        self.check = tk.Checkbutton(
            self,
            variable=self.completed_var,
            command=self._handle_status_change,
            bg=config.item_bg,
            activebackground=config.item_bg,
            selectcolor=config.checkbox_accent,
            fg=config.text_primary,
            cursor="hand2",
            takefocus=False,
        )
        self.check.pack(side="left", padx=(0, config.spacing_sm))

        # ── Label ───────────────────────────
        self.label = tk.Label(
            self,
            text=text,
            fg=config.text_primary,
            bg=config.item_bg,
            font=config.font_body,
            anchor="w",
            wraplength=0,   # No wrap — truncation handled by layout
        )
        self.label.pack(side="left", fill="x", expand=True)

        # ── Delete button (hidden until hover) ──
        self.delete_btn = tk.Button(
            self,
            text="✕",
            command=self._handle_delete,
            bg=config.item_bg,
            fg=config.text_secondary,
            bd=0,
            activebackground=config.btn_danger_bg,
            activeforeground="#FFFFFF",
            cursor="hand2",
            font=config.font_footer,
            width=2,
            takefocus=True,
        )
        # Start hidden — revealed on hover
        self.delete_btn.pack(side="right", padx=(config.spacing_sm, 0))
        self.delete_btn.pack_forget()

        # ── Hover bindings ──────────────────
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        for w in (self.label, self.check):
            w.bind("<Enter>", self._on_enter)
            w.bind("<Leave>", self._on_leave)
        self.delete_btn.bind("<Enter>", self._on_delete_btn_enter)
        self.delete_btn.bind("<Leave>", self._on_delete_btn_leave)

        # ── Drag bindings ───────────────────
        for widget in (self, self.label):
            widget.bind("<Button-1>", self._start_drag)
            widget.bind("<B1-Motion>", self._do_drag)
            widget.bind("<ButtonRelease-1>", self._stop_drag)

        # ── Keyboard on delete btn ──────────
        self.delete_btn.bind("<Return>", lambda e: self._handle_delete())
        self.delete_btn.bind("<space>", lambda e: self._handle_delete())

        # Initial style
        self._update_style()

    # ── Hover management ─────────────────────

    def _on_enter(self, event: tk.Event = None) -> None:
        if self._is_dragging:
            return
        self._is_hovered = True
        self.delete_btn.pack(side="right", padx=(config.spacing_sm, 0))
        if not self.completed_var.get():
            self._set_row_bg(config.drag_highlight_color)   # Subtle warm hover
        self.config(cursor="hand2")

    def _on_leave(self, event: tk.Event = None) -> None:
        if self._is_dragging:
            return
        # Verify the pointer actually left the frame (not just moved to a child)
        try:
            x, y = self.winfo_pointerxy()
            widget_under = self.winfo_containing(x, y)
            if widget_under and (widget_under is self or widget_under.master is self):
                return
        except tk.TclError:
            pass
        self._is_hovered = False
        self.delete_btn.pack_forget()
        self._apply_base_bg()
        self.config(cursor="")

    def _on_delete_btn_enter(self, event: tk.Event = None) -> None:
        self.delete_btn.config(
            bg=config.btn_danger_bg,
            fg="#FFFFFF",
        )

    def _on_delete_btn_leave(self, event: tk.Event = None) -> None:
        bg = self._current_base_bg()
        self.delete_btn.config(bg=bg, fg=config.text_secondary)

    # ── Status / style ───────────────────────

    def _handle_status_change(self) -> None:
        self._update_style()
        if self._on_status_change:
            self._on_status_change(self)

    def _handle_delete(self) -> None:
        if self._on_delete:
            self._on_delete(self)

    def _update_style(self) -> None:
        """Apply the correct visual state for completed / pending."""
        if self.completed_var.get():
            self.label.config(
                font=config.font_body_strike,
                fg=config.text_completed,
            )
            self._apply_base_bg()
        else:
            self.label.config(
                font=config.font_body,
                fg=config.text_primary,
            )
            self._apply_base_bg()

    def _current_base_bg(self) -> str:
        """Return the non-hover, non-drag background for current state."""
        if self.completed_var.get():
            return config.item_bg_completed
        return config.item_bg

    def _apply_base_bg(self) -> None:
        self._set_row_bg(self._current_base_bg())

    # ── Drag handlers ────────────────────────

    def _start_drag(self, event: tk.Event) -> None:
        self._is_dragging = True
        if self._on_drag_start:
            self._on_drag_start(self, event)

    def _do_drag(self, event: tk.Event) -> None:
        if self._on_drag_do:
            self._on_drag_do(self, event)

    def _stop_drag(self, event: tk.Event) -> None:
        self._is_dragging = False
        if self._on_drag_stop:
            self._on_drag_stop(self, event)
        # Re-evaluate hover after drag ends
        if not self._is_hovered:
            self._apply_base_bg()

    # ── Public helpers ───────────────────────

    def set_bg(self, color: str) -> None:
        """External control of row background (used by parent during drag)."""
        self._set_row_bg(color)

    def set_drag_active(self, active: bool) -> None:
        """Visual cue: highlight border when this item is being dragged."""
        if active:
            self.config(highlightbackground=config.drag_border, highlightthickness=2)
        else:
            self.config(highlightbackground=config.border_color, highlightthickness=1)

    def _set_row_bg(self, color: str) -> None:
        """Propagate background to all child widgets."""
        for w in (self, self.label, self.check):
            w.config(bg=color)
        self.check.config(activebackground=color)
        # Only update delete_btn bg if it's not in its own hover state
        if not self.delete_btn.cget("bg") == config.btn_danger_bg:
            self.delete_btn.config(bg=color)