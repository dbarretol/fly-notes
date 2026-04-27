"""
Fly Notes — Lightweight floating sticky-notes task manager.
Entry point: configures the platform, creates the root window, and launches the app.
"""

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


def main() -> None:
    """Application bootstrap."""
    _configure_platform()

    root = tk.Tk()
    root.withdraw()

    from fly_notes.fly_notes_app import FlyNotesApp

    app = FlyNotesApp(root)
    root.deiconify()
    root.mainloop()


if __name__ == "__main__":
    main()