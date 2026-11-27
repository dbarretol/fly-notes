import dataclasses
import json
import logging

import pytest

from fly_notes import config as config_module
from fly_notes.config import (
    DEFAULT_CONFIG,
    _contrast_ratio,
    _deep_merge,
    _hex_to_rgb,
    _is_color,
    _validate_colors,
    _validate_settings,
    _validate_transparency,
    default_config,
    load_config,
)
from fly_notes.paths import AppPaths


def test_hex_to_rgb():
    assert _hex_to_rgb("#FFFFFF") == (255, 255, 255)
    assert _hex_to_rgb("#000000") == (0, 0, 0)
    assert _hex_to_rgb("#FFF") == (255, 255, 255)
    assert _hex_to_rgb("#FF0000AA") == (255, 0, 0)  # Alpha stripped
    with pytest.raises(ValueError):
        _hex_to_rgb("invalid")
    with pytest.raises(ValueError):
        _hex_to_rgb("#FFFF")


def test_contrast_ratio():
    # White on black should be 21:1
    assert _contrast_ratio("#FFFFFF", "#000000") == pytest.approx(21.0)
    # White on white should be 1:1
    assert _contrast_ratio("#FFFFFF", "#FFFFFF") == pytest.approx(1.0)


def test_is_color():
    assert _is_color("#FFF") is True
    assert _is_color("#FFFFFF") is True
    assert _is_color("#RRGGBBAA") is False
    assert _is_color("FFF") is False
    assert _is_color("#FG0000") is False


def test_validate_colors():
    _validate_colors({"bg": "#FFFFFF"})
    with pytest.raises(ValueError):
        _validate_colors({"bg": "red"})


def test_validate_transparency():
    _validate_transparency({"active": 1.0, "inactive": 0.5})
    with pytest.raises(ValueError):
        _validate_transparency({"active": 1.1})
    with pytest.raises(ValueError):
        _validate_transparency({"active": -0.1})


def test_validate_settings():
    _validate_settings({"default_width": 100, "confirm_delete": True})
    with pytest.raises(ValueError):
        _validate_settings({"default_width": -1})
    with pytest.raises(ValueError):
        _validate_settings({"confirm_delete": "yes"})
    with pytest.raises(ValueError):
        _validate_settings({"always_on_top": 1})
    with pytest.raises(ValueError):
        _validate_settings({"inactive_fade_delay_ms": -5})


def test_every_config_section_is_a_typed_dataclass_with_the_default_keys(cfg):
    for section, defaults in DEFAULT_CONFIG.items():
        typed = getattr(cfg, section)
        assert dataclasses.is_dataclass(typed)
        assert {f.name for f in dataclasses.fields(typed)} == set(defaults), section


def test_default_config_values_and_types(cfg):
    assert cfg.colors.header_bg == DEFAULT_CONFIG["colors"]["header_bg"]
    assert cfg.spacing.md == DEFAULT_CONFIG["spacing"]["md"]
    assert cfg.fonts.header == tuple(DEFAULT_CONFIG["fonts"]["header"])
    assert cfg.settings.default_width == DEFAULT_CONFIG["settings"]["default_width"]
    assert cfg.transparency.active == DEFAULT_CONFIG["transparency"]["active"]
    assert isinstance(cfg.transparency.active, float)
    assert cfg.shortcuts.close == DEFAULT_CONFIG["shortcuts"]["close"]

    with pytest.raises(AttributeError):
        _ = cfg.colors.non_existent_colour


def test_config_is_immutable(cfg):
    with pytest.raises(dataclasses.FrozenInstanceError):
        cfg.settings.default_width = 1  # type: ignore[misc]
    changed = cfg.with_settings(max_visible_tasks=3)
    assert changed.settings.max_visible_tasks == 3
    assert cfg.settings.max_visible_tasks == DEFAULT_CONFIG["settings"]["max_visible_tasks"]
    assert changed.colors is cfg.colors


def test_default_config_uses_the_given_tasks_file(cfg, tmp_path):
    assert cfg.settings.tasks_file == str(tmp_path / "tasks.json")


def test_config_string(cfg):
    assert cfg.string("app_title") == DEFAULT_CONFIG["strings"]["app_title"]
    assert cfg.string("badge_format", done=2, total=5) == "2 of 5 done"
    # A missing key comes back as the key itself
    assert cfg.string("missing_key") == "missing_key"


def test_config_string_survives_a_broken_user_template(cfg):
    broken = dataclasses.replace(
        cfg, strings=dataclasses.replace(cfg.strings, badge_format="{oops} done")
    )
    assert broken.string("badge_format", done=1, total=2) == "{oops} done"


def test_importing_the_module_reads_no_config_file():
    # The old module-level ``config = Config()`` read config.json at import time.
    assert not hasattr(config_module, "config")
    assert not hasattr(config_module, "Config")


# ── load_config ──────────────────────────────


def _paths(tmp_path):
    return AppPaths(mode="source", data_dir=tmp_path, assets_dir=tmp_path)


def _write(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_load_config_without_a_file_uses_the_defaults(tmp_path):
    cfg = load_config(tmp_path / "config.json", _paths(tmp_path))
    assert cfg.colors == default_config().colors
    assert cfg.settings.tasks_file == DEFAULT_CONFIG["settings"]["tasks_file"]


def test_load_config_merges_user_values_over_the_defaults(tmp_path):
    config_file = _write(
        tmp_path / "config.json",
        {"settings": {"default_width": 400}, "colors": {"header_bg": "#123456"}},
    )
    cfg = load_config(config_file, _paths(tmp_path))
    assert cfg.settings.default_width == 400
    assert cfg.colors.header_bg == "#123456"
    assert cfg.settings.default_height == DEFAULT_CONFIG["settings"]["default_height"]


def test_load_config_ignores_unknown_keys(tmp_path, caplog):
    config_file = _write(
        tmp_path / "config.json", {"nope": 1, "settings": {"typo_width": 5, "min_width": 250}}
    )
    with caplog.at_level(logging.WARNING, logger="fly_notes.config"):
        cfg = load_config(config_file, _paths(tmp_path))
    assert cfg.settings.min_width == 250
    assert not hasattr(cfg.settings, "typo_width")
    assert "nope" in caplog.text and "settings.typo_width" in caplog.text


@pytest.mark.parametrize(
    "content",
    ["not json", "[1, 2]", json.dumps({"settings": {"default_width": "wide"}})],
)
def test_load_config_falls_back_to_the_defaults_on_a_bad_file(tmp_path, content):
    config_file = tmp_path / "config.json"
    config_file.write_text(content, encoding="utf-8")
    cfg = load_config(config_file, _paths(tmp_path))
    assert cfg.settings.default_width == DEFAULT_CONFIG["settings"]["default_width"]


def test_load_config_resolves_a_relative_tasks_file_in_the_data_folder(tmp_path):
    config_file = _write(tmp_path / "config.json", {"settings": {"tasks_file": "my.json"}})
    cfg = load_config(config_file, _paths(tmp_path))
    assert cfg.settings.tasks_file == str(tmp_path / "my.json")


def test_deep_merge():
    base = {"a": {"b": 1, "c": 2}}
    override = {"a": {"b": 10}}
    _deep_merge(base, override)
    assert base["a"]["b"] == 10
    assert base["a"]["c"] == 2

    # Test ignore unknown
    base = {"a": 1}
    override = {"b": 2}
    _deep_merge(base, override)
    assert "b" not in base
