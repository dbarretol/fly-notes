"""
Data layer — task CRUD with debounced atomic persistence.

Unchanged in this UI/UX pass except for the addition of ``task_count``
and ``completed_count`` helpers that the UI needs for badges.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
import uuid
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

Task = Dict[str, Any]


class TaskManager:
    """Manages task lifecycle and JSON persistence."""

    SAVE_DELAY: float = 0.5

    def __init__(
        self,
        tasks_file: str = "tasks.json",
        error_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.tasks_file = tasks_file
        self.error_callback = error_callback
        self._tasks: List[Task] = []
        self._save_timer: Optional[threading.Timer] = None
        self._lock = threading.Lock()
        self._load_tasks()

    # ── Read access ──────────────────────────

    @property
    def tasks(self) -> List[Task]:
        return list(self._tasks)

    @property
    def task_count(self) -> int:
        return len(self._tasks)

    @property
    def completed_count(self) -> int:
        return sum(1 for t in self._tasks if t["completed"])

    @property
    def pending_count(self) -> int:
        return self.task_count - self.completed_count

    def task_by_id(self, task_id: str) -> Optional[Task]:
        for t in self._tasks:
            if t["id"] == task_id:
                return t
        return None

    def index_of(self, task_id: str) -> int:
        for i, t in enumerate(self._tasks):
            if t["id"] == task_id:
                return i
        raise ValueError(f"Task id '{task_id}' not found")

    # ── CRUD ─────────────────────────────────

    def add_task(self, text: str, completed: bool = False) -> Task:
        task: Task = {
            "id": uuid.uuid4().hex,
            "text": text,
            "completed": completed,
        }
        self._tasks.append(task)
        self._schedule_save()
        logger.info("Task added: %s (id=%s)", text, task["id"])
        return task

    def delete_task(self, task_id: str) -> Optional[Task]:
        try:
            idx = self.index_of(task_id)
        except ValueError:
            logger.warning("delete_task: id '%s' not found", task_id)
            return None
        removed = self._tasks.pop(idx)
        self._schedule_save()
        logger.info("Task deleted: %s", task_id)
        return removed

    def toggle_task(self, task_id: str) -> Optional[Task]:
        try:
            idx = self.index_of(task_id)
        except ValueError:
            return None
        self._tasks[idx]["completed"] = not self._tasks[idx]["completed"]
        self._schedule_save()
        logger.info("Task toggled: %s → %s", task_id, self._tasks[idx]["completed"])
        return self._tasks[idx]

    def reorder_tasks(self, old_idx: int, new_idx: int) -> bool:
        if not (0 <= old_idx < len(self._tasks) and 0 <= new_idx < len(self._tasks)):
            return False
        task = self._tasks.pop(old_idx)
        self._tasks.insert(new_idx, task)
        self._schedule_save()
        return True

    def clear_completed(self) -> int:
        before = len(self._tasks)
        self._tasks = [t for t in self._tasks if not t["completed"]]
        removed = before - len(self._tasks)
        self._schedule_save()
        logger.info("Cleared %d completed task(s)", removed)
        return removed

    # ── Persistence ──────────────────────────

    def _schedule_save(self) -> None:
        with self._lock:
            if self._save_timer is not None:
                self._save_timer.cancel()
            self._save_timer = threading.Timer(self.SAVE_DELAY, self._do_save)
            self._save_timer.daemon = True
            self._save_timer.start()

    def flush(self) -> None:
        with self._lock:
            if self._save_timer is not None:
                self._save_timer.cancel()
                self._save_timer = None
        self._do_save()

    def _do_save(self) -> None:
        try:
            dir_name = os.path.dirname(self.tasks_file) or "."
            fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    json.dump(self._tasks, fh, ensure_ascii=False, indent=2)
                os.replace(tmp_path, self.tasks_file)
            except BaseException:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
        except Exception as exc:
            msg = f"Error saving tasks: {exc}"
            logger.error(msg, exc_info=True)
            if self.error_callback:
                self.error_callback(msg)

    def _load_tasks(self) -> None:
        if not os.path.exists(self.tasks_file):
            logger.info("No tasks file at %s — starting fresh", self.tasks_file)
            return
        try:
            with open(self.tasks_file, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if not isinstance(data, list):
                raise TypeError(f"Expected list, got {type(data).__name__}")
            self._tasks = [self._sanitise_task(t) for t in data]
            logger.info("Loaded %d task(s) from %s", len(self._tasks), self.tasks_file)
        except Exception as exc:
            msg = f"Error loading tasks: {exc}"
            logger.error(msg, exc_info=True)
            if self.error_callback:
                self.error_callback(msg)
            self._tasks = []

    @staticmethod
    def _sanitise_task(raw: Any) -> Task:
        if not isinstance(raw, dict):
            raise TypeError(f"Task must be a dict, got {type(raw).__name__}")
        return {
            "id": raw.get("id") or uuid.uuid4().hex,
            "text": str(raw.get("text", "")),
            "completed": bool(raw.get("completed", False)),
        }