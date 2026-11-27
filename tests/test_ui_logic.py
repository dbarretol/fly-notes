import json
import logging
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


@pytest.fixture(scope="session")
def root():
    r = tk.Tk()
    r.withdraw()
    yield r
    r.destroy()


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


def test_escape_while_typing_does_not_close_the_app(tmp_path, monkeypatch):
    monkeypatch.setitem(config._attr_cache, "tasks_file", str(tmp_path / "tasks.json"))
    app_root = tk.Tk()
    app = FlyNotesApp(app_root)
    try:
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
    update_idletasks(), see docs/issues-v3.md #5). The fix has
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


# ── Scroll affordance (issues-v4 #2) ─────────


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
    become visible (packed) — regression coverage for the '+11 tasks,
    scrollbar barely perceptible' finding in issues-v4 #2."""
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
    edge (see issues-v4 #2: last row cut in half with no affordance)."""
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

        expected = widgets[0].winfo_reqheight() + 2 * config.spacing_xs
        assert int(task_list._canvas["yscrollincrement"]) == expected

        for w in widgets:
            w.destroy()
        task_list.destroy()
    finally:
        win.destroy()


# ── Rounded card + shadow (issues-v4 #3) ─────


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


# ── Section header hierarchy (issues-v4 #4) ──


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
    """The '+N more' hint is a meta note, not a structural separator --
    it must stay lowercase and use text_secondary/font_footer, not the
    bold uppercase section_header treatment."""
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
        assert more_label.cget("fg") == config.text_secondary
        assert "bold" not in str(more_label.cget("font"))
    finally:
        config._data["settings"]["max_visible_tasks"] = original_limit
        config._attr_cache.pop("max_visible_tasks", None)
        for w in widgets:
            w.destroy()
        task_list.destroy()


# ── Window icon (issues-v4 #5) ───────────────


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


def test_closing_from_taskbar_flushes_pending_save(tmp_path, monkeypatch):
    """A change made right before closing via the taskbar entry must reach
    disk, even though saves are debounced."""
    tasks_file = tmp_path / "tasks.json"
    monkeypatch.setitem(config._attr_cache, "tasks_file", str(tasks_file))
    app_root = tk.Tk()
    app_root.withdraw()
    app = FlyNotesApp(app_root)
    app.manager.SAVE_DELAY = 60  # make sure only the close path can write
    app.manager.add_task("written just before closing")
    assert not tasks_file.exists()

    app.window_ctrl._on_proxy_close()

    saved = json.loads(tasks_file.read_text(encoding="utf-8"))
    assert [t["text"] for t in saved] == ["written just before closing"]
