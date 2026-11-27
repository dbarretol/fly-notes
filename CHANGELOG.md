# Changelog

All notable changes to Fly Notes are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-11-27

First stable release. It adds an optional dark theme, and releases are now built and published
by CI from a version tag. `tasks.json`, `state.json` and `config.json` need no changes.

### Added

- Optional dark theme: set `settings.theme` to `"dark"` in `config.json`. Colors set in
  `colors` still override the preset, and both presets pass the same contrast checks. ([#65])
- CI builds `FlyNotes.exe` on every push to `main`, after lint and tests pass, and uploads it
  with a SHA-256 checksum as a workflow artifact. ([#29])
- Pushing a `vX.Y.Z` tag on `main` publishes the GitHub Release: a workflow checks that the
  tag matches `pyproject.toml` and has a `CHANGELOG.md` section, runs the tests, builds
  `FlyNotes.exe` and attaches it with a `FlyNotes.exe.sha256` file, using that section as the
  notes. ([#30])
- Dependabot opens weekly pull requests against `dev` that update the GitHub Actions and the
  development tools in `uv.lock`. ([#32])
- The README shows how to check a downloaded `FlyNotes.exe` against its published SHA-256. The
  `.exe` stays unsigned. ([#32])
- The README explains how display scaling works on a second monitor with a different scaling,
  and why the window isn't rescaled there. ([#66])

### Fixed

- The new-task field and the inline editor take their background from `item_bg` instead of a
  fixed white, so they follow the theme. ([#65])

## [0.3.0] - 2026-11-27

Maintenance and speed release: the code is reorganized, typed and better tested, and long
lists open and react faster. Nothing changes in how the app looks or is used, and
`tasks.json` and `state.json` need no migration. `config.json` is checked more strictly:
a file with an invalid value still falls back to the defaults, with a warning naming the key.

### Changed

- The code is organized in three layers: `fly_notes/model/` (tasks and saving),
  `fly_notes/ui/` (one module per widget) and `fly_notes/platform/` (Windows window
  management, window state, single instance). Nothing changes for users. ([#21])
- Tasks are a typed, immutable `Task` record in the code instead of plain dictionaries.
  The `tasks.json` format is unchanged. ([#20])
- Saves are scheduled with Tk's `after()` on the UI thread instead of a background
  `threading.Timer`, so the task store no longer needs a lock. Saving still happens half a
  second after the last change, and immediately on close. ([#19])
- The configuration is typed and passed in explicitly: `load_config()` builds an immutable
  `AppConfig` (`cfg.colors.header_bg`, `cfg.spacing.md`, ...) in `main()`, and the widgets
  receive it instead of reading a global that loaded `config.json` at import time. Tests use
  pure defaults, whatever `config.json` is on the machine. ([#17])
- `colors.btn_danger_hover` now colors the delete button while it is pressed, and
  `colors.checkbox_bg` the inside of an unticked checkbox. Both were defined but never used;
  their defaults keep the current look. ([#18])
- Tests are split by module (`test_app.py`, `test_task_item.py`, `test_task_list.py`, ...),
  share their Tk fixtures through `tests/conftest.py`, and the ones that need a display are
  marked `gui`. `TaskItem` keeps its child widgets private and offers `bind_scroll()`, which
  also makes the mouse wheel work over the padding around a task's text. ([#22])
- The code is type-checked with pyright in CI, and imports sit at the top of each file
  (ruff `PLC0415`). Callback parameters typed with the builtin `callable` now use
  `Callable[..., None]`. ([#23])
- The task list re-lays out incrementally: section headers, the separator and the
  "Show N more" link are created once and reused, and only rows that are new or out of
  place are packed again. With 100 tasks a swap while dragging takes about 1 ms instead of
  90 ms, and ticking a task about 30 ms instead of 140 ms. ([#25])
- Rows past `max_visible_tasks` are built only when "Show N more" reveals them. Before,
  every task got a full row at startup even if it was never shown. With 1,000 tasks the
  window opens in about 0.46 s instead of 1.1 s. ([#26])
- Hovering, focusing, dragging or ticking a task recolours its card in place instead of
  deleting and redrawing its 14 canvas items, and the shadow colour is computed once per
  row. A hover now takes about a third of the time. ([#27])

### Fixed

- `config.json` is checked more strictly, and an invalid file falls back to the defaults as
  before. Newly rejected values:
  - `0`, negative numbers, `true`/`false` and `null` where a size, limit or delay is expected;
  - spacing values that are not whole numbers of 0 or more;
  - `min_width` or `min_height` above the default size;
  - an unfocused opacity of 0 or above the focused one;
  - a font size that is not a whole number;
  - a font family that is not text;
  - empty shortcuts and non-text strings. ([#18])
- A shortcut that Tk rejects no longer stops the app from starting: it logs a warning and
  uses the default for that action. ([#18])

### Removed

- `settings.animation_ms`, which nothing used. If it is still in a `config.json`, it is
  ignored with a warning. ([#18])

## [0.2.0] - 2026-11-26

Usability release: undo, editing in place, full keyboard control, a remembered window and an
optional always-on-top. Your `tasks.json` is unchanged and needs no migration; the window's
size, position and always-on-top choice go in a new `state.json` next to it.

### Added

- Undo for deleted tasks: a "Task deleted · Undo" notice appears in the footer for a few
  seconds (`settings.undo_timeout_ms`), and `Ctrl+Z` (`shortcuts.undo`) restores the most
  recent deletions, one at a time, at their original position. "Clear completed" can be
  undone the same way. ([#9])
- Edit a task's text in place: double-click it, or hover it and press `F2`
  (`shortcuts.edit_task`). `Enter` or clicking elsewhere saves, `Esc` cancels, and empty text
  keeps the original. Edits use the same length limit as new tasks. ([#10])
- The window reopens with the size and position it had when it was closed, stored in
  `state.json` next to the tasks file. If that position is no longer on any connected
  monitor, the default position is used. ([#11])
- Keyboard navigation: task rows are focusable (`Tab`, or `↓` from the new-task field) and
  show a focus ring. `↑`/`↓` move between tasks, `Space` toggles, `Delete` deletes (undoable),
  `Alt+↑`/`Alt+↓` reorder within the group, and `F2`/`Enter` edit. ([#13])
- Always on top can be switched off and on with the header pin (`▲`/`△`) or `Ctrl+T`
  (`shortcuts.toggle_always_on_top`). The choice is saved in `state.json`; the starting value
  is `settings.always_on_top`. ([#14])
- Only one copy of Fly Notes runs per tasks file. Launching it again brings the running window
  to the front (restoring it if minimized) and exits, instead of opening a second copy whose
  saves would overwrite the first one's. ([#15])

### Changed

- The "+ N more" hint below a long list is now a "Show N more" link (also usable with
  `Enter`/`Space`) that reveals the hidden tasks, `max_visible_tasks` at a time. The startup
  contrast check now also warns when `link_color` is below 4.5:1 on `content_bg`. ([#12])
- "Clear completed" no longer asks for confirmation, since it can be undone. The
  `confirm_clear_title` and `confirm_clear_msg` strings were removed. ([#9])
- The unfocused window is easier to read: the default `transparency.inactive` rises from 0.45
  to 0.75, and the fade starts only after focus has been away for
  `settings.inactive_fade_delay_ms` (800 ms), so a quick click elsewhere doesn't make it
  flicker. ([#14])
- The README was reorganized for new visitors, with a screenshot, a usage table and diagrams
  of how data is stored and recovered. ([#16])

### Fixed

- Long task text wraps onto several lines and re-wraps when the window is resized, instead of
  being cut off at the window edge. ([#8])
- Hovering a task could be mistaken for hovering another one whose internal widget name
  starts the same way (e.g. the 1st and 10th rows). ([#10])
- Reordering across the hidden boundary between groups no longer leaves the on-screen order
  out of step with the saved order. ([#13])
- Moving focus between the window's own widgets (e.g. from the new-task field to a task) no
  longer fades the window for an instant. ([#14])

## [0.1.1] - 2026-11-26

Data-safety and packaging release. Upgrading from 0.1.0 is strongly recommended if you use
the packaged `FlyNotes.exe`.

### Fixed

- The packaged `.exe` no longer loses your tasks on exit: data is stored in
  `%APPDATA%\FlyNotes\` instead of PyInstaller's temporary extraction folder, and a
  `config.json` next to the executable is now read (portable mode). ([#2])
- An unreadable `tasks.json` is never overwritten: it is moved aside as
  `tasks.corrupt-<timestamp>.json` and the previous version is restored from
  `tasks.json.bak`. ([#3])
- Changes made right before closing from the taskbar are saved. ([#4])
- `Esc` clears the new-task field instead of closing the app. ([#5])
- Saves are `fsync`ed before the file is replaced, so a power loss can't leave a truncated
  tasks file. ([#7])

### Changed

- The default close shortcut is now `Ctrl+W`; the duplicate `Ctrl+L` shortcut was removed. ([#5])
- A relative `settings.tasks_file` is resolved against the data folder instead of the
  current working directory. ([#2])
- Task text is no longer written to the log; errors while saving on close are logged
  instead of being ignored. ([#7])

### Added

- Rolling backup `tasks.json.bak`, refreshed before every save. ([#3])
- `python -m fly_notes` and a `fly-notes` console script; `fly_notes.__version__`. ([#6])
- MIT `LICENSE` file, project metadata, and the PyInstaller build spec in the repository. ([#6])
- Continuous integration: ruff and the test suite run on Windows for every pull request. ([#1])

## [0.1.0]

Initial version: floating, always-on-top task widget with drag-to-reorder, grouping of
completed tasks, configurable theme and taskbar-friendly minimize/restore.

[Unreleased]: https://github.com/dbarretol/fly-notes/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/dbarretol/fly-notes/compare/v0.3.0...v1.0.0
[0.3.0]: https://github.com/dbarretol/fly-notes/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/dbarretol/fly-notes/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/dbarretol/fly-notes/releases/tag/v0.1.1
[#1]: https://github.com/dbarretol/fly-notes/issues/1
[#2]: https://github.com/dbarretol/fly-notes/issues/2
[#3]: https://github.com/dbarretol/fly-notes/issues/3
[#4]: https://github.com/dbarretol/fly-notes/issues/4
[#5]: https://github.com/dbarretol/fly-notes/issues/5
[#6]: https://github.com/dbarretol/fly-notes/issues/6
[#7]: https://github.com/dbarretol/fly-notes/issues/7
[#8]: https://github.com/dbarretol/fly-notes/issues/8
[#9]: https://github.com/dbarretol/fly-notes/issues/9
[#10]: https://github.com/dbarretol/fly-notes/issues/10
[#11]: https://github.com/dbarretol/fly-notes/issues/11
[#12]: https://github.com/dbarretol/fly-notes/issues/12
[#13]: https://github.com/dbarretol/fly-notes/issues/13
[#14]: https://github.com/dbarretol/fly-notes/issues/14
[#15]: https://github.com/dbarretol/fly-notes/issues/15
[#16]: https://github.com/dbarretol/fly-notes/issues/16
[#17]: https://github.com/dbarretol/fly-notes/issues/17
[#18]: https://github.com/dbarretol/fly-notes/issues/18
[#19]: https://github.com/dbarretol/fly-notes/issues/19
[#20]: https://github.com/dbarretol/fly-notes/issues/20
[#21]: https://github.com/dbarretol/fly-notes/issues/21
[#22]: https://github.com/dbarretol/fly-notes/issues/22
[#23]: https://github.com/dbarretol/fly-notes/issues/23
[#25]: https://github.com/dbarretol/fly-notes/issues/25
[#26]: https://github.com/dbarretol/fly-notes/issues/26
[#27]: https://github.com/dbarretol/fly-notes/issues/27
[#29]: https://github.com/dbarretol/fly-notes/issues/29
[#30]: https://github.com/dbarretol/fly-notes/issues/30
[#32]: https://github.com/dbarretol/fly-notes/issues/32
[#65]: https://github.com/dbarretol/fly-notes/issues/65
[#66]: https://github.com/dbarretol/fly-notes/issues/66
