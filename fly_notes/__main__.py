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


def _configure_platform() -> None:
    """Platform-specific setup. MUST run before any Tk window is created."""
    if sys.platform == "win32":
        try:
            import ctypes

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

    # Imported only now so that DPI awareness (above) is set before the
    # config module and the UI load, and logging is already configured.
    from fly_notes import __version__
    from fly_notes.config import config
    from fly_notes.single_instance import SingleInstance, instance_key

    # One instance per tasks file: a second launch brings the first to the front.
    guard = SingleInstance(instance_key(config.tasks_file))
    if not guard.acquire():
        if guard.notify_existing():
            log.info("Fly Notes is already running; brought it to the front")
        else:
            log.warning("Fly Notes is already running; could not bring it to the front")
        return
    atexit.register(guard.release)

    root = tk.Tk()
    root.withdraw()

    from fly_notes.fly_notes_app import FlyNotesApp

    log.info("Fly Notes %s starting", __version__)
    app = FlyNotesApp(root)
    app.listen_for_activation(guard.show_requested)
    # Safety net: persist any change still waiting on the save debounce if the
    # process exits by a path that bypasses the app's close handler.
    atexit.register(app.manager.flush)
    root.deiconify()
    root.mainloop()


if __name__ == "__main__":
    main()
