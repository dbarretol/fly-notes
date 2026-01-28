import os
import json
import pytest
from fly_notes.task_manager import TaskManager

@pytest.fixture
def temp_tasks_file(tmp_path):
    f = tmp_path / "tasks.json"
    return str(f)

def test_add_task(temp_tasks_file):
    tm = TaskManager(tasks_file=temp_tasks_file)
    tm.add_task("Test Task 1")
    assert len(tm.tasks) == 1
    assert tm.tasks[0]["text"] == "Test Task 1"
    assert tm.tasks[0]["completed"] is False

def test_delete_task(temp_tasks_file):
    tm = TaskManager(tasks_file=temp_tasks_file)
    tm.add_task("Task 1")
    tm.add_task("Task 2")
    tm.delete_task(0)
    assert len(tm.tasks) == 1
    assert tm.tasks[0]["text"] == "Task 2"

def test_toggle_task(temp_tasks_file):
    tm = TaskManager(tasks_file=temp_tasks_file)
    tm.add_task("Task 1")
    tm.toggle_task(0)
    assert tm.tasks[0]["completed"] is True
    tm.toggle_task(0)
    assert tm.tasks[0]["completed"] is False

def test_reorder_tasks(temp_tasks_file):
    tm = TaskManager(tasks_file=temp_tasks_file)
    tm.add_task("A")
    tm.add_task("B")
    tm.add_task("C")
    tm.reorder_tasks(0, 2) # Move A to end
    assert tm.tasks[0]["text"] == "B"
    assert tm.tasks[1]["text"] == "C"
    assert tm.tasks[2]["text"] == "A"

def test_persistence(temp_tasks_file):
    tm = TaskManager(tasks_file=temp_tasks_file)
    tm.add_task("Persistent Task")
    
    # New manager instance reading same file
    tm2 = TaskManager(tasks_file=temp_tasks_file)
    assert len(tm2.tasks) == 1
    assert tm2.tasks[0]["text"] == "Persistent Task"

def test_clear_completed(temp_tasks_file):
    tm = TaskManager(tasks_file=temp_tasks_file)
    tm.add_task("Incomplete")
    tm.add_task("Complete", completed=True)
    tm.clear_completed()
    assert len(tm.tasks) == 1
    assert tm.tasks[0]["text"] == "Incomplete"
