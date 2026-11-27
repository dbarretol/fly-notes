import json
import logging
import os
import threading

import pytest

from fly_notes.model.store import TaskManager
from fly_notes.model.task import Task


@pytest.fixture
def temp_tasks_file(tmp_path):
    f = tmp_path / "tasks.json"
    return str(f)


def test_add_task(temp_tasks_file):
    tm = TaskManager(tasks_file=temp_tasks_file)
    tm.add_task("Test Task 1")
    assert len(tm.tasks) == 1
    assert tm.tasks[0].text == "Test Task 1"
    assert tm.tasks[0].completed is False


def test_delete_task(temp_tasks_file):
    tm = TaskManager(tasks_file=temp_tasks_file)
    t1 = tm.add_task("Task 1")
    t2 = tm.add_task("Task 2")
    tm.delete_task(t1.id)
    assert len(tm.tasks) == 1
    assert tm.tasks[0].id == t2.id


def test_toggle_task(temp_tasks_file):
    tm = TaskManager(tasks_file=temp_tasks_file)
    t1 = tm.add_task("Task 1")
    tm.toggle_task(t1.id)
    assert tm.tasks[0].completed is True
    tm.toggle_task(t1.id)
    assert tm.tasks[0].completed is False


def test_reorder_tasks(temp_tasks_file):
    tm = TaskManager(tasks_file=temp_tasks_file)
    tm.add_task("A")
    tm.add_task("B")
    tm.add_task("C")
    tm.reorder_tasks(0, 2)  # Move A to end
    assert tm.tasks[0].text == "B"
    assert tm.tasks[1].text == "C"
    assert tm.tasks[2].text == "A"


def test_persistence(temp_tasks_file):
    tm = TaskManager(tasks_file=temp_tasks_file)
    tm.add_task("Persistent Task")
    tm.flush()

    # New manager instance reading same file
    tm2 = TaskManager(tasks_file=temp_tasks_file)
    assert len(tm2.tasks) == 1
    assert tm2.tasks[0].text == "Persistent Task"


def test_clear_completed(temp_tasks_file):
    tm = TaskManager(tasks_file=temp_tasks_file)
    tm.add_task("Incomplete")
    tm.add_task("Complete", completed=True)
    tm.clear_completed()
    assert len(tm.tasks) == 1
    assert tm.tasks[0].text == "Incomplete"


def test_task_by_id(temp_tasks_file):
    tm = TaskManager(tasks_file=temp_tasks_file)
    t1 = tm.add_task("A")
    found = tm.task_by_id(t1.id)
    assert found.text == "A"
    assert tm.task_by_id("invalid") is None


def test_counts(temp_tasks_file):
    tm = TaskManager(tasks_file=temp_tasks_file)
    tm.add_task("P1", completed=False)
    tm.add_task("P2", completed=False)
    tm.add_task("C1", completed=True)
    assert tm.task_count == 3
    assert tm.pending_count == 2
    assert tm.completed_count == 1


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
    # A non-string id is replaced with a freshly generated one.
    assert len(tm.tasks) == 1
    assert isinstance(tm.tasks[0].id, str)


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

    assert [t.text for t in tm2.tasks] == ["first"]
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

    assert [t.text for t in tm.tasks] == ["ok"]
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


# ── Persistence hardening ────────────────────


def test_task_text_is_not_logged(temp_tasks_file, caplog):
    tm = TaskManager(tasks_file=temp_tasks_file)
    with caplog.at_level(logging.DEBUG, logger="fly_notes.model.store"):
        task = tm.add_task("call the dentist about the results")
        tm.flush()
    assert "dentist" not in caplog.text
    assert task.id in caplog.text


def test_save_fsyncs_before_replacing_the_file(temp_tasks_file, monkeypatch):
    import fly_notes.model.store as tm_module

    events = []
    real_fsync, real_replace = tm_module.os.fsync, tm_module.os.replace
    monkeypatch.setattr(tm_module.os, "fsync", lambda fd: (events.append("fsync"), real_fsync(fd)))
    monkeypatch.setattr(
        tm_module.os, "replace", lambda a, b: (events.append("replace"), real_replace(a, b))
    )

    tm = TaskManager(tasks_file=temp_tasks_file)
    tm.add_task("durable")
    tm.flush()

    assert events == ["fsync", "replace"]


# ── Undo (#9) ────────────────────────────────


def _snapshot(tm):
    return [(t.id, t.text, t.completed) for t in tm.tasks]


def test_undo_delete_restores_task_at_its_original_position(temp_tasks_file):
    tm = TaskManager(tasks_file=temp_tasks_file)
    for i in range(4):
        tm.add_task(f"Task {i}")
    before = _snapshot(tm)

    tm.delete_task(tm.tasks[1].id)
    restored = tm.undo()

    assert [t.text for t in restored] == ["Task 1"]
    assert _snapshot(tm) == before


def test_undo_clear_completed_restores_every_task_in_order(temp_tasks_file):
    tm = TaskManager(tasks_file=temp_tasks_file)
    tasks = [tm.add_task(f"Task {i}") for i in range(5)]
    for t in (tasks[0], tasks[2], tasks[4]):
        tm.toggle_task(t.id)
    before = _snapshot(tm)

    assert tm.clear_completed() == 3
    restored = tm.undo()

    assert len(restored) == 3
    assert _snapshot(tm) == before


def test_undo_is_last_in_first_out_and_empty_when_nothing_to_undo(temp_tasks_file):
    tm = TaskManager(tasks_file=temp_tasks_file)
    a, _, c = (tm.add_task(x) for x in "abc")
    tm.delete_task(a.id)
    tm.delete_task(c.id)

    assert [t.text for t in tm.undo()] == ["c"]
    assert [t.text for t in tm.undo()] == ["a"]
    assert [t.text for t in tm.tasks] == ["a", "b", "c"]
    assert tm.can_undo is False
    assert tm.undo() == []


def test_clear_completed_with_nothing_completed_is_not_undoable(temp_tasks_file):
    tm = TaskManager(tasks_file=temp_tasks_file)
    tm.add_task("pending")
    assert tm.clear_completed() == 0
    assert tm.can_undo is False


def test_undo_after_the_list_shrank_appends_at_the_end(temp_tasks_file):
    tm = TaskManager(tasks_file=temp_tasks_file)
    a, b, c = (tm.add_task(x) for x in "abc")
    tm.delete_task(c.id)  # was at index 2
    tm.delete_task(a.id)
    tm.delete_task(b.id)
    tm.undo()  # b
    tm.undo()  # a

    tm.delete_task(b.id)  # list is now [a]; c's index 2 is out of range
    tm.undo()  # b back
    tm.undo()  # c

    assert [t.text for t in tm.tasks] == ["a", "b", "c"]


def test_undo_is_persisted(temp_tasks_file):
    tm = TaskManager(tasks_file=temp_tasks_file)
    a = tm.add_task("keep me")
    tm.delete_task(a.id)
    tm.flush()
    tm.undo()
    tm.flush()

    reloaded = TaskManager(tasks_file=temp_tasks_file)
    assert [t.text for t in reloaded.tasks] == ["keep me"]


def test_undo_history_is_bounded(temp_tasks_file):
    from fly_notes.model import store as task_manager

    tm = TaskManager(tasks_file=temp_tasks_file)
    ids = [tm.add_task(str(i)).id for i in range(task_manager._UNDO_LIMIT + 5)]
    for task_id in ids:
        tm.delete_task(task_id)

    undone = 0
    while tm.undo():
        undone += 1
    assert undone == task_manager._UNDO_LIMIT


# ── Inline edit (#10) ────────────────────────


def test_update_text_replaces_text_and_keeps_id_status_and_order(temp_tasks_file):
    tm = TaskManager(tasks_file=temp_tasks_file)
    a = tm.add_task("first")
    b = tm.add_task("secnod")
    tm.toggle_task(b.id)

    updated = tm.update_text(b.id, "  second  ")

    assert updated == Task(id=b.id, text="second", completed=True)
    assert [t.text for t in tm.tasks] == ["first", "second"]
    assert tm.tasks[0].id == a.id


def test_update_text_rejects_empty_unchanged_and_unknown(temp_tasks_file):
    tm = TaskManager(tasks_file=temp_tasks_file)
    a = tm.add_task("keep")

    assert tm.update_text(a.id, "   ") is None
    assert tm.update_text(a.id, "keep") is None
    assert tm.update_text("missing", "x") is None
    assert tm.tasks[0].text == "keep"


def test_update_text_applies_the_same_length_limit_as_new_tasks(temp_tasks_file):
    tm = TaskManager(tasks_file=temp_tasks_file)
    a = tm.add_task("short")

    updated = tm.update_text(a.id, "x" * 500, max_length=300)

    assert len(updated.text) == 300


def test_update_text_is_persisted(temp_tasks_file):
    tm = TaskManager(tasks_file=temp_tasks_file)
    a = tm.add_task("typo")
    tm.update_text(a.id, "fixed")
    tm.flush()

    assert [t.text for t in TaskManager(tasks_file=temp_tasks_file).tasks] == ["fixed"]


# ── Debounced saving through an injected scheduler (#19) ──


class FakeScheduler:
    """Records scheduled callbacks; the test decides when they run."""

    def __init__(self):
        self.pending = {}
        self.cancelled = []
        self._next = 0

    def schedule(self, delay_ms, callback):
        self._next += 1
        self.pending[self._next] = (delay_ms, callback)
        return self._next

    def cancel(self, handle):
        self.cancelled.append(handle)
        self.pending.pop(handle, None)

    def run_all(self):
        for handle in list(self.pending):
            _, callback = self.pending.pop(handle)
            callback()


def _saved_texts(path):
    with open(path, encoding="utf-8") as fh:
        return [t["text"] for t in json.load(fh)]


def test_changes_schedule_one_debounced_save(temp_tasks_file):
    scheduler = FakeScheduler()
    tm = TaskManager(tasks_file=temp_tasks_file, scheduler=scheduler)

    tm.add_task("a")
    tm.add_task("b")
    tm.toggle_task(tm.tasks[0].id)

    # Each change replaces the pending save, so a burst of edits is one write.
    assert len(scheduler.pending) == 1
    assert scheduler.cancelled == [1, 2]
    [(delay_ms, _)] = scheduler.pending.values()
    assert delay_ms == TaskManager.SAVE_DELAY_MS
    assert not os.path.exists(temp_tasks_file)

    scheduler.run_all()
    assert _saved_texts(temp_tasks_file) == ["a", "b"]


def test_flush_cancels_the_pending_save_and_writes_now(temp_tasks_file):
    scheduler = FakeScheduler()
    tm = TaskManager(tasks_file=temp_tasks_file, scheduler=scheduler)
    tm.add_task("a")

    tm.flush()

    assert scheduler.pending == {}
    assert _saved_texts(temp_tasks_file) == ["a"]
    tm.flush()  # nothing pending: no cancel of a stale handle
    assert scheduler.cancelled == [1]


def test_without_a_scheduler_only_flush_writes(temp_tasks_file):
    tm = TaskManager(tasks_file=temp_tasks_file)
    tm.add_task("a")
    assert not os.path.exists(temp_tasks_file)
    tm.flush()
    assert _saved_texts(temp_tasks_file) == ["a"]


def test_task_manager_starts_no_threads(temp_tasks_file):
    before = threading.active_count()
    tm = TaskManager(tasks_file=temp_tasks_file, scheduler=FakeScheduler())
    tm.add_task("a")
    tm.delete_task(tm.tasks[0].id)
    tm.undo()
    assert threading.active_count() == before
