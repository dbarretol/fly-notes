import pytest

from fly_notes.config import (
    DEFAULT_CONFIG,
    Config,
    _contrast_ratio,
    _hex_to_rgb,
    _is_color,
    _validate_colors,
    _validate_settings,
    _validate_transparency,
)


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


def test_config_dynamic_attributes():
    cfg = Config()
    # Test colors
    assert cfg.header_bg == DEFAULT_CONFIG["colors"]["header_bg"]
    # Test spacing
    assert cfg.spacing_md == DEFAULT_CONFIG["spacing"]["md"]
    # Test fonts
    assert cfg.font_header == tuple(DEFAULT_CONFIG["fonts"]["header"])
    # Test settings
    assert cfg.default_width == DEFAULT_CONFIG["settings"]["default_width"]
    # Test aliases
    assert cfg.active_alpha == DEFAULT_CONFIG["transparency"]["active"]

    with pytest.raises(AttributeError):
        _ = cfg.non_existent_attribute


def test_config_string():
    cfg = Config()
    assert cfg.string("app_title") == DEFAULT_CONFIG["strings"]["app_title"]
    # Test formatting
    assert cfg.string("badge_format", done=2, total=5) == "2 of 5 done"
    # Test missing key returns key
    assert cfg.string("missing_key") == "missing_key"


def test_deep_merge():
    base = {"a": {"b": 1, "c": 2}}
    override = {"a": {"b": 10}}
    Config._deep_merge(base, override)
    assert base["a"]["b"] == 10
    assert base["a"]["c"] == 2

    # Test ignore unknown
    base = {"a": 1}
    override = {"b": 2}
    Config._deep_merge(base, override)
    assert "b" not in base
