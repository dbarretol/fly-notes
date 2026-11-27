# Changelog

All notable changes to Fly Notes are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/dbarretol/fly-notes/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/dbarretol/fly-notes/releases/tag/v0.1.1
[#1]: https://github.com/dbarretol/fly-notes/issues/1
[#2]: https://github.com/dbarretol/fly-notes/issues/2
[#3]: https://github.com/dbarretol/fly-notes/issues/3
[#4]: https://github.com/dbarretol/fly-notes/issues/4
[#5]: https://github.com/dbarretol/fly-notes/issues/5
[#6]: https://github.com/dbarretol/fly-notes/issues/6
[#7]: https://github.com/dbarretol/fly-notes/issues/7
