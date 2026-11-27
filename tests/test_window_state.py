import json

import pytest

from fly_notes.platform.window_state import (
    Rect,
    WindowGeometry,
    choose_geometry,
    is_reachable,
    load_always_on_top,
    load_geometry,
    save_always_on_top,
    save_geometry,
    state_file_for,
)

PRIMARY = Rect(0, 0, 1920, 1040)
RIGHT = Rect(1920, 0, 3840, 1040)
DEFAULT = WindowGeometry(320, 480, 100, 100)


def choose(saved, monitors=(PRIMARY,)):
    return choose_geometry(saved, DEFAULT, list(monitors), min_width=200, min_height=150)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("320x480+100+200", WindowGeometry(320, 480, 100, 200)),
        ("320x480+-8+-8", WindowGeometry(320, 480, -8, -8)),
        ("1x1+0+0", WindowGeometry(1, 1, 0, 0)),
    ],
)
def test_tk_geometry_round_trip(text, expected):
    assert WindowGeometry.from_tk(text) == expected
    assert WindowGeometry.from_tk(expected.to_tk()) == expected


def test_from_tk_rejects_garbage():
    with pytest.raises(ValueError):
        WindowGeometry.from_tk("320x480")


def test_state_file_sits_next_to_the_tasks_file(tmp_path):
    assert state_file_for(str(tmp_path / "tasks.json")) == str(tmp_path / "state.json")


def test_save_then_load_round_trip_keeps_other_keys(tmp_path):
    path = tmp_path / "state.json"
    path.write_text(json.dumps({"future": 1}), encoding="utf-8")
    geometry = WindowGeometry(400, 600, -1500, 30)

    save_geometry(str(path), geometry)

    assert load_geometry(str(path)) == geometry
    assert json.loads(path.read_text(encoding="utf-8"))["future"] == 1
    assert [p.name for p in tmp_path.iterdir()] == ["state.json"]  # no temp files left


@pytest.mark.parametrize(
    "content",
    [
        "{not json",
        "[]",
        '{"window": {"width": 300}}',
        '{"window": {"width": "300", "height": 400, "x": 0, "y": 0}}',
        '{"window": {"width": true, "height": 400, "x": 0, "y": 0}}',
        '{"window": {"width": 0, "height": 400, "x": 0, "y": 0}}',
    ],
)
def test_load_ignores_missing_or_invalid_state(tmp_path, content):
    path = tmp_path / "state.json"
    assert load_geometry(str(path)) is None
    path.write_text(content, encoding="utf-8")
    assert load_geometry(str(path)) is None


def test_saved_geometry_is_restored_when_on_screen():
    saved = WindowGeometry(400, 600, 1200, 300)
    assert choose(saved) == saved


def test_no_saved_geometry_uses_default():
    assert choose(None) == DEFAULT


@pytest.mark.parametrize(
    "saved",
    [
        WindowGeometry(320, 480, 2500, 100),  # was on a monitor that is gone
        WindowGeometry(320, 480, -2000, 100),
        WindowGeometry(320, 480, 100, 1100),  # below the bottom edge
        WindowGeometry(320, 480, 100, -400),  # header above the top edge
        WindowGeometry(320, 480, 1890, 100),  # only 30 px of the header visible
    ],
)
def test_off_screen_position_falls_back_to_default(saved):
    assert choose(saved) == DEFAULT


def test_position_on_a_second_monitor_is_kept_while_it_is_connected():
    saved = WindowGeometry(320, 480, 2500, 100)
    assert choose(saved, monitors=(PRIMARY, RIGHT)) == saved


def test_window_straddling_two_monitors_is_reachable():
    assert is_reachable(WindowGeometry(320, 480, 1800, 100), [PRIMARY, RIGHT])


def test_size_below_minimum_is_raised_to_the_minimum():
    restored = choose(WindowGeometry(50, 40, 100, 100))
    assert (restored.width, restored.height, restored.x, restored.y) == (200, 150, 100, 100)


# ── Always on top (#14) ──────────────────────


def test_always_on_top_round_trips_and_keeps_the_geometry(tmp_path):
    path = str(tmp_path / "state.json")
    assert load_always_on_top(path) is None  # no file yet

    save_geometry(path, WindowGeometry(320, 480, 10, 20))
    save_always_on_top(path, False)
    assert load_always_on_top(path) is False
    assert load_geometry(path) == WindowGeometry(320, 480, 10, 20)

    # ...and saving the geometry again keeps the pin choice
    save_geometry(path, WindowGeometry(400, 500, 0, 0))
    assert load_always_on_top(path) is False


@pytest.mark.parametrize("content", ['{"always_on_top": "no"}', '{"always_on_top": 0}', "[1]", "{"])
def test_invalid_always_on_top_is_ignored(tmp_path, content):
    path = tmp_path / "state.json"
    path.write_text(content, encoding="utf-8")
    assert load_always_on_top(str(path)) is None
