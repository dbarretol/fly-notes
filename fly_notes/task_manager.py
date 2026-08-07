"""
Data layer — task CRUD with debounced atomic persistence.

Thread-safe: all mutations and reads of ``_tasks`` are protected
by ``_lock``.  The save timer serialises a snapshot under the lock
and writes to disk outside it.
"""

from __future__ import annotations

import copy
import json
import logging
import os
import tempfile
import threading
import uuid
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

Task = Dict[str, Any]

_MAX_TEXT_LENGTH = 10_000  # Hard safety limit for loaded task text


class TaskManager:
    """Manages task lifecycle and JSON persistence.

    All public methods are safe to call from the main thread.
    The debounced save runs on a daemon ``Timer`` thread but only
    reads a snapshot taken under the lock.
    """

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

    # ── Read access (thread-safe copies) ─────

    @property
    def tasks(self) -> List[Task]:
        """Return a shallow copy of the task list."""
        with self._lock:
            return list(self._tasks)

    @property
    def task_count(self) -> int:
        with self._lock:
            return len(self._tasks)

    @property
    def completed_count(self) -> int:
        with self._lock:
            return sum(1 for t in self._tasks if t["completed"])

    @property
    def pending_count(self) -> int:
        with self._lock:
            return len(self._tasks) - sum(1 for t in self._tasks if t["completed"])

    def task_by_id(self, task_id: str) -> Optional[Task]:
        with self._lock:
            for t in self._tasks:
                if t["id"] == task_id:
                    return dict(t)  # Return a copy
        return None

    def index_of(self, task_id: str) -> int:
        """Return the current index of *task_id*.

        Raises ``ValueError`` if not found.
        """
        with self._lock:
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
        with self._lock:
            self._tasks.append(task)
        self._schedule_save()
        logger.info("Task added: %s (id=%s)", text, task["id"])
        return dict(task)

    def delete_task(self, task_id: str) -> Optional[Task]:
        with self._lock:
            idx = self._index_of_unlocked(task_id)
            if idx is None:
                logger.warning("delete_task: id '%s' not found", task_id)
                return None
            removed = self._tasks.pop(idx)
        self._schedule_save()
        logger.info("Task deleted: %s", task_id)
        return removed

    def toggle_task(self, task_id: str) -> Optional[Task]:
        with self._lock:
            idx = self._index_of_unlocked(task_id)
            if idx is None:
                return None
            self._tasks[idx]["completed"] = not self._tasks[idx]["completed"]
            result = dict(self._tasks[idx])
        self._schedule_save()
        logger.info("Task toggled: %s → %s", task_id, result["completed"])
        return result

    def reorder_tasks(self, old_idx: int, new_idx: int) -> bool:
        with self._lock:
            if not (0 <= old_idx < len(self._tasks) and 0 <= new_idx < len(self._tasks)):
                return False
            task = self._tasks.pop(old_idx)
            self._tasks.insert(new_idx, task)
        self._schedule_save()
        return True

    def clear_completed(self) -> int:
        with self._lock:
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
        """Cancel any pending timer and save immediately (synchronous)."""
        with self._lock:
            if self._save_timer is not None:
                self._save_timer.cancel()
                self._save_timer = None
        self._do_save()

    def _do_save(self) -> None:
        """Persist tasks to disk atomically.

        Takes a snapshot under the lock, then writes outside it so
        the lock is never held during I/O.
        """
        with self._lock:
            snapshot = copy.deepcopy(self._tasks)

        try:
            dir_name = os.path.dirname(self.tasks_file) or "."
            os.makedirs(dir_name, exist_ok=True)
            fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    json.dump(snapshot, fh, ensure_ascii=False, indent=2)
                os.replace(tmp_path, self.tasks_file)
                logger.debug("Tasks saved to %s", self.tasks_file)
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
                # Callback is expected to be thread-safe (e.g. root.after)
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
            sanitised = []
            for item in data:
                try:
                    sanitised.append(self._sanitise_task(item))
                except (TypeError, ValueError) as exc:
                    logger.warning("Skipping malformed task: %s", exc)
            self._tasks = sanitised
            logger.info("Loaded %d task(s) from %s", len(self._tasks), self.tasks_file)
        except Exception as exc:
            msg = f"Error loading tasks: {exc}"
            logger.error(msg, exc_info=True)
            if self.error_callback:
                self.error_callback(msg)
            self._tasks = []

    @staticmethod
    def _sanitise_task(raw: Any) -> Task:
        """Validate and normalise a single task dict.

        Raises ``TypeError`` if *raw* is not a dict.
        """
        if not isinstance(raw, dict):
            raise TypeError(f"Task must be a dict, got {type(raw).__name__}")

        text = str(raw.get("text", ""))
        if len(text) > _MAX_TEXT_LENGTH:
            text = text[:_MAX_TEXT_LENGTH]
            logger.warning("Truncated oversized task text to %d chars", _MAX_TEXT_LENGTH)

        task_id = raw.get("id")
        if not isinstance(task_id, str) or not task_id.strip():
            task_id = uuid.uuid4().hex

        return {
            "id": task_id,
            "text": text,
            "completed": bool(raw.get("completed", False)),
        }

    # ── Internal helpers ─────────────────────

    def _index_of_unlocked(self, task_id: str) -> Optional[int]:
        """Find index of *task_id* WITHOUT acquiring the lock.

        Must be called while ``self._lock`` is already held.
        Returns ``None`` instead of raising if not found.
        """
        for i, t in enumerate(self._tasks):
            if t["id"] == task_id:
                return i
        return None