"""
Main orchestrator with full UX polish:
* Placeholder entry, empty state, progress badge
* Keyboard shortcuts, mousewheel scroll
* Confirmation dialogs, hover-reveal delete
* Grouped task list (pending / completed)
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from typing import Any, Dict, List, Optional, Tuple

from .config import config
from .task_item import TaskItem
from .task_manager import TaskManager
from .window_controller import WindowController


# ─────────────────────────────────────────────
# Sub-components extracted from the monolithic class
# ─────────────────────────────────────────────


def compute_reorder_target(
    visual_ids: List[str],
    visual_completed: List[bool],
    dragging_id: str,
    delta_y: int,
    threshold: int,
    enforce_group_boundary: bool = True,
) -> Optional[str]:
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
    """Title bar with drag, minimize, and close buttons."""

    def __init__(
        self,
        master: tk.Widget,
        on_close: callable,
        on_minimize: callable,
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
            self, text=config.string("btn_close"), command=on_close,
            bg=config.header_bg, fg=config.text_on_header,
            bd=0, activebackground=config.btn_close_hover_bg,
            activeforeground="#FFFFFF", padx=config.spacing_lg,
            font=config.font_header, cursor="hand2", relief="flat",
        )
        self._close_btn.pack(side="right", fill="y")
        self._close_btn.bind(
            "<Enter>", lambda e: self._close_btn.config(bg=config.btn_close_hover_bg))
        self._close_btn.bind(
            "<Leave>", lambda e: self._close_btn.config(bg=config.header_bg))

        # Minimize
        self._min_btn = tk.Button(
            self, text=config.string("btn_minimize"), command=on_minimize,
            bg=config.header_bg, fg=config.text_on_header,
            bd=0, activebackground=config.btn_header_hover_bg,
            activeforeground="#FFFFFF", padx=config.spacing_lg,
            font=config.font_header, cursor="hand2", relief="flat",
        )
        self._min_btn.pack(side="right", fill="y")
        self._min_btn.bind(
            "<Enter>", lambda e: self._min_btn.config(bg=config.btn_header_hover_bg))
        self._min_btn.bind(
            "<Leave>", lambda e: self._min_btn.config(bg=config.header_bg))

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
            self, bg="#FFFFFF", fg=config.text_placeholder,
            insertbackground=config.text_primary, font=config.font_body,
            bd=0, highlightthickness=2,
            highlightbackground=config.border_color,
            highlightcolor=config.border_focus,
        )
        self._entry.pack(fill="x", ipady=config.spacing_md)
        self._entry.insert(0, self._placeholder)
        self._entry.bind("<FocusIn>", self._focus_in)
        self._entry.bind("<FocusOut>", self._focus_out)
        self._entry.bind("<Return>", lambda _: self._submit())

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

    def _focus_in(self, event: tk.Event = None) -> None:
        if self._entry.get() == self._placeholder:
            self._entry.delete(0, tk.END)
            self._entry.config(fg=config.text_primary)

    def _focus_out(self, event: tk.Event = None) -> None:
        if not self._entry.get().strip():
            self._entry.delete(0, tk.END)
            self._entry.insert(0, self._placeholder)
            self._entry.config(fg=config.text_placeholder)

    def _submit(self) -> None:
        text = self.get_text()
        if text:
            self._on_submit(text[: config.max_task_length])
            self.clear()


class FooterBar(tk.Frame):
    """Status badge and 'clear completed' link."""

    def __init__(
        self,
        master: tk.Widget,
        on_clear: callable,
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

        self._badge_label = tk.Label(
            self, text="", fg=config.text_secondary,
            bg=config.footer_bg, font=config.font_badge,
        )
        self._badge_label.pack(side="left", padx=config.spacing_lg)

        self._clear_btn = tk.Label(
            self, text=config.string("clear_completed_zero"),
            fg=config.link_color, bg=config.footer_bg,
            font=config.font_footer, cursor="hand2",
        )
        self._clear_btn.bind("<Button-1>", lambda _: self._on_clear())
        self._clear_btn.bind("<Enter>", self._on_hover)
        self._clear_btn.bind("<Leave>", self._on_leave)

    def update_counts(self, total: int, done: int) -> None:
        if total == 0:
            self._badge_label.config(text="")
        else:
            self._badge_label.config(
                text=config.string("badge_format", done=done, total=total)
            )
        if done > 0:
            self._clear_btn.config(
                text=config.string("clear_completed", count=done)
            )
            self._clear_btn.pack(side="right", padx=config.spacing_lg)
        else:
            self._clear_btn.pack_forget()

    def _on_hover(self, event: tk.Event = None) -> None:
        self._clear_btn.config(
            fg=config.link_hover,
            font=(*config.font_footer[:2], "underline"),
        )

    def _on_leave(self, event: tk.Event = None) -> None:
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
        self._task_widgets: List[TaskItem] = []
        # Transient widgets (section headers, separators, spacers)
        self._transient_widgets: List[tk.Widget] = []

        # Scrollbar
        self._scrollbar = tk.Scrollbar(
            self, orient="vertical",
            width=config.scrollbar_width,
            troughcolor=config.scrollbar_track,
            bg=config.scrollbar_thumb,
            activebackground=config.scrollbar_thumb,
            bd=0, highlightthickness=0, relief="flat",
        )

        # Canvas
        self._canvas = tk.Canvas(
            self, bg=config.content_bg,
            highlightthickness=0, bd=0,
            yscrollcommand=self._scrollbar_set,
        )
        self._scrollbar.config(command=self._canvas.yview)

        # Inner frame
        self._inner = tk.Frame(
            self._canvas, bg=config.content_bg,
            highlightthickness=0, bd=0,
        )

        self._canvas.pack(side="left", fill="both", expand=True)
        self._canvas_win_id = self._canvas.create_window(
            (0, 0), window=self._inner,
            anchor="nw", width=config.default_width,
        )

        # Empty state label
        self._empty_label = tk.Label(
            self._inner,
            text=config.string("empty_state"),
            fg=config.empty_state_fg, bg=config.content_bg,
            font=config.font_empty_hint, pady=config.spacing_xxl,
        )

        # Mousewheel on canvas & inner frame
        for w in (self._canvas, self._inner):
            w.bind("<MouseWheel>", self._on_mousewheel)
            w.bind("<Button-4>", self._on_mousewheel)
            w.bind("<Button-5>", self._on_mousewheel)

    # ── Public API ───────────────────────────

    @property
    def task_widgets(self) -> List[TaskItem]:
        """Return a copy of the insertion-order widget list."""
        return list(self._task_widgets)

    def visual_order(self) -> List[TaskItem]:
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

    def swap_widgets(self, widget_a: TaskItem, widget_b: TaskItem) -> None:
        """Swap the storage order of two widgets already in this view."""
        i = self._task_widgets.index(widget_a)
        j = self._task_widgets.index(widget_b)
        self._task_widgets[i], self._task_widgets[j] = (
            self._task_widgets[j], self._task_widgets[i],
        )

    @property
    def inner_frame(self) -> tk.Frame:
        return self._inner

    def add_widget(self, widget: TaskItem) -> None:
        self._task_widgets.append(widget)
        # Propagate scroll events
        for child in (widget, widget.label, widget.check, widget.delete_btn):
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
            more_label = self._make_section_label(
                config.string("more_hidden", count=hidden_count)
            )
            more_label.pack(
                fill="x", padx=config.spacing_xl,
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

    def _visible_widgets(self) -> Tuple[List[TaskItem], int]:
        """Cap the rendered widgets at ``config.max_visible_tasks``.

        Applied to the *visual* (post-grouping) order, as one combined
        cap across both groups. Returns the widgets to render and how
        many were left out.
        """
        visual = self.visual_order()
        limit = config.max_visible_tasks
        if len(visual) <= limit:
            return visual, 0
        return visual[:limit], len(visual) - limit

    def _pack_grouped(self, visible: List[TaskItem]) -> None:
        visible_set = set(visible)
        pending = [w for w in self._task_widgets if not w.completed_var.get()]
        completed = [w for w in self._task_widgets if w.completed_var.get()]

        if pending:
            header = self._make_section_label(
                config.string("section_pending", count=len(pending))
            )
            header.pack(
                fill="x", padx=config.spacing_xl,
                pady=(config.spacing_md, config.spacing_xs),
            )
        for w in pending:
            if w in visible_set:
                w.pack(fill="x", pady=config.spacing_xs, padx=config.spacing_md)

        if completed:
            if pending:
                sep = tk.Frame(
                    self._inner, bg=config.separator_color,
                    height=config.separator_height, bd=0,
                )
                sep.pack(
                    fill="x", padx=config.spacing_xl,
                    pady=(config.spacing_lg, config.spacing_xs),
                )
                self._transient_widgets.append(sep)

            header = self._make_section_label(
                config.string("section_completed", count=len(completed))
            )
            header.pack(
                fill="x", padx=config.spacing_xl,
                pady=(config.spacing_xs, config.spacing_xs),
            )
            for w in completed:
                if w in visible_set:
                    w.pack(fill="x", pady=config.spacing_xs, padx=config.spacing_md)

    def _pack_flat(self, visible: List[TaskItem]) -> None:
        visible_set = set(visible)
        for w in self._task_widgets:
            if w in visible_set:
                w.pack(fill="x", pady=config.spacing_xs, padx=config.spacing_md)

    def _make_section_label(self, text: str) -> tk.Label:
        lbl = tk.Label(
            self._inner, text=text,
            fg=config.text_secondary, bg=config.content_bg,
            font=config.font_section, anchor="w",
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

    def _scrollbar_set(self, first: str, last: str) -> None:
        self._scrollbar.set(first, last)
        needs_scroll = not (float(first) <= 0.0 and float(last) >= 1.0)
        if needs_scroll and not self._scrollbar_visible:
            self._scrollbar.pack(side="right", fill="y")
            self._scrollbar_visible = True
        elif not needs_scroll and self._scrollbar_visible:
            self._scrollbar.pack_forget()
            self._scrollbar_visible = False

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
        self.root.geometry(
            f"{config.default_width}x{config.default_height}+100+100"
        )
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.config(bg=config.content_bg, highlightthickness=0, bd=0)
        self.root.attributes("-alpha", config.active_alpha)

        # Data
        self.manager = TaskManager(
            tasks_file=config.tasks_file,
            error_callback=self._handle_error_threadsafe,
        )

        # Window controller
        self.window_ctrl = WindowController(
            self.root, on_resize_callback=self._on_window_resize,
        )

        # Drag state
        self._dragging_item: Optional[TaskItem] = None
        self._drag_start_y: int = 0

        self._build_ui()
        self._bind_events()
        self.window_ctrl.setup_resize_handles(config.content_bg)
        self._load_initial_tasks()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── UI Construction ──────────────────────

    def _build_ui(self) -> None:
        # Header
        self._header = HeaderBar(
            self.root,
            on_close=self._on_close,
            on_minimize=self.window_ctrl.minimize_window,
        )
        self._header.pack(fill="x", side="top")

        # Separator under header
        tk.Frame(
            self.root, bg=config.separator_color,
            height=config.separator_height, bd=0,
        ).pack(fill="x")

        # Footer separator + footer (packed bottom-up)
        self._footer_sep = tk.Frame(
            self.root, bg=config.separator_color,
            height=config.separator_height, bd=0,
        )

        self._footer = FooterBar(self.root, on_clear=self._clear_completed)

        # Pack order: footer at bottom, then separator above it
        self._footer.pack(fill="x", side="bottom")
        self._footer_sep.pack(fill="x", side="bottom")

        # Entry
        self._entry_bar = TaskEntryBar(
            self.root, on_submit=self._add_new_task,
        )
        self._entry_bar.pack(
            fill="x", padx=config.spacing_lg,
            pady=(config.spacing_md, config.spacing_sm),
        )

        # Separator under entry
        tk.Frame(
            self.root, bg=config.separator_color,
            height=config.separator_height, bd=0,
        ).pack(fill="x", padx=config.spacing_lg, pady=(config.spacing_sm, 0))

        # Task list
        self._task_list = TaskListView(self.root)
        self._task_list.pack(fill="both", expand=True)

    # ── Events ───────────────────────────────

    def _bind_events(self) -> None:
        for w in self._header.draggable_widgets:
            self.window_ctrl.bind_drag(w)

        self.root.bind(
            "<FocusIn>",
            lambda _: self.root.attributes("-alpha", config.active_alpha),
        )
        self.root.bind(
            "<FocusOut>",
            lambda _: self.root.attributes("-alpha", config.inactive_alpha),
        )
        self.root.bind("<Map>", lambda _: self.root.attributes("-topmost", True))

        # Shortcuts
        self.root.bind(config.shortcut_close, lambda _: self._on_close())
        self.root.bind(config.shortcut_new_task, lambda _: self._entry_bar.focus_entry())
        self.root.bind(config.shortcut_focus_entry, lambda _: self._entry_bar.focus_entry())
        self.root.bind(config.shortcut_delete_completed, lambda _: self._clear_completed())

    # ── Task CRUD ────────────────────────────

    def _add_new_task(self, text: str) -> None:
        task = self.manager.add_task(text)
        self._create_task_widget(task)
        self._refresh_ui()

    def _create_task_widget(self, task: Dict[str, Any]) -> TaskItem:
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
        )
        self._task_list.add_widget(widget)
        return widget

    def _delete_task(self, item: TaskItem) -> None:
        if config.confirm_delete:
            ok = messagebox.askyesno(
                config.string("confirm_delete_title"),
                config.string("confirm_delete_msg"),
            )
            if not ok:
                return
        self.manager.delete_task(item.task_id)
        self._task_list.remove_widget(item)
        self._refresh_ui()

    def _toggle_task(self, item: TaskItem) -> None:
        self.manager.toggle_task(item.task_id)
        self._refresh_ui()

    def _clear_completed(self) -> None:
        count = self.manager.completed_count
        if count == 0:
            return
        ok = messagebox.askyesno(
            config.string("confirm_clear_title"),
            config.string("confirm_clear_msg", count=count),
        )
        if not ok:
            return
        self.manager.clear_completed()
        to_remove = [w for w in self._task_list.task_widgets if w.completed_var.get()]
        for w in to_remove:
            self._task_list.remove_widget(w)
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

        # Resolve model indices via task_id — safe regardless of grouping
        try:
            model_idx = self.manager.index_of(item.task_id)
            target_model_idx = self.manager.index_of(target_id)
        except ValueError:
            return

        if self.manager.reorder_tasks(model_idx, target_model_idx):
            self._task_list.swap_widgets(item, target_widget)
            self._task_list.repack()
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

    def _on_window_resize(self) -> None:
        self._task_list.update_canvas_width(self.root.winfo_width())

    def _handle_error_threadsafe(self, message: str) -> None:
        """Schedule error dialog on the main Tkinter thread."""
        self.root.after(0, lambda: messagebox.showerror(
            config.string("app_title"), message
        ))

    def _on_close(self) -> None:
        try:
            self.manager.flush()
        except Exception:
            pass
        self.root.destroy()