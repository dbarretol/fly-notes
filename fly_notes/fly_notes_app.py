"""
Main orchestrator with full UX polish:
* Placeholder entry, empty state, progress badge
* Keyboard shortcuts, mousewheel scroll
* Confirmation dialogs, hover-reveal delete
* Grouped task list (pending / completed)
"""

from __future__ import annotations

import logging
import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox
from typing import Any

from .config import blend_alpha_hex, config
from .task_item import TaskItem
from .task_manager import TaskManager
from .window_controller import WindowController
from .window_state import (
    Rect,
    WindowGeometry,
    choose_geometry,
    load_always_on_top,
    load_geometry,
    monitor_work_areas,
    save_always_on_top,
    save_geometry,
    state_file_for,
)

logger = logging.getLogger(__name__)

# How often the running instance checks whether a second launch asked it to show.
_ACTIVATION_POLL_MS = 300

# ─────────────────────────────────────────────
# Sub-components extracted from the monolithic class
# ─────────────────────────────────────────────


def compute_reorder_target(
    visual_ids: list[str],
    visual_completed: list[bool],
    dragging_id: str,
    delta_y: int,
    threshold: int,
    enforce_group_boundary: bool = True,
) -> str | None:
    """Pure decision logic for drag-and-drop reordering.

    Given the *visually rendered* order of task ids (and their completed
    flag in that same order), the id of the task being dragged, and the
    vertical distance dragged since the gesture started, return the id
    of the neighboring task to swap with — or ``None`` if no swap should
    happen (below threshold, at the edge of the list, or the swap would
    cross the pending/completed group boundary).
    """
    try:
        idx = visual_ids.index(dragging_id)
    except ValueError:
        return None

    if delta_y < -threshold and idx > 0:
        direction = -1
    elif delta_y > threshold and idx < len(visual_ids) - 1:
        direction = 1
    else:
        return None

    target_idx = idx + direction
    if enforce_group_boundary and visual_completed[target_idx] != visual_completed[idx]:
        return None

    return visual_ids[target_idx]


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


class TaskEntryBar(tk.Frame):
    """Input field with placeholder behaviour."""

    def __init__(
        self,
        master: tk.Widget,
        on_submit: callable,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            master,
            bg=config.content_bg,
            highlightthickness=0,
            bd=0,
            **kwargs,
        )
        self._on_submit = on_submit
        self._placeholder = config.string("entry_placeholder")

        self._entry = tk.Entry(
            self,
            bg="#FFFFFF",
            fg=config.text_placeholder,
            insertbackground=config.text_primary,
            font=config.font_body,
            bd=0,
            highlightthickness=2,
            highlightbackground=config.border_color,
            highlightcolor=config.border_focus,
        )
        self._entry.pack(fill="x", ipady=config.spacing_md)
        self._entry.insert(0, self._placeholder)
        self._entry.bind("<FocusIn>", self._focus_in)
        self._entry.bind("<FocusOut>", self._focus_out)
        self._entry.bind("<Return>", lambda _: self._submit())
        self._entry.bind("<Escape>", self._cancel)

    @property
    def entry_widget(self) -> tk.Entry:
        return self._entry

    def focus_entry(self) -> None:
        self._entry.focus_set()
        self._focus_in()

    def get_text(self) -> str:
        """Return stripped text, or empty string if placeholder."""
        raw = self._entry.get().strip()
        if raw == self._placeholder:
            return ""
        return raw

    def clear(self) -> None:
        self._entry.delete(0, tk.END)

    # ── Placeholder ──────────────────────────

    def _focus_in(self, event: tk.Event | None = None) -> None:
        if self._entry.get() == self._placeholder:
            self._entry.delete(0, tk.END)
            self._entry.config(fg=config.text_primary)

    def _focus_out(self, event: tk.Event | None = None) -> None:
        if not self._entry.get().strip():
            self._entry.delete(0, tk.END)
            self._entry.insert(0, self._placeholder)
            self._entry.config(fg=config.text_placeholder)

    def _cancel(self, event: tk.Event | None = None) -> str:
        """Escape: discard the typed text and leave the field.

        Returns ``"break"`` so the key never reaches window-level bindings
        (e.g. a user-configured ``<Escape>`` close shortcut).
        """
        self.clear()
        self.winfo_toplevel().focus_set()
        self._focus_out()
        return "break"

    def _submit(self) -> None:
        text = self.get_text()
        if text:
            self._on_submit(text[: config.max_task_length])
            self.clear()


class FooterBar(tk.Frame):
    """Status badge, 'clear completed' link and the temporary undo notice."""

    def __init__(
        self,
        master: tk.Widget,
        on_clear: Callable[[], None],
        on_undo: Callable[[], None] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            master,
            bg=config.footer_bg,
            height=config.footer_height,
            highlightthickness=0,
            bd=0,
            **kwargs,
        )
        self.pack_propagate(False)
        self._on_clear = on_clear
        self._on_undo = on_undo
        self._undo_after_id: str | None = None

        self._badge_label = tk.Label(
            self,
            text="",
            fg=config.text_secondary,
            bg=config.footer_bg,
            font=config.font_badge,
        )
        self._badge_label.pack(side="left", padx=config.spacing_lg)

        self._clear_btn = tk.Label(
            self,
            text=config.string("clear_completed_zero"),
            fg=config.link_color,
            bg=config.footer_bg,
            font=config.font_footer,
            cursor="hand2",
        )
        self._clear_btn.bind("<Button-1>", lambda _: self._on_clear())
        self._clear_btn.bind("<Enter>", self._on_hover)
        self._clear_btn.bind("<Leave>", self._on_leave)

        # Undo notice: replaces the badge for a few seconds after a deletion.
        self._undo_frame = tk.Frame(self, bg=config.footer_bg, bd=0, highlightthickness=0)
        self._undo_msg = tk.Label(
            self._undo_frame,
            text="",
            fg=config.text_secondary,
            bg=config.footer_bg,
            font=config.font_badge,
        )
        self._undo_msg.pack(side="left")
        self._undo_btn = tk.Label(
            self._undo_frame,
            text=config.string("undo_action"),
            fg=config.link_color,
            bg=config.footer_bg,
            font=(*config.font_footer[:2], "bold"),
            cursor="hand2",
        )
        self._undo_btn.pack(side="left", padx=(config.spacing_sm, 0))
        self._undo_btn.bind("<Button-1>", lambda _: self._undo_clicked())
        self._undo_visible = False

    @property
    def undo_visible(self) -> bool:
        return self._undo_visible

    def show_undo(self, message: str) -> None:
        """Show "<message> · Undo" in place of the badge, for ``undo_timeout_ms``."""
        self._cancel_undo_timer()
        self._undo_msg.config(text=message)
        if not self._undo_visible:
            self._badge_label.pack_forget()
            self._undo_frame.pack(side="left", padx=config.spacing_lg)
            self._undo_visible = True
        self._undo_after_id = self.after(config.undo_timeout_ms, self.hide_undo)

    def hide_undo(self) -> None:
        self._cancel_undo_timer()
        if self._undo_visible:
            self._undo_frame.pack_forget()
            self._badge_label.pack(side="left", padx=config.spacing_lg)
            self._undo_visible = False

    def _cancel_undo_timer(self) -> None:
        if self._undo_after_id is not None:
            self.after_cancel(self._undo_after_id)
            self._undo_after_id = None

    def _undo_clicked(self) -> None:
        if self._on_undo:
            self._on_undo()

    def update_counts(self, total: int, done: int) -> None:
        if total == 0:
            self._badge_label.config(text="")
        else:
            self._badge_label.config(text=config.string("badge_format", done=done, total=total))
        if done > 0:
            self._clear_btn.config(text=config.string("clear_completed", count=done))
            self._clear_btn.pack(side="right", padx=config.spacing_lg)
        else:
            self._clear_btn.pack_forget()

    def _on_hover(self, event: tk.Event | None = None) -> None:
        self._clear_btn.config(
            fg=config.link_hover,
            font=(*config.font_footer[:2], "underline"),
        )

    def _on_leave(self, event: tk.Event | None = None) -> None:
        self._clear_btn.config(fg=config.link_color, font=config.font_footer)


class TaskListView(tk.Frame):
    """Scrollable canvas hosting TaskItem widgets with optional grouping."""

    def __init__(self, master: tk.Widget, **kwargs: Any) -> None:
        super().__init__(
            master,
            bg=config.content_bg,
            highlightthickness=0,
            bd=0,
            **kwargs,
        )
        self._scrollbar_visible = False
        self._task_widgets: list[TaskItem] = []
        # Rows revealed past max_visible_tasks with "Show N more" (whole pages).
        self._extra_visible = 0
        # Transient widgets (section headers, separators, spacers)
        self._transient_widgets: list[tk.Widget] = []

        # Scrollbar
        self._scrollbar = tk.Scrollbar(
            self,
            orient="vertical",
            width=config.scrollbar_width,
            troughcolor=config.scrollbar_track,
            bg=config.scrollbar_thumb,
            activebackground=config.scrollbar_thumb,
            bd=0,
            highlightthickness=0,
            relief="flat",
        )

        # Canvas
        self._canvas = tk.Canvas(
            self,
            bg=config.content_bg,
            highlightthickness=0,
            bd=0,
            yscrollcommand=self._scrollbar_set,
        )
        self._scrollbar.config(command=self._canvas.yview)

        # Inner frame
        self._inner = tk.Frame(
            self._canvas,
            bg=config.content_bg,
            highlightthickness=0,
            bd=0,
        )

        self._canvas.pack(side="left", fill="both", expand=True)
        self._canvas_win_id = self._canvas.create_window(
            (0, 0),
            window=self._inner,
            anchor="nw",
            width=config.default_width,
        )

        # "More content below" indicator — shown only while scrolled above
        # the bottom. shadow_color has an alpha channel Tk can't render
        # directly, so it's flattened onto content_bg once at construction.
        self._bottom_shadow = tk.Frame(
            self,
            bg=blend_alpha_hex(config.shadow_color, config.content_bg),
            height=3,
            bd=0,
            highlightthickness=0,
        )
        self._bottom_shadow_visible = False

        # Empty state label
        self._empty_label = tk.Label(
            self._inner,
            text=config.string("empty_state"),
            fg=config.empty_state_fg,
            bg=config.content_bg,
            font=config.font_empty_hint,
            pady=config.spacing_xxl,
        )

        # Rows change height when their text re-wraps (e.g. on resize), so the
        # scroll region follows the inner frame's size instead of only repack().
        self._inner.bind("<Configure>", self._on_inner_configure)

        # Mousewheel on canvas & inner frame
        for w in (self._canvas, self._inner):
            w.bind("<MouseWheel>", self._on_mousewheel)
            w.bind("<Button-4>", self._on_mousewheel)
            w.bind("<Button-5>", self._on_mousewheel)

    # ── Public API ───────────────────────────

    @property
    def task_widgets(self) -> list[TaskItem]:
        """Return a copy of the insertion-order widget list."""
        return list(self._task_widgets)

    def visual_order(self) -> list[TaskItem]:
        """Return widgets in the order they are actually rendered.

        Mirrors ``_pack_grouped``/``_pack_flat``: when grouping is
        enabled, pending widgets come first, then completed ones; each
        group otherwise keeps insertion order.
        """
        if config.group_completed:
            pending = [w for w in self._task_widgets if not w.completed_var.get()]
            completed = [w for w in self._task_widgets if w.completed_var.get()]
            return pending + completed
        return list(self._task_widgets)

    def sync_order(self, task_ids: list[str]) -> None:
        """Reorder the insertion-order list to match the model's *task_ids*.

        A reorder moves a task within the model (pop + insert), which with
        grouping can jump over tasks of the other group; swapping just the
        two widgets would leave the widget order out of step with the model.
        """
        position = {task_id: i for i, task_id in enumerate(task_ids)}
        self._task_widgets.sort(key=lambda w: position.get(w.task_id, len(position)))

    def packed_order(self) -> list[TaskItem]:
        """Widgets currently rendered (not hidden by the cap), top to bottom."""
        return [w for w in self.visual_order() if w.winfo_manager()]

    def ensure_visible(self, widget: TaskItem) -> None:
        """Scroll just enough for *widget* to be fully inside the viewport."""
        self._inner.update_idletasks()
        total = self._inner.winfo_height()
        view_h = self._canvas.winfo_height()
        if total <= 0 or view_h <= 1:
            return
        top = widget.winfo_y()
        bottom = top + widget.winfo_height()
        view_top = int(self._canvas.canvasy(0))
        # Tk rounds the view origin to the nearest yscrollincrement, so aim at a
        # multiple of it: down when scrolling up, up when scrolling down.
        step = max(1, int(self._canvas.cget("yscrollincrement")))
        if top < view_top:
            self._canvas.yview_moveto((top // step) * step / total)
        elif bottom > view_top + view_h:
            self._canvas.yview_moveto(-(-(bottom - view_h) // step) * step / total)

    @property
    def inner_frame(self) -> tk.Frame:
        return self._inner

    def add_widget(self, widget: TaskItem, index: int | None = None) -> None:
        """Add *widget* at *index* of the insertion order (the end by default).

        The insertion order mirrors the TaskManager's list, so a restored task
        is inserted at its model index.
        """
        if index is None:
            self._task_widgets.append(widget)
        else:
            self._task_widgets.insert(index, widget)
        # Propagate scroll events
        for child in (widget, widget.card_canvas, widget.label, widget.check, widget.delete_btn):
            child.bind("<MouseWheel>", self._on_mousewheel)
            child.bind("<Button-4>", self._on_mousewheel)
            child.bind("<Button-5>", self._on_mousewheel)

    def remove_widget(self, widget: TaskItem) -> None:
        if widget in self._task_widgets:
            self._task_widgets.remove(widget)
        widget.destroy()

    def repack(self) -> None:
        """Re-layout all task widgets with optional grouping."""
        # Destroy old transient widgets
        for w in self._transient_widgets:
            try:
                w.destroy()
            except tk.TclError:
                pass
        self._transient_widgets.clear()

        # Unpack task widgets (don't destroy)
        for w in self._task_widgets:
            w.pack_forget()

        if not self._task_widgets:
            self._update_empty_state()
            self._update_scroll_region()
            return

        visible, hidden_count = self._visible_widgets()

        if config.group_completed:
            self._pack_grouped(visible)
        else:
            self._pack_flat(visible)

        if hidden_count:
            self._make_show_more_link(hidden_count).pack(
                anchor="w",
                padx=config.spacing_xl,
                pady=(config.spacing_xs, config.spacing_xs),
            )

        # Bottom spacer
        spacer = tk.Frame(self._inner, bg=config.content_bg, height=config.spacing_lg, bd=0)
        spacer.pack(fill="x")
        self._transient_widgets.append(spacer)

        self._update_empty_state()
        self._update_scroll_region()

    def update_canvas_width(self, width: int) -> None:
        self._canvas.itemconfigure(self._canvas_win_id, width=width)
        self._update_scroll_region()

    # ── Private helpers ──────────────────────

    def show_more(self) -> None:
        """Reveal the next page (``max_visible_tasks`` rows) of hidden tasks."""
        self._extra_visible += config.max_visible_tasks
        self.repack()

    def _make_show_more_link(self, hidden_count: int) -> tk.Label:
        """The "Show N more" link under the list, for rows past the cap.

        Deliberately not routed through _make_section_label: this is a
        meta hint, not a structural section separator, so it keeps the
        plain footer-sized link styling rather than the bold uppercase
        header treatment (see issues-v4 #4).
        """
        page = min(hidden_count, config.max_visible_tasks)
        if page < hidden_count:
            text = config.string("more_hidden_paged", count=page, hidden=hidden_count)
        else:
            text = config.string("more_hidden", count=page)
        link = tk.Label(
            self._inner,
            text=text,
            fg=config.link_color,
            bg=config.content_bg,
            font=config.font_footer,
            anchor="w",
            cursor="hand2",
            takefocus=True,
            highlightthickness=1,
            highlightbackground=config.content_bg,
            highlightcolor=config.border_focus,
        )
        underline = (*config.font_footer[:2], "underline")
        link.bind("<Button-1>", lambda _: self.show_more())
        link.bind("<Return>", lambda _: self.show_more())
        link.bind("<space>", lambda _: self.show_more())
        link.bind("<Enter>", lambda _: link.config(fg=config.link_hover, font=underline))
        link.bind("<Leave>", lambda _: link.config(fg=config.link_color, font=config.font_footer))
        link.bind("<MouseWheel>", self._on_mousewheel)
        self._transient_widgets.append(link)
        return link

    def _visible_widgets(self) -> tuple[list[TaskItem], int]:
        """Cap the rendered widgets at ``config.max_visible_tasks``.

        Applied to the *visual* (post-grouping) order, as one combined
        cap across both groups, plus any pages revealed with "Show N
        more". Returns the widgets to render and how many were left out.
        """
        visual = self.visual_order()
        limit = config.max_visible_tasks + self._extra_visible
        if len(visual) <= limit:
            return visual, 0
        return visual[:limit], len(visual) - limit

    def _pack_grouped(self, visible: list[TaskItem]) -> None:
        visible_set = set(visible)
        pending = [w for w in self._task_widgets if not w.completed_var.get()]
        completed = [w for w in self._task_widgets if w.completed_var.get()]

        if pending:
            header = self._make_section_label(config.string("section_pending", count=len(pending)))
            header.pack(
                fill="x",
                padx=config.spacing_xl,
                pady=(config.spacing_md, config.spacing_xs),
            )
        for w in pending:
            if w in visible_set:
                w.pack(fill="x", pady=config.spacing_xs, padx=config.spacing_md)

        if completed:
            if pending:
                sep = tk.Frame(
                    self._inner,
                    bg=config.separator_color,
                    height=config.separator_height,
                    bd=0,
                )
                sep.pack(
                    fill="x",
                    padx=config.spacing_xl,
                    pady=(config.spacing_lg, config.spacing_xs),
                )
                self._transient_widgets.append(sep)

            header = self._make_section_label(
                config.string("section_completed", count=len(completed))
            )
            header.pack(
                fill="x",
                padx=config.spacing_xl,
                pady=(config.spacing_xs, config.spacing_xs),
            )
            for w in completed:
                if w in visible_set:
                    w.pack(fill="x", pady=config.spacing_xs, padx=config.spacing_md)

    def _pack_flat(self, visible: list[TaskItem]) -> None:
        visible_set = set(visible)
        for w in self._task_widgets:
            if w in visible_set:
                w.pack(fill="x", pady=config.spacing_xs, padx=config.spacing_md)

    def _make_section_label(self, text: str) -> tk.Label:
        # Uppercase is the "letter-spacing" simulation Tk can't do natively
        # (no real tracking support) — combined with the bold, larger
        # font_section and the dedicated section_header colour, it gives
        # section separators more visual weight than the 11pt body text.
        lbl = tk.Label(
            self._inner,
            text=text.upper(),
            fg=config.section_header,
            bg=config.content_bg,
            font=config.font_section,
            anchor="w",
        )
        self._transient_widgets.append(lbl)
        return lbl

    def _update_empty_state(self) -> None:
        if not self._task_widgets:
            self._empty_label.pack(fill="x", padx=config.spacing_xl)
        else:
            self._empty_label.pack_forget()

    def _update_scroll_region(self) -> None:
        self._inner.update_idletasks()
        bbox = self._canvas.bbox("all")
        if bbox:
            self._canvas.config(scrollregion=bbox)
        self._sync_scroll_increment()

    def _on_inner_configure(self, event: tk.Event | None = None) -> None:
        bbox = self._canvas.bbox("all")
        if bbox:
            self._canvas.config(scrollregion=bbox)
        self._sync_scroll_increment()

    def _sync_scroll_increment(self) -> None:
        """Scroll in steps of one single-line task row.

        Tk's canvas constrains the visible y-origin to multiples of
        ``yscrollincrement`` for every scroll source (wheel, scrollbar
        drag/click). Rows whose text wraps are taller, so the step is the
        *shortest* row: a wheel notch never jumps past more than one row,
        and lists of single-line tasks still scroll by exactly one row.
        """
        if not self._task_widgets:
            self._canvas.config(yscrollincrement=1)
            return
        row_height = min(w.winfo_reqheight() for w in self._task_widgets) + 2 * config.spacing_xs
        self._canvas.config(yscrollincrement=max(1, row_height))

    def _scrollbar_set(self, first: str, last: str) -> None:
        self._scrollbar.set(first, last)
        first_f, last_f = float(first), float(last)
        needs_scroll = not (first_f <= 0.0 and last_f >= 1.0)
        if needs_scroll and not self._scrollbar_visible:
            self._scrollbar.pack(side="right", fill="y")
            self._scrollbar_visible = True
        elif not needs_scroll and self._scrollbar_visible:
            self._scrollbar.pack_forget()
            self._scrollbar_visible = False

        show_shadow = needs_scroll and last_f < 0.999
        if show_shadow and not self._bottom_shadow_visible:
            self._bottom_shadow.place(relx=0, rely=1.0, relwidth=1.0, anchor="sw")
            self._bottom_shadow_visible = True
        elif not show_shadow and self._bottom_shadow_visible:
            self._bottom_shadow.place_forget()
            self._bottom_shadow_visible = False

    def _on_mousewheel(self, event: tk.Event) -> None:
        if event.num == 4:
            delta = -1
        elif event.num == 5:
            delta = 1
        else:
            delta = int(-1 * (event.delta / 120))
        self._canvas.yview_scroll(delta, "units")


# ─────────────────────────────────────────────
# Main application controller
# ─────────────────────────────────────────────


class FlyNotesApp:
    """Top-level controller for the Fly Notes application."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(config.string("app_title"))
        self.root.overrideredirect(True)
        self.root.config(bg=config.content_bg, highlightthickness=0, bd=0)
        self.root.attributes("-alpha", config.active_alpha)
        self._fade_after_id: str | None = None
        self._activation_after_id: str | None = None

        # Data
        self.manager = TaskManager(
            tasks_file=config.tasks_file,
            error_callback=self._handle_error_threadsafe,
        )

        # Window geometry: last session's size/position, if still on a monitor
        self._state_file = state_file_for(config.tasks_file)
        self._initial_geometry = self._restored_geometry()
        self.root.geometry(self._initial_geometry.to_tk())

        # Window controller
        self.window_ctrl = WindowController(
            self.root,
            on_resize_callback=self._on_window_resize,
            on_close=self._on_close,
        )

        # Always on top: last session's choice, else the configured default
        saved_on_top = load_always_on_top(self._state_file)
        self._always_on_top = config.always_on_top if saved_on_top is None else saved_on_top
        self._apply_always_on_top()

        # Drag state
        self._dragging_item: TaskItem | None = None
        self._drag_start_y: int = 0

        self._build_ui()
        self._bind_events()
        self.window_ctrl.setup_resize_handles(config.content_bg)
        # The list's canvas starts at default_width; match the restored width.
        self._on_window_resize(self._initial_geometry.width)
        self._load_initial_tasks()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── UI Construction ──────────────────────

    def _build_ui(self) -> None:
        # Header
        self._header = HeaderBar(
            self.root,
            on_close=self._on_close,
            on_minimize=self.window_ctrl.minimize_window,
            on_toggle_pin=self.toggle_always_on_top,
            pinned=self._always_on_top,
        )
        self._header.pack(fill="x", side="top")

        # Separator under header
        tk.Frame(
            self.root,
            bg=config.separator_color,
            height=config.separator_height,
            bd=0,
        ).pack(fill="x")

        # Footer separator + footer (packed bottom-up)
        self._footer_sep = tk.Frame(
            self.root,
            bg=config.separator_color,
            height=config.separator_height,
            bd=0,
        )

        self._footer = FooterBar(self.root, on_clear=self._clear_completed, on_undo=self._undo)

        # Pack order: footer at bottom, then separator above it
        self._footer.pack(fill="x", side="bottom")
        self._footer_sep.pack(fill="x", side="bottom")

        # Entry
        self._entry_bar = TaskEntryBar(
            self.root,
            on_submit=self._add_new_task,
        )
        # Down from the new-task field jumps into the list.
        self._entry_bar.entry_widget.bind("<Down>", lambda _: self._focus_first_task())
        self._entry_bar.pack(
            fill="x",
            padx=config.spacing_lg,
            pady=(config.spacing_md, config.spacing_sm),
        )

        # Separator under entry
        tk.Frame(
            self.root,
            bg=config.separator_color,
            height=config.separator_height,
            bd=0,
        ).pack(fill="x", padx=config.spacing_lg, pady=(config.spacing_sm, 0))

        # Task list
        self._task_list = TaskListView(self.root)
        self._task_list.pack(fill="both", expand=True)

    # ── Events ───────────────────────────────

    def _bind_events(self) -> None:
        for w in self._header.draggable_widgets:
            self.window_ctrl.bind_drag(w)

        self.root.bind("<FocusIn>", self._on_app_focus_in)
        self.root.bind("<FocusOut>", self._on_app_focus_out)
        self.root.bind("<Map>", lambda _: self._apply_always_on_top())

        # Shortcuts
        self.root.bind(config.shortcut_close, lambda _: self._on_close())
        self.root.bind(config.shortcut_new_task, lambda _: self._entry_bar.focus_entry())
        self.root.bind(config.shortcut_delete_completed, lambda _: self._clear_completed())
        self.root.bind(config.shortcut_undo, lambda _: self._undo())
        self.root.bind(config.shortcut_edit_task, lambda _: self._edit_current_task())
        self.root.bind(config.shortcut_toggle_always_on_top, lambda _: self.toggle_always_on_top())

    # ── Single instance ──────────────────────

    def listen_for_activation(self, show_requested: Callable[[], bool]) -> None:
        """Poll *show_requested* and come to the front whenever it returns True.

        A second launch of the app signals the running one this way (see
        ``single_instance``) instead of opening a competing copy.
        """
        self._show_requested = show_requested
        self._poll_activation()

    def _poll_activation(self) -> None:
        self._activation_after_id = None
        try:
            if self._show_requested():
                self.window_ctrl.bring_to_front()
        except Exception:
            logger.exception("Could not handle a request to show the window")
        self._activation_after_id = self.root.after(_ACTIVATION_POLL_MS, self._poll_activation)

    # ── Always on top / inactive fade ────────

    @property
    def always_on_top(self) -> bool:
        return self._always_on_top

    def toggle_always_on_top(self) -> None:
        """Header pin / Ctrl+T: switch between staying on top and a normal window."""
        self._always_on_top = not self._always_on_top
        self._apply_always_on_top()
        self._header.set_pinned(self._always_on_top)

    def _apply_always_on_top(self) -> None:
        self.window_ctrl.always_on_top = self._always_on_top
        self.root.attributes("-topmost", self._always_on_top)

    def _on_app_focus_in(self, _event: tk.Event | None = None) -> None:
        self._cancel_fade()
        self.root.attributes("-alpha", config.active_alpha)

    def _on_app_focus_out(self, _event: tk.Event | None = None) -> None:
        # Focus moving between our own widgets also sends FocusOut (then FocusIn), and a
        # quick click elsewhere shouldn't flash the window: fade only if focus stays away.
        self._cancel_fade()
        self._fade_after_id = self.root.after(config.inactive_fade_delay_ms, self._fade_if_inactive)

    def _fade_if_inactive(self) -> None:
        self._fade_after_id = None
        try:
            focused = self.root.focus_get()
        except (KeyError, tk.TclError):
            focused = None
        if focused is None:
            self.root.attributes("-alpha", config.inactive_alpha)

    def _cancel_fade(self) -> None:
        if self._fade_after_id is not None:
            self.root.after_cancel(self._fade_after_id)
            self._fade_after_id = None

    # ── Task CRUD ────────────────────────────

    def _add_new_task(self, text: str) -> None:
        task = self.manager.add_task(text)
        self._create_task_widget(task)
        self._refresh_ui()

    def _create_task_widget(self, task: dict[str, Any], index: int | None = None) -> TaskItem:
        widget = TaskItem(
            self._task_list.inner_frame,
            task_id=task["id"],
            text=task["text"],
            completed=task["completed"],
            on_status_change=self._toggle_task,
            on_delete=self._delete_task,
            on_drag_start=self._start_reorder,
            on_drag_do=self._do_reorder,
            on_drag_stop=self._stop_reorder,
            on_text_change=self._change_task_text,
            on_navigate=self._navigate_from,
            on_move=self._move_task,
        )
        self._task_list.add_widget(widget, index=index)
        return widget

    def _delete_task(self, item: TaskItem) -> None:
        if config.confirm_delete:
            ok = messagebox.askyesno(
                config.string("confirm_delete_title"),
                config.string("confirm_delete_msg"),
            )
            if not ok:
                return
        # Keyboard users keep their place: focus moves to the next row (or the previous one).
        had_focus = item.has_focus
        next_focus = self._neighbour(item) if had_focus else None
        if self.manager.delete_task(item.task_id) is None:
            return
        self._task_list.remove_widget(item)
        self._refresh_ui()
        self._footer.show_undo(config.string("undo_deleted"))
        if next_focus is not None:
            self._focus_task(next_focus)
        elif had_focus:
            self._entry_bar.focus_entry()

    # ── Keyboard navigation ──────────────────

    def _neighbour(self, item: TaskItem) -> TaskItem | None:
        rows = self._task_list.packed_order()
        if item not in rows:
            return None
        i = rows.index(item)
        if i + 1 < len(rows):
            return rows[i + 1]
        return rows[i - 1] if i > 0 else None

    def _focus_task(self, item: TaskItem) -> None:
        item.focus_row()
        self._task_list.ensure_visible(item)

    def _focus_first_task(self) -> str | None:
        rows = self._task_list.packed_order()
        if not rows:
            return None
        self._focus_task(rows[0])
        return "break"

    def _navigate_from(self, item: TaskItem, delta: int) -> None:
        """Up/Down on a row: focus the adjacent row; Up from the first goes to the entry."""
        rows = self._task_list.packed_order()
        if item not in rows:
            return
        target = rows.index(item) + delta
        if target < 0:
            self._entry_bar.focus_entry()
        elif target < len(rows):
            self._focus_task(rows[target])

    def _move_task(self, item: TaskItem, delta: int) -> None:
        """Alt+Up/Down: swap with the adjacent task, staying inside its group."""
        visual = self._task_list.visual_order()
        target_pos = visual.index(item) + delta
        if not 0 <= target_pos < len(visual):
            return
        target = visual[target_pos]
        if config.group_completed and target.completed_var.get() != item.completed_var.get():
            return
        if self._reorder(item, target):
            self._focus_task(item)

    def _reorder(self, item: TaskItem, target: TaskItem) -> bool:
        """Move *item* to *target*'s place in the model and re-sync the widgets."""
        try:
            model_idx = self.manager.index_of(item.task_id)
            target_model_idx = self.manager.index_of(target.task_id)
        except ValueError:
            return False
        if not self.manager.reorder_tasks(model_idx, target_model_idx):
            return False
        self._task_list.sync_order([t["id"] for t in self.manager.tasks])
        self._task_list.repack()
        return True

    def _change_task_text(self, item: TaskItem, text: str) -> str | None:
        """Save an inline edit; return the stored text, or None to keep the old one."""
        task = self.manager.update_text(item.task_id, text, max_length=config.max_task_length)
        return task["text"] if task else None

    def _edit_current_task(self) -> None:
        """F2: edit the task with keyboard focus, else the one under the pointer."""
        focused = self.root.focus_get()
        widgets = self._task_list.task_widgets
        target = next((w for w in widgets if w.contains(focused)), None) or next(
            (w for w in widgets if w.is_hovered), None
        )
        if target is not None and target.winfo_ismapped():
            target.begin_edit()

    def _toggle_task(self, item: TaskItem) -> None:
        self.manager.toggle_task(item.task_id)
        self._refresh_ui()

    def _clear_completed(self) -> None:
        # No confirmation dialog: the clear can be undone from the footer or Ctrl+Z.
        count = self.manager.clear_completed()
        if count == 0:
            return
        to_remove = [w for w in self._task_list.task_widgets if w.completed_var.get()]
        for w in to_remove:
            self._task_list.remove_widget(w)
        self._refresh_ui()
        self._footer.show_undo(config.string("undo_cleared", count=count))

    def _undo(self) -> None:
        """Bring back the most recently deleted or cleared task(s) in place."""
        restored = self.manager.undo()
        self._footer.hide_undo()
        if not restored:
            return
        for task in restored:
            self._create_task_widget(task, index=self.manager.index_of(task["id"]))
        self._refresh_ui()

    # ── Drag-and-drop (model-safe) ───────────

    def _start_reorder(self, item: TaskItem, event: tk.Event) -> None:
        self._dragging_item = item
        self._drag_start_y = event.y_root
        item.set_drag_active(True)
        item.set_bg(config.drag_highlight_color)

    def _stop_reorder(self, item: TaskItem, event: tk.Event) -> None:
        if self._dragging_item:
            self._dragging_item.set_drag_active(False)
            self._dragging_item.set_bg(config.item_bg)
            self._dragging_item = None
        self._task_list.repack()

    def _do_reorder(self, item: TaskItem, event: tk.Event) -> None:
        if self._dragging_item is None:
            return

        visual = self._task_list.visual_order()
        target_id = compute_reorder_target(
            visual_ids=[w.task_id for w in visual],
            visual_completed=[w.completed_var.get() for w in visual],
            dragging_id=item.task_id,
            delta_y=event.y_root - self._drag_start_y,
            threshold=config.drag_threshold,
            enforce_group_boundary=config.group_completed,
        )
        if target_id is None:
            return

        target_widget = next(w for w in visual if w.task_id == target_id)

        # Model indices are resolved via task_id — safe regardless of grouping
        if self._reorder(item, target_widget):
            self._drag_start_y = event.y_root

    # ── UI State ─────────────────────────────

    def _load_initial_tasks(self) -> None:
        for task in self.manager.tasks:
            self._create_task_widget(task)
        self._refresh_ui()

    def _refresh_ui(self) -> None:
        """Single entry point to update footer + empty state + layout."""
        self._footer.update_counts(
            total=self.manager.task_count,
            done=self.manager.completed_count,
        )
        self._task_list.repack()

    def _on_window_resize(self, new_width: int) -> None:
        self._task_list.update_canvas_width(new_width)

    def _handle_error_threadsafe(self, message: str) -> None:
        """Schedule error dialog on the main Tkinter thread."""
        self.root.after(0, lambda: messagebox.showerror(config.string("app_title"), message))

    def _restored_geometry(self) -> WindowGeometry:
        default = WindowGeometry(config.default_width, config.default_height, 100, 100)
        monitors = monitor_work_areas() or [
            Rect(0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight())
        ]
        return choose_geometry(
            load_geometry(self._state_file),
            default,
            monitors,
            min_width=config.min_width,
            min_height=config.min_height,
        )

    def _save_window_geometry(self) -> None:
        try:
            # wm geometry keeps the last size/position even while minimized (withdrawn).
            geometry = WindowGeometry.from_tk(self.root.wm_geometry())
            save_geometry(self._state_file, geometry)
        except Exception:
            logger.exception("Could not save the window position")
        try:
            save_always_on_top(self._state_file, self._always_on_top)
        except Exception:
            logger.exception("Could not save the always-on-top setting")

    def _on_close(self) -> None:
        self._cancel_fade()
        if self._activation_after_id is not None:
            self.root.after_cancel(self._activation_after_id)
            self._activation_after_id = None
        try:
            self.manager.flush()
        except Exception:
            # Closing must still succeed, but a failed final save must not be silent.
            logger.exception("Could not save tasks while closing")
        self._save_window_geometry()
        self.root.destroy()
