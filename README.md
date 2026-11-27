# Fly Notes

A minimal, floating "widget-style" task manager built with Python + Tkinter.
Optimized for Windows 11: stays on top, fades when unfocused, and supports
reliable minimize/restore using a taskbar proxy window.

## Features

- **Floating & borderless widget**, always on top by default; the header pin (`▲`/`△`) or
  `Ctrl+T` turns that off and on, and the choice is remembered
- **Dynamic transparency** — opaque when focused, translucent shortly after it loses focus
- **Task management**
  - Add tasks quickly (**type + Enter**); long tasks wrap onto several lines
  - Mark complete (**checkbox + strikethrough**)
  - **Drag-and-drop reorder** (drag the task label)
  - **Fully keyboard-driven**: `Tab` or `↓` from the new-task field moves into the list;
    see [Keyboard Shortcuts](#keyboard-shortcuts)
  - **Edit in place**: double-click a task (or hover it and press `F2`); `Enter` saves,
    `Esc` cancels
  - Delete tasks individually
  - **Clear completed** tasks
  - **Undo** a deletion or a clear (footer "Undo" link for a few seconds, or `Ctrl+Z`):
    tasks come back at their original position
  - Automatic grouping into "To Do" / "Completed" sections, with a
    configurable cap on how many rows render at once (`settings.max_visible_tasks`);
    a **"Show N more"** link under the list reveals the rest, one page at a time
- **Header-only movement**: drag the header bar to move the window
- **8-direction manual resizing**: drag any edge or corner
- **Remembers its size and position** between sessions (and falls back to the default
  spot if that position is no longer on any connected monitor)
- **Reliable minimize/restore on Windows 11**, via a **Taskbar Proxy Window** strategy
- **Single instance**: launching Fly Notes again while it runs brings the open window to the
  front (restoring it if minimized) instead of starting a second copy that would overwrite
  the same `tasks.json`. Copies that use different tasks files can still run side by side
- **Debounced, atomic persistence** to a local `tasks.json` (survives crashes mid-write)
  - The previous version is kept as `tasks.json.bak`. If `tasks.json` ever becomes
    unreadable, it is moved aside as `tasks.corrupt-<timestamp>.json` (never overwritten)
    and the backup is restored automatically.
- **Fully configurable** — colors, spacing, fonts, shortcuts and behavior via `config.json`

## Screens / Demo

<p align="center">
  <img src="docs/images/fly-notes.png" width="330"
       alt="Fly Notes window: a header with the always-on-top pin, the new-task field, a To Do section with four tasks (one wrapping onto two lines), a Completed section with two struck-through tasks, and a footer reading '2 of 6 done' with a 'Clear completed (2)' link">
</p>

## Keyboard Shortcuts

| Key | Action |
|---|---|
| `Ctrl+N` | Focus the new-task field |
| `Enter` | Add the typed task |
| `Esc` | Clear the new-task field (never closes the app) |
| `F2` / double-click | Edit the task under the pointer (`Enter` saves, `Esc` cancels) |
| `Ctrl+D` | Clear completed tasks |
| `Ctrl+Z` | Undo the last deletion or clear (repeat to go further back) |
| `Ctrl+T` | Toggle always on top (same as the header pin) |
| `Ctrl+W` | Close Fly Notes |

On a focused task row (highlighted with a focus ring):

| Key | Action |
|---|---|
| `↑` / `↓` | Move to the previous / next task (`↑` on the first row returns to the new-task field) |
| `Space` | Mark complete / not complete |
| `Delete` | Delete the task (undo with `Ctrl+Z`) |
| `Alt+↑` / `Alt+↓` | Move the task up / down within its group |
| `F2` / `Enter` | Edit the task |

`↓` in the new-task field jumps to the first task. The window-level shortcuts above
can be changed in the `shortcuts` section of `config.json`, using Tk event
syntax (e.g. `"close": "<Control-q>"`).

## Requirements

- **Windows 11** (primary supported experience — see [Platform Notes](#platform-notes--limitations))
- **Python 3.12+**
- Tkinter (bundled with the standard Python installer on Windows)
- [uv](https://docs.astral.sh/uv/) (recommended for dependency/venv management — see `docs/AGENTS.md`)

## Quick Start

### Option A: Run the prebuilt executable

Download `FlyNotes.exe` from the [latest release](https://github.com/dbarretol/fly-notes/releases/latest)
(or build it yourself, see [Build the .exe](#build-the-exe-pyinstaller)) and run it directly — no
installation required.

### Option B: Run from source (uv)

```powershell
uv sync
uv run main.py
```

### Option B (alternative): Run from source (pip)

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -e .
fly-notes            # or: python -m fly_notes
```

## Project Structure

```
FLY_NOTES/
├── main.py                    # Thin launcher (also the PyInstaller entry script)
├── fly_notes/
│   ├── __main__.py            # Bootstrap: platform setup, logging, Tk root, mainloop
│   ├── config.py              # DEFAULT_CONFIG, validation, config.json loading/merging
│   ├── paths.py               # Where config/data live (source, installed .exe, portable .exe)
│   ├── task_manager.py        # Task CRUD + debounced atomic JSON persistence (no Tkinter)
│   ├── task_item.py           # TaskItem row widget + custom checkbox
│   ├── window_controller.py   # Borderless drag/resize + taskbar proxy (Windows-only bits)
│   ├── window_state.py        # Remembered window geometry + monitor checks (state.json)
│   ├── single_instance.py     # One running copy per tasks file (Windows named mutex)
│   └── fly_notes_app.py       # Main app orchestrator: header/entry/list/footer wiring
├── tests/                     # pytest suite (task manager, config, paths, window state, single instance, UI)
├── docs/                      # Contributor notes (AGENTS.md) and README images
├── .github/                   # CI workflow (ruff + pytest on Windows) and PR template
├── config.json                # Optional — your local overrides (not tracked; see below)
├── tasks.json                 # Your task data when running from source (not tracked)
├── FlyNotes.spec              # PyInstaller build spec
├── CHANGELOG.md
├── LICENSE
└── pyproject.toml
```

## Configuration

Fly Notes ships with sensible defaults (`fly_notes/config.py: DEFAULT_CONFIG`) covering
colors, spacing, fonts, window size/behavior, keyboard shortcuts and UI strings.

To customize anything, create a `config.json` file in the [data folder](#where-your-data-lives).
You only need to include the keys you want to override — everything else falls back to
the default. Unknown keys are ignored (with a warning logged), and invalid values
(e.g. a malformed hex color) cause the whole file to be rejected in favor of defaults,
so a typo can never crash the app.

Example — change the accent color and default window size:

```json
{
  "colors": {
    "header_bg": "#2D6A4F",
    "border_focus": "#2D6A4F"
  },
  "settings": {
    "default_width": 360,
    "default_height": 520,
    "max_visible_tasks": 50
  }
}
```

Available top-level sections: `colors`, `transparency`, `spacing`, `settings`, `fonts`,
`shortcuts`, `strings`. See `fly_notes/config.py` for the full list of keys and their
defaults.

### Where your data lives

| How you run Fly Notes | Location of `config.json`, `tasks.json` (+ `.bak`) and `state.json` |
|---|---|
| From source (`uv run main.py`) | Project root, next to `main.py` |
| `FlyNotes.exe` | `%APPDATA%\FlyNotes\` (created on first save) |
| `FlyNotes.exe`, portable | The executable's folder — used whenever a `config.json` or `tasks.json` already sits next to `FlyNotes.exe` |

The window's last size and position, and whether it stays on top, are kept in
`state.json`, next to `tasks.json`. Deleting it resets the window to the default size and
position and to `settings.always_on_top`.

`settings.tasks_file` overrides the tasks file location. A relative path is resolved
against the data folder above; an absolute path (environment variables such as
`%USERPROFILE%` are expanded) is used as-is.

## Development

Install dev dependencies (pytest, pytest-cov, ruff, pyinstaller):

```powershell
uv sync --extra dev
```

Run the test suite:

```powershell
uv run pytest tests/ -v
```

With coverage:

```powershell
uv run pytest tests/ --cov=fly_notes --cov-report=term-missing
```

Lint and format (configured in `pyproject.toml`):

```powershell
uv run ruff check .
uv run ruff format .
```

### Branches and CI

Work happens on short-lived branches (`feat/*`, `fix/*`, `chore/*`, `docs/*`) opened as pull
requests against `dev`; `main` only receives stable releases from `dev`. GitHub Actions
(`.github/workflows/ci.yml`) runs ruff and the test suite on Windows for every pull request
and push to `dev` and `main`.

## Build the .exe (PyInstaller)

### Using the provided spec (recommended)

```powershell
uv run pyinstaller FlyNotes.spec --clean
```

### Ad-hoc, without the spec file

```powershell
uv run pyinstaller --onefile --noconsole --name FlyNotes main.py --clean
```

Output: `dist/FlyNotes.exe`

> **Note:** the packaged `.exe` is a PyInstaller *onefile* build that extracts itself to a
> temporary directory on each launch, so it never stores data there. See
> [Where your data lives](#where-your-data-lives); to run it portably, put a `tasks.json`
> containing `[]` (or a `config.json`) next to `FlyNotes.exe`.

## Platform Notes / Limitations

- **Windows-only by design.** The borderless window + reliable minimize/restore relies
  on a **Taskbar Proxy Window** technique (see `fly_notes/window_controller.py`) built
  specifically around how Windows removes `overrideredirect(True)` windows from the
  taskbar.
- The `.exe` built by PyInstaller runs **only on Windows**.
- Transparency and borderless behavior depend on the OS/window manager.
- **Running on macOS/Linux is unsupported and untested.** The app still launches (a
  warning is logged), but expect broken behavior:
  - `overrideredirect(True)` behaves differently per window manager — the window may
    lose its taskbar/dock entry entirely, with no equivalent of the Windows taskbar
    icon to restore it from.
  - The taskbar-proxy minimize/restore trick assumes Windows taskbar semantics and does
    not translate to other platforms.
  - Dragging, resizing, and the task list itself are plain Tk and should still work.

## Tech Stack

- **Python 3.12+**
- **Tkinter** (built-in GUI toolkit)
- **PyInstaller** (dev-only: packaging into a single executable)
- **pytest / pytest-cov** (dev-only: test suite)
- **ruff** (dev-only: lint and format) and **GitHub Actions** (CI on Windows)
- **Windows integration**: taskbar proxy technique for consistent minimize/restore on
  borderless windows

## License

[MIT](LICENSE)
