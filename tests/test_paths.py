from pathlib import Path

import pytest

from fly_notes.config import _validate_settings
from fly_notes.paths import APP_DIR_NAME, resolve_paths


@pytest.fixture
def env(tmp_path):
    """A fake install layout: exe dir, PyInstaller temp dir, %APPDATA% and home."""
    exe_dir = tmp_path / "Programs" / "FlyNotes"
    exe_dir.mkdir(parents=True)
    meipass = tmp_path / "Temp" / "_MEI12345"
    meipass.mkdir(parents=True)
    return {
        "executable": exe_dir / "FlyNotes.exe",
        "exe_dir": exe_dir,
        "meipass": meipass,
        "appdata": str(tmp_path / "Roaming"),
        "home": tmp_path / "home",
        "source_root": tmp_path / "src",
    }


def _resolve(env, frozen=True, **overrides):
    kwargs = {k: env[k] for k in ("executable", "meipass", "appdata", "home", "source_root")}
    kwargs.update(overrides)
    return resolve_paths(frozen=frozen, **kwargs)


def test_source_mode_keeps_everything_in_project_root(env):
    paths = _resolve(env, frozen=False)
    assert paths.mode == "source"
    assert paths.tasks_file == env["source_root"] / "tasks.json"
    assert paths.config_file == env["source_root"] / "config.json"
    assert paths.icon_file == env["source_root"] / "assets" / "fly_notes.ico"


def test_frozen_exe_stores_data_in_appdata_not_in_temp_extraction_dir(env):
    paths = _resolve(env)
    assert paths.mode == "installed"
    assert paths.data_dir == Path(env["appdata"]) / APP_DIR_NAME
    assert paths.tasks_file == Path(env["appdata"]) / APP_DIR_NAME / "tasks.json"
    # Data must never live under the onefile extraction dir, which is deleted on exit.
    assert env["meipass"] not in paths.tasks_file.parents
    assert env["meipass"] not in paths.config_file.parents


def test_frozen_exe_reads_bundled_assets_from_meipass(env):
    paths = _resolve(env)
    assert paths.icon_file == env["meipass"] / "assets" / "fly_notes.ico"


@pytest.mark.parametrize("marker", ["config.json", "tasks.json"])
def test_portable_mode_when_data_file_sits_next_to_exe(env, marker):
    (env["exe_dir"] / marker).write_text("{}", encoding="utf-8")
    paths = _resolve(env)
    assert paths.mode == "portable"
    assert paths.data_dir == env["exe_dir"].resolve()
    assert paths.config_file == env["exe_dir"].resolve() / "config.json"


def test_missing_appdata_falls_back_to_home_roaming(env):
    paths = _resolve(env, appdata=None)
    assert paths.data_dir == env["home"] / "AppData" / "Roaming" / APP_DIR_NAME


def test_frozen_without_meipass_uses_exe_dir_for_assets(env):
    paths = _resolve(env, meipass=None)
    assert paths.icon_file == env["exe_dir"].resolve() / "assets" / "fly_notes.ico"


def test_relative_tasks_file_is_resolved_against_data_dir(env):
    paths = _resolve(env)
    assert paths.resolve_data_path("lists/work.json") == paths.data_dir / "lists" / "work.json"


def test_absolute_tasks_file_is_kept(env, tmp_path):
    target = tmp_path / "elsewhere" / "tasks.json"
    assert _resolve(env).resolve_data_path(str(target)) == target


def test_empty_tasks_file_is_rejected():
    with pytest.raises(ValueError):
        _validate_settings({"tasks_file": "  "})
