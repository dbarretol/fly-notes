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


def test_unknown_dragging_id_has_no_target(cfg):
    threshold = cfg.settings.drag_threshold
    assert compute_reorder_target(["A", "B"], [False, False], "missing", -50, threshold) is None


def test_movement_below_the_threshold_has_no_target(cfg):
    ids, done = ["A", "B", "C"], [False, False, False]
    threshold = cfg.settings.drag_threshold
    assert compute_reorder_target(ids, done, "B", 0, threshold) is None
    assert compute_reorder_target(ids, done, "B", threshold, threshold) is None
    assert compute_reorder_target(ids, done, "B", -threshold, threshold) is None


def test_edges_have_no_target_in_their_direction(cfg):
    ids, done = ["A", "B", "C"], [False, False, False]
    threshold = cfg.settings.drag_threshold
    assert compute_reorder_target(ids, done, "A", -(threshold + 1), threshold) is None
    assert compute_reorder_target(ids, done, "C", threshold + 1, threshold) is None


def test_downward_drag_targets_the_next_visible_item(cfg):
    ids, done = ["A", "C", "D"], [False, False, False]
    threshold = cfg.settings.drag_threshold
    assert compute_reorder_target(ids, done, "C", threshold + 1, threshold) == "D"


def test_group_boundary_can_be_disabled(cfg):
    ids, done = ["A", "B"], [False, True]
    threshold = cfg.settings.drag_threshold
    assert compute_reorder_target(ids, done, "A", threshold + 1, threshold) is None
    assert compute_reorder_target(ids, done, "A", threshold + 1, threshold, False) == "B"
