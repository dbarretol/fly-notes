"""Canvas-drawn checkbox, consistent across platforms."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable

from .drawing import draw_rounded_rect


class CustomCheckbox(tk.Canvas):
    """
    Canvas-drawn checkbox — consistent across all platforms.

    Draws a circle (``round_box``) or a rounded-rect box, with a checkmark. Supports hover feedback
    and checked/unchecked states with distinct visual treatment.
    """

    def __init__(
        self,
        master: tk.Misc,
        size: int = 18,
        checked: bool = False,
        command: Callable[[], None] | None = None,
        bg: str = "#FFFFFF",
        check_color: str = "#B35C00",
        border_color: str = "#B0977A",
        hover_color: str = "#FFF0E0",
        box_color: str = "#FFFFFF",
        round_box: bool = False,
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
        self._box_color = box_color
        self._is_hovered = False
        self._round = round_box

        # Pre-compute geometry constants
        self._pad = 2
        self._radius = 3
        self._check_width = 2.5

        self.bind("<Button-1>", self._on_click)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

        self._draw()

    @property
    def checked(self) -> bool:
        return self._checked

    @checked.setter
    def checked(self, value: bool) -> None:
        if self._checked != value:
            self._checked = value
            self._draw()

    def _on_click(self, event: tk.Event | None = None) -> None:
        self._checked = not self._checked
        self._draw()
        if self._command:
            self._command()

    def _on_enter(self, event: tk.Event | None = None) -> None:
        if not self._is_hovered:
            self._is_hovered = True
            self._draw()

    def _on_leave(self, event: tk.Event | None = None) -> None:
        if self._is_hovered:
            self._is_hovered = False
            self._draw()

    def _draw(self) -> None:
        self.delete("all")
        s = self._size
        pad = self._pad
        r = self._radius

        # Determine visual state
        if self._checked:
            fill = self._check_color
            outline = self._check_color
            border_w = 2
        elif self._is_hovered:
            fill = self._hover_color
            outline = self._check_color
            border_w = 2
        else:
            fill = self._box_color
            outline = self._border_color
            border_w = 1.5

        if self._round:
            self.create_oval(pad, pad, s - pad, s - pad, fill=fill, outline=outline, width=border_w)
        else:
            draw_rounded_rect(self, pad, pad, s - pad, s - pad, r, fill, outline, border_w)

        # Checkmark
        if self._checked:
            cx, cy = s / 2, s / 2
            cw = self._check_width
            self.create_line(
                cx - 4,
                cy,
                cx - 1,
                cy + 3,
                fill="white",
                width=cw,
                capstyle="round",
            )
            self.create_line(
                cx - 1,
                cy + 3,
                cx + 5,
                cy - 4,
                fill="white",
                width=cw,
                capstyle="round",
            )

    def set_canvas_bg(self, color: str) -> None:
        """Update background (used when row bg changes on hover/drag)."""
        self.config(bg=color)
