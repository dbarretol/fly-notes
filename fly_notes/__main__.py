"""
Fly Notes — lightweight floating task widget.

Entry point: configures the platform, creates the root window and launches
the app. Run with ``python -m fly_notes``, the ``fly-notes`` console script,
or ``python main.py`` from a source checkout.
"""

import atexit
import logging
import sys
import tkinter as tk

from fly_notes import __version__
from fly_notes.config import load_config
from fly_notes.platform.single_instance import SingleInstance, instance_key
from fly_notes.ui.app import FlyNotesApp


def _configure_platform() -> None:
    """Platform-specific setup. MUST run before any Tk window is created."""
    if sys.platform == "win32":
        try:
            import ctypes  # noqa: PLC0415 -- Windows-only, inside the guard

            # 1 = system aware: sharp on the main display; Windows stretches (and blurs)
            # the window on a monitor with another scaling. Per-monitor awareness (2) would
            # need every font and pixel size rebuilt on WM_DPICHANGED, which Tk 8.6 doesn't
            # do, so the window would just stay the wrong size there (#66, README).
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (ImportError, AttributeError, OSError):
            pass


def _configure_logging() -> None:
    """Bootstrap application-wide logging."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def main() -> None:
    """Application bootstrap."""
    _configure_logging()
    _configure_platform()
    log = logging.getLogger(__name__)

    cfg = load_config()

    # One instance per tasks file: a second launch brings the first to the front.
    guard = SingleInstance(instance_key(cfg.settings.tasks_file))
    if not guard.acquire():
        if guard.notify_existing():
            log.info("Fly Notes is already running; brought it to the front")
        else:
            log.warning("Fly Notes is already running; could not bring it to the front")
        return
    atexit.register(guard.release)

    root = tk.Tk()
    root.withdraw()

    log.info("Fly Notes %s starting", __version__)
    app = FlyNotesApp(root, cfg)
    app.listen_for_activation(guard.show_requested)
    # Safety net: persist any change still waiting on the save debounce if the
    # process exits by a path that bypasses the app's close handler.
    atexit.register(app.manager.flush)
    root.deiconify()
    root.mainloop()


if __name__ == "__main__":
    main()
