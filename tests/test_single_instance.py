import sys
import uuid

import pytest

from fly_notes import __main__
from fly_notes.config import default_config
from fly_notes.platform.single_instance import SingleInstance, instance_key

windows_only = pytest.mark.skipif(sys.platform != "win32", reason="named mutex is Windows-only")


@pytest.fixture
def key():
    # Unique per test so parallel or leftover handles never collide.
    return f"FlyNotesTest-{uuid.uuid4().hex}"


@pytest.fixture
def guards():
    made = []
    yield made
    for g in made:
        g.release()


def _guard(guards, key):
    g = SingleInstance(key)
    guards.append(g)
    return g


def test_instance_key_depends_only_on_the_tasks_file(tmp_path):
    a = instance_key(str(tmp_path / "tasks.json"))
    assert a == instance_key(str(tmp_path / "." / "tasks.json"))
    assert a != instance_key(str(tmp_path / "other.json"))
    assert "\\" not in a  # backslash is reserved in kernel object names


@windows_only
def test_instance_key_ignores_case_on_windows(tmp_path):
    path = str(tmp_path / "tasks.json")
    assert instance_key(path) == instance_key(path.upper())


@windows_only
def test_second_instance_for_the_same_key_is_refused(guards, key):
    assert _guard(guards, key).acquire()
    assert not _guard(guards, key).acquire()


@windows_only
def test_a_different_tasks_file_can_run_side_by_side(guards, key):
    assert _guard(guards, key).acquire()
    assert _guard(guards, key + "-other").acquire()


@windows_only
def test_released_guard_lets_the_next_instance_start(guards, key):
    first = _guard(guards, key)
    assert first.acquire()
    first.release()
    assert _guard(guards, key).acquire()


@windows_only
def test_second_launch_signals_the_running_instance_once(guards, key):
    first = _guard(guards, key)
    assert first.acquire()
    assert not first.show_requested()

    second = _guard(guards, key)
    assert not second.acquire()
    assert second.notify_existing()

    assert first.show_requested()
    assert not first.show_requested()  # auto-reset: one request, one show


def test_guard_is_a_no_op_without_the_windows_api(key):
    guard = SingleInstance(key)
    guard._kernel32 = None  # as on other platforms
    assert guard.acquire()
    assert not guard.notify_existing()
    assert not guard.show_requested()
    guard.release()


def test_main_exits_without_a_window_when_already_running(monkeypatch, tmp_path):
    calls = []

    class Taken:
        def __init__(self, key):
            pass

        def acquire(self):
            return False

        def notify_existing(self):
            calls.append("notify")
            return True

    def no_window(*args, **kwargs):
        raise AssertionError("a second instance must not create a window")

    monkeypatch.setattr(__main__, "SingleInstance", Taken)
    monkeypatch.setattr(__main__, "load_config", lambda: default_config(tmp_path / "t.json"))
    monkeypatch.setattr(__main__, "_configure_logging", lambda: None)
    monkeypatch.setattr(__main__, "_configure_platform", lambda: None)
    monkeypatch.setattr(__main__.tk, "Tk", no_window)
    __main__.main()
    assert calls == ["notify"]
