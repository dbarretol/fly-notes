"""TaskEntryBar: the new-task input."""

from fly_notes.config import default_config
from fly_notes.ui.entry import TaskEntryBar

# ── Escape / shortcuts ────────────────────────


def test_escape_in_entry_clears_text_and_restores_placeholder(root, cfg):
    submitted = []
    bar = TaskEntryBar(root, cfg, on_submit=submitted.append)
    bar.pack()
    bar.focus_entry()
    bar.entry_widget.insert(0, "half-typed task")

    result = bar._cancel()

    assert result == "break"
    assert bar.get_text() == ""
    assert bar.entry_widget.get() == cfg.string("entry_placeholder")
    assert submitted == []
    bar.destroy()


def test_entry_background_follows_the_theme(root, tmp_path):
    dark = default_config(tasks_file=tmp_path / "tasks.json", theme="dark")
    bar = TaskEntryBar(root, dark, on_submit=lambda _text: None)

    assert bar.entry_widget.cget("bg") == dark.colors.entry_bg
    bar.destroy()
