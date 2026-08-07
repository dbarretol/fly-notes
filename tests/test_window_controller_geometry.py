"""Unit tests for WindowController's pure resize-geometry logic.

``compute_resize_geometry`` has no Tkinter dependency, so these tests
run without a real display/``tk.Tk()`` — unlike the rest of
WindowController, which drives real Tk windows and taskbar proxies.
"""

from fly_notes.window_controller import compute_resize_geometry

START = dict(start_w=300, start_h=400, start_win_x=100, start_win_y=50)
MIN = dict(min_width=240, min_height=180)


def _resize(edge, dx, dy):
    return compute_resize_geometry(edge=edge, dx=dx, dy=dy, **START, **MIN)


# ── One edge per axis, growing and shrinking ─

def test_east_edge_grows_width_only():
    x, y, w, h = _resize("e", dx=50, dy=0)
    assert (x, y, w, h) == (100, 50, 350, 400)


def test_west_edge_grows_width_and_moves_x():
    x, y, w, h = _resize("w", dx=-50, dy=0)
    assert (x, y, w, h) == (50, 50, 350, 400)


def test_south_edge_grows_height_only():
    x, y, w, h = _resize("s", dx=0, dy=50)
    assert (x, y, w, h) == (100, 50, 300, 450)


def test_north_edge_grows_height_and_moves_y():
    x, y, w, h = _resize("n", dx=0, dy=-50)
    assert (x, y, w, h) == (100, 0, 300, 450)


# ── Corners: both axes at once ───────────────

def test_northeast_corner():
    x, y, w, h = _resize("ne", dx=30, dy=-20)
    assert (x, y, w, h) == (100, 30, 330, 420)


def test_northwest_corner():
    x, y, w, h = _resize("nw", dx=-30, dy=-20)
    assert (x, y, w, h) == (70, 30, 330, 420)


def test_southeast_corner():
    x, y, w, h = _resize("se", dx=30, dy=20)
    assert (x, y, w, h) == (100, 50, 330, 420)


def test_southwest_corner():
    x, y, w, h = _resize("sw", dx=-30, dy=20)
    assert (x, y, w, h) == (70, 50, 330, 420)


# ── Clamping at min_width/min_height ─────────

def test_east_edge_clamps_at_min_width():
    x, y, w, h = _resize("e", dx=-1000, dy=0)
    assert w == MIN["min_width"]
    assert (x, y) == (100, 50)  # east edge never moves x


def test_west_edge_clamps_and_freezes_right_edge():
    # Dragging west edge far to the right (dx large positive) shrinks
    # width toward min; x must stop advancing once clamped, so the
    # window's right edge (x + w) stays fixed rather than drifting.
    x, y, w, h = _resize("w", dx=1000, dy=0)
    assert w == MIN["min_width"]
    assert x + w == START["start_win_x"] + START["start_w"]


def test_south_edge_clamps_at_min_height():
    x, y, w, h = _resize("s", dx=0, dy=-1000)
    assert h == MIN["min_height"]
    assert (x, y) == (100, 50)  # south edge never moves y


def test_north_edge_clamps_and_freezes_bottom_edge():
    x, y, w, h = _resize("n", dx=0, dy=1000)
    assert h == MIN["min_height"]
    assert y + h == START["start_win_y"] + START["start_h"]


def test_northwest_corner_clamps_both_axes():
    x, y, w, h = _resize("nw", dx=1000, dy=1000)
    assert (w, h) == (MIN["min_width"], MIN["min_height"])
    assert x + w == START["start_win_x"] + START["start_w"]
    assert y + h == START["start_win_y"] + START["start_h"]


# ── No-op ─────────────────────────────────────

def test_zero_delta_is_a_no_op_for_every_edge():
    for edge in ("n", "s", "e", "w", "ne", "nw", "se", "sw"):
        x, y, w, h = _resize(edge, dx=0, dy=0)
        assert (x, y, w, h) == (
            START["start_win_x"], START["start_win_y"],
            START["start_w"], START["start_h"],
        )
