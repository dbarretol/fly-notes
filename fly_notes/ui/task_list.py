"""Scrollable, grouped list of task rows."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from typing import Any

from ..config import AppConfig
from .drawing import blend_alpha_hex
from .task_item import BoolValue, TaskItem

# Options of one ``pack()`` call.
PackOptions = dict[str, Any]


class LazyRow:
    """A task whose row has not been built yet: just enough to sort and count it.

    ``create`` builds the real ``TaskItem`` the first time the row is shown.
    """

    __slots__ = ("completed_var", "create", "task_id")

    def __init__(self, task_id: str, completed: bool, create: Callable[[], TaskItem]) -> None:
        self.task_id = task_id
        self.completed_var = BoolValue(completed)
        self.create = create


# One entry of the list: a built row or one still waiting to be shown.
Row = TaskItem | LazyRow


class TaskListView(tk.Frame):
    """Scrollable canvas hosting TaskItem widgets with optional grouping."""

    def __init__(self, master: tk.Misc, cfg: AppConfig, **kwargs: Any) -> None:
        self._cfg = cfg
        super().__init__(
            master,
            bg=self._cfg.colors.content_bg,
            highlightthickness=0,
            bd=0,
            **kwargs,
        )
        self._scrollbar_visible = False
        # Every task, in the model's order. Rows past the visible cap stay LazyRow.
        self._rows: list[Row] = []
        # Rows revealed past max_visible_tasks with "Show N more" (whole pages).
        self._extra_visible = 0

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

        # Section headers, separator, "Show N more" link and bottom spacer are
        # created once and only re-packed (and re-labelled) by repack().
        self._pending_header = self._make_section_label()
        self._completed_header = self._make_section_label()
        self._separator = tk.Frame(
            self._inner,
            bg=self._cfg.colors.separator_color,
            height=self._cfg.settings.separator_height,
            bd=0,
        )
        self._more_link = self._make_show_more_link()
        self._spacer = tk.Frame(
            self._inner, bg=self._cfg.colors.content_bg, height=self._cfg.spacing.lg, bd=0
        )

        sp = self._cfg.spacing
        self._row_opts: PackOptions = {"fill": "x", "pady": sp.xs, "padx": sp.md}
        self._pack_opts: dict[tk.Widget, PackOptions] = {
            self._empty_label: {"fill": "x", "padx": sp.xl},
            self._pending_header: {"fill": "x", "padx": sp.xl, "pady": (sp.md, sp.xs)},
            self._separator: {"fill": "x", "padx": sp.xl, "pady": (sp.lg, sp.xs)},
            self._completed_header: {"fill": "x", "padx": sp.xl, "pady": (sp.xs, sp.xs)},
            self._more_link: {"anchor": "w", "padx": sp.xl, "pady": (sp.xs, sp.xs)},
            self._spacer: {"fill": "x"},
        }

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
        """The rows built so far, in insertion order (rows never shown are not built)."""
        return [r for r in self._rows if isinstance(r, TaskItem)]

    @property
    def row_count(self) -> int:
        """How many tasks the list holds, built or not."""
        return len(self._rows)

    def visual_order(self) -> list[Row]:
        """Return rows in the order they are rendered (hidden ones included, last).

        Mirrors ``_layout``: when grouping is
        enabled, pending widgets come first, then completed ones; each
        group otherwise keeps insertion order.
        """
        if self._cfg.settings.group_completed:
            pending = [r for r in self._rows if not r.completed_var.get()]
            completed = [r for r in self._rows if r.completed_var.get()]
            return pending + completed
        return list(self._rows)

    def sync_order(self, task_ids: list[str]) -> None:
        """Reorder the insertion-order list to match the model's *task_ids*.

        A reorder moves a task within the model (pop + insert), which with
        grouping can jump over tasks of the other group; swapping just the
        two widgets would leave the widget order out of step with the model.
        """
        position = {task_id: i for i, task_id in enumerate(task_ids)}
        self._rows.sort(key=lambda r: position.get(r.task_id, len(position)))

    def packed_order(self) -> list[TaskItem]:
        """Widgets currently rendered (not hidden by the cap), top to bottom."""
        return [r for r in self.visual_order() if isinstance(r, TaskItem) and r.winfo_manager()]

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
        self._insert_row(widget, index)
        widget.bind_scroll(self._on_mousewheel)

    def add_lazy(
        self,
        task_id: str,
        completed: bool,
        create: Callable[[], TaskItem],
        index: int | None = None,
    ) -> None:
        """Add a task whose row is built by *create* only when it is first shown.

        Rows past ``max_visible_tasks`` are never built until "Show N more"
        reveals them, so a long list starts without creating every row.
        """
        self._insert_row(LazyRow(task_id, completed, create), index)

    def _insert_row(self, row: Row, index: int | None) -> None:
        if index is None:
            self._rows.append(row)
        else:
            self._rows.insert(index, row)

    def remove_widget(self, widget: TaskItem) -> None:
        if widget in self._rows:
            self._rows.remove(widget)
        widget.destroy()

    def remove_task(self, task_id: str) -> None:
        """Remove a task's row, built or not."""
        for row in self._rows:
            if row.task_id == task_id:
                self._rows.remove(row)
                if isinstance(row, TaskItem):
                    row.destroy()
                return

    def repack(self) -> None:
        """Bring the rendered rows in line with the task order, grouping and cap.

        Incremental: the structural widgets are reused, and only the widgets
        that are missing or out of place are packed, so a swap while dragging
        moves one row instead of re-laying out the whole list.
        """
        self._apply_layout(self._layout())
        self._update_scroll_region()

    def update_canvas_width(self, width: int) -> None:
        self._canvas.itemconfigure(self._canvas_win_id, width=width)
        self._update_scroll_region()

    # ── Private helpers ──────────────────────

    def show_more(self) -> None:
        """Reveal the next page (``max_visible_tasks`` rows) of hidden tasks."""
        self._extra_visible += self._cfg.settings.max_visible_tasks
        self.repack()

    def _show_more_text(self, hidden_count: int) -> str:
        page = min(hidden_count, self._cfg.settings.max_visible_tasks)
        if page < hidden_count:
            return self._cfg.string("more_hidden_paged", count=page, hidden=hidden_count)
        return self._cfg.string("more_hidden", count=page)

    def _make_show_more_link(self) -> tk.Label:
        """The "Show N more" link under the list, for rows past the cap.

        Deliberately not routed through _make_section_label: this is a
        meta hint, not a structural section separator, so it keeps the
        plain footer-sized link styling rather than the semibold
        section-header treatment.
        """
        link = tk.Label(
            self._inner,
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
        return link

    def _visible_widgets(self) -> tuple[list[TaskItem], int]:
        """Cap the rendered rows at ``self._cfg.settings.max_visible_tasks``.

        Applied to the *visual* (post-grouping) order, as one combined
        cap across both groups, plus any pages revealed with "Show N
        more". Builds the rows that are shown for the first time. Returns
        the widgets to render and how many rows were left out.
        """
        visual = self.visual_order()
        limit = self._cfg.settings.max_visible_tasks + self._extra_visible
        return [self._built(r) for r in visual[:limit]], max(0, len(visual) - limit)

    def _built(self, row: Row) -> TaskItem:
        """The TaskItem for *row*, building it in place if it is still lazy."""
        if isinstance(row, TaskItem):
            return row
        widget = row.create()
        widget.completed_var.set(row.completed_var.get())
        widget.bind_scroll(self._on_mousewheel)
        self._rows[self._rows.index(row)] = widget
        return widget

    def _layout(self) -> list[tk.Widget]:
        """The widgets that should be packed in the inner frame, top to bottom.

        Also updates the texts of the section headers and the "Show N more" link.
        """
        if not self._rows:
            return [self._empty_label]

        visible, hidden_count = self._visible_widgets()
        visible_set: set[Row] = set(visible)
        layout: list[tk.Widget] = []
        if self._cfg.settings.group_completed:
            pending = [r for r in self._rows if not r.completed_var.get()]
            completed = [r for r in self._rows if r.completed_var.get()]
            if pending:
                self._set_text(
                    self._pending_header,
                    self._cfg.string("section_pending", count=len(pending)).upper(),
                )
                layout.append(self._pending_header)
                layout += [r for r in pending if isinstance(r, TaskItem) and r in visible_set]
            if completed:
                if pending:
                    layout.append(self._separator)
                self._set_text(
                    self._completed_header,
                    self._cfg.string("section_completed", count=len(completed)).upper(),
                )
                layout.append(self._completed_header)
                layout += [r for r in completed if isinstance(r, TaskItem) and r in visible_set]
        else:
            layout += visible

        if hidden_count:
            self._set_text(self._more_link, self._show_more_text(hidden_count))
            layout.append(self._more_link)
        layout.append(self._spacer)
        return layout

    def _apply_layout(self, layout: list[tk.Widget]) -> None:
        """Pack *layout* in order, touching only what differs from the current packing."""
        wanted = set(layout)
        current = []
        for w in self._inner.pack_slaves():
            if w in wanted:
                current.append(w)
            else:
                w.pack_forget()

        for i, w in enumerate(layout):
            if i < len(current) and current[i] is w:
                continue
            if w in current:
                current.remove(w)
            opts = self._pack_opts.get(w, self._row_opts)
            if i > 0:
                w.pack(**opts, after=layout[i - 1])
            elif current:
                w.pack(**opts, before=current[0])
            else:
                w.pack(**opts)
            current.insert(i, w)

    @staticmethod
    def _set_text(label: tk.Label, text: str) -> None:
        """Change *label*'s text only when it differs (a change re-lays out the label)."""
        if label.cget("text") != text:
            label.config(text=text)

    def _make_section_label(self) -> tk.Label:
        # Small uppercase semibold text in the muted section_header colour: it
        # labels the group without competing with the task text or the header.
        return tk.Label(
            self._inner,
            fg=self._cfg.colors.section_header,
            bg=self._cfg.colors.content_bg,
            font=self._cfg.fonts.section,
            anchor="w",
        )

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
        built = self.task_widgets
        if not built:
            self._canvas.config(yscrollincrement=1)
            return
        row_height = min(w.winfo_reqheight() for w in built) + 2 * self._cfg.spacing.xs
        self._canvas.config(yscrollincrement=max(1, row_height))

    def _scrollbar_set(self, first: float | str, last: float | str) -> None:
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
