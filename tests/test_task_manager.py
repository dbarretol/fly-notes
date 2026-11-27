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
    t1 = tm.add_task("Task 1")
    t2 = tm.add_task("Task 2")
    tm.delete_task(t1["id"])
    assert len(tm.tasks) == 1
    assert tm.tasks[0]["id"] == t2["id"]


def test_toggle_task(temp_tasks_file):
    tm = TaskManager(tasks_file=temp_tasks_file)
    t1 = tm.add_task("Task 1")
    tm.toggle_task(t1["id"])
    assert tm.tasks[0]["completed"] is True
    tm.toggle_task(t1["id"])
    assert tm.tasks[0]["completed"] is False


def test_reorder_tasks(temp_tasks_file):
    tm = TaskManager(tasks_file=temp_tasks_file)
    tm.add_task("A")
    tm.add_task("B")
    tm.add_task("C")
    tm.reorder_tasks(0, 2)  # Move A to end
    assert tm.tasks[0]["text"] == "B"
    assert tm.tasks[1]["text"] == "C"
    assert tm.tasks[2]["text"] == "A"


def test_persistence(temp_tasks_file):
    tm = TaskManager(tasks_file=temp_tasks_file)
    tm.add_task("Persistent Task")
    tm.flush()

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


def test_task_by_id(temp_tasks_file):
    tm = TaskManager(tasks_file=temp_tasks_file)
    t1 = tm.add_task("A")
    found = tm.task_by_id(t1["id"])
    assert found["text"] == "A"
    assert tm.task_by_id("invalid") is None


def test_counts(temp_tasks_file):
    tm = TaskManager(tasks_file=temp_tasks_file)
    tm.add_task("P1", completed=False)
    tm.add_task("P2", completed=False)
    tm.add_task("C1", completed=True)
    assert tm.task_count == 3
    assert tm.pending_count == 2
    assert tm.completed_count == 1


def test_sanitise_task():
    # Test internal static method
    raw = {"text": "Hello", "completed": "True"}
    clean = TaskManager._sanitise_task(raw)
    assert clean["text"] == "Hello"
    assert clean["completed"] is True
    assert "id" in clean

    with pytest.raises(TypeError):
        TaskManager._sanitise_task("not a dict")


def test_flush(temp_tasks_file):
    tm = TaskManager(tasks_file=temp_tasks_file)
    tm.add_task("Immediate")
    tm.flush()
    # Check if file exists and contains the task
    with open(temp_tasks_file, encoding="utf-8") as f:
        data = json.load(f)
    assert len(data) == 1
    assert data[0]["text"] == "Immediate"


def test_load_malformed_json(temp_tasks_file):
    with open(temp_tasks_file, "w", encoding="utf-8") as f:
        f.write("not json")

    tm = TaskManager(tasks_file=temp_tasks_file)
    assert len(tm.tasks) == 0


def test_load_invalid_task_format(temp_tasks_file):
    with open(temp_tasks_file, "w", encoding="utf-8") as f:
        json.dump([{"id": 1, "text": "Wrong ID type"}], f)

    tm = TaskManager(tasks_file=temp_tasks_file)
    # Sanitiser should fix the ID type or at least load it as string if it can
    # TaskManager._sanitise_task uses str(raw.get("id")) wait no
    # task_id = raw.get("id")
    # if not isinstance(task_id, str) or not task_id.strip(): ...
    # So it should generate a new one.
    assert len(tm.tasks) == 1
    assert isinstance(tm.tasks[0]["id"], str)


# ── Corrupt-file safety ──────────────────────


def _corrupt_copies(path):
    return sorted(path.parent.glob(f"{path.stem}.corrupt-*{path.suffix}"))


def test_unreadable_file_is_moved_aside_and_not_overwritten(tmp_path):
    tasks_file = tmp_path / "tasks.json"
    original = '[{"id": "a", "text": "precious", "completed": false'  # truncated JSON
    tasks_file.write_text(original, encoding="utf-8")
    errors = []

    tm = TaskManager(tasks_file=str(tasks_file), error_callback=errors.append)
    tm.add_task("new")
    tm.flush()

    copies = _corrupt_copies(tasks_file)
    assert len(copies) == 1
    assert copies[0].read_text(encoding="utf-8") == original
    assert [t["text"] for t in json.loads(tasks_file.read_text(encoding="utf-8"))] == ["new"]
    assert errors and str(copies[0]) in errors[0]


def test_unreadable_file_is_restored_from_backup(tmp_path):
    tasks_file = tmp_path / "tasks.json"
    tm = TaskManager(tasks_file=str(tasks_file))
    tm.add_task("first")
    tm.flush()
    tm.add_task("second")
    tm.flush()  # backup now holds ["first"]
    tasks_file.write_text("garbage", encoding="utf-8")
    errors = []

    tm2 = TaskManager(tasks_file=str(tasks_file), error_callback=errors.append)

    assert [t["text"] for t in tm2.tasks] == ["first"]
    assert [t["text"] for t in json.loads(tasks_file.read_text(encoding="utf-8"))] == ["first"]
    assert _corrupt_copies(tasks_file)[0].read_text(encoding="utf-8") == "garbage"
    assert "Restored 1 task(s)" in errors[0]


def test_saves_are_blocked_when_unreadable_file_cannot_be_moved(tmp_path, monkeypatch):
    tasks_file = tmp_path / "tasks.json"
    tasks_file.write_text("garbage", encoding="utf-8")
    monkeypatch.setattr(TaskManager, "_preserve_original", lambda self, move: None)
    errors = []

    tm = TaskManager(tasks_file=str(tasks_file), error_callback=errors.append)
    tm.add_task("new")
    tm.flush()

    assert tasks_file.read_text(encoding="utf-8") == "garbage"
    assert "Saving is disabled" in errors[0]


def test_skipped_malformed_entries_keep_a_copy_of_the_original(tmp_path):
    tasks_file = tmp_path / "tasks.json"
    original = json.dumps([{"id": "a", "text": "ok", "completed": False}, "not a task"])
    tasks_file.write_text(original, encoding="utf-8")
    errors = []

    tm = TaskManager(tasks_file=str(tasks_file), error_callback=errors.append)

    assert [t["text"] for t in tm.tasks] == ["ok"]
    copies = _corrupt_copies(tasks_file)
    assert len(copies) == 1 and copies[0].read_text(encoding="utf-8") == original
    assert "1 malformed task(s)" in errors[0]


def test_backup_holds_previous_version(tmp_path):
    tasks_file = tmp_path / "tasks.json"
    tm = TaskManager(tasks_file=str(tasks_file))
    tm.add_task("one")
    tm.flush()
    assert not (tmp_path / "tasks.json.bak").exists()  # nothing to back up on first save
    tm.add_task("two")
    tm.flush()

    backup = json.loads((tmp_path / "tasks.json.bak").read_text(encoding="utf-8"))
    assert [t["text"] for t in backup] == ["one"]
