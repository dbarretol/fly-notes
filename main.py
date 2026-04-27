"""
Fly Notes — Lightweight floating sticky‑notes task manager.
Entry point: configures the platform, creates the root window, and launches the app.
"""

import sys
import tkinter as tk

def _configure_platform() -> None:
    """Platform-specific setup. MUST run before any Tk window is created."""
    if sys.platform == "win32":
        try:
            import ctypes
            # 1 = PROCESS_SYSTEM_DPI_AWARE — respects per-monitor DPI
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (ImportError, AttributeError, OSError):
            pass  # Graceful fallback on older Windows versions


def main() -> None:
    """Application bootstrap."""
    _configure_platform()            # ← ANTES de tk.Tk()

    root = tk.Tk()
    root.withdraw()                  # Hide until fully built

    # Lazy import so platform config takes effect first
    from fly_notes.fly_notes_app import FlyNotesApp

    app = FlyNotesApp(root)
    root.deiconify()                 # Show once UI is ready
    root.mainloop()


if __name__ == "__main__":
    main()