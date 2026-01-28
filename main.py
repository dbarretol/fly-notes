import tkinter as tk
import sys
from fly_notes.fly_notes_app import FlyNotesApp

def main():
    root = tk.Tk()
    # Ensure DPI awareness if on Windows
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass # Fallback if shcore is not available

    app = FlyNotesApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
