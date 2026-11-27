# Notes for coding agents

Fly Notes is a small Python + Tkinter task widget for Windows. It has no third-party
runtime dependencies.

## Tooling

- Use [uv](https://docs.astral.sh/uv/) as the package and virtual environment manager.
- Run the app: `uv run fly-notes`
- Lint and format: `uv run ruff check .` and `uv run ruff format .` (line length 100)
- Tests: `uv run pytest`
- Build the executable: `uv run pyinstaller FlyNotes.spec --clean`

## Conventions

- Code, comments, commits, issues and pull requests are in English.
- Branches: `feat/*`, `fix/*`, `docs/*` and `chore/*` branch off `dev` and go back to it through
  a pull request. `main` only receives release pull requests from `dev`.
- Record user-visible changes under `[Unreleased]` in `CHANGELOG.md`.
- `tasks.json`, `config.json` and `state.json` hold personal data. Never commit them, and use a
  temporary or portable data folder when running the app for tests.
