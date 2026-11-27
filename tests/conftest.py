import tkinter as tk

import pytest

from fly_notes.config import default_config


@pytest.fixture
def cfg(tmp_path):
    """The built-in defaults, never a local ``config.json``, with the tasks
    file in the test's temporary folder.

    Derive a variant with ``cfg.with_settings(...)`` or ``dataclasses.replace``.
    """
    return default_config(tasks_file=tmp_path / "tasks.json")


@pytest.fixture(scope="session")
def root():
    r = tk.Tk()
    r.withdraw()
    yield r
    r.destroy()


@pytest.fixture
def app_window(root):
    """A fresh window to host a full FlyNotesApp.

    A Toplevel of the shared root, never a second ``tk.Tk()``: creating
    another Tcl interpreter under pytest's output capture intermittently fails
    on Windows with "Can't find a usable init.tcl".
    """
    win = tk.Toplevel(root)
    win.withdraw()
    yield win
    if win.winfo_exists():
        win.destroy()


def pytest_collection_modifyitems(items):
    """Mark every test that needs a Tk display (directly or through ``app_window``) as ``gui``,
    so ``pytest -m "not gui"`` runs the rest on a machine without one."""
    for item in items:
        if "root" in getattr(item, "fixturenames", ()):
            item.add_marker(pytest.mark.gui)
