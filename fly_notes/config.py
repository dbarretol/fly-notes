"""
Centralised, validated configuration with deep-merge support and
WCAG-compliant colour tokens organised in a semantic design system.
"""

from __future__ import annotations

import copy
import json
import logging
from typing import Any

from .paths import APP_PATHS

logger = logging.getLogger(__name__)

# Where config/data/assets live depends on how the app runs (source,
# installed .exe, portable .exe) — see fly_notes/paths.py.
CONFIG_FILE = APP_PATHS.config_file
DEFAULT_TASKS_FILE = APP_PATHS.tasks_file
ICON_PATH = APP_PATHS.icon_file

DEFAULT_CONFIG: dict[str, Any] = {
    "colors": {
        # Surfaces
        "header_bg": "#B35C00",
        "content_bg": "#FFF4E6",
        "item_bg": "#FFFFFF",
        "item_bg_completed": "#E8E0D8",
        "footer_bg": "#F0E6D8",
        "separator_color": "#E0D0C0",
        # Text
        "text_primary": "#2D1810",
        "text_secondary": "#5C4033",
        "text_completed": "#6B5B4E",
        "text_on_header": "#FFFFFF",
        "text_placeholder": "#8C7E72",
        "section_header": "#8B4500",
        # Interactive
        "border_color": "#D4B896",
        "border_focus": "#B35C00",
        "btn_danger_bg": "#DC3545",
        "btn_danger_hover": "#C82333",
        "btn_close_hover_bg": "#FF4500",
        "btn_header_hover_bg": "#8B4500",
        "link_color": "#8B4D00",
        "link_hover": "#B35C00",
        # Feedback
        "drag_highlight": "#FFE0B2",
        "drag_border": "#B35C00",
        "checkbox_check": "#B35C00",
        "checkbox_bg": "#FFFFFF",
        "checkbox_border": "#B0977A",
        "checkbox_hover_bg": "#FFF0E0",
        "scrollbar_thumb": "#A8763F",
        "scrollbar_track": "#FFF4E6",
        # State
        "shadow_color": "#00000015",
        "empty_state_fg": "#887868",
    },
    "transparency": {
        "active": 1.0,
        "inactive": 0.45,
    },
    "spacing": {
        "xs": 2,
        "sm": 4,
        "md": 8,
        "lg": 12,
        "xl": 16,
        "xxl": 24,
    },
    "settings": {
        "tasks_file": str(DEFAULT_TASKS_FILE),
        "default_width": 320,
        "default_height": 440,
        "drag_threshold": 18,
        "min_width": 240,
        "min_height": 180,
        "max_task_length": 300,
        "item_padding_y": 7,
        "item_padding_x": 10,
        "header_height": 38,
        "footer_height": 32,
        "border_radius": 6,
        "animation_ms": 150,
        "confirm_delete": False,
        "undo_timeout_ms": 5000,
        "max_visible_tasks": 100,
        "checkbox_size": 18,
        "group_completed": True,
        "separator_height": 1,
        "scrollbar_width": 8,
    },
    "fonts": {
        "header": ["Segoe UI", 10, "bold"],
        "body": ["Segoe UI", 11],
        "body_strike": ["Segoe UI", 11, "overstrike"],
        "footer": ["Segoe UI", 9],
        "empty_hint": ["Segoe UI", 10, "italic"],
        "badge": ["Segoe UI", 8, "bold"],
        "section": ["Segoe UI", 9, "bold"],
    },
    "shortcuts": {
        "new_task": "<Control-n>",
        "delete_completed": "<Control-d>",
        # Not <Escape>: Escape means "cancel" (it clears the entry), never "quit".
        "close": "<Control-w>",
        "undo": "<Control-z>",
    },
    "strings": {
        "app_title": "Fly Notes",
        "entry_placeholder": "Add a new task…",
        "clear_completed": "Clear completed ({count})",
        "clear_completed_zero": "Clear completed",
        "empty_state": "No tasks yet — type above to start!",
        "confirm_delete_title": "Delete Task",
        "confirm_delete_msg": "Remove this task permanently?",
        "undo_deleted": "Task deleted",
        "undo_cleared": "{count} completed task(s) cleared",
        "undo_action": "Undo",
        "section_pending": "To Do ({count})",
        "section_completed": "Completed ({count})",
        "more_hidden": "+ {count} more",
        "badge_format": "{done} of {total} done",
        "btn_close": "✕",
        "btn_minimize": "—",
    },
}


# ──────────────────────────────────────────────
# Known keys per section (for deep-merge filtering)
# ──────────────────────────────────────────────


def _known_keys() -> dict[str, set[str]]:
    """Return the set of valid keys for each top-level section."""
    return {section: set(values.keys()) for section, values in DEFAULT_CONFIG.items()}


_KNOWN_KEYS = _known_keys()


# ──────────────────────────────────────────────
# Contrast validation (WCAG AA)
# ──────────────────────────────────────────────


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert a hex colour (#RGB, #RRGGBB, #RRGGBBAA) to (r, g, b).
    Alpha channel is stripped if present."""
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    elif len(h) == 8:
        h = h[:6]  # Strip alpha channel explicitly
    if len(h) != 6:
        raise ValueError(f"Cannot parse colour: {hex_color!r}")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _relative_luminance(r: int, g: int, b: int) -> float:
    def _ch(c: int) -> float:
        s = c / 255.0
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4

    return 0.2126 * _ch(r) + 0.7152 * _ch(g) + 0.0722 * _ch(b)


def blend_alpha_hex(rgba_hex: str, background_hex: str) -> str:
    """Flatten an ``#RRGGBBAA`` colour onto an opaque background.

    Tk widget colour options don't accept an alpha channel, so colours like
    ``shadow_color`` (``#00000015``) can't be used directly as a ``bg``. This
    alpha-composites *rgba_hex* over *background_hex* and returns a plain
    ``#RRGGBB`` string Tk can use.
    """
    rgba = rgba_hex.lstrip("#")
    if len(rgba) != 8:
        return f"#{rgba[:6]}" if len(rgba) >= 6 else background_hex
    r, g, b, a = (int(rgba[i : i + 2], 16) for i in (0, 2, 4, 6))
    bg = background_hex.lstrip("#")
    br, bgc, bb = (int(bg[i : i + 2], 16) for i in (0, 2, 4))
    alpha = a / 255.0
    out_r = round(r * alpha + br * (1 - alpha))
    out_g = round(g * alpha + bgc * (1 - alpha))
    out_b = round(b * alpha + bb * (1 - alpha))
    return f"#{out_r:02x}{out_g:02x}{out_b:02x}"


def _contrast_ratio(fg: str, bg: str) -> float:
    l1 = _relative_luminance(*_hex_to_rgb(fg))
    l2 = _relative_luminance(*_hex_to_rgb(bg))
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


_CONTRAST_PAIRS: list[tuple[str, str, float]] = [
    ("text_primary", "item_bg", 4.5),
    ("text_completed", "item_bg_completed", 4.5),
    ("text_on_header", "header_bg", 4.5),
    ("text_secondary", "content_bg", 4.5),
    ("section_header", "content_bg", 4.5),
    ("text_placeholder", "item_bg", 3.0),
    ("link_color", "footer_bg", 4.5),
    ("empty_state_fg", "content_bg", 3.0),
]


def _is_color(value: Any) -> bool:
    if not isinstance(value, str) or not value.startswith("#"):
        return False
    h = value.lstrip("#")
    if len(h) not in (3, 6, 8):
        return False
    try:
        int(h, 16)
        return True
    except ValueError:
        return False


def _validate_colors(colors: dict[str, str]) -> None:
    for key, val in colors.items():
        if not _is_color(val):
            raise ValueError(f"colors.{key}: '{val}' is not a valid hex colour")


def _validate_contrast(colors: dict[str, str]) -> None:
    for fg_key, bg_key, min_ratio in _CONTRAST_PAIRS:
        fg, bg = colors.get(fg_key), colors.get(bg_key)
        if not fg or not bg:
            continue
        # Skip colours with alpha — luminance calc is unreliable
        if len(fg.lstrip("#")) == 8 or len(bg.lstrip("#")) == 8:
            continue
        try:
            ratio = _contrast_ratio(fg, bg)
            if ratio < min_ratio:
                logger.warning(
                    "WCAG contrast fail: %s (%s) on %s (%s) = %.2f:1 (need %.1f:1)",
                    fg_key,
                    fg,
                    bg_key,
                    bg,
                    ratio,
                    min_ratio,
                )
        except Exception:
            pass


def _validate_transparency(trans: dict[str, float]) -> None:
    for key in ("active", "inactive"):
        val = trans.get(key)
        if not isinstance(val, (int, float)) or not (0.0 <= val <= 1.0):
            raise ValueError(f"transparency.{key}: must be float 0.0-1.0, got {val!r}")


def _validate_settings(settings: dict[str, Any]) -> None:
    int_keys = (
        "default_width",
        "default_height",
        "drag_threshold",
        "min_width",
        "min_height",
        "max_task_length",
        "item_padding_y",
        "item_padding_x",
        "header_height",
        "footer_height",
        "border_radius",
        "animation_ms",
        "max_visible_tasks",
        "checkbox_size",
        "separator_height",
        "scrollbar_width",
        "undo_timeout_ms",
    )
    for key in int_keys:
        val = settings.get(key)
        if val is not None and (not isinstance(val, int) or val < 0):
            raise ValueError(f"settings.{key}: must be a positive int, got {val!r}")

    bool_keys = ("confirm_delete", "group_completed")
    for key in bool_keys:
        val = settings.get(key)
        if val is not None and not isinstance(val, bool):
            raise ValueError(f"settings.{key}: must be a bool, got {val!r}")

    tf = settings.get("tasks_file")
    if tf is not None and (not isinstance(tf, str) or not tf.strip()):
        raise ValueError(f"settings.tasks_file: must be a non-empty string path, got {tf!r}")


def _validate_fonts(fonts: dict[str, list]) -> None:
    for key, val in fonts.items():
        if not isinstance(val, list) or len(val) < 2:
            raise ValueError(f"fonts.{key}: expected [family, size, ...], got {val!r}")


# ──────────────────────────────────────────────
# Config class — uses __getattr__ to eliminate DRY violation
# ──────────────────────────────────────────────

# Map from property name → (section, key, cast)
# This is built automatically; only special-name mappings are listed here.
_PROPERTY_ALIASES: dict[str, tuple[str, str]] = {
    # Aliases where property name ≠ key name
    "drag_highlight_color": ("colors", "drag_highlight"),
    "active_alpha": ("transparency", "active"),
    "inactive_alpha": ("transparency", "inactive"),
}

# Section-level prefixes for auto-resolution
_SECTION_PREFIXES: dict[str, tuple[str, ...]] = {
    "colors": (),
    "transparency": (),
    "settings": (),
    "shortcuts": (),
}

_SPACING_PREFIX = "spacing_"
_FONT_PREFIX = "font_"
_SHORTCUT_PREFIX = "shortcut_"


class Config:
    """Immutable-after-load application configuration.

    Properties are resolved dynamically via ``__getattr__`` to eliminate
    the ~80-property boilerplate.  Attribute names follow these conventions:

    - ``config.<color_key>``        → ``_data["colors"][key]`` (str)
    - ``config.spacing_<key>``      → ``_data["spacing"][key]`` (int)
    - ``config.font_<key>``         → ``_data["fonts"][key]``   (tuple)
    - ``config.shortcut_<key>``     → ``_data["shortcuts"][key]``(str)
    - ``config.<settings_key>``     → ``_data["settings"][key]``
    - ``config.active_alpha``       → ``_data["transparency"]["active"]``
    - ``config.inactive_alpha``     → ``_data["transparency"]["inactive"]``
    - ``config.drag_highlight_color`` → alias for ``drag_highlight``
    """

    def __init__(self) -> None:
        self._data: dict[str, Any] = copy.deepcopy(DEFAULT_CONFIG)
        self._load()
        self._resolve_tasks_file()
        # Pre-build a lookup cache for __getattr__
        self._attr_cache: dict[str, Any] = {}

    # ── Loading ──────────────────────────────

    def _load(self) -> None:
        if not CONFIG_FILE.exists():
            logger.info("No user config at %s — using defaults", CONFIG_FILE)
            self._post_validate()
            return
        try:
            with open(CONFIG_FILE, encoding="utf-8") as fh:
                user_cfg = json.load(fh)
            if not isinstance(user_cfg, dict):
                raise TypeError(f"Config root must be a dict, got {type(user_cfg).__name__}")
            self._deep_merge(self._data, user_cfg)
            self._validate_structure()
            self._post_validate()
            logger.info("User config loaded from %s", CONFIG_FILE)
        except Exception as exc:
            logger.warning("Bad config — falling back to defaults: %s", exc)
            self._data = copy.deepcopy(DEFAULT_CONFIG)

    def _resolve_tasks_file(self) -> None:
        """Make ``settings.tasks_file`` absolute; relative paths are taken from the data dir."""
        settings = self._data["settings"]
        settings["tasks_file"] = str(APP_PATHS.resolve_data_path(settings["tasks_file"]))
        logger.info("Data mode: %s — tasks file: %s", APP_PATHS.mode, settings["tasks_file"])

    def _validate_structure(self) -> None:
        _validate_colors(self._data["colors"])
        _validate_transparency(self._data["transparency"])
        _validate_settings(self._data["settings"])
        _validate_fonts(self._data["fonts"])

    def _post_validate(self) -> None:
        _validate_contrast(self._data["colors"])

    @staticmethod
    def _deep_merge(base: dict, override: dict) -> dict:
        """Recursively merge *override* into *base*, ignoring unknown keys."""
        for key, value in override.items():
            if key not in base:
                logger.warning("Ignoring unknown config key: %r", key)
                continue
            if isinstance(value, dict) and isinstance(base.get(key), dict):
                # Filter unknown sub-keys
                known = _KNOWN_KEYS.get(key)
                if known is not None:
                    unknown = set(value.keys()) - known
                    for uk in unknown:
                        logger.warning("Ignoring unknown config key: %s.%s", key, uk)
                    value = {k: v for k, v in value.items() if k in known}
                Config._deep_merge(base[key], value)
            else:
                base[key] = value
        return base

    # ── Dynamic attribute access ─────────────

    def __getattr__(self, name: str) -> Any:
        # Fast path: cached
        cache = self.__dict__.get("_attr_cache")
        if cache is not None and name in cache:
            return cache[name]

        value = self._resolve_attr(name)
        if value is _SENTINEL:
            raise AttributeError(f"Config has no attribute {name!r}")

        # Cache for future access
        if cache is not None:
            cache[name] = value
        return value

    def _resolve_attr(self, name: str) -> Any:
        # 1. Explicit aliases
        if name in _PROPERTY_ALIASES:
            section, key = _PROPERTY_ALIASES[name]
            return self._cast(section, self._data[section][key])

        # 2. spacing_<key>
        if name.startswith(_SPACING_PREFIX):
            key = name[len(_SPACING_PREFIX) :]
            if key in self._data["spacing"]:
                return int(self._data["spacing"][key])

        # 3. font_<key>
        if name.startswith(_FONT_PREFIX):
            key = name[len(_FONT_PREFIX) :]
            if key in self._data["fonts"]:
                return tuple(self._data["fonts"][key])

        # 4. shortcut_<key>
        if name.startswith(_SHORTCUT_PREFIX):
            key = name[len(_SHORTCUT_PREFIX) :]
            if key in self._data["shortcuts"]:
                return str(self._data["shortcuts"][key])

        # 5. colors (direct key match)
        if name in self._data["colors"]:
            return str(self._data["colors"][name])

        # 6. settings (direct key match)
        if name in self._data["settings"]:
            return self._data["settings"][name]

        return _SENTINEL

    @staticmethod
    def _cast(section: str, value: Any) -> Any:
        if section == "colors":
            return str(value)
        if section == "transparency":
            return float(value)
        if section == "spacing":
            return int(value)
        if section == "fonts":
            return tuple(value)
        if section == "shortcuts":
            return str(value)
        return value

    # ── Strings (i18n) ───────────────────────

    def string(self, key: str, **kwargs: Any) -> str:
        template = self._data["strings"].get(key, key)
        try:
            return template.format(**kwargs) if kwargs else template
        except (KeyError, IndexError):
            return template


_SENTINEL = object()

config = Config()
