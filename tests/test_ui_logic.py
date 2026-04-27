import tkinter as tk
import pytest
from fly_notes.task_item import TaskItem
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
