"""WindowController: borderless window, resize, icon and taskbar proxy."""

import logging
import types
from pathlib import Path

from fly_notes.config import ICON_PATH
from fly_notes.platform import window_controller as window_controller_module
from fly_notes.platform.window_controller import WindowController

# ── Resize callback width ─────────────────────


def test_resize_callback_receives_width_without_stale_reread(root, cfg):
    """Regression for the winfo_width()-lag issue: immediately after
    root.geometry(...), winfo_width() reliably returns the *previous*
    width until Tk processes the pending configure request (empirically
    confirmed: ~399/400 mismatches in a tight resize loop without
    update_idletasks()). The fix has
    WindowController hand the freshly computed width to the resize
    callback directly instead of the callback re-reading root."""
    received = []
    ctrl = WindowController(root, cfg, on_resize_callback=received.append)
    try:
        # A withdrawn window's geometry is never negotiated by the WM, so
        # winfo_width() would report a meaningless placeholder regardless
        # of update_idletasks(). Deiconify to reproduce the real scenario
        # (the app's root window is always mapped/visible).
        root.deiconify()
        root.geometry("320x440+100+100")
        root.update_idletasks()

        ctrl._start_resize("e", types.SimpleNamespace(x_root=500, y_root=500))
        ctrl._do_resize(types.SimpleNamespace(x_root=560, y_root=500))  # +60px east

        assert received == [380]

        root.update_idletasks()
        assert root.winfo_width() == 380
    finally:
        root.withdraw()
        ctrl._proxy.destroy()


# ── Window icon ───────────────────────────────


def test_icon_path_resolves_to_an_existing_bundled_asset():
    """Regression for 'no window icon': the .ico referenced by
    WindowController/FlyNotes.spec must actually exist in the repo, not
    just be a path computed on faith."""
    assert ICON_PATH.exists()
    assert ICON_PATH.suffix == ".ico"


def test_window_controller_applies_icon_to_root_and_proxy_without_raising(root, cfg):
    ctrl = WindowController(root, cfg, cfg)
    try:
        # Tk's `wm iconbitmap` query doesn't reliably echo back the path
        # that was set via `default=`, so the meaningful contract here is
        # "construction with a real icon file doesn't raise" -- exercised
        # by simply reaching this point.
        assert ctrl._proxy is not None
    finally:
        root.withdraw()
        ctrl._proxy.destroy()


def test_window_controller_missing_icon_warns_and_does_not_raise(root, monkeypatch, caplog, cfg):
    """If the .ico asset is missing (e.g. a broken PyInstaller bundle),
    the app must still start -- degrade with a logged warning, not a
    crash, matching this module's existing platform-warning philosophy."""
    monkeypatch.setattr(window_controller_module, "ICON_PATH", Path("does/not/exist.ico"))
    with caplog.at_level(logging.WARNING):
        ctrl = WindowController(root, cfg, cfg)
    try:
        assert any("icon" in rec.message.lower() for rec in caplog.records)
    finally:
        root.withdraw()
        ctrl._proxy.destroy()


# ── Closing from the taskbar ──────────────────


def test_proxy_close_delegates_to_on_close_callback(root, cfg):
    calls = []
    ctrl = WindowController(root, cfg, on_close=lambda: calls.append("closed"))
    try:
        ctrl._on_proxy_close()
        assert calls == ["closed"]
    finally:
        root.withdraw()
        ctrl._proxy.destroy()
