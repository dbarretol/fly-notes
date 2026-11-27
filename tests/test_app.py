"""FlyNotesApp: the window as a whole, wired to the task store."""

import dataclasses
import json
import logging
import threading
import time
import tkinter as tk
import types
from pathlib import Path
from typing import cast

import pytest

from fly_notes.model.store import TaskManager
from fly_notes.platform.window_state import Rect, WindowGeometry
from fly_notes.ui import app as fly_notes_app
from fly_notes.ui.app import FlyNotesApp, TkScheduler
from fly_notes.ui.task_item import TaskItem
from fly_notes.ui.task_list import TaskListView

# ── Close error handling ──────────────────────


def test_close_logs_save_failure_and_still_closes(app_window, tmp_path, monkeypatch, caplog, cfg):
    app_root = app_window
    app = FlyNotesApp(app_root, cfg)

    def boom():
        raise OSError("disk full")

    monkeypatch.setattr(app.manager, "flush", boom)
    with caplog.at_level(logging.ERROR, logger="fly_notes.ui.app"):
        app._on_close()

    assert "Could not save tasks while closing" in caplog.text
    assert not app_root.winfo_exists()


# ── Escape / shortcuts ────────────────────────


def test_default_close_shortcut_is_not_escape(cfg):
    assert cfg.shortcuts.close != "<Escape>"
    assert not hasattr(cfg.shortcuts, "focus_entry")


def test_escape_while_typing_does_not_close_the_app(app_window, tmp_path, monkeypatch, cfg):
    app_root = app_window
    app = FlyNotesApp(app_root, cfg)
    try:
        app_root.deiconify()  # key events are only delivered to a mapped window
        entry = app._entry_bar.entry_widget
        entry.focus_force()
        app_root.update()
        entry.insert("end", "typing")

        entry.event_generate("<Escape>")
        app_root.update()

        assert app_root.winfo_exists()
        assert app._entry_bar.get_text() == ""
    finally:
        app._on_close()


# ── Drag-and-drop reorder ─────────────────────


def test_do_reorder_regression_respects_grouping(root, tmp_path, cfg):
    """End-to-end regression for the reported bug: A(pend), B(done),
    C(pend), dragging C above A must yield model order [C, A, B] —
    not [A, C, B], which is what the old insertion-order-based
    _do_reorder produced."""
    manager = TaskManager(tasks_file=str(tmp_path / "tasks.json"))
    task_a = manager.add_task("A")
    task_b = manager.add_task("B", completed=True)
    task_c = manager.add_task("C")

    task_list = TaskListView(root, cfg)
    widgets = {}
    for t in (task_a, task_b, task_c):
        w = TaskItem(
            task_list.inner_frame,
            cfg,
            task_id=t.id,
            text=t.text,
            completed=t.completed,
        )
        task_list.add_widget(w)
        widgets[t.text] = w
    task_list.repack()

    app = FlyNotesApp.__new__(FlyNotesApp)
    app._cfg = cfg
    app.manager = manager
    app._task_list = task_list
    app._dragging_item = widgets["C"]
    app._drag_start_y = 1000

    event = cast(tk.Event, types.SimpleNamespace(y_root=1000 - cfg.settings.drag_threshold - 1))
    app._do_reorder(widgets["C"], event)

    assert [t.text for t in manager.tasks] == ["C", "A", "B"]

    for w in widgets.values():
        w.destroy()
    task_list.destroy()


# ── Undo delete (#9) ──────────────────────────


def _app_with_tasks(app_window, cfg, tasks):
    tasks_file = Path(cfg.settings.tasks_file)
    tasks_file.write_text(json.dumps(tasks), encoding="utf-8")
    return FlyNotesApp(app_window, cfg)


def _widget_state(app):
    return [(w.task_id, w.completed_var.get()) for w in app._task_list.task_widgets]


def _model_state(app):
    return [(t.id, t.completed) for t in app.manager.tasks]


SAMPLE_TASKS = [
    {"id": "a", "text": "A", "completed": False},
    {"id": "b", "text": "B", "completed": True},
    {"id": "c", "text": "C", "completed": False},
    {"id": "d", "text": "D", "completed": True},
]


def test_delete_then_undo_restores_the_same_list_and_order(app_window, tmp_path, monkeypatch, cfg):
    app = _app_with_tasks(app_window, cfg, SAMPLE_TASKS)
    try:
        before = _widget_state(app)
        target = next(w for w in app._task_list.task_widgets if w.task_id == "c")

        app._delete_task(target)
        assert app._footer.undo_visible
        assert app._footer._undo_msg.cget("text") == cfg.string("undo_deleted")
        assert "c" not in [w.task_id for w in app._task_list.task_widgets]

        app._undo()

        assert _widget_state(app) == before
        assert _model_state(app) == before
        assert not app._footer.undo_visible
    finally:
        app._on_close()


def test_clear_completed_needs_no_dialog_and_can_be_undone(app_window, tmp_path, monkeypatch, cfg):

    def no_dialogs(*args, **kwargs):
        raise AssertionError("clear completed must not ask for confirmation")

    monkeypatch.setattr(fly_notes_app.messagebox, "askyesno", no_dialogs)
    app = _app_with_tasks(app_window, cfg, SAMPLE_TASKS)
    try:
        before = _widget_state(app)

        app._clear_completed()
        assert [w.task_id for w in app._task_list.task_widgets] == ["a", "c"]
        assert app._footer._undo_msg.cget("text") == cfg.string("undo_cleared", count=2)

        app._undo()
        assert _widget_state(app) == before
        assert _model_state(app) == before
    finally:
        app._on_close()


def test_undo_shortcut_is_bound_and_noop_without_history(app_window, tmp_path, monkeypatch, cfg):
    app = _app_with_tasks(app_window, cfg, SAMPLE_TASKS)
    try:
        assert cfg.shortcuts.undo == "<Control-z>"
        assert app.root.bind(cfg.shortcuts.undo)
        before = _widget_state(app)
        app._undo()
        assert _widget_state(app) == before
    finally:
        app._on_close()


def test_undo_notice_hides_itself_after_the_timeout(app_window, tmp_path, monkeypatch, cfg):
    cfg = cfg.with_settings(undo_timeout_ms=10)
    app = _app_with_tasks(app_window, cfg, SAMPLE_TASKS)
    try:
        app._delete_task(app._task_list.task_widgets[0])
        assert app._footer.undo_visible

        deadline = time.monotonic() + 2
        while app._footer.undo_visible and time.monotonic() < deadline:
            app.root.update()
        assert not app._footer.undo_visible
        # The undo itself stays available (Ctrl+Z) after the notice is gone.
        assert app.manager.can_undo
    finally:
        app._on_close()


def test_clicking_undo_in_the_footer_restores_the_task(app_window, tmp_path, monkeypatch, cfg):
    app = _app_with_tasks(app_window, cfg, SAMPLE_TASKS)
    try:
        before = _widget_state(app)
        app._delete_task(app._task_list.task_widgets[0])
        app._footer._undo_clicked()
        assert _widget_state(app) == before
    finally:
        app._on_close()


# ── Inline edit (#10) ─────────────────────────


def test_inline_edit_is_saved_to_the_model(app_window, tmp_path, monkeypatch, cfg):
    app = _app_with_tasks(app_window, cfg, SAMPLE_TASKS)
    try:
        item = app._task_list.task_widgets[0]
        item.begin_edit()
        editor = item._editor
        assert editor is not None
        editor.delete(0, tk.END)
        editor.insert(0, "A edited")
        item.commit_edit()

        task = app.manager.task_by_id("a")
        assert task is not None
        assert task.text == "A edited"
        assert item._label.cget("text") == "A edited"
    finally:
        app._on_close()


def test_f2_edits_the_hovered_task(app_window, tmp_path, monkeypatch, cfg):
    app = _app_with_tasks(app_window, cfg, SAMPLE_TASKS)
    try:
        assert cfg.shortcuts.edit_task == "<F2>"
        assert app.root.bind(cfg.shortcuts.edit_task)
        app_window.deiconify()
        app_window.update()
        target = app._task_list.task_widgets[2]
        target._is_hovered = True

        app._edit_current_task()

        assert target.is_editing
        assert not any(w.is_editing for w in app._task_list.task_widgets if w is not target)
    finally:
        app._on_close()


def test_f2_without_a_target_does_nothing(app_window, tmp_path, monkeypatch, cfg):
    app = _app_with_tasks(app_window, cfg, SAMPLE_TASKS)
    try:
        app._edit_current_task()
        assert not any(w.is_editing for w in app._task_list.task_widgets)
    finally:
        app._on_close()


# ── Remember window geometry (#11) ────────────


def test_window_geometry_is_saved_on_close_and_restored(
    app_window, root, tmp_path, monkeypatch, cfg
):

    monkeypatch.setattr(fly_notes_app, "monitor_work_areas", lambda: [Rect(0, 0, 1920, 1040)])
    app = FlyNotesApp(app_window, cfg)
    app_window.deiconify()  # Tk applies a new size only to a mapped window
    app_window.geometry("410x520+333+222")
    app_window.update()
    app_window.withdraw()  # like minimizing: the last geometry must still be saved
    app._on_close()

    saved = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))["window"]
    assert saved == {"width": 410, "height": 520, "x": 333, "y": 222}

    second = tk.Toplevel(root)
    second.withdraw()
    try:
        app2 = FlyNotesApp(second, cfg)
        second.update_idletasks()
        assert WindowGeometry.from_tk(second.wm_geometry()) == WindowGeometry(410, 520, 333, 222)
        assert int(app2._task_list._canvas.itemcget(app2._task_list._canvas_win_id, "width")) == 410
        app2._on_close()
    finally:
        if second.winfo_exists():
            second.destroy()


def test_off_screen_saved_geometry_opens_at_the_default(app_window, tmp_path, monkeypatch, cfg):

    monkeypatch.setattr(fly_notes_app, "monitor_work_areas", lambda: [Rect(0, 0, 1920, 1040)])
    (tmp_path / "state.json").write_text(
        json.dumps({"window": {"width": 410, "height": 520, "x": 5000, "y": 200}}),
        encoding="utf-8",
    )
    app = FlyNotesApp(app_window, cfg)
    try:
        app_window.update_idletasks()
        expected = WindowGeometry(cfg.settings.default_width, cfg.settings.default_height, 100, 100)
        assert WindowGeometry.from_tk(app_window.wm_geometry()) == expected
    finally:
        app._on_close()


def test_failing_to_save_geometry_still_closes(app_window, tmp_path, monkeypatch, caplog, cfg):

    def boom(*args):
        raise OSError("read-only")

    monkeypatch.setattr(fly_notes_app, "save_geometry", boom)
    app = FlyNotesApp(app_window, cfg)
    with caplog.at_level(logging.ERROR, logger="fly_notes.ui.app"):
        app._on_close()

    assert "Could not save the window position" in caplog.text
    assert not app_window.winfo_exists()


# ── Always on top and inactive fade (#14) ─────


def _topmost(win):
    return bool(int(win.attributes("-topmost")))


def test_pin_button_toggles_always_on_top(app_window, tmp_path, monkeypatch, cfg):
    app = FlyNotesApp(app_window, cfg)
    try:
        assert app.always_on_top and _topmost(app_window)
        assert app._header.pin_text == cfg.string("btn_pin_on")

        app._header._pin_btn.invoke()
        assert not app.always_on_top
        assert not _topmost(app_window)
        assert not app.window_ctrl.always_on_top  # restoring from the taskbar keeps it off
        assert app._header.pin_text == cfg.string("btn_pin_off")

        app.toggle_always_on_top()  # what Ctrl+T calls
        assert app.always_on_top and _topmost(app_window)
        assert app_window.bind(cfg.shortcuts.toggle_always_on_top)
    finally:
        app._on_close()


def test_mapping_the_window_no_longer_forces_it_on_top(app_window, tmp_path, monkeypatch, cfg):
    app = FlyNotesApp(app_window, cfg)
    try:
        app.toggle_always_on_top()
        app_window.event_generate("<Map>")
        assert not _topmost(app_window)
    finally:
        app._on_close()


def test_always_on_top_choice_is_remembered(app_window, root, tmp_path, monkeypatch, cfg):
    app = FlyNotesApp(app_window, cfg)
    app.toggle_always_on_top()
    app._on_close()

    second = tk.Toplevel(root)
    second.withdraw()
    try:
        app2 = FlyNotesApp(second, cfg)
        assert not app2.always_on_top
        assert not _topmost(second)
        assert app2._header.pin_text == cfg.string("btn_pin_off")
        app2._on_close()
    finally:
        if second.winfo_exists():
            second.destroy()


def test_always_on_top_default_comes_from_config(app_window, tmp_path, monkeypatch, cfg):
    cfg = cfg.with_settings(always_on_top=False)
    app = FlyNotesApp(app_window, cfg)
    try:
        assert not app.always_on_top and not _topmost(app_window)
    finally:
        app._on_close()


def test_default_inactive_opacity_is_readable(cfg):
    assert cfg.transparency.inactive >= 0.7


def _alpha(win):
    return round(float(win.attributes("-alpha")), 2)


def test_window_fades_only_after_focus_stays_away(app_window, tmp_path, monkeypatch, cfg):
    app = FlyNotesApp(app_window, cfg)
    try:
        monkeypatch.setattr(app_window, "focus_get", lambda: None)  # focus left the app
        app._on_app_focus_out()
        assert _alpha(app_window) == round(cfg.transparency.active, 2)  # not yet: fade is delayed
        assert app._fade_after_id is not None

        app._fade_if_inactive()  # the delay elapses
        assert _alpha(app_window) == round(cfg.transparency.inactive, 2)

        app._on_app_focus_in()
        assert _alpha(app_window) == round(cfg.transparency.active, 2)
    finally:
        app._on_close()


def test_focus_moving_inside_the_window_does_not_fade_it(app_window, tmp_path, monkeypatch, cfg):
    app = FlyNotesApp(app_window, cfg)
    try:
        # e.g. entry -> task row: FocusOut then FocusIn
        app._on_app_focus_out()
        app._on_app_focus_in()
        assert app._fade_after_id is None

        # focus still on one of our widgets when the delay elapses
        monkeypatch.setattr(app_window, "focus_get", lambda: app._entry_bar.entry_widget)
        app._on_app_focus_out()
        app._fade_if_inactive()
        assert _alpha(app_window) == round(cfg.transparency.active, 2)
    finally:
        app._on_close()


# ── Single instance (#15) ─────────────────────


def test_activation_request_brings_the_window_to_the_front(app_window, tmp_path, monkeypatch, cfg):
    app = FlyNotesApp(app_window, cfg)
    shown = []
    monkeypatch.setattr(app.window_ctrl, "bring_to_front", lambda: shown.append(True))
    requests = iter([False, True])
    try:
        app.listen_for_activation(lambda: next(requests, False))
        assert shown == []  # first poll: no request
        app._poll_activation()  # next poll: a second launch asked to show
        assert shown == [True]
        assert app._activation_after_id is not None  # keeps listening
    finally:
        app._on_close()
    assert app._activation_after_id is None


def test_bring_to_front_restores_a_minimized_window(app_window, tmp_path, monkeypatch, cfg):
    app = FlyNotesApp(app_window, cfg)
    try:
        app.toggle_always_on_top()  # off: surfacing must not leave it pinned
        app.window_ctrl.minimize_window()
        assert app_window.state() == "withdrawn"

        app.window_ctrl.bring_to_front()
        app_window.update()
        assert app_window.state() == "normal"
        assert not app.window_ctrl._was_minimized
        assert not _topmost(app_window)
    finally:
        app._on_close()


# ── Keyboard navigation (#13) ─────────────────


NAV_TASKS = [
    {"id": "a", "text": "A", "completed": False},
    {"id": "b", "text": "B", "completed": True},
    {"id": "c", "text": "C", "completed": False},
    {"id": "d", "text": "D", "completed": False},
]


@pytest.fixture
def nav_app(app_window, tmp_path, monkeypatch, cfg):
    """App with NAV_TASKS; records where keyboard focus is sent instead of
    relying on real OS focus (unreliable for a test window)."""
    app = _app_with_tasks(app_window, cfg, NAV_TASKS)
    focused = []
    monkeypatch.setattr(app, "_focus_task", focused.append)
    monkeypatch.setattr(app._entry_bar, "focus_entry", lambda: focused.append("entry"))
    yield app, focused
    app._on_close()


def _row(app, task_id):
    return next(w for w in app._task_list.task_widgets if w.task_id == task_id)


def _ids(widgets):
    return [w.task_id for w in widgets]


def test_rows_are_focusable_and_bind_the_navigation_keys(nav_app):
    app, _ = nav_app
    canvas = _row(app, "a")._card_canvas
    assert int(canvas.cget("takefocus")) == 1
    for key in ("<Up>", "<Down>", "<Alt-Up>", "<Alt-Down>", "<space>", "<Delete>", "<F2>"):
        assert canvas.bind(key), key


def test_arrow_keys_move_focus_through_rows_in_visual_order(nav_app):
    app, focused = nav_app
    # Visual order with grouping: a, c, d (to do) then b (completed)
    assert _ids(app._task_list.packed_order()) == ["a", "c", "d", "b"]

    assert _row(app, "a")._navigate(1) == "break"
    assert _row(app, "d")._navigate(1) == "break"
    _row(app, "b")._navigate(1)  # last row: nowhere to go
    _row(app, "a")._navigate(-1)  # first row: back to the entry

    assert [f if f == "entry" else f.task_id for f in focused] == ["c", "b", "entry"]


def test_down_in_the_entry_focuses_the_first_row(nav_app):
    app, focused = nav_app
    assert app._focus_first_task() == "break"
    assert _ids(focused) == ["a"]
    assert app._entry_bar.entry_widget.bind("<Down>")


def test_space_toggles_the_focused_row(nav_app):
    app, _ = nav_app
    row = _row(app, "a")
    assert row._key_toggle() == "break"
    assert row.completed_var.get() is True
    assert app.manager.task_by_id("a").completed is True


def test_delete_key_removes_the_row_moves_focus_and_is_undoable(nav_app):
    app, focused = nav_app
    row = _row(app, "c")
    row._has_focus = True

    assert row._key_delete() == "break"

    assert "c" not in _ids(app._task_list.task_widgets)
    assert _ids(focused) == ["d"]
    assert app._footer.undo_visible
    app._undo()
    assert _ids(app._task_list.task_widgets) == ["a", "b", "c", "d"]


def test_deleting_the_last_focused_row_focuses_the_previous_one(nav_app):
    app, focused = nav_app
    row = _row(app, "b")  # last in visual order
    row._has_focus = True
    row._key_delete()
    assert _ids(focused) == ["d"]


def test_alt_arrows_reorder_within_the_group_and_keep_model_and_widgets_in_sync(nav_app):
    app, focused = nav_app
    assert _row(app, "d")._move(-1) == "break"  # d above c

    assert _ids(app._task_list.visual_order()) == ["a", "d", "c", "b"]
    assert _ids(app._task_list.task_widgets) == [t.id for t in app.manager.tasks]
    assert _ids(focused) == ["d"]


def test_alt_arrows_never_cross_the_group_boundary(nav_app):
    app, _ = nav_app
    before = [t.id for t in app.manager.tasks]
    _row(app, "d")._move(1)  # next visual row is the completed "b"
    _row(app, "b")._move(-1)
    _row(app, "a")._move(-1)  # already first
    assert [t.id for t in app.manager.tasks] == before


def test_reorder_across_hidden_group_keeps_widget_order_equal_to_model(nav_app):
    """Moving c above a jumps over the completed b in the model (pop+insert);
    the old widget *swap* left the widget order out of step with the model,
    which broke restoring a deleted task at its model index (#9)."""
    app, _ = nav_app
    _row(app, "c")._move(-1)

    model = [t.id for t in app.manager.tasks]
    assert _ids(app._task_list.task_widgets) == model

    # Deleting and undoing still restores the exact same order.
    app._delete_task(_row(app, "b"))
    app._undo()
    assert _ids(app._task_list.task_widgets) == model


# ── Closing from the taskbar ──────────────────


def test_closing_from_taskbar_flushes_pending_save(app_window, tmp_path, monkeypatch, cfg):
    """A change made right before closing via the taskbar entry must reach
    disk, even though saves are debounced."""
    tasks_file = tmp_path / "tasks.json"
    app_root = app_window
    app = FlyNotesApp(app_root, cfg)
    app.manager.SAVE_DELAY_MS = 60_000  # make sure only the close path can write
    app.manager.add_task("written just before closing")
    assert not tasks_file.exists()

    app.window_ctrl._on_proxy_close()

    saved = json.loads(tasks_file.read_text(encoding="utf-8"))
    assert [t["text"] for t in saved] == ["written just before closing"]


# ── Saves scheduled with Tk's after() (#19) ───


def test_app_saves_through_tk_after_on_the_main_thread(app_window, tmp_path, monkeypatch, cfg):

    tasks_file = tmp_path / "tasks.json"
    app = FlyNotesApp(app_window, cfg)
    app.manager.SAVE_DELAY_MS = 10
    threads_before = threading.active_count()

    app.manager.add_task("saved by after()")
    assert threading.active_count() == threads_before  # no timer thread
    assert not tasks_file.exists()

    deadline = time.monotonic() + 5
    while not tasks_file.exists() and time.monotonic() < deadline:
        app_window.update()
        time.sleep(0.01)

    saved = json.loads(tasks_file.read_text(encoding="utf-8"))
    assert [t["text"] for t in saved] == ["saved by after()"]


def test_tk_scheduler_cancel_survives_a_destroyed_window(root):

    win = tk.Toplevel(root)
    scheduler = TkScheduler(win)
    fired = []
    handle = scheduler.schedule(10_000, lambda: fired.append(True))
    scheduler.cancel(handle)
    win.destroy()
    scheduler.cancel(handle)  # e.g. the atexit flush after the window closed
    assert fired == []


# ── Config values that used to be ignored or crash (#18) ───


def test_a_shortcut_tk_rejects_falls_back_to_the_default(app_window, cfg, caplog):
    bad = dataclasses.replace(cfg, shortcuts=dataclasses.replace(cfg.shortcuts, undo="<NoSuchKey>"))
    with caplog.at_level(logging.WARNING, logger="fly_notes.ui.app"):
        FlyNotesApp(app_window, bad)  # used to raise TclError on startup
    assert "shortcuts.undo" in caplog.text
    assert app_window.bind("<Control-z>")
    assert app_window.bind(cfg.shortcuts.new_task)  # the others are still bound


# ── Lazy rows (#26) ───────────────────────────

MANY_TASKS = [{"id": str(i), "text": f"T{i}", "completed": i % 2 == 1} for i in range(10)]


def test_startup_builds_only_the_rows_it_shows(app_window, cfg):
    app = _app_with_tasks(app_window, cfg.with_settings(max_visible_tasks=3), MANY_TASKS)
    assert app._task_list.row_count == 10
    assert [w.task_id for w in app._task_list.task_widgets] == ["0", "2", "4"]


def test_clear_completed_also_removes_rows_never_built(app_window, cfg):
    app = _app_with_tasks(app_window, cfg.with_settings(max_visible_tasks=3), MANY_TASKS)
    app._clear_completed()
    assert app._task_list.row_count == 5
    assert all(not r.completed_var.get() for r in app._task_list.visual_order())

    app._undo()
    assert app._task_list.row_count == 10
    assert [r.task_id for r in app._task_list.visual_order()] == [
        str(i) for i in (0, 2, 4, 6, 8, 1, 3, 5, 7, 9)
    ]


def test_moving_the_last_shown_row_past_the_cap(app_window, cfg):
    app = _app_with_tasks(app_window, cfg.with_settings(max_visible_tasks=3), MANY_TASKS)
    last = app._task_list.packed_order()[-1]
    assert last.task_id == "4"

    app._move_task(last, +1)  # swaps with "6", whose row was never built

    assert [t.id for t in app.manager.tasks if not t.completed] == ["0", "2", "6", "4", "8"]
    assert [w.task_id for w in app._task_list.packed_order()] == ["0", "2", "6"]
