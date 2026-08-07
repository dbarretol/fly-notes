"""
Self-contained task-row widget with:
* Custom-drawn Canvas checkbox (consistent cross-platform)
* Hover-reveal delete button
* Distinct completed vs pending visual states
* Keyboard-accessible delete
* Drag-and-drop callbacks
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional, Tuple

from .config import blend_alpha_hex, config


def draw_rounded_rect(
    canvas: tk.Canvas,
    x1: float, y1: float, x2: float, y2: float,
    r: float, fill: str, outline: str, width: float,
    tags: Tuple[str, ...] = (),
) -> None:
    """Draw a rounded rectangle on *canvas* using arcs + fill rects.

    Shared by ``CustomCheckbox`` and ``TaskItem``'s card background so the
    same corner-drawing logic isn't duplicated per widget.
    """
    d = r * 2
    canvas.create_arc(x1, y1, x1 + d, y1 + d, start=90, extent=90,
                       fill=fill, outline=outline, width=width, style="pieslice", tags=tags)
    canvas.create_arc(x2 - d, y1, x2, y1 + d, start=0, extent=90,
                       fill=fill, outline=outline, width=width, style="pieslice", tags=tags)
    canvas.create_arc(x1, y2 - d, x1 + d, y2, start=180, extent=90,
                       fill=fill, outline=outline, width=width, style="pieslice", tags=tags)
    canvas.create_arc(x2 - d, y2 - d, x2, y2, start=270, extent=90,
                       fill=fill, outline=outline, width=width, style="pieslice", tags=tags)
    # Fill center regions
    canvas.create_rectangle(x1 + r, y1, x2 - r, y2, fill=fill, outline=fill, tags=tags)
    canvas.create_rectangle(x1, y1 + r, x2, y2 - r, fill=fill, outline=fill, tags=tags)
    # Clean border on top
    canvas.create_rectangle(x1, y1, x2, y2, fill="", outline=outline, width=width, tags=tags)


class CustomCheckbox(tk.Canvas):
    """
    Canvas-drawn checkbox — consistent across all platforms.

    Draws a rounded-rect box with checkmark. Supports hover feedback
    and checked/unchecked states with distinct visual treatment.
    """

    def __init__(
        self,
        master: tk.Widget,
        size: int = 18,
        checked: bool = False,
        command: Optional[Callable[[], None]] = None,
        bg: str = "#FFFFFF",
        check_color: str = "#B35C00",
        border_color: str = "#B0977A",
        hover_color: str = "#FFF0E0",
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

    def _on_click(self, event: tk.Event = None) -> None:
        self._checked = not self._checked
        self._draw()
        if self._command:
            self._command()

    def _on_enter(self, event: tk.Event = None) -> None:
        if not self._is_hovered:
            self._is_hovered = True
            self._draw()

    def _on_leave(self, event: tk.Event = None) -> None:
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
            fill = self._bg
            outline = self._border_color
            border_w = 1.5

        # Rounded rectangle via arcs + fill rects
        self._draw_rounded_rect(pad, pad, s - pad, s - pad, r, fill, outline, border_w)

        # Checkmark
        if self._checked:
            cx, cy = s / 2, s / 2
            cw = self._check_width
            self.create_line(
                cx - 4, cy, cx - 1, cy + 3,
                fill="white", width=cw, capstyle="round",
            )
            self.create_line(
                cx - 1, cy + 3, cx + 5, cy - 4,
                fill="white", width=cw, capstyle="round",
            )

    def _draw_rounded_rect(
        self,
        x1: float, y1: float, x2: float, y2: float,
        r: int, fill: str, outline: str, width: float,
    ) -> None:
        """Draw a rounded rectangle using arcs and rectangles."""
        draw_rounded_rect(self, x1, y1, x2, y2, r, fill, outline, width)

    def set_canvas_bg(self, color: str) -> None:
        """Update background (used when row bg changes on hover/drag)."""
        self.config(bg=color)


class TaskItem(tk.Frame):
    """One task row: custom checkbox │ label │ delete button.

    Exposes ``task_id``, ``completed_var``, and public references to
    ``label``, ``check``, and ``delete_btn`` for external event binding.
    """

    def __init__(
        self,
        master: tk.Widget,
        task_id: str,
        text: str,
        completed: bool = False,
        on_status_change: Optional[Callable[["TaskItem"], None]] = None,
        on_delete: Optional[Callable[["TaskItem"], None]] = None,
        on_drag_start: Optional[Callable[["TaskItem", tk.Event], None]] = None,
        on_drag_do: Optional[Callable[["TaskItem", tk.Event], None]] = None,
        on_drag_stop: Optional[Callable[["TaskItem", tk.Event], None]] = None,
        **kwargs,
    ) -> None:
        super().__init__(
            master,
            bg=config.content_bg,
            highlightthickness=0,
            bd=0,
            **kwargs,
        )

        # Identity
        self.task_id: str = task_id
        self.task_text: str = text  # Renamed to avoid shadowing tk internals

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
        self._drag_active = False
        self._card_fill = config.item_bg_completed if completed else config.item_bg
        self._radius = config.border_radius
        self._shadow_px = 2

        # ── Card background (rounded rect + subtle drop shadow) ──
        # tk.Frame/tk.Label can't draw rounded corners natively, so the
        # visible "card" is drawn on a Canvas behind a content Frame that
        # is inset by _radius — the drawn corners are never covered by the
        # (square-cornered) content frame sitting on top of them.
        self.card_canvas = tk.Canvas(
            self, bg=config.content_bg, highlightthickness=0, bd=0,
        )
        self.card_canvas.pack(fill="both", expand=True)
        self.card_canvas.bind("<Configure>", self._on_canvas_configure)

        self._content = tk.Frame(
            self.card_canvas, bg=self._card_fill,
            padx=config.item_padding_x, pady=config.item_padding_y,
        )
        self._content_win = self.card_canvas.create_window(
            self._radius, self._radius, window=self._content, anchor="nw",
        )

        # ── Custom Checkbox ─────────────────
        self.check = CustomCheckbox(
            self._content,
            size=config.checkbox_size,
            checked=completed,
            command=self._handle_status_change,
            bg=self._card_fill,
            check_color=config.checkbox_check,
            border_color=config.checkbox_border,
            hover_color=config.checkbox_hover_bg,
        )
        self.check.pack(side="left", padx=(0, config.spacing_md))

        # ── Label ───────────────────────────
        self.label = tk.Label(
            self._content,
            text=text,
            fg=config.text_primary,
            bg=self._card_fill,
            font=config.font_body,
            anchor="w",
        )
        self.label.pack(side="left", fill="x", expand=True)

        # ── Delete button (hidden by default) ──
        self.delete_btn = tk.Button(
            self._content,
            text=config.string("btn_close"),
            command=self._handle_delete,
            bg=self._card_fill,
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
        self._delete_visible = False

        # ── Bindings ────────────────────────
        self._bind_hover()
        self._bind_drag()
        self._bind_keyboard()

        self._init_card_size()
        self._update_style()

    def _init_card_size(self) -> None:
        """Give the card canvas an initial size before its first <Configure>.

        Height is fixed for the row's lifetime (content doesn't grow/shrink
        vertically); width is a placeholder immediately superseded once the
        parent's geometry manager allocates the row's real width and fires
        <Configure> (handled by ``_on_canvas_configure``).
        """
        self._content.update_idletasks()
        content_w = self._content.winfo_reqwidth()
        content_h = self._content.winfo_reqheight()
        span = 2 * self._radius + self._shadow_px
        self.card_canvas.config(width=content_w + span, height=content_h + span)
        self.card_canvas.itemconfigure(self._content_win, width=content_w)

    # ── Binding setup ────────────────────────

    def _bind_hover(self) -> None:
        # card_canvas covers essentially all of `self` visually (including
        # the card's padding margin), so it needs the same bindings for
        # hover to trigger anywhere within the row, not just over the label.
        for w in (self, self.card_canvas, self.label, self.check):
            w.bind("<Enter>", self._on_enter)
            w.bind("<Leave>", self._on_leave)
        self.delete_btn.bind("<Enter>", self._on_delete_btn_enter)
        self.delete_btn.bind("<Leave>", self._on_delete_btn_leave)

    def _bind_drag(self) -> None:
        for w in (self, self.card_canvas, self.label):
            w.bind("<Button-1>", self._start_drag)
            w.bind("<B1-Motion>", self._do_drag)
            w.bind("<ButtonRelease-1>", self._stop_drag)

    def _bind_keyboard(self) -> None:
        self.delete_btn.bind("<Return>", lambda e: self._handle_delete())
        self.delete_btn.bind("<space>", lambda e: self._handle_delete())

    # ── Hover ────────────────────────────────

    def _on_enter(self, event: tk.Event = None) -> None:
        if self._is_dragging:
            return
        self._is_hovered = True
        self._show_delete_btn()
        if not self.completed_var.get():
            self._set_row_bg(config.drag_highlight_color)
        self.card_canvas.config(cursor="hand2")

    def _on_leave(self, event: tk.Event = None) -> None:
        if self._is_dragging:
            return
        if self._pointer_still_inside():
            return
        self._is_hovered = False
        self._hide_delete_btn()
        self._apply_base_bg()
        self.card_canvas.config(cursor="")

    def _on_delete_btn_enter(self, event: tk.Event = None) -> None:
        self._is_hovered = True
        self.delete_btn.config(bg=config.btn_danger_bg, fg="#FFFFFF")

    def _on_delete_btn_leave(self, event: tk.Event = None) -> None:
        bg = self._current_base_bg()
        self.delete_btn.config(bg=bg, fg=config.text_secondary)
        if not self._pointer_still_inside():
            self._is_hovered = False
            self._hide_delete_btn()
            self._apply_base_bg()

    def _pointer_still_inside(self) -> bool:
        """Check if the mouse pointer is still within this row's widget tree."""
        try:
            x, y = self.winfo_pointerxy()
            w = self.winfo_containing(x, y)
            return w is not None and (w is self or str(w).startswith(str(self)))
        except tk.TclError:
            return False

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
        completed = self.completed_var.get()
        if completed:
            self.label.config(font=config.font_body_strike, fg=config.text_completed)
        else:
            self.label.config(font=config.font_body, fg=config.text_primary)
        # Sync checkbox without triggering redundant redraws
        self.check.checked = completed
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
        self._drag_active = active
        self._redraw_card()

    def _set_row_bg(self, color: str) -> None:
        """Propagate background colour to all child widgets in the row."""
        self._card_fill = color
        self._content.config(bg=color)
        self.label.config(bg=color)
        self.check.set_canvas_bg(color)
        if self._delete_visible and self.delete_btn.cget("bg") != config.btn_danger_bg:
            self.delete_btn.config(bg=color)
        self._redraw_card()

    # ── Card canvas (rounded rect + shadow) ──

    def _on_canvas_configure(self, event: tk.Event) -> None:
        content_width = max(1, event.width - 2 * self._radius)
        self.card_canvas.itemconfigure(self._content_win, width=content_width)
        self._redraw_card(event.width, event.height)

    def _redraw_card(self, width: Optional[int] = None, height: Optional[int] = None) -> None:
        w = width if width is not None else self.card_canvas.winfo_width()
        h = height if height is not None else self.card_canvas.winfo_height()
        if w <= 1 or h <= 1:
            return
        self.card_canvas.delete("card")
        r = self._radius
        off = self._shadow_px

        # Shadow: a solid rounded rect offset down-right, drawn first so the
        # main card (drawn on top, inset by `off`) leaves only a thin sliver
        # visible along the bottom/right edges — a cheap drop-shadow with no
        # real alpha compositing support in Tk.
        shadow_fill = blend_alpha_hex(config.shadow_color, config.content_bg)
        draw_rounded_rect(
            self.card_canvas, off, off, w, h, r,
            fill=shadow_fill, outline=shadow_fill, width=0, tags=("card",),
        )

        outline = config.drag_border if self._drag_active else config.border_color
        outline_width = 2 if self._drag_active else 1
        draw_rounded_rect(
            self.card_canvas, 0, 0, w - off, h - off, r,
            fill=self._card_fill, outline=outline, width=outline_width, tags=("card",),
        )