import types
import tkinter as tk
import pytest
from fly_notes.task_item import TaskItem
from fly_notes.task_manager import TaskManager
from fly_notes.fly_notes_app import FlyNotesApp, TaskListView, compute_reorder_target
from fly_notes.config import config

@pytest.fixture(scope="session")
def root():
    r = tk.Tk()
    r.withdraw()
    yield r
    r.destroy()

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
    def on_start(item, event): nonlocal start_called; start_called = True
    def on_stop(item, event): nonlocal stop_called; stop_called = True

    item = TaskItem(root, task_id="123", text="Drag Task", 
                    on_drag_start=on_start, on_drag_stop=on_stop)
    
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
        visual_ids, visual_completed,
        dragging_id="C", delta_y=-(config.drag_threshold + 1),
        threshold=config.drag_threshold, enforce_group_boundary=True,
    )
    assert target == "A"


def test_compute_reorder_target_stops_at_group_boundary():
    """Dragging the first completed item further up (into the pending
    group) must not swap across the boundary."""
    visual_ids = ["A", "C", "B"]
    visual_completed = [False, False, True]

    target = compute_reorder_target(
        visual_ids, visual_completed,
        dragging_id="B", delta_y=-(config.drag_threshold + 1),
        threshold=config.drag_threshold, enforce_group_boundary=True,
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
            task_list.inner_frame, task_id=t["id"],
            text=t["text"], completed=t["completed"],
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
