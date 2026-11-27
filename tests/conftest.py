import pytest

from fly_notes.config import default_config


@pytest.fixture
def cfg(tmp_path):
    """The built-in defaults, never a local ``config.json``, with the tasks
    file in the test's temporary folder.

    Derive a variant with ``cfg.with_settings(...)`` or ``dataclasses.replace``.
    """
    return default_config(tasks_file=tmp_path / "tasks.json")
