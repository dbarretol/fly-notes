"""
Self-contained task-row widget with:
* Custom-drawn Canvas checkbox (consistent cross-platform)
* Hover-reveal delete button
* Distinct completed vs pending visual states
* Keyboard-accessible delete
* Inline text editing (double-click or F2)
* Keyboard focus with a visible focus ring (arrows, Space, Delete, Alt+arrows)
* Drag-and-drop callbacks
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable

from .config import blend_alpha_hex, config

# Never wrap narrower than this, so a tiny window doesn't stack one word per line.
_MIN_WRAP_WIDTH = 60


def draw_rounded_rect(
    canvas: tk.Canvas,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    r: float,
    fill: str,
    outline: str,
    width: float,
    tags: tuple[str, ...] = (),
) -> None:
    """Draw a rounded rectangle on *canvas* using arcs + fill rects.

    Shared by ``CustomCheckbox`` and ``TaskItem``'s card background so the
    same corner-drawing logic isn't duplicated per widget.
    """
    d = r * 2
    canvas.create_arc(
        x1,
        y1,
        x1 + d,
        y1 + d,
        start=90,
        extent=90,
        fill=fill,
        outline=outline,
        width=width,
        style="pieslice",
        tags=tags,
    )
    canvas.create_arc(
        x2 - d,
        y1,
        x2,
        y1 + d,
        start=0,
        extent=90,
        fill=fill,
        outline=outline,
        width=width,
        style="pieslice",
        tags=tags,
    )
    canvas.create_arc(
        x1,
        y2 - d,
        x1 + d,
        y2,
        start=180,
        extent=90,
        fill=fill,
        outline=outline,
        width=width,
        style="pieslice",
        tags=tags,
    )
    canvas.create_arc(
        x2 - d,
        y2 - d,
        x2,
        y2,
        start=270,
        extent=90,
        fill=fill,
        outline=outline,
        width=width,
        style="pieslice",
        tags=tags,
    )
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
        command: Callable[[], None] | None = None,
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

    def _draw_rounded_rect(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        r: int,
        fill: str,
        outline: str,
        width: float,
    ) -> None:
        """Draw a rounded rectangle using arcs and rectangles."""
        draw_rounded_rect(self, x1, y1, x2, y2, r, fill, outline, width)

    def set_canvas_bg(self, color: str) -> None:
        """Update background (used when row bg changes on hover/drag)."""
        self.config(bg=color)


class _BoolValue:
    """``get()``/``set()`` holder with the same interface as ``tk.BooleanVar``.

    No widget is bound to the completed flag, so a Tcl variable isn't needed;
    a ``BooleanVar`` also breaks when it is garbage-collected off the main
    thread (e.g. during the save timer), which logs "main thread is not in
    main loop" from its ``__del__``.
    """

    __slots__ = ("_value",)

    def __init__(self, value: bool = False) -> None:
        self._value = bool(value)

    def get(self) -> bool:
        return self._value

    def set(self, value: bool) -> None:
        self._value = bool(value)


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
        on_status_change: Callable[[TaskItem], None] | None = None,
        on_delete: Callable[[TaskItem], None] | None = None,
        on_drag_start: Callable[[TaskItem, tk.Event], None] | None = None,
        on_drag_do: Callable[[TaskItem, tk.Event], None] | None = None,
        on_drag_stop: Callable[[TaskItem, tk.Event], None] | None = None,
        on_text_change: Callable[[TaskItem, str], str | None] | None = None,
        on_navigate: Callable[[TaskItem, int], None] | None = None,
        on_move: Callable[[TaskItem, int], None] | None = None,
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
        self._on_text_change = on_text_change
        self._on_navigate = on_navigate
        self._on_move = on_move

        # State
        self.completed_var = _BoolValue(completed)
        self._is_hovered = False
        self._is_dragging = False
        self._drag_active = False
        self._has_focus = False
        self._card_fill = config.item_bg_completed if completed else config.item_bg
        self._radius = config.border_radius
        self._shadow_px = 2

        # ── Card background (rounded rect + subtle drop shadow) ──
        # tk.Frame/tk.Label can't draw rounded corners natively, so the
        # visible "card" is drawn on a Canvas behind a content Frame that
        # is inset by _radius — the drawn corners are never covered by the
        # (square-cornered) content frame sitting on top of them.
        # The card canvas is also the row's keyboard focus target (Tab/arrows).
        self.card_canvas = tk.Canvas(
            self,
            bg=config.content_bg,
            highlightthickness=0,
            bd=0,
            takefocus=1,
        )
        self.card_canvas.pack(fill="both", expand=True)
        self.card_canvas.bind("<Configure>", self._on_canvas_configure)

        self._content = tk.Frame(
            self.card_canvas,
            bg=self._card_fill,
            padx=config.item_padding_x,
            pady=config.item_padding_y,
        )
        self._content_win = self.card_canvas.create_window(
            self._radius,
            self._radius,
            window=self._content,
            anchor="nw",
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
            justify="left",
        )
        self.label.pack(side="left", fill="x", expand=True)
        # Set from the row's real width in ``_on_canvas_configure``; 0 = no wrap.
        self._wrap_width = 0
        # Inline editor, only while editing (see begin_edit).
        self._editor: tk.Entry | None = None

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

        Both values are placeholders: once the parent's geometry manager
        allocates the row's real width, ``_on_canvas_configure`` wraps the
        label to it and resizes the card to the wrapped text's height.
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
        self.label.bind("<Double-Button-1>", lambda e: self.begin_edit())

        c = self.card_canvas
        c.bind("<FocusIn>", self._on_focus_in)
        c.bind("<FocusOut>", self._on_focus_out)
        c.bind("<Up>", lambda e: self._navigate(-1))
        c.bind("<Down>", lambda e: self._navigate(1))
        c.bind("<Alt-Up>", lambda e: self._move(-1))
        c.bind("<Alt-Down>", lambda e: self._move(1))
        c.bind("<space>", self._key_toggle)
        c.bind("<Delete>", self._key_delete)
        c.bind("<F2>", self._key_edit)
        c.bind("<Return>", self._key_edit)

    # ── Keyboard focus ───────────────────────

    @property
    def has_focus(self) -> bool:
        return self._has_focus

    def focus_row(self) -> None:
        """Give this row keyboard focus (shows the focus ring)."""
        self.card_canvas.focus_set()

    def toggle(self) -> None:
        """Flip completed, exactly like clicking the checkbox."""
        self.check.checked = not self.check.checked
        self._handle_status_change()

    def _on_focus_in(self, event: tk.Event | None = None) -> None:
        self._has_focus = True
        self._redraw_card()

    def _on_focus_out(self, event: tk.Event | None = None) -> None:
        self._has_focus = False
        self._redraw_card()

    def _navigate(self, delta: int) -> str:
        if self._on_navigate:
            self._on_navigate(self, delta)
        return "break"

    def _move(self, delta: int) -> str:
        if self._on_move:
            self._on_move(self, delta)
        return "break"

    def _key_toggle(self, event: tk.Event | None = None) -> str:
        self.toggle()
        return "break"

    def _key_delete(self, event: tk.Event | None = None) -> str:
        self._handle_delete()
        return "break"

    def _key_edit(self, event: tk.Event | None = None) -> str:
        self.begin_edit()
        return "break"

    # ── Inline edit ──────────────────────────

    @property
    def is_editing(self) -> bool:
        return self._editor is not None

    def begin_edit(self) -> None:
        """Swap the label for an Entry holding the task text, selected and focused."""
        if self._editor is not None:
            return
        self._is_dragging = False
        editor = tk.Entry(
            self._content,
            bg="#FFFFFF",
            fg=config.text_primary,
            insertbackground=config.text_primary,
            font=config.font_body,
            bd=0,
            highlightthickness=1,
            highlightbackground=config.border_color,
            highlightcolor=config.border_focus,
        )
        editor.insert(0, self.task_text)
        editor.select_range(0, tk.END)
        editor.icursor(tk.END)
        editor.bind("<Return>", self._commit_edit_event)
        editor.bind("<KP_Enter>", self._commit_edit_event)
        editor.bind("<Escape>", self._cancel_edit_event)
        editor.bind("<FocusOut>", lambda e: self.commit_edit())
        self.label.pack_forget()
        editor.pack(side="left", fill="x", expand=True, before=self._pack_anchor())
        self._editor = editor
        editor.focus_set()

    def commit_edit(self) -> None:
        """Save the edited text through ``on_text_change``; empty or unchanged text cancels."""
        if self._editor is None:
            return
        new_text = self._editor.get()
        saved = self._on_text_change(self, new_text) if self._on_text_change else None
        if saved is not None:
            self.task_text = saved
            self.label.config(text=saved)
        self._close_editor()

    def cancel_edit(self) -> None:
        """Discard the edit and show the original text again."""
        if self._editor is not None:
            self._close_editor()

    def _commit_edit_event(self, event: tk.Event | None = None) -> str:
        self.commit_edit()
        return "break"

    def _cancel_edit_event(self, event: tk.Event | None = None) -> str:
        # "break": Escape never reaches window-level bindings while editing.
        self.cancel_edit()
        return "break"

    def _close_editor(self) -> None:
        editor, self._editor = self._editor, None
        had_focus = editor is not None and editor.focus_get() is editor
        if editor is not None:
            editor.destroy()
        self.label.pack(side="left", fill="x", expand=True, before=self._pack_anchor())
        if had_focus:
            self.winfo_toplevel().focus_set()
        self._refit()

    def _pack_anchor(self) -> tk.Widget | None:
        """The widget the label/editor must be packed before (keeps the delete button last)."""
        return self.delete_btn if self._delete_visible else None

    # ── Hover ────────────────────────────────

    def _on_enter(self, event: tk.Event | None = None) -> None:
        if self._is_dragging:
            return
        self._is_hovered = True
        self._show_delete_btn()
        if not self.completed_var.get():
            self._set_row_bg(config.drag_highlight_color)
        self.card_canvas.config(cursor="hand2")

    def _on_leave(self, event: tk.Event | None = None) -> None:
        if self._is_dragging:
            return
        if self._pointer_still_inside():
            return
        self._is_hovered = False
        self._hide_delete_btn()
        self._apply_base_bg()
        self.card_canvas.config(cursor="")

    def _on_delete_btn_enter(self, event: tk.Event | None = None) -> None:
        self._is_hovered = True
        self.delete_btn.config(bg=config.btn_danger_bg, fg="#FFFFFF")

    def _on_delete_btn_leave(self, event: tk.Event | None = None) -> None:
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
            return self.contains(self.winfo_containing(x, y))
        except tk.TclError:
            return False

    def contains(self, widget: tk.Misc | None) -> bool:
        """True if *widget* is this row or one of its descendants.

        Compares Tk path names on a ``.`` boundary, so ``.!taskitem1`` does
        not claim ``.!taskitem10``'s children.
        """
        if widget is None:
            return False
        path, own = str(widget), str(self)
        return path == own or path.startswith(own + ".")

    @property
    def is_hovered(self) -> bool:
        return self._is_hovered

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
        if self._apply_wrap(content_width):
            # The card's height changes: a new <Configure> follows and redraws it.
            return
        self._redraw_card(event.width, event.height)

    def _refit(self) -> None:
        """Re-wrap the label at the current width (after its text changed)."""
        width = self.card_canvas.winfo_width()
        if width <= 1:
            return
        self._wrap_width = 0
        if not self._apply_wrap(max(1, width - 2 * self._radius)):
            self._redraw_card()

    def _label_wrap_width(self, content_width: int) -> int:
        """Width available to the label inside a content frame *content_width* wide.

        Room for the delete button is always reserved, so revealing it on
        hover never re-wraps the text.
        """
        reserved = (
            2 * config.item_padding_x
            + self.check.winfo_reqwidth()
            + config.spacing_md
            + self.delete_btn.winfo_reqwidth()
            + config.spacing_sm
        )
        return max(_MIN_WRAP_WIDTH, content_width - reserved)

    def _apply_wrap(self, content_width: int) -> bool:
        """Wrap the label to *content_width*; return True if the card height changed."""
        wrap = self._label_wrap_width(content_width)
        if wrap == self._wrap_width:
            return False
        self._wrap_width = wrap
        self.label.config(wraplength=wrap)
        # Computed from the children instead of update_idletasks(), which
        # would flush every pending idle task in the app from inside an event.
        content_h = (
            max(self.label.winfo_reqheight(), self.check.winfo_reqheight())
            + 2 * config.item_padding_y
        )
        height = content_h + 2 * self._radius + self._shadow_px
        if height == int(self.card_canvas.cget("height")):
            return False
        self.card_canvas.config(height=height)
        return True

    def _redraw_card(self, width: int | None = None, height: int | None = None) -> None:
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
            self.card_canvas,
            off,
            off,
            w,
            h,
            r,
            fill=shadow_fill,
            outline=shadow_fill,
            width=0,
            tags=("card",),
        )

        if self._drag_active:
            outline, outline_width = config.drag_border, 2
        elif self._has_focus:
            outline, outline_width = config.border_focus, 2
        else:
            outline, outline_width = config.border_color, 1
        draw_rounded_rect(
            self.card_canvas,
            0,
            0,
            w - off,
            h - off,
            r,
            fill=self._card_fill,
            outline=outline,
            width=outline_width,
            tags=("card",),
        )
