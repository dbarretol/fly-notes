import copy
import dataclasses
import json
import logging

import pytest

from fly_notes import config as config_module
from fly_notes.config import (
    _CONTRAST_PAIRS,
    DARK_COLORS,
    DEFAULT_CONFIG,
    THEMES,
    _contrast_ratio,
    _deep_merge,
    _hex_to_rgb,
    _is_color,
    _validate_colors,
    _validate_fonts,
    _validate_settings,
    _validate_shortcuts,
    _validate_spacing,
    _validate_strings,
    _validate_structure,
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


# ── Validation gaps (#18) ─────────────────────


def test_the_defaults_pass_every_check():
    _validate_structure(copy.deepcopy(DEFAULT_CONFIG))


@pytest.mark.parametrize("key", ["default_width", "max_visible_tasks", "drag_threshold"])
@pytest.mark.parametrize("value", [0, -1, True, False, None, 1.5, "10"])
def test_positive_int_settings_reject_zero_bools_and_non_ints(key, value):
    with pytest.raises(ValueError):
        _validate_settings({key: value})


@pytest.mark.parametrize("key", ["item_padding_x", "border_radius", "inactive_fade_delay_ms"])
def test_zero_is_allowed_where_it_means_none(key):
    _validate_settings({key: 0})
    with pytest.raises(ValueError):
        _validate_settings({key: True})
    with pytest.raises(ValueError):
        _validate_settings({key: -1})


def test_bool_and_path_settings_reject_null():
    with pytest.raises(ValueError):
        _validate_settings({"group_completed": None})
    with pytest.raises(ValueError):
        _validate_settings({"checkbox_round": None})
    with pytest.raises(ValueError):
        _validate_settings({"tasks_file": None})


@pytest.mark.parametrize("axis", ["width", "height"])
def test_min_size_must_not_exceed_default_size(axis):
    _validate_settings({f"min_{axis}": 200, f"default_{axis}": 200})
    with pytest.raises(ValueError, match=f"min_{axis}"):
        _validate_settings({f"min_{axis}": 201, f"default_{axis}": 200})


@pytest.mark.parametrize(
    "trans",
    [
        {"active": 0.8, "inactive": 0.9},  # inactive above active
        {"active": 1.0, "inactive": 0.0},  # an invisible window
        {"active": True, "inactive": 0.5},
    ],
)
def test_transparency_rejects_inverted_zero_and_bool_values(trans):
    with pytest.raises(ValueError):
        _validate_transparency(trans)


def test_inactive_may_equal_active():
    _validate_transparency({"active": 0.9, "inactive": 0.9})


@pytest.mark.parametrize("value", [-1, True, 2.5, None])
def test_spacing_must_be_non_negative_ints(value):
    _validate_spacing({"md": 0})
    with pytest.raises(ValueError):
        _validate_spacing({"md": value})


@pytest.mark.parametrize(
    "font",
    [
        ["Segoe UI", 10.5],
        ["Segoe UI", "10"],
        ["Segoe UI", True],
        ["Segoe UI", 0],
        ["", 10],
        [10, 10],
        ["Segoe UI", 10, 1],
    ],
)
def test_fonts_need_a_family_a_whole_size_and_string_styles(font):
    with pytest.raises(ValueError):
        _validate_fonts({"body": font})


def test_valid_fonts_include_pixel_sizes_and_styles():
    _validate_fonts({"body": ["Segoe UI", 11], "px": ["Segoe UI", -14, "bold", "italic"]})


@pytest.mark.parametrize("value", ["", "   ", None, 5])
def test_shortcuts_must_be_non_empty_strings(value):
    with pytest.raises(ValueError):
        _validate_shortcuts({"undo": value})


def test_strings_must_be_text():
    with pytest.raises(ValueError):
        _validate_strings({"app_title": 5})


@pytest.mark.parametrize(
    "user_cfg",
    [
        {"settings": {"min_width": 500}},  # above default_width
        {"settings": {"max_visible_tasks": 0}},
        {"transparency": {"inactive": 1.0, "active": 0.5}},
        {"fonts": {"body": ["Segoe UI", "big"]}},
        {"shortcuts": {"undo": ""}},
    ],
)
def test_load_config_falls_back_to_the_defaults_on_a_new_check(tmp_path, user_cfg):
    config_file = _write(tmp_path / "config.json", user_cfg)
    cfg = load_config(config_file, _paths(tmp_path))
    assert cfg.settings == default_config(cfg.settings.tasks_file).settings
    assert cfg.transparency == default_config().transparency
    assert cfg.fonts == default_config().fonts


def test_removed_animation_ms_is_ignored_not_an_error(tmp_path, caplog):
    config_file = _write(
        tmp_path / "config.json", {"settings": {"animation_ms": 150, "min_width": 250}}
    )
    with caplog.at_level(logging.WARNING, logger="fly_notes.config"):
        cfg = load_config(config_file, _paths(tmp_path))
    assert cfg.settings.min_width == 250
    assert "settings.animation_ms" in caplog.text


# ── Themes (#65) ──────────────────────────────


def test_every_theme_sets_every_colour_and_passes_the_contrast_checks():
    for name, colors in THEMES.items():
        assert set(colors) == set(DEFAULT_CONFIG["colors"]), name
        _validate_colors(colors)
        for fg, bg, minimum in _CONTRAST_PAIRS:
            assert _contrast_ratio(colors[fg], colors[bg]) >= minimum, (name, fg, bg)


def test_light_is_the_default_theme(cfg):
    assert cfg.settings.theme == "light"
    assert dataclasses.asdict(cfg.colors) == DEFAULT_CONFIG["colors"]


def test_default_config_can_use_the_dark_theme():
    cfg = default_config(theme="dark")
    assert cfg.settings.theme == "dark"
    assert dataclasses.asdict(cfg.colors) == DARK_COLORS


def test_load_config_applies_the_dark_preset(tmp_path):
    config_file = _write(tmp_path / "config.json", {"settings": {"theme": "dark"}})
    cfg = load_config(config_file, _paths(tmp_path))
    assert cfg.settings.theme == "dark"
    assert dataclasses.asdict(cfg.colors) == DARK_COLORS


def test_colours_in_the_file_override_the_preset(tmp_path):
    config_file = _write(
        tmp_path / "config.json",
        {"settings": {"theme": "dark"}, "colors": {"header_bg": "#123456"}},
    )
    cfg = load_config(config_file, _paths(tmp_path))
    assert cfg.colors.header_bg == "#123456"
    assert cfg.colors.content_bg == DARK_COLORS["content_bg"]


@pytest.mark.parametrize("theme", ["Dark", "blue", "", None, 1])
def test_an_unknown_theme_falls_back_to_the_defaults(tmp_path, caplog, theme):
    config_file = _write(tmp_path / "config.json", {"settings": {"theme": theme, "min_width": 250}})
    with caplog.at_level(logging.WARNING, logger="fly_notes.config"):
        cfg = load_config(config_file, _paths(tmp_path))
    assert cfg.settings.theme == "light"
    assert cfg.settings.min_width == DEFAULT_CONFIG["settings"]["min_width"]
    assert "settings.theme" in caplog.text


# ── Font fallback (#77) ──────────────────────


def test_missing_variable_fonts_fall_back_to_segoe_ui(cfg):
    fonts = cfg.with_available_fonts({"Segoe UI"}).fonts
    assert fonts.body == ("Segoe UI", 11)
    assert fonts.body_strike == ("Segoe UI", 11, "overstrike")
    # The semibold family becomes Segoe UI bold.
    assert fonts.header == ("Segoe UI", 10, "bold")
    assert fonts.section == ("Segoe UI", 9, "bold")


def test_installed_fonts_are_kept(cfg):
    installed = {"Segoe UI Variable Text", "Segoe UI Variable Text Semibold"}
    assert cfg.with_available_fonts(installed) is cfg


def test_fonts_without_a_fallback_are_kept(cfg):
    custom = dataclasses.replace(
        cfg, fonts=dataclasses.replace(cfg.fonts, body=("Comic Sans MS", 12))
    )
    assert custom.with_available_fonts(set()).fonts.body == ("Comic Sans MS", 12)
