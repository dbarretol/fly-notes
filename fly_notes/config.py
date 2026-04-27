"""
Centralised, validated configuration with deep‑merge support.

* Loads user overrides from ``config.json`` next to the package.
* Exposes a module‑level ``config`` singleton for convenience.
* Every colour, size and font value is type‑checked on load.
"""

from __future__ import annotations

import copy
import json
import logging
import os
from typing import Any, Dict, List, Tuple, Union

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Paths — resolved relative to *this* file,
# not to the caller's working directory.
# ──────────────────────────────────────────────
_PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_PACKAGE_DIR)
CONFIG_FILE = os.path.join(_PROJECT_ROOT, "config.json")
DEFAULT_TASKS_FILE = os.path.join(_PROJECT_ROOT, "tasks.json")

# ──────────────────────────────────────────────
# Default values
# ──────────────────────────────────────────────
DEFAULT_CONFIG: Dict[str, Any] = {
    "colors": {
        "header_bg":      "#FF8C00",
        "content_bg":     "#FFDAB9",
        "item_bg":        "#FFE4B5",
        "text_color":     "#4B2E1E",
        "strike_color":   "#A0522D",
        "border_color":   "#DAA520",
        "drag_highlight": "#E9967A",
    },
    "transparency": {
        "active":   1.0,
        "inactive": 0.3,
    },
    "settings": {
        "tasks_file":     DEFAULT_TASKS_FILE,
        "default_width":  300,
        "default_height": 400,
        "drag_threshold": 20,
        "min_width":      200,
        "min_height":     150,
        "max_task_length": 300,
    },
    "fonts": {
        "header":       ["Segoe UI", 10, "bold"],
        "body":         ["Segoe UI", 11],
        "body_strike":  ["Segoe UI", 11, "overstrike"],
        "footer":       ["Segoe UI", 8, "bold"],
    },
}

# ──────────────────────────────────────────────
# Validation helpers
# ──────────────────────────────────────────────
def _is_color(value: Any) -> bool:
    """Rudimentary hex‑colour check."""
    return isinstance(value, str) and value.startswith("#") and len(value) in (4, 7, 9)


def _validate_colors(colors: Dict[str, str]) -> None:
    for key, val in colors.items():
        if not _is_color(val):
            raise ValueError(f"colors.{key}: '{val}' is not a valid hex colour")


def _validate_transparency(trans: Dict[str, float]) -> None:
    for key in ("active", "inactive"):
        val = trans.get(key)
        if not isinstance(val, (int, float)) or not (0.0 <= val <= 1.0):
            raise ValueError(f"transparency.{key}: must be a float 0.0‑1.0, got {val!r}")


def _validate_settings(settings: Dict[str, Any]) -> None:
    int_keys = ("default_width", "default_height", "drag_threshold",
                "min_width", "min_height", "max_task_length")
    for key in int_keys:
        val = settings.get(key)
        if val is not None and (not isinstance(val, int) or val < 0):
            raise ValueError(f"settings.{key}: must be a positive int, got {val!r}")


def _validate_fonts(fonts: Dict[str, list]) -> None:
    for key, val in fonts.items():
        if not isinstance(val, list) or len(val) < 2:
            raise ValueError(f"fonts.{key}: expected [family, size, ...], got {val!r}")


# ──────────────────────────────────────────────
# Config class
# ──────────────────────────────────────────────
class Config:
    """
    Immutable‑after‑load application configuration.

    Usage::

        from fly_notes.config import config
        bg = config.header_bg
    """

    def __init__(self) -> None:
        self._data: Dict[str, Any] = copy.deepcopy(DEFAULT_CONFIG)
        self._load()

    # -- Loading & merging ---------------------

    def _load(self) -> None:
        if not os.path.exists(CONFIG_FILE):
            logger.info("No user config at %s — using defaults", CONFIG_FILE)
            return
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as fh:
                user_cfg = json.load(fh)
            self._deep_merge(self._data, user_cfg)
            self._validate()
            logger.info("User config loaded from %s", CONFIG_FILE)
        except Exception as exc:
            logger.warning("Bad config — falling back to defaults: %s", exc)
            self._data = copy.deepcopy(DEFAULT_CONFIG)

    @staticmethod
    def _deep_merge(base: dict, override: dict) -> dict:
        """Recursively merge *override* into *base* (mutates *base*)."""
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(base.get(key), dict):
                Config._deep_merge(base[key], value)
            else:
                base[key] = value
        return base

    def _validate(self) -> None:
        _validate_colors(self._data["colors"])
        _validate_transparency(self._data["transparency"])
        _validate_settings(self._data["settings"])
        _validate_fonts(self._data["fonts"])

    # -- Colour properties ---------------------

    @property
    def header_bg(self) -> str:
        return self._data["colors"]["header_bg"]

    @property
    def content_bg(self) -> str:
        return self._data["colors"]["content_bg"]

    @property
    def item_bg(self) -> str:
        return self._data["colors"]["item_bg"]

    @property
    def text_color(self) -> str:
        return self._data["colors"]["text_color"]

    @property
    def strike_color(self) -> str:
        return self._data["colors"]["strike_color"]

    @property
    def border_color(self) -> str:
        return self._data["colors"]["border_color"]

    @property
    def drag_highlight_color(self) -> str:
        return self._data["colors"]["drag_highlight"]

    # -- Transparency --------------------------

    @property
    def active_alpha(self) -> float:
        return float(self._data["transparency"]["active"])

    @property
    def inactive_alpha(self) -> float:
        return float(self._data["transparency"]["inactive"])

    # -- Settings ------------------------------

    @property
    def tasks_file(self) -> str:
        return self._data["settings"]["tasks_file"]

    @property
    def default_width(self) -> int:
        return int(self._data["settings"]["default_width"])

    @property
    def default_height(self) -> int:
        return int(self._data["settings"]["default_height"])

    @property
    def drag_threshold(self) -> int:
        return int(self._data["settings"].get("drag_threshold", 20))

    @property
    def min_width(self) -> int:
        return int(self._data["settings"].get("min_width", 200))

    @property
    def min_height(self) -> int:
        return int(self._data["settings"].get("min_height", 150))

    @property
    def max_task_length(self) -> int:
        return int(self._data["settings"].get("max_task_length", 300))

    # -- Fonts ---------------------------------

    @property
    def font_header(self) -> Tuple[str, ...]:
        return tuple(self._data["fonts"]["header"])

    @property
    def font_body(self) -> Tuple[str, ...]:
        return tuple(self._data["fonts"]["body"])

    @property
    def font_body_strike(self) -> Tuple[str, ...]:
        return tuple(self._data["fonts"]["body_strike"])

    @property
    def font_footer(self) -> Tuple[str, ...]:
        return tuple(self._data["fonts"]["footer"])


# Module‑level singleton
config = Config()