"""Scrollable, grouped list of task rows."""

from __future__ import annotations

import tkinter as tk
from typing import Any

from ..config import AppConfig
from .drawing import blend_alpha_hex
from .task_item import TaskItem


class TaskListView(tk.Frame):
    """Scrollable canvas hosting TaskItem widgets with optional grouping."""

    def __init__(self, master: tk.Widget, cfg: AppConfig, **kwargs: Any) -> None:
        self._cfg = cfg
        super().__init__(
            master,
            bg=self._cfg.colors.content_bg,
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
            width=self._cfg.settings.scrollbar_width,
            troughcolor=self._cfg.colors.scrollbar_track,
            bg=self._cfg.colors.scrollbar_thumb,
            activebackground=self._cfg.colors.scrollbar_thumb,
            bd=0,
            highlightthickness=0,
            relief="flat",
        )

        # Canvas
        self._canvas = tk.Canvas(
            self,
            bg=self._cfg.colors.content_bg,
            highlightthickness=0,
            bd=0,
            yscrollcommand=self._scrollbar_set,
        )
        self._scrollbar.config(command=self._canvas.yview)

        # Inner frame
        self._inner = tk.Frame(
            self._canvas,
            bg=self._cfg.colors.content_bg,
            highlightthickness=0,
            bd=0,
        )

        self._canvas.pack(side="left", fill="both", expand=True)
        self._canvas_win_id = self._canvas.create_window(
            (0, 0),
            window=self._inner,
            anchor="nw",
            width=self._cfg.settings.default_width,
        )

        # "More content below" indicator — shown only while scrolled above
        # the bottom. shadow_color has an alpha channel Tk can't render
        # directly, so it's flattened onto content_bg once at construction.
        self._bottom_shadow = tk.Frame(
            self,
            bg=blend_alpha_hex(self._cfg.colors.shadow_color, self._cfg.colors.content_bg),
            height=3,
            bd=0,
            highlightthickness=0,
        )
        self._bottom_shadow_visible = False

        # Empty state label
        self._empty_label = tk.Label(
            self._inner,
            text=self._cfg.string("empty_state"),
            fg=self._cfg.colors.empty_state_fg,
            bg=self._cfg.colors.content_bg,
            font=self._cfg.fonts.empty_hint,
            pady=self._cfg.spacing.xxl,
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
        if self._cfg.settings.group_completed:
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
        widget.bind_scroll(self._on_mousewheel)

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

        if self._cfg.settings.group_completed:
            self._pack_grouped(visible)
        else:
            self._pack_flat(visible)

        if hidden_count:
            self._make_show_more_link(hidden_count).pack(
                anchor="w",
                padx=self._cfg.spacing.xl,
                pady=(self._cfg.spacing.xs, self._cfg.spacing.xs),
            )

        # Bottom spacer
        spacer = tk.Frame(
            self._inner, bg=self._cfg.colors.content_bg, height=self._cfg.spacing.lg, bd=0
        )
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
        self._extra_visible += self._cfg.settings.max_visible_tasks
        self.repack()

    def _make_show_more_link(self, hidden_count: int) -> tk.Label:
        """The "Show N more" link under the list, for rows past the cap.

        Deliberately not routed through _make_section_label: this is a
        meta hint, not a structural section separator, so it keeps the
        plain footer-sized link styling rather than the bold uppercase
        header treatment.
        """
        page = min(hidden_count, self._cfg.settings.max_visible_tasks)
        if page < hidden_count:
            text = self._cfg.string("more_hidden_paged", count=page, hidden=hidden_count)
        else:
            text = self._cfg.string("more_hidden", count=page)
        link = tk.Label(
            self._inner,
            text=text,
            fg=self._cfg.colors.link_color,
            bg=self._cfg.colors.content_bg,
            font=self._cfg.fonts.footer,
            anchor="w",
            cursor="hand2",
            takefocus=True,
            highlightthickness=1,
            highlightbackground=self._cfg.colors.content_bg,
            highlightcolor=self._cfg.colors.border_focus,
        )
        underline = (*self._cfg.fonts.footer[:2], "underline")
        link.bind("<Button-1>", lambda _: self.show_more())
        link.bind("<Return>", lambda _: self.show_more())
        link.bind("<space>", lambda _: self.show_more())
        link.bind("<Enter>", lambda _: link.config(fg=self._cfg.colors.link_hover, font=underline))
        link.bind(
            "<Leave>",
            lambda _: link.config(fg=self._cfg.colors.link_color, font=self._cfg.fonts.footer),
        )
        link.bind("<MouseWheel>", self._on_mousewheel)
        self._transient_widgets.append(link)
        return link

    def _visible_widgets(self) -> tuple[list[TaskItem], int]:
        """Cap the rendered widgets at ``self._cfg.settings.max_visible_tasks``.

        Applied to the *visual* (post-grouping) order, as one combined
        cap across both groups, plus any pages revealed with "Show N
        more". Returns the widgets to render and how many were left out.
        """
        visual = self.visual_order()
        limit = self._cfg.settings.max_visible_tasks + self._extra_visible
        if len(visual) <= limit:
            return visual, 0
        return visual[:limit], len(visual) - limit

    def _pack_grouped(self, visible: list[TaskItem]) -> None:
        visible_set = set(visible)
        pending = [w for w in self._task_widgets if not w.completed_var.get()]
        completed = [w for w in self._task_widgets if w.completed_var.get()]

        if pending:
            header = self._make_section_label(
                self._cfg.string("section_pending", count=len(pending))
            )
            header.pack(
                fill="x",
                padx=self._cfg.spacing.xl,
                pady=(self._cfg.spacing.md, self._cfg.spacing.xs),
            )
        for w in pending:
            if w in visible_set:
                w.pack(fill="x", pady=self._cfg.spacing.xs, padx=self._cfg.spacing.md)

        if completed:
            if pending:
                sep = tk.Frame(
                    self._inner,
                    bg=self._cfg.colors.separator_color,
                    height=self._cfg.settings.separator_height,
                    bd=0,
                )
                sep.pack(
                    fill="x",
                    padx=self._cfg.spacing.xl,
                    pady=(self._cfg.spacing.lg, self._cfg.spacing.xs),
                )
                self._transient_widgets.append(sep)

            header = self._make_section_label(
                self._cfg.string("section_completed", count=len(completed))
            )
            header.pack(
                fill="x",
                padx=self._cfg.spacing.xl,
                pady=(self._cfg.spacing.xs, self._cfg.spacing.xs),
            )
            for w in completed:
                if w in visible_set:
                    w.pack(fill="x", pady=self._cfg.spacing.xs, padx=self._cfg.spacing.md)

    def _pack_flat(self, visible: list[TaskItem]) -> None:
        visible_set = set(visible)
        for w in self._task_widgets:
            if w in visible_set:
                w.pack(fill="x", pady=self._cfg.spacing.xs, padx=self._cfg.spacing.md)

    def _make_section_label(self, text: str) -> tk.Label:
        # Uppercase is the "letter-spacing" simulation Tk can't do natively
        # (no real tracking support) — combined with the bold, larger
        # font_section and the dedicated section_header colour, it gives
        # section separators more visual weight than the 11pt body text.
        lbl = tk.Label(
            self._inner,
            text=text.upper(),
            fg=self._cfg.colors.section_header,
            bg=self._cfg.colors.content_bg,
            font=self._cfg.fonts.section,
            anchor="w",
        )
        self._transient_widgets.append(lbl)
        return lbl

    def _update_empty_state(self) -> None:
        if not self._task_widgets:
            self._empty_label.pack(fill="x", padx=self._cfg.spacing.xl)
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
        row_height = min(w.winfo_reqheight() for w in self._task_widgets) + 2 * self._cfg.spacing.xs
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
