# Changelog

All notable changes to Fly Notes are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- The code is organized in three layers: `fly_notes/model/` (tasks and saving),
  `fly_notes/ui/` (one module per widget) and `fly_notes/platform/` (Windows window
  management, window state, single instance). Nothing changes for users. ([#21])

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

[Unreleased]: https://github.com/dbarretol/fly-notes/compare/v0.2.0...HEAD
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
[#21]: https://github.com/dbarretol/fly-notes/issues/21
