"""
Main application orchestrator — wires together UI, data and window management.

Key improvements over the original
───────────────────────────────────
* Tasks are referenced by **UUID**, not parallel‑list index.
* Mouse‑wheel scrolling on the canvas.
* ``flush()`` called on shutdown to avoid data loss from debounce.
* Input length is capped via ``config.max_task_length``.
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
    """Top‑level controller for the Fly Notes application."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Fly Notes")
        self.root.geometry(
            f"{config.default_width}x{config.default_height}+100+100"
        )
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.config(bg=config.content_bg)
        self.root.attributes("-alpha", config.active_alpha)

        # Data layer
        self.manager = TaskManager(
            tasks_file=config.tasks_file,
            error_callback=self._handle_error,
        )

        # Window behaviour
        self.window_ctrl = WindowController(
            self.root, on_resize_callback=self._on_window_resize
        )

        # Drag‑reorder state
        self._dragging_item: Optional[TaskItem] = None
        self._drag_start_y: int = 0

        # Ordered list of visible task widgets
        self._task_widgets: List[TaskItem] = []

        self._build_ui()
        self._bind_events()
        self.window_ctrl.setup_resize_handles(config.content_bg)
        self._load_initial_tasks()

        # Ensure pending saves are flushed on exit
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── UI construction ──────────────────────

    def _build_ui(self) -> None:
        # --- Header ---
        self._header = tk.Frame(self.root, bg=config.header_bg, height=35)
        self._header.pack(fill="x", side="top")

        self._title_lbl = tk.Label(
            self._header,
            text="Fly Notes",
            fg="white",
            bg=config.header_bg,
            font=config.font_header,
        )
        self._title_lbl.pack(side="left", padx=10, pady=5)

        self._close_btn = tk.Button(
            self._header,
            text="✕",
            command=self._on_close,
            bg=config.header_bg,
            fg="white",
            bd=0,
            activebackground="#FF4500",
            padx=10,
            font=config.font_header,
        )
        self._close_btn.pack(side="right", fill="y")

        self._min_btn = tk.Button(
            self._header,
            text="—",
            command=self.window_ctrl.minimize_window,
            bg=config.header_bg,
            fg="white",
            bd=0,
            activebackground="#FF4500",
            padx=10,
            font=config.font_header,
        )
        self._min_btn.pack(side="right", fill="y")

        # --- Entry ---
        entry_frame = tk.Frame(self.root, bg=config.content_bg, pady=10)
        entry_frame.pack(fill="x")

        self._task_entry = tk.Entry(
            entry_frame,
            bg="white",
            fg=config.text_color,
            insertbackground=config.text_color,
            font=config.font_body,
            bd=0,
            highlightthickness=1,
            highlightbackground=config.border_color,
        )
        self._task_entry.pack(fill="x", padx=10, ipady=5)
        self._task_entry.bind("<Return>", lambda _: self._add_new_task())

        # --- Scrollable task list ---
        self._list_canvas = tk.Canvas(
            self.root, bg=config.content_bg, highlightthickness=0
        )
        self._scroll_frame = tk.Frame(self._list_canvas, bg=config.content_bg)

        self._list_canvas.pack(fill="both", expand=True)
        self._canvas_win_id = self._list_canvas.create_window(
            (0, 0),
            window=self._scroll_frame,
            anchor="nw",
            width=config.default_width,
        )

        # --- Footer ---
        footer = tk.Frame(self.root, bg=config.content_bg, pady=5)
        footer.pack(fill="x", side="bottom")

        self._clear_btn = tk.Button(
            footer,
            text="Clear Completed",
            command=self._clear_completed,
            bg=config.content_bg,
            fg=config.strike_color,
            bd=0,
            font=config.font_footer,
            activebackground=config.content_bg,
            activeforeground=config.text_color,
            cursor="hand2",
        )
        self._clear_btn.pack(side="right", padx=10)

    # ── Event bindings ───────────────────────

    def _bind_events(self) -> None:
        self.window_ctrl.bind_drag(self._header)
        self.window_ctrl.bind_drag(self._title_lbl)

        self.root.bind(
            "<FocusIn>",
            lambda _: self.root.attributes("-alpha", config.active_alpha),
        )
        self.root.bind(
            "<FocusOut>",
            lambda _: self.root.attributes("-alpha", config.inactive_alpha),
        )
        self.root.bind(
            "<Map>", lambda _: self.root.attributes("-topmost", True)
        )

        # Mouse‑wheel scroll
        self._list_canvas.bind("<MouseWheel>", self._on_mousewheel)
        self._list_canvas.bind("<Button-4>", self._on_mousewheel)   # Linux up
        self._list_canvas.bind("<Button-5>", self._on_mousewheel)   # Linux down
        self._scroll_frame.bind("<MouseWheel>", self._on_mousewheel)
        self._scroll_frame.bind("<Button-4>", self._on_mousewheel)
        self._scroll_frame.bind("<Button-5>", self._on_mousewheel)

    def _on_mousewheel(self, event: tk.Event) -> None:
        """Cross‑platform mouse‑wheel handler."""
        if event.num == 4:          # Linux scroll‑up
            delta = -1
        elif event.num == 5:        # Linux scroll‑down
            delta = 1
        else:                       # Windows / macOS
            delta = int(-1 * (event.delta / 120))
        self._list_canvas.yview_scroll(delta, "units")

    # ── Task CRUD (UI ↔ data) ────────────────

    def _add_new_task(self) -> None:
        text = self._task_entry.get().strip()
        if not text:
            return
        # Enforce length limit
        if len(text) > config.max_task_length:
            text = text[: config.max_task_length]
        task = self.manager.add_task(text)
        self._task_entry.delete(0, tk.END)
        self._create_task_widget(task)
        self._update_canvas()

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
        widget.pack(fill="x", pady=2, padx=5)

        # Propagate mousewheel events from each child
        for child in (widget, widget.label, widget.check, widget.delete_btn):
            child.bind("<MouseWheel>", self._on_mousewheel)
            child.bind("<Button-4>", self._on_mousewheel)
            child.bind("<Button-5>", self._on_mousewheel)

        self._task_widgets.append(widget)
        return widget

    def _delete_task(self, item: TaskItem) -> None:
        self.manager.delete_task(item.task_id)
        self._task_widgets.remove(item)
        item.destroy()
        self._update_canvas()

    def _toggle_task(self, item: TaskItem) -> None:
        self.manager.toggle_task(item.task_id)

    def _clear_completed(self) -> None:
        self.manager.clear_completed()
        to_remove = [w for w in self._task_widgets if w.completed_var.get()]
        for w in to_remove:
            self._task_widgets.remove(w)
            w.destroy()
        self._update_canvas()

    # ── Drag‑and‑drop reorder ────────────────

    def _start_reorder(self, item: TaskItem, event: tk.Event) -> None:
        self._dragging_item = item
        self._drag_start_y = event.y_root
        item.set_bg(config.drag_highlight_color)

    def _stop_reorder(self, item: TaskItem, event: tk.Event) -> None:
        if self._dragging_item:
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
                    self._task_widgets[idx - 1],
                    self._task_widgets[idx],
                )
                self._repack_tasks()
                self._drag_start_y = y
        elif (
            y > self._drag_start_y + config.drag_threshold
            and idx < len(self._task_widgets) - 1
        ):
            if self.manager.reorder_tasks(idx, idx + 1):
                self._task_widgets[idx], self._task_widgets[idx + 1] = (
                    self._task_widgets[idx + 1],
                    self._task_widgets[idx],
                )
                self._repack_tasks()
                self._drag_start_y = y

    # ── Helpers ──────────────────────────────

    def _load_initial_tasks(self) -> None:
        for task in self.manager.tasks:
            self._create_task_widget(task)
        self._update_canvas()

    def _repack_tasks(self) -> None:
        for w in self._task_widgets:
            w.pack_forget()
        for w in self._task_widgets:
            w.pack(fill="x", pady=2, padx=5)
        self._update_canvas()

    def _update_canvas(self) -> None:
        self._scroll_frame.update_idletasks()
        self._list_canvas.config(scrollregion=self._list_canvas.bbox("all"))

    def _on_window_resize(self) -> None:
        new_w = self.root.winfo_width()
        self._list_canvas.itemconfigure(self._canvas_win_id, width=new_w)
        self._update_canvas()

    def _handle_error(self, message: str) -> None:
        messagebox.showerror("Fly Notes Error", message)

    def _on_close(self) -> None:
        """Flush pending saves and destroy the window."""
        try:
            self.manager.flush()
        except Exception:
            pass
        self.root.destroy()