"""
Data layer — task CRUD with debounced atomic persistence.

Thread-safe: all mutations and reads of ``_tasks`` are protected
by ``_lock``.  The save timer serialises a snapshot under the lock
and writes to disk outside it.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
import threading
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime

from .task import MAX_TEXT_LENGTH, Task

logger = logging.getLogger(__name__)

_UNDO_LIMIT = 20  # Deletions remembered for undo (each "clear completed" counts as one)


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
        error_callback: Callable[[str], None] | None = None,
    ) -> None:
        self.tasks_file = tasks_file
        self.error_callback = error_callback
        self._tasks: list[Task] = []
        self._save_timer: threading.Timer | None = None
        self._lock = threading.Lock()
        # Set when an unreadable tasks file could not be moved aside: saving
        # would overwrite the user's only copy, so writes are refused instead.
        self._saves_blocked = False
        # Each entry is one undoable removal: the removed tasks with the index
        # each one had in the list before it was removed, in ascending order.
        self._undo_stack: list[list[tuple[int, Task]]] = []
        self._load_tasks()

    @property
    def backup_file(self) -> str:
        """Rolling copy of the previous tasks file, refreshed before every save."""
        return self.tasks_file + ".bak"

    # ── Read access (thread-safe) ────────────
    # Tasks are immutable, so handing them out needs no copy: only the list is copied.

    @property
    def tasks(self) -> list[Task]:
        """Return a copy of the task list."""
        with self._lock:
            return list(self._tasks)

    @property
    def task_count(self) -> int:
        with self._lock:
            return len(self._tasks)

    @property
    def completed_count(self) -> int:
        with self._lock:
            return sum(1 for t in self._tasks if t.completed)

    @property
    def pending_count(self) -> int:
        with self._lock:
            return len(self._tasks) - sum(1 for t in self._tasks if t.completed)

    def task_by_id(self, task_id: str) -> Task | None:
        with self._lock:
            for t in self._tasks:
                if t.id == task_id:
                    return t
        return None

    def index_of(self, task_id: str) -> int:
        """Return the current index of *task_id*.

        Raises ``ValueError`` if not found.
        """
        with self._lock:
            for i, t in enumerate(self._tasks):
                if t.id == task_id:
                    return i
        raise ValueError(f"Task id '{task_id}' not found")

    # ── CRUD ─────────────────────────────────

    def add_task(self, text: str, completed: bool = False) -> Task:
        task = Task.new(text, completed)
        with self._lock:
            self._tasks.append(task)
        self._schedule_save()
        # Only the id: task text is user content and stays out of the logs.
        logger.info("Task added: id=%s", task.id)
        return task

    def delete_task(self, task_id: str) -> Task | None:
        with self._lock:
            idx = self._index_of_unlocked(task_id)
            if idx is None:
                logger.warning("delete_task: id '%s' not found", task_id)
                return None
            removed = self._tasks.pop(idx)
            self._push_undo([(idx, removed)])
        self._schedule_save()
        logger.info("Task deleted: %s", task_id)
        return removed

    def toggle_task(self, task_id: str) -> Task | None:
        with self._lock:
            idx = self._index_of_unlocked(task_id)
            if idx is None:
                return None
            result = replace(self._tasks[idx], completed=not self._tasks[idx].completed)
            self._tasks[idx] = result
        self._schedule_save()
        logger.info("Task toggled: %s → %s", task_id, result.completed)
        return result

    def update_text(self, task_id: str, text: str, max_length: int | None = None) -> Task | None:
        """Replace a task's text; return the updated task, or ``None`` if nothing changed.

        *text* is stripped and cut to *max_length* (the UI passes the same
        ``max_task_length`` used for new tasks). Empty text is rejected, so an
        edit can never blank a task out.
        """
        clean = text.strip()
        limit = MAX_TEXT_LENGTH if max_length is None else min(max_length, MAX_TEXT_LENGTH)
        clean = clean[:limit].rstrip()
        if not clean:
            return None
        with self._lock:
            idx = self._index_of_unlocked(task_id)
            if idx is None:
                logger.warning("update_text: id '%s' not found", task_id)
                return None
            if self._tasks[idx].text == clean:
                return None
            result = replace(self._tasks[idx], text=clean)
            self._tasks[idx] = result
        self._schedule_save()
        logger.info("Task edited: %s", task_id)
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
            cleared = [(i, t) for i, t in enumerate(self._tasks) if t.completed]
            self._tasks = [t for t in self._tasks if not t.completed]
            removed = len(cleared)
            if cleared:
                self._push_undo(cleared)
        self._schedule_save()
        logger.info("Cleared %d completed task(s)", removed)
        return removed

    # ── Undo ─────────────────────────────────

    @property
    def can_undo(self) -> bool:
        with self._lock:
            return bool(self._undo_stack)

    def undo(self) -> list[Task]:
        """Restore the most recent deletion (or "clear completed") in place.

        Each task goes back to the index it had before it was removed (or
        the end of the list, if the list has since become shorter). Returns
        the restored tasks in list order; empty if nothing to undo.
        """
        with self._lock:
            if not self._undo_stack:
                return []
            entry = self._undo_stack.pop()
            present = {t.id for t in self._tasks}
            restored: list[Task] = []
            for idx, task in entry:
                if task.id in present:
                    continue
                self._tasks.insert(min(idx, len(self._tasks)), task)
                restored.append(task)
        if restored:
            self._schedule_save()
        logger.info("Undo restored %d task(s)", len(restored))
        return restored

    def _push_undo(self, entry: list[tuple[int, Task]]) -> None:
        """Remember a removal. Must be called while ``self._lock`` is held."""
        self._undo_stack.append(entry)
        del self._undo_stack[:-_UNDO_LIMIT]

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
        if self._saves_blocked:
            logger.warning("Save skipped: %s could not be read or moved aside", self.tasks_file)
            return

        with self._lock:
            snapshot = [t.to_dict() for t in self._tasks]

        try:
            dir_name = os.path.dirname(self.tasks_file) or "."
            os.makedirs(dir_name, exist_ok=True)
            fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    json.dump(snapshot, fh, ensure_ascii=False, indent=2)
                    # Make sure the bytes are on disk before the rename below,
                    # so a power loss can't leave a truncated tasks file.
                    fh.flush()
                    os.fsync(fh.fileno())
                self._refresh_backup()
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

    def _refresh_backup(self) -> None:
        """Copy the current tasks file to ``backup_file`` before it is replaced."""
        if not os.path.exists(self.tasks_file):
            return
        try:
            shutil.copy2(self.tasks_file, self.backup_file)
        except OSError as exc:
            logger.warning("Could not refresh backup %s: %s", self.backup_file, exc)

    def _load_tasks(self) -> None:
        if not os.path.exists(self.tasks_file):
            logger.info("No tasks file at %s — starting fresh", self.tasks_file)
            return
        try:
            tasks, skipped = self._read_tasks_file(self.tasks_file)
        except Exception as exc:
            logger.error("Error loading tasks from %s", self.tasks_file, exc_info=True)
            self._recover_from_unreadable_file(exc)
            return

        self._tasks = tasks
        logger.info("Loaded %d task(s) from %s", len(tasks), self.tasks_file)
        if skipped:
            kept = self._preserve_original(move=False)
            where = f" The original file was kept at {kept}." if kept else ""
            self._report(f"{skipped} malformed task(s) in {self.tasks_file} were skipped.{where}")

    def _read_tasks_file(self, path: str) -> tuple[list[Task], int]:
        """Parse *path*; return the sanitised tasks and how many entries were skipped.

        Raises if the file is not valid JSON or its root is not a list.
        """
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, list):
            raise TypeError(f"Expected list, got {type(data).__name__}")
        sanitised: list[Task] = []
        skipped = 0
        for item in data:
            try:
                sanitised.append(Task.from_dict(item))
            except (TypeError, ValueError) as exc:
                skipped += 1
                logger.warning("Skipping malformed task: %s", exc)
        return sanitised, skipped

    def _recover_from_unreadable_file(self, exc: Exception) -> None:
        """Never let the next save overwrite a file we failed to read.

        The unreadable file is moved aside; if a valid backup exists it is
        restored, otherwise the app starts empty. If the file can't be moved,
        saving is disabled for this session.
        """
        self._tasks = []
        moved = self._preserve_original(move=True)
        if moved is None:
            self._saves_blocked = True
            self._report(
                f"Could not read {self.tasks_file} ({exc}). Saving is disabled so the file "
                "is not overwritten — fix or remove it, then restart Fly Notes."
            )
            return

        if os.path.exists(self.backup_file):
            try:
                tasks, _ = self._read_tasks_file(self.backup_file)
            except Exception:
                logger.warning("Backup %s is unreadable too", self.backup_file, exc_info=True)
            else:
                self._tasks = tasks
                self._do_save()
                self._report(
                    f"{self.tasks_file} could not be read ({exc}) and was moved to {moved}. "
                    f"Restored {len(tasks)} task(s) from the last backup."
                )
                return

        self._report(
            f"{self.tasks_file} could not be read ({exc}) and was moved to {moved}. "
            "Starting with an empty list."
        )

    def _preserve_original(self, *, move: bool) -> str | None:
        """Move or copy the tasks file to ``<name>.corrupt-<timestamp>.json``.

        Returns the new path, or ``None`` if the file couldn't be preserved.
        """
        base, ext = os.path.splitext(self.tasks_file)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        target = f"{base}.corrupt-{stamp}{ext}"
        n = 1
        while os.path.exists(target):
            target = f"{base}.corrupt-{stamp}-{n}{ext}"
            n += 1
        try:
            if move:
                os.replace(self.tasks_file, target)
            else:
                shutil.copy2(self.tasks_file, target)
        except OSError:
            logger.error("Could not preserve %s as %s", self.tasks_file, target, exc_info=True)
            return None
        logger.warning("Preserved original tasks file as %s", target)
        return target

    def _report(self, message: str) -> None:
        logger.error(message)
        if self.error_callback:
            self.error_callback(message)

    # ── Internal helpers ─────────────────────

    def _index_of_unlocked(self, task_id: str) -> int | None:
        """Find index of *task_id* WITHOUT acquiring the lock.

        Must be called while ``self._lock`` is already held.
        Returns ``None`` instead of raising if not found.
        """
        for i, t in enumerate(self._tasks):
            if t.id == task_id:
                return i
        return None
