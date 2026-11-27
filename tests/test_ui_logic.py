import json
import logging
import time
import tkinter as tk
import types
from pathlib import Path

import pytest

from fly_notes import window_controller as window_controller_module
from fly_notes.config import ICON_PATH, config
from fly_notes.fly_notes_app import (
    FlyNotesApp,
    TaskEntryBar,
    TaskListView,
    blend_alpha_hex,
    compute_reorder_target,
)
from fly_notes.task_item import TaskItem
from fly_notes.task_manager import TaskManager
from fly_notes.window_controller import WindowController
from fly_notes.window_state import Rect, WindowGeometry


@pytest.fixture(scope="session")
def root():
    r = tk.Tk()
    r.withdraw()
    yield r
    r.destroy()


@pytest.fixture
def app_window(root):
    """A fresh window to host a full FlyNotesApp.

    A Toplevel of the shared root, never a second ``tk.Tk()``: creating
    another Tcl interpreter under pytest's output capture intermittently fails
    on Windows with "Can't find a usable init.tcl".
    """
    win = tk.Toplevel(root)
    win.withdraw()
    yield win
    if win.winfo_exists():
        win.destroy()


# ── Close error handling ─────────────────────


def test_close_logs_save_failure_and_still_closes(app_window, tmp_path, monkeypatch, caplog):
    monkeypatch.setitem(config._attr_cache, "tasks_file", str(tmp_path / "tasks.json"))
    app_root = app_window
    app = FlyNotesApp(app_root)

    def boom():
        raise OSError("disk full")

    monkeypatch.setattr(app.manager, "flush", boom)
    with caplog.at_level(logging.ERROR, logger="fly_notes.fly_notes_app"):
        app._on_close()

    assert "Could not save tasks while closing" in caplog.text
    assert not app_root.winfo_exists()


# ── Escape / shortcuts ───────────────────────


def test_default_close_shortcut_is_not_escape():
    assert config.shortcut_close != "<Escape>"
    assert "focus_entry" not in config._data["shortcuts"]


def test_escape_in_entry_clears_text_and_restores_placeholder(root):
    submitted = []
    bar = TaskEntryBar(root, on_submit=submitted.append)
    bar.pack()
    bar.focus_entry()
    bar.entry_widget.insert(0, "half-typed task")

    result = bar._cancel()

    assert result == "break"
    assert bar.get_text() == ""
    assert bar.entry_widget.get() == config.string("entry_placeholder")
    assert submitted == []
    bar.destroy()


def test_escape_while_typing_does_not_close_the_app(app_window, tmp_path, monkeypatch):
    monkeypatch.setitem(config._attr_cache, "tasks_file", str(tmp_path / "tasks.json"))
    app_root = app_window
    app = FlyNotesApp(app_root)
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


def test_task_item_initial_state(root):
    item = TaskItem(root, task_id="123", text="Test Task", completed=False)
    assert item.task_id == "123"
    assert item.task_text == "Test Task"
    assert item.completed_var.get() is False
    # Check initial label style
    assert item.label.cget("text") == "Test Task"
    assert item.label.cget("fg") == config.text_primary
    item.destroy()


def test_task_item_toggle_style(root):
    item = TaskItem(root, task_id="123", text="Test Task", completed=False)

    # Simulate status change
    item.check.checked = True
    item._handle_status_change()

    assert item.completed_var.get() is True
    assert item.label.cget("fg") == config.text_completed

    item.destroy()


def test_task_item_drag_callbacks(root):
    start_called = False
    stop_called = False

    def on_start(item, event):
        nonlocal start_called
        start_called = True

    def on_stop(item, event):
        nonlocal stop_called
        stop_called = True

    item = TaskItem(
        root, task_id="123", text="Drag Task", on_drag_start=on_start, on_drag_stop=on_stop
    )

    item._start_drag(None)
    assert start_called is True

    item._stop_drag(None)
    assert stop_called is True
    item.destroy()


def test_task_item_hover_logic(root):
    item = TaskItem(root, task_id="123", text="Hover Task")

    # Test enter
    item._on_enter()
    assert item._is_hovered is True
    assert item._delete_visible is True

    # Test leave (pointer inside, so should remain hovered)
    # Mocking pointer_still_inside because it's hard to test GUI coordinates
    item._pointer_still_inside = lambda: True
    item._on_leave()
    assert item._is_hovered is True

    # Test actual leave
    item._pointer_still_inside = lambda: False
    item._on_leave()
    assert item._is_hovered is False
    assert item._delete_visible is False

    item.destroy()


# ── Drag-and-drop reorder (Issue #1) ─────────


def test_compute_reorder_target_uses_visual_order_not_insertion_order():
    """A(pend), B(done), C(pend) in insertion order render visually as
    [A, C, B] when grouped. Dragging C up past A should target A —
    not B, which is C's raw-insertion-order neighbor."""
    visual_ids = ["A", "C", "B"]
    visual_completed = [False, False, True]

    target = compute_reorder_target(
        visual_ids,
        visual_completed,
        dragging_id="C",
        delta_y=-(config.drag_threshold + 1),
        threshold=config.drag_threshold,
        enforce_group_boundary=True,
    )
    assert target == "A"


def test_compute_reorder_target_stops_at_group_boundary():
    """Dragging the first completed item further up (into the pending
    group) must not swap across the boundary."""
    visual_ids = ["A", "C", "B"]
    visual_completed = [False, False, True]

    target = compute_reorder_target(
        visual_ids,
        visual_completed,
        dragging_id="B",
        delta_y=-(config.drag_threshold + 1),
        threshold=config.drag_threshold,
        enforce_group_boundary=True,
    )
    assert target is None


def test_do_reorder_regression_respects_grouping(root, tmp_path):
    """End-to-end regression for the reported bug: A(pend), B(done),
    C(pend), dragging C above A must yield model order [C, A, B] —
    not [A, C, B], which is what the old insertion-order-based
    _do_reorder produced."""
    manager = TaskManager(tasks_file=str(tmp_path / "tasks.json"))
    task_a = manager.add_task("A")
    task_b = manager.add_task("B", completed=True)
    task_c = manager.add_task("C")

    task_list = TaskListView(root)
    widgets = {}
    for t in (task_a, task_b, task_c):
        w = TaskItem(
            task_list.inner_frame,
            task_id=t["id"],
            text=t["text"],
            completed=t["completed"],
        )
        task_list.add_widget(w)
        widgets[t["text"]] = w
    task_list.repack()

    app = FlyNotesApp.__new__(FlyNotesApp)
    app.manager = manager
    app._task_list = task_list
    app._dragging_item = widgets["C"]
    app._drag_start_y = 1000

    event = types.SimpleNamespace(y_root=1000 - config.drag_threshold - 1)
    app._do_reorder(widgets["C"], event)

    assert [t["text"] for t in manager.tasks] == ["C", "A", "B"]

    for w in widgets.values():
        w.destroy()
    task_list.destroy()


# ── max_visible_tasks (Issue #2) ─────────────


def test_repack_caps_rendered_rows_to_max_visible_tasks(root):
    """With max_visible_tasks=3 and 5 tasks loaded, at most 3 task rows
    are actually packed (rendered) — the rest stay unpacked, with a
    '+N more' indicator instead."""
    task_list = TaskListView(root)
    widgets = []
    for i in range(5):
        w = TaskItem(task_list.inner_frame, task_id=str(i), text=f"Task {i}")
        task_list.add_widget(w)
        widgets.append(w)

    original_limit = config._data["settings"]["max_visible_tasks"]
    config._data["settings"]["max_visible_tasks"] = 3
    config._attr_cache.pop("max_visible_tasks", None)  # __getattr__ caches by name
    try:
        task_list.repack()
        packed = [w for w in widgets if w.winfo_manager()]
        assert len(packed) == 3
        assert packed == widgets[:3]

        indicator_texts = [
            w.cget("text") for w in task_list._transient_widgets if isinstance(w, tk.Label)
        ]
        assert config.string("more_hidden", count=2) in indicator_texts
    finally:
        config._data["settings"]["max_visible_tasks"] = original_limit
        config._attr_cache.pop("max_visible_tasks", None)
        for w in widgets:
            w.destroy()
        task_list.destroy()


# ── Resize callback width (Issue #5) ─────────


def test_resize_callback_receives_width_without_stale_reread(root):
    """Regression for the winfo_width()-lag issue: immediately after
    root.geometry(...), winfo_width() reliably returns the *previous*
    width until Tk processes the pending configure request (empirically
    confirmed: ~399/400 mismatches in a tight resize loop without
    update_idletasks()). The fix has
    WindowController hand the freshly computed width to the resize
    callback directly instead of the callback re-reading root."""
    received = []
    ctrl = WindowController(root, on_resize_callback=received.append)
    try:
        # A withdrawn window's geometry is never negotiated by the WM, so
        # winfo_width() would report a meaningless placeholder regardless
        # of update_idletasks(). Deiconify to reproduce the real scenario
        # (the app's root window is always mapped/visible).
        root.deiconify()
        root.geometry("320x440+100+100")
        root.update_idletasks()

        ctrl._start_resize("e", types.SimpleNamespace(x_root=500, y_root=500))
        ctrl._do_resize(types.SimpleNamespace(x_root=560, y_root=500))  # +60px east

        assert received == [380]

        root.update_idletasks()
        assert root.winfo_width() == 380
    finally:
        root.withdraw()
        ctrl._proxy.destroy()


# ── Scroll affordance ────────────────────────


def test_blend_alpha_hex_flattens_alpha_onto_background():
    """shadow_color (#00000015, ~8% black) over a white background should
    land close to white, tinted slightly darker — not pure black and not
    unchanged."""
    result = blend_alpha_hex("#00000015", "#FFFFFF")
    r, g, b = int(result[1:3], 16), int(result[3:5], 16), int(result[5:7], 16)
    assert r == g == b
    assert 220 < r < 255  # slightly darkened, not unchanged, not black


def test_blend_alpha_hex_passes_through_opaque_colors():
    assert blend_alpha_hex("#B35C00", "#FFFFFF") == "#B35C00"


def test_scrollbar_activates_when_content_exceeds_visible_height(root):
    """With enough tasks to overflow a short window, the scrollbar must
    become visible (packed): with 11+ tasks the scrollbar used to be
    barely perceptible."""
    win = tk.Toplevel(root)
    try:
        win.geometry("320x150+0+0")
        task_list = TaskListView(win)
        task_list.pack(fill="both", expand=True)
        win.update_idletasks()

        widgets = []
        for i in range(20):
            w = TaskItem(task_list.inner_frame, task_id=str(i), text=f"Task {i}")
            task_list.add_widget(w)
            widgets.append(w)
        task_list.repack()
        win.update_idletasks()

        assert task_list._scrollbar_visible is True
        assert task_list._scrollbar.winfo_manager() == "pack"

        for w in widgets:
            w.destroy()
        task_list.destroy()
    finally:
        win.destroy()


def test_scrollbar_stays_hidden_when_content_fits(root):
    win = tk.Toplevel(root)
    try:
        win.geometry("320x440+0+0")
        task_list = TaskListView(win)
        task_list.pack(fill="both", expand=True)
        win.update_idletasks()

        widgets = []
        for i in range(2):
            w = TaskItem(task_list.inner_frame, task_id=str(i), text=f"Task {i}")
            task_list.add_widget(w)
            widgets.append(w)
        task_list.repack()
        win.update_idletasks()

        assert task_list._scrollbar_visible is False

        for w in widgets:
            w.destroy()
        task_list.destroy()
    finally:
        win.destroy()


def test_scroll_increment_matches_task_row_height_to_prevent_split_rows(root):
    """yscrollincrement must equal a whole task row's footprint, so Tk's
    canvas can never leave a row rendered half-visible at the viewport
    edge (the last row used to be cut in half with no affordance)."""
    win = tk.Toplevel(root)
    try:
        win.geometry("320x150+0+0")
        task_list = TaskListView(win)
        task_list.pack(fill="both", expand=True)

        widgets = []
        for i in range(10):
            w = TaskItem(task_list.inner_frame, task_id=str(i), text=f"Task {i}")
            task_list.add_widget(w)
            widgets.append(w)
        task_list.repack()
        win.update_idletasks()

        expected = min(w.winfo_reqheight() for w in widgets) + 2 * config.spacing_xs
        assert int(task_list._canvas["yscrollincrement"]) == expected

        for w in widgets:
            w.destroy()
        task_list.destroy()
    finally:
        win.destroy()


# ── Rounded card + shadow ────────────────────


def test_task_item_card_canvas_gets_real_size_and_draws_rounded_shapes(root):
    """Regression for 'border_radius/shadow_color declared but never
    applied': the card canvas must end up with a real pixel size and both
    the shadow + main rounded rect drawn (14 tagged shapes: 2 x [4 arcs +
    2 fill rects + 1 border rect])."""
    win = tk.Toplevel(root)
    try:
        win.geometry("320x100+0+0")
        item = TaskItem(win, task_id="1", text="Sample task")
        item.pack(fill="x")
        win.update_idletasks()

        assert item.card_canvas.winfo_width() > 1
        assert item.card_canvas.winfo_height() > 1
        assert len(item.card_canvas.find_withtag("card")) == 14

        item.destroy()
    finally:
        win.destroy()


def test_task_item_hover_and_status_change_update_card_fill(root):
    win = tk.Toplevel(root)
    try:
        win.geometry("320x100+0+0")
        item = TaskItem(win, task_id="1", text="Sample task")
        item.pack(fill="x")
        win.update_idletasks()

        assert item._card_fill == config.item_bg

        item._on_enter()
        assert item._card_fill == config.drag_highlight_color

        item._on_leave()
        assert item._card_fill == config.item_bg

        item.check.checked = True
        item._handle_status_change()
        assert item._card_fill == config.item_bg_completed

        item.destroy()
    finally:
        win.destroy()


def test_task_item_drag_active_toggles_outline_without_error(root):
    win = tk.Toplevel(root)
    try:
        win.geometry("320x100+0+0")
        item = TaskItem(win, task_id="1", text="Sample task")
        item.pack(fill="x")
        win.update_idletasks()

        item.set_drag_active(True)
        assert item._drag_active is True
        item.set_drag_active(False)
        assert item._drag_active is False

        item.destroy()
    finally:
        win.destroy()


def test_task_item_card_resizes_with_row_width(root):
    """The card canvas must track the row's actual allotted width (not
    just its own natural label-text width) -- otherwise the rounded card
    wouldn't stretch to fill the list the way the old square row did."""
    win = tk.Toplevel(root)
    try:
        win.geometry("320x100+0+0")
        canvas = tk.Canvas(win, highlightthickness=0, bd=0)
        canvas.pack(fill="both", expand=True)
        inner = tk.Frame(canvas)
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw", width=320)

        item = TaskItem(inner, task_id="1", text="Sample task")
        item.pack(fill="x")
        win.update()

        narrow_width = item.card_canvas.winfo_width()

        canvas.itemconfigure(win_id, width=500)
        win.update()

        assert item.card_canvas.winfo_width() > narrow_width

        item.destroy()
    finally:
        win.destroy()


# ── Long task text wraps (#8) ────────────────

LONG_TEXT = " ".join(["wrapping"] * 25)  # ~225 characters


def _item_in_list_of_width(root, text, width):
    """A TaskItem inside a canvas-window inner frame, like TaskListView's rows."""
    win = tk.Toplevel(root)
    win.geometry(f"{width}x400+0+0")
    canvas = tk.Canvas(win, highlightthickness=0, bd=0)
    canvas.pack(fill="both", expand=True)
    inner = tk.Frame(canvas)
    win_id = canvas.create_window((0, 0), window=inner, anchor="nw", width=width)
    item = TaskItem(inner, task_id="1", text=text)
    item.pack(fill="x")
    win.update()
    return win, canvas, win_id, item


def test_long_task_text_wraps_to_fit_the_default_width(root):
    win, _, _, item = _item_in_list_of_width(root, LONG_TEXT, config.default_width)
    try:
        short_win, _, _, short_item = _item_in_list_of_width(root, "Short", config.default_width)
        try:
            short_height = short_item.card_canvas.winfo_height()
        finally:
            short_win.destroy()

        wrap = int(item.label.cget("wraplength"))
        assert 0 < wrap < config.default_width
        # The whole text fits in the label's width: nothing is clipped at the edge.
        assert item.label.winfo_reqwidth() <= item.label.winfo_width() + 1
        assert item.card_canvas.winfo_height() > 2 * short_height - 20
        assert len(item.card_canvas.find_withtag("card")) == 14
    finally:
        win.destroy()


def test_long_task_text_rewraps_when_the_list_is_resized(root):
    win, canvas, win_id, item = _item_in_list_of_width(root, LONG_TEXT, 500)
    try:
        wide_wrap = int(item.label.cget("wraplength"))
        wide_height = item.card_canvas.winfo_height()

        win.geometry("250x400+0+0")
        canvas.itemconfigure(win_id, width=250)
        win.update()

        assert int(item.label.cget("wraplength")) < wide_wrap
        assert item.card_canvas.winfo_height() > wide_height
    finally:
        win.destroy()


def test_revealing_the_delete_button_does_not_rewrap_the_text(root):
    win, _, _, item = _item_in_list_of_width(root, LONG_TEXT, config.default_width)
    try:
        wrap = item.label.cget("wraplength")
        height = item.card_canvas.winfo_height()

        item._show_delete_btn()
        win.update()

        assert item.label.cget("wraplength") == wrap
        assert item.card_canvas.winfo_height() == height
    finally:
        win.destroy()


def test_scroll_region_and_increment_follow_wrapped_rows(root):
    win = tk.Toplevel(root)
    try:
        win.geometry("320x150+0+0")
        task_list = TaskListView(win)
        task_list.pack(fill="both", expand=True)
        texts = [LONG_TEXT] + [f"Task {i}" for i in range(5)]
        widgets = []
        for i, text in enumerate(texts):
            w = TaskItem(task_list.inner_frame, task_id=str(i), text=text)
            task_list.add_widget(w)
            widgets.append(w)
        task_list.update_canvas_width(320)
        task_list.repack()
        win.update()

        long_row, short_row = widgets[0], widgets[1]
        assert long_row.winfo_height() > short_row.winfo_height()

        # Step = shortest row, so a wheel notch never skips a single-line task.
        expected = short_row.winfo_reqheight() + 2 * config.spacing_xs
        assert int(task_list._canvas["yscrollincrement"]) == expected

        # The scroll region covers the wrapped (taller) row too.
        scroll_bottom = int(str(task_list._canvas.cget("scrollregion")).split()[3])
        assert scroll_bottom >= task_list.inner_frame.winfo_height()
    finally:
        win.destroy()


# ── Undo delete (#9) ─────────────────────────


def _app_with_tasks(app_window, tmp_path, monkeypatch, tasks):
    tasks_file = tmp_path / "tasks.json"
    tasks_file.write_text(json.dumps(tasks), encoding="utf-8")
    monkeypatch.setitem(config._attr_cache, "tasks_file", str(tasks_file))
    return FlyNotesApp(app_window)


def _widget_state(app):
    return [(w.task_id, w.completed_var.get()) for w in app._task_list.task_widgets]


def _model_state(app):
    return [(t["id"], t["completed"]) for t in app.manager.tasks]


SAMPLE_TASKS = [
    {"id": "a", "text": "A", "completed": False},
    {"id": "b", "text": "B", "completed": True},
    {"id": "c", "text": "C", "completed": False},
    {"id": "d", "text": "D", "completed": True},
]


def test_delete_then_undo_restores_the_same_list_and_order(app_window, tmp_path, monkeypatch):
    app = _app_with_tasks(app_window, tmp_path, monkeypatch, SAMPLE_TASKS)
    try:
        before = _widget_state(app)
        target = next(w for w in app._task_list.task_widgets if w.task_id == "c")

        app._delete_task(target)
        assert app._footer.undo_visible
        assert app._footer._undo_msg.cget("text") == config.string("undo_deleted")
        assert "c" not in [w.task_id for w in app._task_list.task_widgets]

        app._undo()

        assert _widget_state(app) == before
        assert _model_state(app) == before
        assert not app._footer.undo_visible
    finally:
        app._on_close()


def test_clear_completed_needs_no_dialog_and_can_be_undone(app_window, tmp_path, monkeypatch):
    from fly_notes import fly_notes_app

    def no_dialogs(*args, **kwargs):
        raise AssertionError("clear completed must not ask for confirmation")

    monkeypatch.setattr(fly_notes_app.messagebox, "askyesno", no_dialogs)
    app = _app_with_tasks(app_window, tmp_path, monkeypatch, SAMPLE_TASKS)
    try:
        before = _widget_state(app)

        app._clear_completed()
        assert [w.task_id for w in app._task_list.task_widgets] == ["a", "c"]
        assert app._footer._undo_msg.cget("text") == config.string("undo_cleared", count=2)

        app._undo()
        assert _widget_state(app) == before
        assert _model_state(app) == before
    finally:
        app._on_close()


def test_undo_shortcut_is_bound_and_noop_without_history(app_window, tmp_path, monkeypatch):
    app = _app_with_tasks(app_window, tmp_path, monkeypatch, SAMPLE_TASKS)
    try:
        assert config.shortcut_undo == "<Control-z>"
        assert app.root.bind(config.shortcut_undo)
        before = _widget_state(app)
        app._undo()
        assert _widget_state(app) == before
    finally:
        app._on_close()


def test_undo_notice_hides_itself_after_the_timeout(app_window, tmp_path, monkeypatch):
    monkeypatch.setitem(config._attr_cache, "undo_timeout_ms", 10)
    app = _app_with_tasks(app_window, tmp_path, monkeypatch, SAMPLE_TASKS)
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


def test_clicking_undo_in_the_footer_restores_the_task(app_window, tmp_path, monkeypatch):
    app = _app_with_tasks(app_window, tmp_path, monkeypatch, SAMPLE_TASKS)
    try:
        before = _widget_state(app)
        app._delete_task(app._task_list.task_widgets[0])
        app._footer._undo_clicked()
        assert _widget_state(app) == before
    finally:
        app._on_close()


# ── Inline edit (#10) ────────────────────────


def _editable_item(root, text="Original", on_text_change=None):
    win = tk.Toplevel(root)
    win.geometry("320x120+0+0")
    item = TaskItem(win, task_id="1", text=text, on_text_change=on_text_change)
    item.pack(fill="x")
    win.update()
    return win, item


def test_begin_edit_swaps_label_for_entry_with_the_task_text(root):
    win, item = _editable_item(root)
    try:
        item.begin_edit()
        assert item.is_editing
        assert item._editor.get() == "Original"
        assert not item.label.winfo_manager()
        item.begin_edit()  # second call is a no-op
        assert item._editor.get() == "Original"
    finally:
        win.destroy()


def test_enter_saves_the_edit_through_the_callback(root):
    calls = []

    def on_change(item, text):
        calls.append(text)
        return text.strip()

    win, item = _editable_item(root, on_text_change=on_change)
    try:
        item.begin_edit()
        item._editor.delete(0, tk.END)
        item._editor.insert(0, " Fixed ")
        assert item._commit_edit_event() == "break"

        assert calls == [" Fixed "]
        assert not item.is_editing
        assert item.label.cget("text") == "Fixed"
        assert item.task_text == "Fixed"
        assert item.label.winfo_manager() == "pack"
    finally:
        win.destroy()


def test_escape_cancels_the_edit_without_calling_back(root):
    calls = []
    win, item = _editable_item(root, on_text_change=lambda i, t: calls.append(t) or t)
    try:
        item.begin_edit()
        item._editor.delete(0, tk.END)
        item._editor.insert(0, "changed")
        assert item._cancel_edit_event() == "break"

        assert calls == []
        assert item.label.cget("text") == "Original"
        assert not item.is_editing
    finally:
        win.destroy()


def test_rejected_edit_keeps_the_original_text(root):
    """The app returns None for empty/unchanged text: the label must not change."""
    win, item = _editable_item(root, on_text_change=lambda i, t: None)
    try:
        item.begin_edit()
        item._editor.delete(0, tk.END)
        item.commit_edit()

        assert item.label.cget("text") == "Original"
        assert not item.is_editing
    finally:
        win.destroy()


def test_edited_text_rewraps_the_card(root):
    win, item = _editable_item(root, on_text_change=lambda i, t: t)
    try:
        short_height = item.card_canvas.winfo_height()
        item.begin_edit()
        item._editor.insert(tk.END, " " + LONG_TEXT)
        item.commit_edit()
        win.update()

        assert item.card_canvas.winfo_height() > short_height
    finally:
        win.destroy()


def test_double_click_on_label_starts_editing(root):
    win, item = _editable_item(root)
    try:
        win.deiconify()
        win.update()
        # Tk can't synthesize "<Double-...>" directly: two quick clicks make one.
        for _ in range(2):
            item.label.event_generate("<ButtonPress-1>", x=5, y=5)
            item.label.event_generate("<ButtonRelease-1>", x=5, y=5)
        win.update()
        assert item.is_editing
    finally:
        win.destroy()


def test_contains_does_not_match_a_sibling_with_a_longer_name(root):
    win = tk.Toplevel(root)
    try:
        first = TaskItem(win, task_id="1", text="1", name="row1")
        tenth = TaskItem(win, task_id="10", text="10", name="row10")
        assert str(tenth).startswith(str(first))  # the trap: ".row1" is a prefix of ".row10"
        assert first.contains(first.label)
        assert not first.contains(tenth.label)
        assert not first.contains(None)
    finally:
        win.destroy()


def test_inline_edit_is_saved_to_the_model(app_window, tmp_path, monkeypatch):
    app = _app_with_tasks(app_window, tmp_path, monkeypatch, SAMPLE_TASKS)
    try:
        item = app._task_list.task_widgets[0]
        item.begin_edit()
        item._editor.delete(0, tk.END)
        item._editor.insert(0, "A edited")
        item.commit_edit()

        assert app.manager.task_by_id("a")["text"] == "A edited"
        assert item.label.cget("text") == "A edited"
    finally:
        app._on_close()


def test_f2_edits_the_hovered_task(app_window, tmp_path, monkeypatch):
    app = _app_with_tasks(app_window, tmp_path, monkeypatch, SAMPLE_TASKS)
    try:
        assert config.shortcut_edit_task == "<F2>"
        assert app.root.bind(config.shortcut_edit_task)
        app_window.deiconify()
        app_window.update()
        target = app._task_list.task_widgets[2]
        target._is_hovered = True

        app._edit_current_task()

        assert target.is_editing
        assert not any(w.is_editing for w in app._task_list.task_widgets if w is not target)
    finally:
        app._on_close()


def test_f2_without_a_target_does_nothing(app_window, tmp_path, monkeypatch):
    app = _app_with_tasks(app_window, tmp_path, monkeypatch, SAMPLE_TASKS)
    try:
        app._edit_current_task()
        assert not any(w.is_editing for w in app._task_list.task_widgets)
    finally:
        app._on_close()


# ── Remember window geometry (#11) ───────────


def test_window_geometry_is_saved_on_close_and_restored(app_window, root, tmp_path, monkeypatch):
    from fly_notes import fly_notes_app

    monkeypatch.setattr(fly_notes_app, "monitor_work_areas", lambda: [Rect(0, 0, 1920, 1040)])
    monkeypatch.setitem(config._attr_cache, "tasks_file", str(tmp_path / "tasks.json"))
    app = FlyNotesApp(app_window)
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
        app2 = FlyNotesApp(second)
        second.update_idletasks()
        assert WindowGeometry.from_tk(second.wm_geometry()) == WindowGeometry(410, 520, 333, 222)
        assert int(app2._task_list._canvas.itemcget(app2._task_list._canvas_win_id, "width")) == 410
        app2._on_close()
    finally:
        if second.winfo_exists():
            second.destroy()


def test_off_screen_saved_geometry_opens_at_the_default(app_window, tmp_path, monkeypatch):
    from fly_notes import fly_notes_app

    monkeypatch.setattr(fly_notes_app, "monitor_work_areas", lambda: [Rect(0, 0, 1920, 1040)])
    monkeypatch.setitem(config._attr_cache, "tasks_file", str(tmp_path / "tasks.json"))
    (tmp_path / "state.json").write_text(
        json.dumps({"window": {"width": 410, "height": 520, "x": 5000, "y": 200}}),
        encoding="utf-8",
    )
    app = FlyNotesApp(app_window)
    try:
        app_window.update_idletasks()
        expected = WindowGeometry(config.default_width, config.default_height, 100, 100)
        assert WindowGeometry.from_tk(app_window.wm_geometry()) == expected
    finally:
        app._on_close()


def test_failing_to_save_geometry_still_closes(app_window, tmp_path, monkeypatch, caplog):
    from fly_notes import fly_notes_app

    def boom(*args):
        raise OSError("read-only")

    monkeypatch.setitem(config._attr_cache, "tasks_file", str(tmp_path / "tasks.json"))
    monkeypatch.setattr(fly_notes_app, "save_geometry", boom)
    app = FlyNotesApp(app_window)
    with caplog.at_level(logging.ERROR, logger="fly_notes.fly_notes_app"):
        app._on_close()

    assert "Could not save the window position" in caplog.text
    assert not app_window.winfo_exists()


# ── Always on top and inactive fade (#14) ────


def _topmost(win):
    return bool(int(win.attributes("-topmost")))


def test_pin_button_toggles_always_on_top(app_window, tmp_path, monkeypatch):
    monkeypatch.setitem(config._attr_cache, "tasks_file", str(tmp_path / "tasks.json"))
    app = FlyNotesApp(app_window)
    try:
        assert app.always_on_top and _topmost(app_window)
        assert app._header.pin_text == config.string("btn_pin_on")

        app._header._pin_btn.invoke()
        assert not app.always_on_top
        assert not _topmost(app_window)
        assert not app.window_ctrl.always_on_top  # restoring from the taskbar keeps it off
        assert app._header.pin_text == config.string("btn_pin_off")

        app.toggle_always_on_top()  # what Ctrl+T calls
        assert app.always_on_top and _topmost(app_window)
        assert app_window.bind(config.shortcut_toggle_always_on_top)
    finally:
        app._on_close()


def test_mapping_the_window_no_longer_forces_it_on_top(app_window, tmp_path, monkeypatch):
    monkeypatch.setitem(config._attr_cache, "tasks_file", str(tmp_path / "tasks.json"))
    app = FlyNotesApp(app_window)
    try:
        app.toggle_always_on_top()
        app_window.event_generate("<Map>")
        assert not _topmost(app_window)
    finally:
        app._on_close()


def test_always_on_top_choice_is_remembered(app_window, root, tmp_path, monkeypatch):
    monkeypatch.setitem(config._attr_cache, "tasks_file", str(tmp_path / "tasks.json"))
    app = FlyNotesApp(app_window)
    app.toggle_always_on_top()
    app._on_close()

    second = tk.Toplevel(root)
    second.withdraw()
    try:
        app2 = FlyNotesApp(second)
        assert not app2.always_on_top
        assert not _topmost(second)
        assert app2._header.pin_text == config.string("btn_pin_off")
        app2._on_close()
    finally:
        if second.winfo_exists():
            second.destroy()


def test_always_on_top_default_comes_from_config(app_window, tmp_path, monkeypatch):
    monkeypatch.setitem(config._attr_cache, "tasks_file", str(tmp_path / "tasks.json"))
    monkeypatch.setitem(config._attr_cache, "always_on_top", False)
    app = FlyNotesApp(app_window)
    try:
        assert not app.always_on_top and not _topmost(app_window)
    finally:
        app._on_close()


def test_default_inactive_opacity_is_readable():
    assert config.inactive_alpha >= 0.7


def _alpha(win):
    return round(float(win.attributes("-alpha")), 2)


def test_window_fades_only_after_focus_stays_away(app_window, tmp_path, monkeypatch):
    monkeypatch.setitem(config._attr_cache, "tasks_file", str(tmp_path / "tasks.json"))
    app = FlyNotesApp(app_window)
    try:
        monkeypatch.setattr(app_window, "focus_get", lambda: None)  # focus left the app
        app._on_app_focus_out()
        assert _alpha(app_window) == round(config.active_alpha, 2)  # not yet: fade is delayed
        assert app._fade_after_id is not None

        app._fade_if_inactive()  # the delay elapses
        assert _alpha(app_window) == round(config.inactive_alpha, 2)

        app._on_app_focus_in()
        assert _alpha(app_window) == round(config.active_alpha, 2)
    finally:
        app._on_close()


def test_focus_moving_inside_the_window_does_not_fade_it(app_window, tmp_path, monkeypatch):
    monkeypatch.setitem(config._attr_cache, "tasks_file", str(tmp_path / "tasks.json"))
    app = FlyNotesApp(app_window)
    try:
        # e.g. entry -> task row: FocusOut then FocusIn
        app._on_app_focus_out()
        app._on_app_focus_in()
        assert app._fade_after_id is None

        # focus still on one of our widgets when the delay elapses
        monkeypatch.setattr(app_window, "focus_get", lambda: app._entry_bar.entry_widget)
        app._on_app_focus_out()
        app._fade_if_inactive()
        assert _alpha(app_window) == round(config.active_alpha, 2)
    finally:
        app._on_close()


# ── Single instance (#15) ────────────────────


def test_activation_request_brings_the_window_to_the_front(app_window, tmp_path, monkeypatch):
    monkeypatch.setitem(config._attr_cache, "tasks_file", str(tmp_path / "tasks.json"))
    app = FlyNotesApp(app_window)
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


def test_bring_to_front_restores_a_minimized_window(app_window, tmp_path, monkeypatch):
    monkeypatch.setitem(config._attr_cache, "tasks_file", str(tmp_path / "tasks.json"))
    app = FlyNotesApp(app_window)
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


# ── Keyboard navigation (#13) ────────────────

NAV_TASKS = [
    {"id": "a", "text": "A", "completed": False},
    {"id": "b", "text": "B", "completed": True},
    {"id": "c", "text": "C", "completed": False},
    {"id": "d", "text": "D", "completed": False},
]


@pytest.fixture
def nav_app(app_window, tmp_path, monkeypatch):
    """App with NAV_TASKS; records where keyboard focus is sent instead of
    relying on real OS focus (unreliable for a test window)."""
    app = _app_with_tasks(app_window, tmp_path, monkeypatch, NAV_TASKS)
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
    canvas = _row(app, "a").card_canvas
    assert int(canvas.cget("takefocus")) == 1
    for key in ("<Up>", "<Down>", "<Alt-Up>", "<Alt-Down>", "<space>", "<Delete>", "<F2>"):
        assert canvas.bind(key), key


def test_focused_row_draws_a_focus_ring(root):
    win = tk.Toplevel(root)
    try:
        win.geometry("320x100+0+0")
        item = TaskItem(win, task_id="1", text="Sample task")
        item.pack(fill="x")
        win.update_idletasks()

        def outlines():
            return {
                item.card_canvas.itemcget(i, "outline")
                for i in item.card_canvas.find_withtag("card")
            }

        assert config.border_focus not in outlines()
        item._on_focus_in()
        assert item.has_focus
        assert config.border_focus in outlines()
        item._on_focus_out()
        assert config.border_focus not in outlines()
    finally:
        win.destroy()


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
    assert app.manager.task_by_id("a")["completed"] is True


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
    assert _ids(app._task_list.task_widgets) == [t["id"] for t in app.manager.tasks]
    assert _ids(focused) == ["d"]


def test_alt_arrows_never_cross_the_group_boundary(nav_app):
    app, _ = nav_app
    before = [t["id"] for t in app.manager.tasks]
    _row(app, "d")._move(1)  # next visual row is the completed "b"
    _row(app, "b")._move(-1)
    _row(app, "a")._move(-1)  # already first
    assert [t["id"] for t in app.manager.tasks] == before


def test_reorder_across_hidden_group_keeps_widget_order_equal_to_model(nav_app):
    """Moving c above a jumps over the completed b in the model (pop+insert);
    the old widget *swap* left the widget order out of step with the model,
    which broke restoring a deleted task at its model index (#9)."""
    app, _ = nav_app
    _row(app, "c")._move(-1)

    model = [t["id"] for t in app.manager.tasks]
    assert _ids(app._task_list.task_widgets) == model

    # Deleting and undoing still restores the exact same order.
    app._delete_task(_row(app, "b"))
    app._undo()
    assert _ids(app._task_list.task_widgets) == model


def test_ensure_visible_scrolls_a_row_into_view(root):
    win = tk.Toplevel(root)
    try:
        win.geometry("320x150+0+0")
        task_list = TaskListView(win)
        task_list.pack(fill="both", expand=True)
        widgets = []
        for i in range(15):
            w = TaskItem(task_list.inner_frame, task_id=str(i), text=f"Task {i}")
            task_list.add_widget(w)
            widgets.append(w)
        task_list.repack()
        win.update()
        assert task_list._canvas.canvasy(0) == 0

        task_list.ensure_visible(widgets[-1])
        win.update()
        view_top = task_list._canvas.canvasy(0)
        view_bottom = view_top + task_list._canvas.winfo_height()
        last = widgets[-1]
        assert view_top > 0
        assert last.winfo_y() + last.winfo_height() <= view_bottom + 1

        task_list.ensure_visible(widgets[0])
        win.update()
        assert task_list._canvas.canvasy(0) <= widgets[0].winfo_y()
    finally:
        win.destroy()


# ── Section header hierarchy ─────────────────


def test_section_headers_are_uppercase_bold_and_use_dedicated_color(root, tmp_path):
    """Regression for 'headers look like secondary body text': pending/
    completed section headers must render uppercase, in font_section
    (now bold), and in the dedicated section_header colour -- distinct
    from the plain text_secondary/font_footer '+N more' hint."""
    manager = TaskManager(tasks_file=str(tmp_path / "tasks.json"))
    task_a = manager.add_task("Pending A")
    task_b = manager.add_task("Done B", completed=True)

    task_list = TaskListView(root)
    widgets = []
    for t in (task_a, task_b):
        w = TaskItem(
            task_list.inner_frame, task_id=t["id"], text=t["text"], completed=t["completed"]
        )
        task_list.add_widget(w)
        widgets.append(w)
    task_list.repack()

    labels = [w for w in task_list._transient_widgets if isinstance(w, tk.Label)]
    texts = {lbl.cget("text") for lbl in labels}
    assert "TO DO (1)" in texts
    assert "COMPLETED (1)" in texts
    for lbl in labels:
        assert lbl.cget("fg") == config.section_header
        assert "bold" in str(lbl.cget("font"))

    for w in widgets:
        w.destroy()
    task_list.destroy()


def test_more_hidden_indicator_keeps_plain_style_not_header_style(root):
    """The 'Show N more' link is a meta note, not a structural separator --
    it must stay lowercase and use link_color/font_footer, not the bold
    uppercase section_header treatment."""
    task_list = TaskListView(root)
    widgets = []
    for i in range(5):
        w = TaskItem(task_list.inner_frame, task_id=str(i), text=f"Task {i}")
        task_list.add_widget(w)
        widgets.append(w)

    original_limit = config._data["settings"]["max_visible_tasks"]
    config._data["settings"]["max_visible_tasks"] = 3
    config._attr_cache.pop("max_visible_tasks", None)
    try:
        task_list.repack()
        more_label = next(
            w
            for w in task_list._transient_widgets
            if isinstance(w, tk.Label) and "more" in w.cget("text")
        )
        assert more_label.cget("text") == config.string("more_hidden", count=2)
        assert more_label.cget("fg") == config.link_color
        assert "bold" not in str(more_label.cget("font"))
    finally:
        config._data["settings"]["max_visible_tasks"] = original_limit
        config._attr_cache.pop("max_visible_tasks", None)
        for w in widgets:
            w.destroy()
        task_list.destroy()


# ── "Show N more" is actionable (#12) ────────


@pytest.fixture
def capped_list(root, monkeypatch):
    """A TaskListView with 8 tasks and max_visible_tasks=3."""
    monkeypatch.setitem(config._attr_cache, "max_visible_tasks", 3)
    task_list = TaskListView(root)
    widgets = []
    for i in range(8):
        w = TaskItem(task_list.inner_frame, task_id=str(i), text=f"Task {i}")
        task_list.add_widget(w)
        widgets.append(w)
    task_list.repack()
    yield task_list, widgets
    task_list.destroy()


def _show_more_link(task_list):
    links = [
        w
        for w in task_list._transient_widgets
        if isinstance(w, tk.Label) and w.cget("cursor") == "hand2"
    ]
    return links[0] if links else None


def _packed_ids(widgets):
    return [w.task_id for w in widgets if w.winfo_manager()]


def test_show_more_link_names_the_next_page_and_the_total(capped_list):
    task_list, widgets = capped_list
    link = _show_more_link(task_list)
    assert link.cget("text") == config.string("more_hidden_paged", count=3, hidden=5)
    assert _packed_ids(widgets) == ["0", "1", "2"]


def test_clicking_show_more_reveals_one_page_at_a_time(capped_list):
    task_list, widgets = capped_list

    _show_more_link(task_list).event_generate("<Button-1>")
    assert _packed_ids(widgets) == ["0", "1", "2", "3", "4", "5"]
    link = _show_more_link(task_list)
    assert link.cget("text") == config.string("more_hidden", count=2)

    link.event_generate("<Button-1>")
    assert _packed_ids(widgets) == [str(i) for i in range(8)]
    assert _show_more_link(task_list) is None


def test_show_more_works_from_the_keyboard(capped_list):
    task_list, _ = capped_list
    link = _show_more_link(task_list)
    assert int(link.cget("takefocus")) == 1
    assert link.bind("<Return>")
    assert link.bind("<space>")


def test_revealed_rows_stay_visible_after_a_repack(capped_list):
    """Adding/toggling a task repacks the list: it must not collapse again."""
    task_list, widgets = capped_list
    task_list.show_more()
    task_list.repack()
    assert len(_packed_ids(widgets)) == 6


def test_link_color_is_validated_against_the_list_background():
    from fly_notes.config import _CONTRAST_PAIRS

    assert ("link_color", "content_bg", 4.5) in _CONTRAST_PAIRS


# ── Window icon ──────────────────────────────


def test_icon_path_resolves_to_an_existing_bundled_asset():
    """Regression for 'no window icon': the .ico referenced by
    WindowController/FlyNotes.spec must actually exist in the repo, not
    just be a path computed on faith."""
    assert ICON_PATH.exists()
    assert ICON_PATH.suffix == ".ico"


def test_window_controller_applies_icon_to_root_and_proxy_without_raising(root):
    ctrl = WindowController(root)
    try:
        # Tk's `wm iconbitmap` query doesn't reliably echo back the path
        # that was set via `default=`, so the meaningful contract here is
        # "construction with a real icon file doesn't raise" -- exercised
        # by simply reaching this point.
        assert ctrl._proxy is not None
    finally:
        root.withdraw()
        ctrl._proxy.destroy()


def test_window_controller_missing_icon_warns_and_does_not_raise(root, monkeypatch, caplog):
    """If the .ico asset is missing (e.g. a broken PyInstaller bundle),
    the app must still start -- degrade with a logged warning, not a
    crash, matching this module's existing platform-warning philosophy."""
    monkeypatch.setattr(window_controller_module, "ICON_PATH", Path("does/not/exist.ico"))
    with caplog.at_level(logging.WARNING):
        ctrl = WindowController(root)
    try:
        assert any("icon" in rec.message.lower() for rec in caplog.records)
    finally:
        root.withdraw()
        ctrl._proxy.destroy()


# ── Closing from the taskbar ─────────────────


def test_proxy_close_delegates_to_on_close_callback(root):
    calls = []
    ctrl = WindowController(root, on_close=lambda: calls.append("closed"))
    try:
        ctrl._on_proxy_close()
        assert calls == ["closed"]
    finally:
        root.withdraw()
        ctrl._proxy.destroy()


def test_closing_from_taskbar_flushes_pending_save(app_window, tmp_path, monkeypatch):
    """A change made right before closing via the taskbar entry must reach
    disk, even though saves are debounced."""
    tasks_file = tmp_path / "tasks.json"
    monkeypatch.setitem(config._attr_cache, "tasks_file", str(tasks_file))
    app_root = app_window
    app = FlyNotesApp(app_root)
    app.manager.SAVE_DELAY = 60  # make sure only the close path can write
    app.manager.add_task("written just before closing")
    assert not tasks_file.exists()

    app.window_ctrl._on_proxy_close()

    saved = json.loads(tasks_file.read_text(encoding="utf-8"))
    assert [t["text"] for t in saved] == ["written just before closing"]
