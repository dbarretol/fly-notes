"""Pure decision logic for drag-and-drop reordering (no Tkinter)."""

from __future__ import annotations


def compute_reorder_target(
    visual_ids: list[str],
    visual_completed: list[bool],
    dragging_id: str,
    delta_y: int,
    threshold: int,
    enforce_group_boundary: bool = True,
) -> str | None:
    """Pure decision logic for drag-and-drop reordering.

    Given the *visually rendered* order of task ids (and their completed
    flag in that same order), the id of the task being dragged, and the
    vertical distance dragged since the gesture started, return the id
    of the neighboring task to swap with — or ``None`` if no swap should
    happen (below threshold, at the edge of the list, or the swap would
    cross the pending/completed group boundary).
    """
    try:
        idx = visual_ids.index(dragging_id)
    except ValueError:
        return None

    if delta_y < -threshold and idx > 0:
        direction = -1
    elif delta_y > threshold and idx < len(visual_ids) - 1:
        direction = 1
    else:
        return None

    target_idx = idx + direction
    if enforce_group_boundary and visual_completed[target_idx] != visual_completed[idx]:
        return None

    return visual_ids[target_idx]
