"""
Main orchestrator with full UX polish:
* Placeholder entry, empty state, progress badge
* Keyboard shortcuts, mousewheel scroll
* Confirmation dialogs, hover-reveal delete
* Proper footer rendering with explicit height
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from typing import Any, Dict, List, Optional

from .config import config
from .task_item import TaskItem
from .task_manager import TaskManager
from .window_controller import WindowController


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
        # ── FIX: Remove root border artifacts ──
        self.root.config(
            bg=config.content_bg,
            highlightthickness=0,
            bd=0,
        )
        self.root.attributes("-alpha", config.active_alpha)

        # Data
        self.manager = TaskManager(
            tasks_file=config.tasks_file,
            error_callback=self._handle_error,
        )

        # Window
        self.window_ctrl = WindowController(
            self.root, on_resize_callback=self._on_window_resize
        )

        # Drag state
        self._dragging_item: Optional[TaskItem] = None
        self._drag_start_y: int = 0
        self._task_widgets: List[TaskItem] = []

        self._build_ui()
        self._bind_events()
        self.window_ctrl.setup_resize_handles(config.content_bg)
        self._load_initial_tasks()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── UI Construction ──────────────────────

    def _build_ui(self) -> None:
        # ─── Header ──────────────────────────
        self._header = tk.Frame(
            self.root,
            bg=config.header_bg,
            height=config.header_height,
            highlightthickness=0,
            bd=0,
        )
        self._header.pack(fill="x", side="top")
        self._header.pack_propagate(False)

        self._title_lbl = tk.Label(
            self._header,
            text=config.string("app_title"),
            fg=config.text_on_header,
            bg=config.header_bg,
            font=config.font_header,
        )
        self._title_lbl.pack(side="left", padx=config.spacing_lg, pady=config.spacing_md)

        # Close
        self._close_btn = tk.Button(
            self._header, text="✕", command=self._on_close,
            bg=config.header_bg, fg=config.text_on_header,
            bd=0, activebackground=config.btn_close_hover_bg,
            activeforeground="#FFFFFF", padx=config.spacing_lg,
            font=config.font_header, cursor="hand2", relief="flat",
        )
        self._close_btn.pack(side="right", fill="y")
        self._close_btn.bind("<Enter>",
            lambda e: self._close_btn.config(bg=config.btn_close_hover_bg))
        self._close_btn.bind("<Leave>",
            lambda e: self._close_btn.config(bg=config.header_bg))

        # Minimize
        self._min_btn = tk.Button(
            self._header, text="—", command=self.window_ctrl.minimize_window,
            bg=config.header_bg, fg=config.text_on_header,
            bd=0, activebackground=config.btn_header_hover_bg,
            activeforeground="#FFFFFF", padx=config.spacing_lg,
            font=config.font_header, cursor="hand2", relief="flat",
        )
        self._min_btn.pack(side="right", fill="y")
        self._min_btn.bind("<Enter>",
            lambda e: self._min_btn.config(bg=config.btn_header_hover_bg))
        self._min_btn.bind("<Leave>",
            lambda e: self._min_btn.config(bg=config.header_bg))

        # ─── Separator under header ─────────
        tk.Frame(
            self.root, bg=config.separator_color,
            height=config.separator_height, bd=0,
        ).pack(fill="x")

        # ─── Footer (pack BEFORE canvas) ─────
        # Separator above footer
        self._footer_sep = tk.Frame(
            self.root, bg=config.separator_color,
            height=config.separator_height, bd=0,
        )
        self._footer_sep.pack(fill="x", side="bottom")

        self._footer = tk.Frame(
            self.root, bg=config.footer_bg,
            height=config.footer_height,
            highlightthickness=0, bd=0,
        )
        self._footer.pack(fill="x", side="bottom")
        self._footer.pack_propagate(False)

        # Re-pack separator after footer so visual order is: content | sep | footer
        self._footer_sep.pack_forget()
        self._footer_sep.pack(fill="x", side="bottom", before=self._footer)
        self._footer.pack(fill="x", side="bottom")

        self._badge_label = tk.Label(
            self._footer, text="", fg=config.text_secondary,
            bg=config.footer_bg, font=config.font_badge,
        )
        self._badge_label.pack(side="left", padx=config.spacing_lg)

        self._clear_btn = tk.Label(
            self._footer, text=config.string("clear_completed_zero"),
            fg=config.link_color, bg=config.footer_bg,
            font=config.font_footer, cursor="hand2",
        )
        self._clear_btn.bind("<Button-1>", lambda _: self._clear_completed())
        self._clear_btn.bind("<Enter>", self._on_clear_hover)
        self._clear_btn.bind("<Leave>", self._on_clear_leave)

        # ─── Entry ───────────────────────────
        entry_frame = tk.Frame(
            self.root, bg=config.content_bg,
            highlightthickness=0, bd=0,
        )
        entry_frame.pack(
            fill="x",
            padx=config.spacing_lg,
            pady=(config.spacing_md, config.spacing_sm),
        )

        self._task_entry = tk.Entry(
            entry_frame, bg="#FFFFFF", fg=config.text_placeholder,
            insertbackground=config.text_primary, font=config.font_body,
            bd=0, highlightthickness=2,
            highlightbackground=config.border_color,
            highlightcolor=config.border_focus,
        )
        self._task_entry.pack(fill="x", ipady=config.spacing_md)
        self._task_entry.insert(0, config.string("entry_placeholder"))
        self._task_entry.bind("<FocusIn>", self._entry_focus_in)
        self._task_entry.bind("<FocusOut>", self._entry_focus_out)
        self._task_entry.bind("<Return>", lambda _: self._add_new_task())

        # ─── Separator under entry ───────────
        tk.Frame(
            self.root, bg=config.separator_color,
            height=config.separator_height, bd=0,
        ).pack(fill="x", padx=config.spacing_lg, pady=(config.spacing_sm, 0))

        # ─── Scrollable task list + scrollbar ─
        list_container = tk.Frame(
            self.root, bg=config.content_bg,
            highlightthickness=0, bd=0,
        )
        list_container.pack(fill="both", expand=True)

        # Custom thin scrollbar
        self._scrollbar = tk.Scrollbar(
            list_container,
            orient="vertical",
            width=config.scrollbar_width,
            troughcolor=config.scrollbar_track,
            bg=config.scrollbar_thumb,
            activebackground=config.scrollbar_thumb,
            bd=0,
            highlightthickness=0,
            relief="flat",
        )

        self._list_canvas = tk.Canvas(
            list_container, bg=config.content_bg,
            highlightthickness=0, bd=0,
            yscrollcommand=self._scrollbar_set,
        )
        self._scrollbar.config(command=self._list_canvas.yview)

        self._scroll_frame = tk.Frame(
            self._list_canvas, bg=config.content_bg,
            highlightthickness=0, bd=0,
        )

        # Pack canvas (scrollbar shown/hidden dynamically)
        self._list_canvas.pack(side="left", fill="both", expand=True)
        self._canvas_win_id = self._list_canvas.create_window(
            (0, 0), window=self._scroll_frame,
            anchor="nw", width=config.default_width,
        )

        # Section headers for grouping
        self._pending_header = None
        self._completed_header = None
        self._completed_sep = None

        # ─── Empty state ─────────────────────
        self._empty_label = tk.Label(
            self._scroll_frame,
            text=config.string("empty_state"),
            fg=config.empty_state_fg, bg=config.content_bg,
            font=config.font_empty_hint, pady=config.spacing_xxl,
        )
        # Track if scrollbar is visible
        self._scrollbar_visible = False

    def _scrollbar_set(self, first: str, last: str) -> None:
        """Show scrollbar only when content overflows."""
        self._scrollbar.set(first, last)
        if float(first) <= 0.0 and float(last) >= 1.0:
            if self._scrollbar_visible:
                self._scrollbar.pack_forget()
                self._scrollbar_visible = False
        else:
            if not self._scrollbar_visible:
                self._scrollbar.pack(side="right", fill="y")
                self._scrollbar_visible = True

    # ── Clear button hover ───────────────────

    def _on_clear_hover(self, event: tk.Event = None) -> None:
        self._clear_btn.config(
            fg=config.link_hover,
            font=(*config.font_footer[:2], "underline"),
        )

    def _on_clear_leave(self, event: tk.Event = None) -> None:
        self._clear_btn.config(
            fg=config.link_color,
            font=config.font_footer,
        )

    # ── Placeholder behaviour ────────────────

    def _entry_focus_in(self, event: tk.Event = None) -> None:
        if self._task_entry.get() == config.string("entry_placeholder"):
            self._task_entry.delete(0, tk.END)
            self._task_entry.config(fg=config.text_primary)

    def _entry_focus_out(self, event: tk.Event = None) -> None:
        if not self._task_entry.get().strip():
            self._task_entry.delete(0, tk.END)
            self._task_entry.insert(0, config.string("entry_placeholder"))
            self._task_entry.config(fg=config.text_placeholder)

    # ── Events ───────────────────────────────

    def _bind_events(self) -> None:
        self.window_ctrl.bind_drag(self._header)
        self.window_ctrl.bind_drag(self._title_lbl)

        self.root.bind("<FocusIn>",
            lambda _: self.root.attributes("-alpha", config.active_alpha))
        self.root.bind("<FocusOut>",
            lambda _: self.root.attributes("-alpha", config.inactive_alpha))
        self.root.bind("<Map>",
            lambda _: self.root.attributes("-topmost", True))

        # Mousewheel
        for w in (self._list_canvas, self._scroll_frame):
            w.bind("<MouseWheel>", self._on_mousewheel)
            w.bind("<Button-4>", self._on_mousewheel)
            w.bind("<Button-5>", self._on_mousewheel)

        # Keyboard shortcuts
        self.root.bind(config.shortcut_close, lambda _: self._on_close())
        self.root.bind(config.shortcut_new_task, lambda _: self._focus_entry())
        self.root.bind(config.shortcut_focus_entry, lambda _: self._focus_entry())
        self.root.bind(config.shortcut_delete_completed, lambda _: self._clear_completed())

    def _focus_entry(self) -> None:
        self._task_entry.focus_set()
        self._entry_focus_in()

    def _on_mousewheel(self, event: tk.Event) -> None:
        if event.num == 4:
            delta = -1
        elif event.num == 5:
            delta = 1
        else:
            delta = int(-1 * (event.delta / 120))
        self._list_canvas.yview_scroll(delta, "units")

    # ── Task CRUD ────────────────────────────

    def _add_new_task(self) -> None:
        raw = self._task_entry.get().strip()
        if not raw or raw == config.string("entry_placeholder"):
            return
        text = raw[: config.max_task_length]
        task = self.manager.add_task(text)
        self._task_entry.delete(0, tk.END)
        self._create_task_widget(task)
        self._refresh_footer()
        self._update_empty_state()
        self._repack_tasks()

    def _create_task_widget(self, task: Dict[str, Any]) -> TaskItem:
        widget = TaskItem(
            self._scroll_frame,
            task_id=task["id"],
            text=task["text"],
            completed=task["completed"],
            on_status_change=self._toggle_task,
            on_delete=self._delete_task,
            on_drag_start=self._start_reorder,
            on_drag_do=self._do_reorder,
            on_drag_stop=self._stop_reorder,
        )
        widget.pack(fill="x", pady=config.spacing_xs, padx=config.spacing_md)

        # Propagate scroll
        for child in (widget, widget.label, widget.check, widget.delete_btn):
            child.bind("<MouseWheel>", self._on_mousewheel)
            child.bind("<Button-4>", self._on_mousewheel)
            child.bind("<Button-5>", self._on_mousewheel)

        self._task_widgets.append(widget)
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
        self._task_widgets.remove(item)
        item.destroy()
        self._refresh_footer()
        self._update_empty_state()
        self._repack_tasks()

    def _toggle_task(self, item: TaskItem) -> None:
        self.manager.toggle_task(item.task_id)
        self._refresh_footer()
        # Re-group after toggle if grouping is enabled
        if config.group_completed:
            self._repack_tasks()

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
        to_remove = [w for w in self._task_widgets if w.completed_var.get()]
        for w in to_remove:
            self._task_widgets.remove(w)
            w.destroy()
        self._refresh_footer()
        self._update_empty_state()
        self._repack_tasks()

    # ── Drag-and-drop ────────────────────────

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
        self._update_canvas()

    def _do_reorder(self, item: TaskItem, event: tk.Event) -> None:
        if self._dragging_item is None:
            return
        y = event.y_root
        try:
            idx = self._task_widgets.index(item)
        except ValueError:
            return

        if y < self._drag_start_y - config.drag_threshold and idx > 0:
            if self.manager.reorder_tasks(idx, idx - 1):
                self._task_widgets[idx], self._task_widgets[idx - 1] = (
                    self._task_widgets[idx - 1], self._task_widgets[idx],
                )
                self._repack_tasks()
                self._drag_start_y = y
        elif (
            y > self._drag_start_y + config.drag_threshold
            and idx < len(self._task_widgets) - 1
        ):
            if self.manager.reorder_tasks(idx, idx + 1):
                self._task_widgets[idx], self._task_widgets[idx + 1] = (
                    self._task_widgets[idx + 1], self._task_widgets[idx],
                )
                self._repack_tasks()
                self._drag_start_y = y

    # ── UI State ─────────────────────────────

    def _load_initial_tasks(self) -> None:
        for task in self.manager.tasks:
            self._create_task_widget(task)
        self._refresh_footer()
        self._update_empty_state()
        self._repack_tasks()

    def _repack_tasks(self) -> None:
        """Repack all task widgets, optionally grouped by completion status."""
        # Remove everything from scroll_frame
        for w in self._scroll_frame.winfo_children():
            w.pack_forget()

        if not self._task_widgets:
            return

        if config.group_completed:
            pending = [w for w in self._task_widgets if not w.completed_var.get()]
            completed = [w for w in self._task_widgets if w.completed_var.get()]

            # Pack pending tasks
            for w in pending:
                w.pack(fill="x", pady=config.spacing_xs, padx=config.spacing_md)

            # Separator + section header for completed
            if completed and pending:
                sep = tk.Frame(
                    self._scroll_frame,
                    bg=config.separator_color,
                    height=config.separator_height,
                    bd=0,
                )
                sep.pack(fill="x", padx=config.spacing_xl, pady=(config.spacing_md, config.spacing_xs))

                header = tk.Label(
                    self._scroll_frame,
                    text=config.string("section_completed"),
                    fg=config.text_secondary,
                    bg=config.content_bg,
                    font=config.font_section,
                    anchor="w",
                )
                header.pack(fill="x", padx=config.spacing_xl, pady=(0, config.spacing_xs))

            for w in completed:
                w.pack(fill="x", pady=config.spacing_xs, padx=config.spacing_md)
        else:
            for w in self._task_widgets:
                w.pack(fill="x", pady=config.spacing_xs, padx=config.spacing_md)

        self._update_canvas()

    def _update_canvas(self) -> None:
        self._scroll_frame.update_idletasks()
        bbox = self._list_canvas.bbox("all")
        if bbox:
            self._list_canvas.config(scrollregion=bbox)

    def _update_empty_state(self) -> None:
        if not self._task_widgets:
            self._empty_label.pack(fill="x", padx=config.spacing_xl)
        else:
            self._empty_label.pack_forget()

    def _refresh_footer(self) -> None:
        total = self.manager.task_count
        done = self.manager.completed_count

        if total == 0:
            self._badge_label.config(text="")
        else:
            self._badge_label.config(text=f"{done} of {total} done")

        if done > 0:
            self._clear_btn.config(
                text=config.string("clear_completed", count=done)
            )
            self._clear_btn.pack(side="right", padx=config.spacing_lg)
        else:
            self._clear_btn.pack_forget()

    def _on_window_resize(self) -> None:
        new_w = self.root.winfo_width()
        self._list_canvas.itemconfigure(self._canvas_win_id, width=new_w)
        self._update_canvas()

    def _handle_error(self, message: str) -> None:
        messagebox.showerror(config.string("app_title"), message)

    def _on_close(self) -> None:
        try:
            self.manager.flush()
        except Exception:
            pass
        self.root.destroy()