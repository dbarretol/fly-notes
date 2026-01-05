# Fly Notes 📝

A minimal, floating "widget-style" task manager for Windows 11. Designed to be lightweight and stay out of the way while keeping your tasks visible.

## Key Features

- **Floating Widget**: Stays on top of other windows.
- **Dynamic Transparency**: 
  - **100% Opaque** when you are interacting with it.
  - **30% Transparency** when you click away, preventing it from obstructing your view.
- **Customizable Orange Theme**: Features a strong orange title bar and pastel peach content area for high visibility and a modern look.
- **Task Management**:
  - **Quick Add**: Type and press Enter.
  - **Strikethrough**: Mark tasks as completed with a single click.
  - **Drag-and-Drop Reorder**: Effortlessly reorder tasks by dragging the task labels.
  - **Delete individual tasks** or **Clear all completed tasks** at once.
- **Header-Only Movement**: Drag the "Fly Notes" title bar to move the window.
- **Standalone Executable**: No installation required. Runs as a single `.exe`.

## How to Run

### Standalone (Recommended)
Simply run the executable located in `dist/FlyNotes.exe`.

### From Source
If you have Python installed, you can run it directly:
1. Install dependencies:
   ```bash
   pip install pyinstaller
   ```
2. Run the script:
   ```bash
   python fly_notes.py
   ```

## Configuration

You can easily customize the appearance by editing the global variables at the top of `fly_notes.py`:

```python
# --- GLOBAL CONFIGURATION ---
HEADER_BG = "#FF8C00"      # Strong Orange
CONTENT_BG = "#FFDAB9"     # Pastel Orange
ACTIVE_ALPHA = 1.0         # Opacity when focused
INACTIVE_ALPHA = 0.3       # Opacity when unfocused
```

## Building the Standalone Executable

The app is bundled using **PyInstaller**. This process creates a single `.exe` (Windows) or binary (Linux) that contains all necessary dependencies.

### Windows (Primary Support)

As this is a Windows 11 focused widget, the build process is most robust here.

1. **Prerequisites**:
   - Python 3.12+ installed.
   - A virtual environment is recommended:
     ```bash
     python -m venv venv
     .\venv\Scripts\activate
     ```
2. **Install Build Tools**:
   ```bash
   pip install pyinstaller
   ```
3. **Build Command**:
   ```bash
   pyinstaller --onefile --noconsole --name FlyNotes fly_notes.py --clean
   ```
   The result will be in the `dist/` folder.

### Linux (Experimental)

The app script (`fly_notes.py`) can run on Linux, but the "widget" experience (blur/transparency handling and window-over-all behavior) may vary depending on your desktop environment (GNOME, KDE, etc.).

1. **Prerequisites**:
   - Ensure `tkinter` is installed (often separate on Linux distributions):
     ```bash
     # Ubuntu/Debian
     sudo apt-get install python3-tk
     ```
2. **Build Command**:
   The same `pyinstaller` command applies. On Linux, this will generate a Linux ELF binary instead of an `.exe`.

### Platform Limitations
> [!IMPORTANT]
> - **Windows Only**: The standalone `.exe` generated on Windows **only works on Windows**. You cannot run the `.exe` on Linux or macOS.
> - **Visual Effects**: Specific features like `attributes("-alpha", ...)` and `overrideredirect(True)` are handled by the OS window manager. On Linux, some tiling window managers might ignore these settings.

## Technology

- **Language**: Python 3.x
- **GUI Framework**: `tkinter` (Built-in, lightweight)
- **Bundler**: `PyInstaller`
