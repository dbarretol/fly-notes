# Fly Notes

A minimal, floating “widget-style” task manager built with Python + Tkinter. Optimized for Windows 11: stays on top, fades when inactive, and supports reliable minimize/restore using a taskbar proxy window.

## Features

- **Floating & borderless widget** (always on top)
- **Dynamic transparency**
  - **100% opaque** when focused
  - **30% transparent** when unfocused
- **Task management**
  - Add tasks quickly (**type + Enter**)
  - Mark complete (**checkbox + strikethrough**)
  - **Drag-and-drop reorder** (drag the task label)
  - Delete tasks individually
  - **Clear completed** tasks
- **Header-only movement**: drag the orange header to move the window
- **Manual resizing**: drag right/bottom edges or bottom-right corner
- **Reliable minimize/restore on Windows 11**: implemented via a **Taskbar Proxy Window** strategy

## Screens / Demo

(Add a screenshot or GIF here)

## Requirements

- **Windows 11** (primary supported experience)
- **Python**: 3.12+ recommended (you’re currently using 3.13.x)
- Tkinter is included with most Python installs on Windows.

## Run

### Option A: Run the standalone executable (recommended)
Run:
- `dist/FlyNotes.exe`

No installation required.

### Option B: Run from source
1. (Optional) Create and activate a virtual environment:
   ```powershell
   python -m venv venv
   .\venv\Scripts\activate
   ```

2. Run:
   ```powershell
   python fly_notes.py
   ```

> Note: You only need `pyinstaller` if you want to **build** the `.exe`.

## Configuration (Theme / Opacity)

Edit the global constants at the top of `fly_notes.py`:

```python
HEADER_BG = "#FF8C00"      # Title bar color
CONTENT_BG = "#FFDAB9"     # Body background
ITEM_BG = "#FFE4B5"        # Task row background

ACTIVE_ALPHA = 1.0         # Opacity when focused
INACTIVE_ALPHA = 0.3       # Opacity when unfocused
```

## Build (PyInstaller)

### Windows
1. Install PyInstaller:
   ```powershell
   pip install pyinstaller
   ```

2. Build:
   ```powershell
   pyinstaller --onefile --noconsole --name FlyNotes fly_notes.py --clean
   ```

Output:
- `dist/FlyNotes.exe`

## Platform Notes / Limitations

- The Windows `.exe` built by PyInstaller runs **only on Windows**.
- Transparency and borderless behavior depend on the OS/window manager.
- Linux/macOS may run the script, but the “widget-like” behavior (topmost, alpha, borderless, taskbar behavior) may differ.

## Tech Stack

- **Python**
- **Tkinter** (built-in GUI toolkit)
- **PyInstaller** (optional: packaging into a single executable)
- **Windows integration**: taskbar proxy technique for consistent minimize/restore on borderless windows

## License

MIT