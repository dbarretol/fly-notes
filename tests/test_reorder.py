"""compute_reorder_target: drag-and-drop decisions (no Tk)."""

from fly_notes.model.reorder import compute_reorder_target

# ── Drag-and-drop reorder ─────────────────────


def test_compute_reorder_target_uses_visual_order_not_insertion_order(cfg):
    """A(pend), B(done), C(pend) in insertion order render visually as
    [A, C, B] when grouped. Dragging C up past A should target A —
    not B, which is C's raw-insertion-order neighbor."""
    visual_ids = ["A", "C", "B"]
    visual_completed = [False, False, True]

    target = compute_reorder_target(
        visual_ids,
        visual_completed,
        dragging_id="C",
        delta_y=-(cfg.settings.drag_threshold + 1),
        threshold=cfg.settings.drag_threshold,
        enforce_group_boundary=True,
    )
    assert target == "A"


def test_compute_reorder_target_stops_at_group_boundary(cfg):
    """Dragging the first completed item further up (into the pending
    group) must not swap across the boundary."""
    visual_ids = ["A", "C", "B"]
    visual_completed = [False, False, True]

    target = compute_reorder_target(
        visual_ids,
        visual_completed,
        dragging_id="B",
        delta_y=-(cfg.settings.drag_threshold + 1),
        threshold=cfg.settings.drag_threshold,
        enforce_group_boundary=True,
    )
    assert target is None
