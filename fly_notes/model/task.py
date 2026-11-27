"""The ``Task`` record and its conversion to and from the JSON in ``tasks.json``."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

MAX_TEXT_LENGTH = 10_000  # Hard safety limit for task text, whatever the config says


def new_task_id() -> str:
    return uuid.uuid4().hex


@dataclass(frozen=True, slots=True)
class Task:
    """One task. Immutable: change it with ``dataclasses.replace``."""

    id: str
    text: str
    completed: bool = False

    @classmethod
    def new(cls, text: str, completed: bool = False) -> Task:
        """A task with a fresh random id."""
        return cls(id=new_task_id(), text=text, completed=completed)

    def to_dict(self) -> dict[str, Any]:
        """The JSON object stored in ``tasks.json``."""
        return {"id": self.id, "text": self.text, "completed": self.completed}

    @classmethod
    def from_dict(cls, raw: Any) -> Task:
        """Build a task from a ``tasks.json`` entry, repairing what it can.

        Text is converted to a string and cut to ``MAX_TEXT_LENGTH``. A missing
        or blank id, or one that is not a string, is replaced with a new one.
        ``completed`` is read as a boolean.

        Raises ``TypeError`` if *raw* is not a dict.
        """
        if not isinstance(raw, dict):
            raise TypeError(f"Task must be a dict, got {type(raw).__name__}")

        text = str(raw.get("text", ""))
        if len(text) > MAX_TEXT_LENGTH:
            text = text[:MAX_TEXT_LENGTH]
            logger.warning("Truncated oversized task text to %d chars", MAX_TEXT_LENGTH)

        task_id = raw.get("id")
        if not isinstance(task_id, str) or not task_id.strip():
            task_id = new_task_id()

        return cls(id=task_id, text=text, completed=bool(raw.get("completed", False)))
