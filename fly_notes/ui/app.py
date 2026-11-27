"""Top-level controller: builds the window and wires the task store to the widgets.

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

from ..config import AppConfig
from ..model.reorder import compute_reorder_target
from ..model.store import TaskManager
from ..model.task import Task
from ..platform.window_controller import WindowController
from ..platform.window_state import (
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
from .entry import TaskEntryBar
from .footer import FooterBar
from .header import HeaderBar
from .task_item import TaskItem
from .task_list import TaskListView

logger = logging.getLogger(__name__)

# How often the running instance checks whether a second launch asked it to show.
_ACTIVATION_POLL_MS = 300


class TkScheduler:
    """``Scheduler`` for ``TaskManager`` backed by ``after()`` on a Tk widget."""

    def __init__(self, widget: tk.Misc) -> None:
        self._widget = widget

    def schedule(self, delay_ms: int, callback: Callable[[], None]) -> str:
        return self._widget.after(delay_ms, callback)

    def cancel(self, handle: object) -> None:
        try:
            self._widget.after_cancel(str(handle))
        except tk.TclError:
            pass  # The window is already gone (e.g. the atexit flush after closing).


class FlyNotesApp:
    """Top-level controller for the Fly Notes application."""

    def __init__(self, root: tk.Tk, cfg: AppConfig) -> None:
        self._cfg = cfg
        self.root = root
        self.root.title(self._cfg.string("app_title"))
        self.root.overrideredirect(True)
        self.root.config(bg=self._cfg.colors.content_bg, highlightthickness=0, bd=0)
        self.root.attributes("-alpha", self._cfg.transparency.active)
        self._fade_after_id: str | None = None
        self._activation_after_id: str | None = None

        # Data
        self.manager = TaskManager(
            tasks_file=self._cfg.settings.tasks_file,
            error_callback=self._show_error_later,
            scheduler=TkScheduler(self.root),
        )

        # Window geometry: last session's size/position, if still on a monitor
        self._state_file = state_file_for(self._cfg.settings.tasks_file)
        self._initial_geometry = self._restored_geometry()
        self.root.geometry(self._initial_geometry.to_tk())

        # Window controller
        self.window_ctrl = WindowController(
            self.root,
            cfg,
            on_resize_callback=self._on_window_resize,
            on_close=self._on_close,
        )

        # Always on top: last session's choice, else the configured default
        saved_on_top = load_always_on_top(self._state_file)
        self._always_on_top = (
            self._cfg.settings.always_on_top if saved_on_top is None else saved_on_top
        )
        self._apply_always_on_top()

        # Drag state
        self._dragging_item: TaskItem | None = None
        self._drag_start_y: int = 0

        self._build_ui()
        self._bind_events()
        self.window_ctrl.setup_resize_handles(self._cfg.colors.content_bg)
        # The list's canvas starts at default_width; match the restored width.
        self._on_window_resize(self._initial_geometry.width)
        self._load_initial_tasks()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── UI Construction ──────────────────────

    def _build_ui(self) -> None:
        # Header
        self._header = HeaderBar(
            self.root,
            self._cfg,
            on_close=self._on_close,
            on_minimize=self.window_ctrl.minimize_window,
            on_toggle_pin=self.toggle_always_on_top,
            pinned=self._always_on_top,
        )
        self._header.pack(fill="x", side="top")

        # Separator under header
        tk.Frame(
            self.root,
            bg=self._cfg.colors.separator_color,
            height=self._cfg.settings.separator_height,
            bd=0,
        ).pack(fill="x")

        # Footer separator + footer (packed bottom-up)
        self._footer_sep = tk.Frame(
            self.root,
            bg=self._cfg.colors.separator_color,
            height=self._cfg.settings.separator_height,
            bd=0,
        )

        self._footer = FooterBar(
            self.root, self._cfg, on_clear=self._clear_completed, on_undo=self._undo
        )

        # Pack order: footer at bottom, then separator above it
        self._footer.pack(fill="x", side="bottom")
        self._footer_sep.pack(fill="x", side="bottom")

        # Entry
        self._entry_bar = TaskEntryBar(
            self.root,
            self._cfg,
            on_submit=self._add_new_task,
        )
        # Down from the new-task field jumps into the list.
        self._entry_bar.entry_widget.bind("<Down>", lambda _: self._focus_first_task())
        self._entry_bar.pack(
            fill="x",
            padx=self._cfg.spacing.lg,
            pady=(self._cfg.spacing.md, self._cfg.spacing.sm),
        )

        # Separator under entry
        tk.Frame(
            self.root,
            bg=self._cfg.colors.separator_color,
            height=self._cfg.settings.separator_height,
            bd=0,
        ).pack(fill="x", padx=self._cfg.spacing.lg, pady=(self._cfg.spacing.sm, 0))

        # Task list
        self._task_list = TaskListView(self.root, self._cfg)
        self._task_list.pack(fill="both", expand=True)

    # ── Events ───────────────────────────────

    def _bind_events(self) -> None:
        for w in self._header.draggable_widgets:
            self.window_ctrl.bind_drag(w)

        self.root.bind("<FocusIn>", self._on_app_focus_in)
        self.root.bind("<FocusOut>", self._on_app_focus_out)
        self.root.bind("<Map>", lambda _: self._apply_always_on_top())

        # Shortcuts
        self.root.bind(self._cfg.shortcuts.close, lambda _: self._on_close())
        self.root.bind(self._cfg.shortcuts.new_task, lambda _: self._entry_bar.focus_entry())
        self.root.bind(self._cfg.shortcuts.delete_completed, lambda _: self._clear_completed())
        self.root.bind(self._cfg.shortcuts.undo, lambda _: self._undo())
        self.root.bind(self._cfg.shortcuts.edit_task, lambda _: self._edit_current_task())
        self.root.bind(
            self._cfg.shortcuts.toggle_always_on_top, lambda _: self.toggle_always_on_top()
        )

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
        self.root.attributes("-alpha", self._cfg.transparency.active)

    def _on_app_focus_out(self, _event: tk.Event | None = None) -> None:
        # Focus moving between our own widgets also sends FocusOut (then FocusIn), and a
        # quick click elsewhere shouldn't flash the window: fade only if focus stays away.
        self._cancel_fade()
        self._fade_after_id = self.root.after(
            self._cfg.settings.inactive_fade_delay_ms, self._fade_if_inactive
        )

    def _fade_if_inactive(self) -> None:
        self._fade_after_id = None
        try:
            focused = self.root.focus_get()
        except (KeyError, tk.TclError):
            focused = None
        if focused is None:
            self.root.attributes("-alpha", self._cfg.transparency.inactive)

    def _cancel_fade(self) -> None:
        if self._fade_after_id is not None:
            self.root.after_cancel(self._fade_after_id)
            self._fade_after_id = None

    # ── Task CRUD ────────────────────────────

    def _add_new_task(self, text: str) -> None:
        task = self.manager.add_task(text)
        self._create_task_widget(task)
        self._refresh_ui()

    def _create_task_widget(self, task: Task, index: int | None = None) -> TaskItem:
        widget = TaskItem(
            self._task_list.inner_frame,
            self._cfg,
            task_id=task.id,
            text=task.text,
            completed=task.completed,
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
        if self._cfg.settings.confirm_delete:
            ok = messagebox.askyesno(
                self._cfg.string("confirm_delete_title"),
                self._cfg.string("confirm_delete_msg"),
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
        self._footer.show_undo(self._cfg.string("undo_deleted"))
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
        if (
            self._cfg.settings.group_completed
            and target.completed_var.get() != item.completed_var.get()
        ):
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
        self._task_list.sync_order([t.id for t in self.manager.tasks])
        self._task_list.repack()
        return True

    def _change_task_text(self, item: TaskItem, text: str) -> str | None:
        """Save an inline edit; return the stored text, or None to keep the old one."""
        task = self.manager.update_text(
            item.task_id, text, max_length=self._cfg.settings.max_task_length
        )
        return task.text if task else None

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
        self._footer.show_undo(self._cfg.string("undo_cleared", count=count))

    def _undo(self) -> None:
        """Bring back the most recently deleted or cleared task(s) in place."""
        restored = self.manager.undo()
        self._footer.hide_undo()
        if not restored:
            return
        for task in restored:
            self._create_task_widget(task, index=self.manager.index_of(task.id))
        self._refresh_ui()

    # ── Drag-and-drop (model-safe) ───────────

    def _start_reorder(self, item: TaskItem, event: tk.Event) -> None:
        self._dragging_item = item
        self._drag_start_y = event.y_root
        item.set_drag_active(True)
        item.set_bg(self._cfg.colors.drag_highlight)

    def _stop_reorder(self, item: TaskItem, event: tk.Event) -> None:
        if self._dragging_item:
            self._dragging_item.set_drag_active(False)
            self._dragging_item.set_bg(self._cfg.colors.item_bg)
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
            threshold=self._cfg.settings.drag_threshold,
            enforce_group_boundary=self._cfg.settings.group_completed,
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

    def _show_error_later(self, message: str) -> None:
        """Show an error dialog once the event loop is idle.

        Deferred so a load error reported while the window is still being
        built (before ``mainloop``) doesn't open a dialog mid-construction.
        """
        self.root.after(0, lambda: messagebox.showerror(self._cfg.string("app_title"), message))

    def _restored_geometry(self) -> WindowGeometry:
        default = WindowGeometry(
            self._cfg.settings.default_width, self._cfg.settings.default_height, 100, 100
        )
        monitors = monitor_work_areas() or [
            Rect(0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight())
        ]
        return choose_geometry(
            load_geometry(self._state_file),
            default,
            monitors,
            min_width=self._cfg.settings.min_width,
            min_height=self._cfg.settings.min_height,
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
