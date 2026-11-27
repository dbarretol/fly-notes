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

    root = tk.Tk()
    root.withdraw()

    # Imported only now so that DPI awareness (above) is set before the
    # config module and the UI load, and logging is already configured.
    from fly_notes import __version__
    from fly_notes.fly_notes_app import FlyNotesApp

    logging.getLogger(__name__).info("Fly Notes %s starting", __version__)
    app = FlyNotesApp(root)
    # Safety net: persist any change still waiting on the save debounce if the
    # process exits by a path that bypasses the app's close handler.
    atexit.register(app.manager.flush)
    root.deiconify()
    root.mainloop()


if __name__ == "__main__":
    main()
