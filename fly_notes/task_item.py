"""
Self-contained task-row widget with:
* Custom-drawn Canvas checkbox (replaces ugly native Checkbutton)
* Hover-reveal delete button
* Distinct completed vs pending visual states
* Keyboard-accessible delete
* Drag-and-drop callbacks
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional

from .config import config


class CustomCheckbox(tk.Canvas):
    """
    A canvas-drawn checkbox that replaces the native Tkinter Checkbutton.
    
    Renders a rounded-ish box with an animated checkmark.
    Visually consistent across all platforms.
    """

    def __init__(
        self,
        master: tk.Widget,
        size: int = 18,
        checked: bool = False,
        command: Optional[Callable[[], None]] = None,
        bg: str = "#FFFFFF",
        check_color: str = "#B35C00",
        border_color: str = "#D4B896",
        hover_color: str = "#FFF4E6",
        **kwargs,
    ) -> None:
        super().__init__(
            master,
            width=size,
            height=size,
            bg=bg,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
            **kwargs,
        )
        self._size = size
        self._checked = checked
        self._command = command
        self._bg = bg
        self._check_color = check_color
        self._border_color = border_color
        self._hover_color = hover_color
        self._is_hovered = False

        self.bind("<Button-1>", self._on_click)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

        self._draw()

    @property
    def checked(self) -> bool:
        return self._checked

    @checked.setter
    def checked(self, value: bool) -> None:
        self._checked = value
        self._draw()

    def _on_click(self, event: tk.Event = None) -> None:
        self._checked = not self._checked
        self._draw()
        if self._command:
            self._command()

    def _on_enter(self, event: tk.Event = None) -> None:
        self._is_hovered = True
        self._draw()

    def _on_leave(self, event: tk.Event = None) -> None:
        self._is_hovered = False
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        s = self._size
        pad = 1
        r = 3  # corner radius approximation

        # Background fill
        if self._checked:
            fill = self._check_color
            outline = self._check_color
        elif self._is_hovered:
            fill = self._hover_color
            outline = self._check_color
        else:
            fill = self._bg
            outline = self._border_color

        # Rounded rectangle (approximated with polygon)
        self.create_rectangle(
            pad, pad, s - pad, s - pad,
            fill=fill,
            outline=outline,
            width=1.5,
        )

        # Checkmark
        if self._checked:
            # Draw a white checkmark
            cx, cy = s / 2, s / 2
            self.create_line(
                cx - 4, cy,
                cx - 1, cy + 3,
                fill="white", width=2, capstyle="round",
            )
            self.create_line(
                cx - 1, cy + 3,
                cx + 4, cy - 3,
                fill="white", width=2, capstyle="round",
            )

    def set_canvas_bg(self, color: str) -> None:
        """Update the canvas background (for row hover propagation)."""
        self.config(bg=color)


class TaskItem(tk.Frame):
    """One task row: custom checkbox │ label │ delete button."""

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

        # ── Custom Checkbox ─────────────────
        self.check = CustomCheckbox(
            self,
            size=config.checkbox_size,
            checked=completed,
            command=self._handle_status_change,
            bg=config.item_bg,
            check_color=config.checkbox_check,
            border_color=config.border_color,
            hover_color=config.drag_highlight_color,
        )
        self.check.pack(side="left", padx=(0, config.spacing_md))

        # ── Label ───────────────────────────
        self.label = tk.Label(
            self,
            text=text,
            fg=config.text_primary,
            bg=config.item_bg,
            font=config.font_body,
            anchor="w",
        )
        self.label.pack(side="left", fill="x", expand=True)

        # ── Delete button (hidden by default) ──
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
            relief="flat",
            takefocus=True,
        )
        # Starts hidden
        self._delete_visible = False

        # ── Hover bindings ──────────────────
        for w in (self, self.label, self.check):
            w.bind("<Enter>", self._on_enter)
            w.bind("<Leave>", self._on_leave)
        self.delete_btn.bind("<Enter>", self._on_delete_btn_enter)
        self.delete_btn.bind("<Leave>", self._on_delete_btn_leave)

        # ── Drag bindings ───────────────────
        for widget in (self, self.label):
            widget.bind("<Button-1>", self._start_drag)
            widget.bind("<B1-Motion>", self._do_drag)
            widget.bind("<ButtonRelease-1>", self._stop_drag)

        # ── Keyboard ────────────────────────
        self.delete_btn.bind("<Return>", lambda e: self._handle_delete())
        self.delete_btn.bind("<space>", lambda e: self._handle_delete())

        self._update_style()

    # ── Hover ────────────────────────────────

    def _on_enter(self, event: tk.Event = None) -> None:
        if self._is_dragging:
            return
        self._is_hovered = True
        self._show_delete_btn()
        if not self.completed_var.get():
            self._set_row_bg(config.drag_highlight_color)
        self.config(cursor="hand2")

    def _on_leave(self, event: tk.Event = None) -> None:
        if self._is_dragging:
            return
        try:
            x, y = self.winfo_pointerxy()
            w = self.winfo_containing(x, y)
            if w and (w is self or str(w).startswith(str(self))):
                return
        except tk.TclError:
            pass
        self._is_hovered = False
        self._hide_delete_btn()
        self._apply_base_bg()
        self.config(cursor="")

    def _on_delete_btn_enter(self, event: tk.Event = None) -> None:
        self._is_hovered = True  # Keep parent hover alive
        self.delete_btn.config(bg=config.btn_danger_bg, fg="#FFFFFF")

    def _on_delete_btn_leave(self, event: tk.Event = None) -> None:
        bg = self._current_base_bg()
        self.delete_btn.config(bg=bg, fg=config.text_secondary)
        # Check if we truly left the row
        try:
            x, y = self.winfo_pointerxy()
            w = self.winfo_containing(x, y)
            if not w or not str(w).startswith(str(self)):
                self._is_hovered = False
                self._hide_delete_btn()
                self._apply_base_bg()
        except tk.TclError:
            pass

    def _show_delete_btn(self) -> None:
        if not self._delete_visible:
            self.delete_btn.pack(side="right", padx=(config.spacing_sm, 0))
            self._delete_visible = True

    def _hide_delete_btn(self) -> None:
        if self._delete_visible:
            self.delete_btn.pack_forget()
            self._delete_visible = False

    # ── Status ───────────────────────────────

    def _handle_status_change(self) -> None:
        new_state = self.check.checked
        self.completed_var.set(new_state)
        self._update_style()
        if self._on_status_change:
            self._on_status_change(self)

    def _handle_delete(self) -> None:
        if self._on_delete:
            self._on_delete(self)

    def _update_style(self) -> None:
        if self.completed_var.get():
            self.label.config(font=config.font_body_strike, fg=config.text_completed)
            self.check.checked = True
        else:
            self.label.config(font=config.font_body, fg=config.text_primary)
            self.check.checked = False
        self._apply_base_bg()

    def _current_base_bg(self) -> str:
        return config.item_bg_completed if self.completed_var.get() else config.item_bg

    def _apply_base_bg(self) -> None:
        self._set_row_bg(self._current_base_bg())

    # ── Drag ─────────────────────────────────

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
        if not self._is_hovered:
            self._apply_base_bg()

    # ── Public helpers ───────────────────────

    def set_bg(self, color: str) -> None:
        self._set_row_bg(color)

    def set_drag_active(self, active: bool) -> None:
        if active:
            self.config(highlightbackground=config.drag_border, highlightthickness=2)
        else:
            self.config(highlightbackground=config.border_color, highlightthickness=1)

    def _set_row_bg(self, color: str) -> None:
        for w in (self, self.label):
            w.config(bg=color)
        self.check.set_canvas_bg(color)
        if self._delete_visible and self.delete_btn.cget("bg") != config.btn_danger_bg:
            self.delete_btn.config(bg=color)