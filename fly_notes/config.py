"""
Validated, typed configuration: built-in defaults merged with ``config.json``.

``load_config()`` returns an immutable ``AppConfig`` with one dataclass per
section (``cfg.colors.header_bg``, ``cfg.spacing.md``, ...). Nothing is read
at import time: ``main()`` builds the config and passes it to the UI.
"""

from __future__ import annotations

import copy
import json
import logging
import os
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from .paths import APP_PATHS, AppPaths

logger = logging.getLogger(__name__)

# Where config/data/assets live depends on how the app runs (source,
# installed .exe, portable .exe) — see fly_notes/paths.py.
CONFIG_FILE = APP_PATHS.config_file
DEFAULT_TASKS_FILE = APP_PATHS.tasks_file
ICON_PATH = APP_PATHS.icon_file

DEFAULT_CONFIG: dict[str, Any] = {
    # Sticky-note look: one pale-yellow surface, flat task rows (no card border or
    # shadow), an amber accent for focus and links, and a green check mark.
    "colors": {
        # Surfaces
        "header_bg": "#FCEE9E",
        "content_bg": "#FFF8C5",
        "item_bg": "#FFF8C5",
        "item_bg_completed": "#FFF8C5",
        "footer_bg": "#FFF8C5",
        "separator_color": "#F0E39C",
        "window_border": "#E6D36E",
        # Text
        "text_primary": "#3B3200",
        "text_secondary": "#5E5214",
        "text_completed": "#6E6224",
        "text_on_header": "#3B3200",
        "text_placeholder": "#8A7D3A",
        "section_header": "#6B5E1C",
        "header_icon": "#5E5214",
        # Interactive
        "border_color": "#EEDF94",
        "border_focus": "#A16207",
        # Same as item_bg: rows without a card border. Set a colour to draw one.
        "item_border": "#FFF8C5",
        "entry_bg": "#FFFCE6",
        "entry_border": "#EEDF94",
        "btn_danger_bg": "#D92D20",
        "btn_danger_hover": "#B42318",
        "btn_close_hover_bg": "#D92D20",
        "btn_header_hover_bg": "#F5E27E",
        "link_color": "#8A5206",
        "link_hover": "#6B3F04",
        # Feedback
        "drag_highlight": "#FFF1A6",
        "drag_border": "#A16207",
        "checkbox_check": "#3E8E4F",
        "checkbox_bg": "#FFFCE6",
        "checkbox_border": "#B3A055",
        "checkbox_hover_bg": "#E4F2D2",
        "scrollbar_thumb": "#E5D27C",
        "scrollbar_track": "#FFF8C5",
        # State
        "shadow_color": "#00000000",
        "empty_state_fg": "#857832",
    },
    "transparency": {
        "active": 1.0,
        "inactive": 0.75,
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
        "item_padding_y": 5,
        "item_padding_x": 10,
        "header_height": 38,
        "footer_height": 32,
        "border_radius": 3,
        "confirm_delete": False,
        "undo_timeout_ms": 5000,
        # Starting value only: the header pin (or Ctrl+T) choice is remembered in state.json.
        "always_on_top": True,
        # Wait this long after the window loses focus before fading it.
        "inactive_fade_delay_ms": 800,
        "max_visible_tasks": 100,
        "checkbox_size": 18,
        "checkbox_round": True,
        "group_completed": True,
        "separator_height": 1,
        "scrollbar_width": 8,
        # Colour preset: "light" (the colours above) or "dark" (DARK_COLORS). Colours set
        # in config.json are applied on top of the preset.
        "theme": "light",
    },
    # Segoe UI Variable ships with Windows 11; FONT_FALLBACKS maps it to Segoe UI elsewhere.
    "fonts": {
        "header": ["Segoe UI Variable Text Semibold", 10],
        "body": ["Segoe UI Variable Text", 11],
        "body_strike": ["Segoe UI Variable Text", 11, "overstrike"],
        "footer": ["Segoe UI Variable Text", 9],
        "empty_hint": ["Segoe UI Variable Text", 10, "italic"],
        "badge": ["Segoe UI Variable Text", 9],
        "section": ["Segoe UI Variable Text Semibold", 9],
    },
    "shortcuts": {
        "new_task": "<Control-n>",
        "delete_completed": "<Control-d>",
        # Not <Escape>: Escape means "cancel" (it clears the entry), never "quit".
        "close": "<Control-w>",
        "undo": "<Control-z>",
        # Edits the task under the mouse pointer (or the one with keyboard focus).
        "edit_task": "<F2>",
        "toggle_always_on_top": "<Control-t>",
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
        "more_hidden": "Show {count} more",
        "more_hidden_paged": "Show {count} more (of {hidden})",
        "badge_format": "{done} of {total} done",
        "btn_close": "✕",
        "btn_minimize": "—",
        # Header pin: filled while the window stays on top, outlined when it doesn't.
        "btn_pin_on": "▲",
        "btn_pin_off": "△",
    },
}


# The "dark" preset: the same flat layout on a warm charcoal surface.
DARK_COLORS: dict[str, str] = {
    # Surfaces
    "header_bg": "#2A2720",
    "content_bg": "#22201A",
    "item_bg": "#22201A",
    "item_bg_completed": "#22201A",
    "footer_bg": "#22201A",
    "separator_color": "#36322A",
    "window_border": "#4A4535",
    # Text
    "text_primary": "#F2EBD3",
    "text_secondary": "#C2B89A",
    "text_completed": "#A39A80",
    "text_on_header": "#F2EBD3",
    "text_placeholder": "#8F876F",
    "section_header": "#B5AB8C",
    "header_icon": "#C2B89A",
    # Interactive
    "border_color": "#3D392D",
    "border_focus": "#E0B341",
    "item_border": "#22201A",
    "entry_bg": "#2B2820",
    "entry_border": "#3D392D",
    "btn_danger_bg": "#C82333",
    "btn_danger_hover": "#A71D2A",
    "btn_close_hover_bg": "#C82333",
    "btn_header_hover_bg": "#3A362B",
    "link_color": "#E6BE55",
    "link_hover": "#F2D27A",
    # Feedback
    "drag_highlight": "#2F2B22",
    "drag_border": "#E0B341",
    "checkbox_check": "#4FA562",
    "checkbox_bg": "#2B2820",
    "checkbox_border": "#8A8168",
    "checkbox_hover_bg": "#2C3A29",
    "scrollbar_thumb": "#4A4535",
    "scrollbar_track": "#22201A",
    # State
    "shadow_color": "#00000000",
    "empty_state_fg": "#958C72",
}

# Font family -> (family, extra styles) to use when it is not installed.
FONT_FALLBACKS: dict[str, tuple[str, tuple[str, ...]]] = {
    "Segoe UI Variable Text": ("Segoe UI", ()),
    "Segoe UI Variable Text Semibold": ("Segoe UI", ("bold",)),
}

THEMES: dict[str, dict[str, str]] = {
    "light": dict(DEFAULT_CONFIG["colors"]),
    "dark": DARK_COLORS,
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
    ("header_icon", "header_bg", 4.5),
    ("text_primary", "entry_bg", 4.5),
    ("text_placeholder", "entry_bg", 3.0),
    ("link_color", "footer_bg", 4.5),
    ("link_color", "content_bg", 4.5),  # "Show N more" link in the task list
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


def _is_int(value: Any) -> bool:
    """A real int: ``bool`` is an ``int`` subclass, but ``true`` is not a size."""
    return isinstance(value, int) and not isinstance(value, bool)


def _validate_transparency(trans: dict[str, Any]) -> None:
    for key in ("active", "inactive"):
        if key not in trans:
            continue
        val = trans[key]
        if isinstance(val, bool) or not isinstance(val, (int, float)) or not 0.0 < val <= 1.0:
            raise ValueError(
                f"transparency.{key}: must be a number above 0 and up to 1, got {val!r}"
            )
    if "active" in trans and "inactive" in trans and trans["inactive"] > trans["active"]:
        raise ValueError(
            f"transparency.inactive ({trans['inactive']}) must not be above "
            f"transparency.active ({trans['active']})"
        )


# Settings that must be at least 1: a zero size, limit or delay would break the window.
_POSITIVE_INT_SETTINGS = (
    "default_width",
    "default_height",
    "min_width",
    "min_height",
    "drag_threshold",
    "max_task_length",
    "header_height",
    "footer_height",
    "max_visible_tasks",
    "checkbox_size",
    "scrollbar_width",
    "undo_timeout_ms",
)
# Settings where 0 is meaningful (no padding, square corners, no separator, fade at once).
_NON_NEGATIVE_INT_SETTINGS = (
    "item_padding_y",
    "item_padding_x",
    "border_radius",
    "separator_height",
    "inactive_fade_delay_ms",
)
_BOOL_SETTINGS = ("confirm_delete", "group_completed", "always_on_top", "checkbox_round")


def _validate_settings(settings: dict[str, Any]) -> None:
    for key in _POSITIVE_INT_SETTINGS:
        if key in settings and not (_is_int(settings[key]) and settings[key] >= 1):
            raise ValueError(
                f"settings.{key}: must be a whole number of 1 or more, got {settings[key]!r}"
            )
    for key in _NON_NEGATIVE_INT_SETTINGS:
        if key in settings and not (_is_int(settings[key]) and settings[key] >= 0):
            raise ValueError(
                f"settings.{key}: must be a whole number of 0 or more, got {settings[key]!r}"
            )
    for key in _BOOL_SETTINGS:
        if key in settings and not isinstance(settings[key], bool):
            raise ValueError(f"settings.{key}: must be true or false, got {settings[key]!r}")

    if "theme" in settings and settings["theme"] not in THEMES:
        raise ValueError(
            f"settings.theme: must be one of {', '.join(map(repr, THEMES))}, "
            f"got {settings['theme']!r}"
        )

    if "tasks_file" in settings:
        tf = settings["tasks_file"]
        if not isinstance(tf, str) or not tf.strip():
            raise ValueError(f"settings.tasks_file: must be a non-empty string path, got {tf!r}")

    for minimum, default in (("min_width", "default_width"), ("min_height", "default_height")):
        if minimum in settings and default in settings and settings[minimum] > settings[default]:
            raise ValueError(
                f"settings.{minimum} ({settings[minimum]}) must not be above "
                f"settings.{default} ({settings[default]})"
            )


def _validate_spacing(spacing: dict[str, Any]) -> None:
    for key, val in spacing.items():
        if not (_is_int(val) and val >= 0):
            raise ValueError(f"spacing.{key}: must be a whole number of 0 or more, got {val!r}")


def _validate_fonts(fonts: dict[str, Any]) -> None:
    for key, val in fonts.items():
        if not isinstance(val, list) or len(val) < 2:
            raise ValueError(f"fonts.{key}: expected [family, size, ...], got {val!r}")
        family, size, *styles = val
        if not isinstance(family, str) or not family.strip():
            raise ValueError(f"fonts.{key}: the family must be a non-empty string, got {family!r}")
        # Tk reads a positive size as points and a negative one as pixels; 0 is meaningless.
        if not _is_int(size) or size == 0:
            raise ValueError(f"fonts.{key}: the size must be a non-zero whole number, got {size!r}")
        if not all(isinstance(style, str) for style in styles):
            raise ValueError(f'fonts.{key}: styles must be strings like "bold", got {styles!r}')


def _validate_shortcuts(shortcuts: dict[str, Any]) -> None:
    """Shape only. Whether Tk accepts the sequence is checked when it is bound."""
    for key, val in shortcuts.items():
        if not isinstance(val, str) or not val.strip():
            raise ValueError(
                f'shortcuts.{key}: must be a Tk key sequence like "<Control-n>", got {val!r}'
            )


def _validate_strings(strings: dict[str, Any]) -> None:
    for key, val in strings.items():
        if not isinstance(val, str):
            raise ValueError(f"strings.{key}: must be text, got {val!r}")


# ──────────────────────────────────────────────
# Typed configuration
# ──────────────────────────────────────────────

Font = tuple[str, int, *tuple[str, ...]]


@dataclass(frozen=True, slots=True)
class Colors:
    """Colour tokens (``#RRGGBB``, or ``#RRGGBBAA`` for ``shadow_color``)."""

    header_bg: str
    content_bg: str
    item_bg: str
    item_bg_completed: str
    footer_bg: str
    separator_color: str
    text_primary: str
    text_secondary: str
    text_completed: str
    text_on_header: str
    text_placeholder: str
    section_header: str
    border_color: str
    border_focus: str
    item_border: str
    entry_bg: str
    entry_border: str
    window_border: str
    header_icon: str
    btn_danger_bg: str
    btn_danger_hover: str
    btn_close_hover_bg: str
    btn_header_hover_bg: str
    link_color: str
    link_hover: str
    drag_highlight: str
    drag_border: str
    checkbox_check: str
    checkbox_bg: str
    checkbox_border: str
    checkbox_hover_bg: str
    scrollbar_thumb: str
    scrollbar_track: str
    shadow_color: str
    empty_state_fg: str


@dataclass(frozen=True, slots=True)
class Transparency:
    """Window opacity, 0.0 to 1.0, while focused and unfocused."""

    active: float
    inactive: float


@dataclass(frozen=True, slots=True)
class Spacing:
    """Spacing scale in pixels."""

    xs: int
    sm: int
    md: int
    lg: int
    xl: int
    xxl: int


@dataclass(frozen=True, slots=True)
class Settings:
    """Sizes, limits and behaviour switches."""

    tasks_file: str
    default_width: int
    default_height: int
    drag_threshold: int
    min_width: int
    min_height: int
    max_task_length: int
    item_padding_y: int
    item_padding_x: int
    header_height: int
    footer_height: int
    border_radius: int
    confirm_delete: bool
    undo_timeout_ms: int
    always_on_top: bool
    inactive_fade_delay_ms: int
    max_visible_tasks: int
    checkbox_size: int
    group_completed: bool
    checkbox_round: bool
    separator_height: int
    scrollbar_width: int
    theme: str


@dataclass(frozen=True, slots=True)
class Fonts:
    """Tk font tuples: ``(family, size, *styles)``."""

    header: Font
    body: Font
    body_strike: Font
    footer: Font
    empty_hint: Font
    badge: Font
    section: Font


@dataclass(frozen=True, slots=True)
class Shortcuts:
    """Tk event sequences for the keyboard shortcuts."""

    new_task: str
    delete_completed: str
    close: str
    undo: str
    edit_task: str
    toggle_always_on_top: str


@dataclass(frozen=True, slots=True)
class Strings:
    """UI text; some are ``str.format`` templates (see ``AppConfig.string``)."""

    app_title: str
    entry_placeholder: str
    clear_completed: str
    clear_completed_zero: str
    empty_state: str
    confirm_delete_title: str
    confirm_delete_msg: str
    undo_deleted: str
    undo_cleared: str
    undo_action: str
    section_pending: str
    section_completed: str
    more_hidden: str
    more_hidden_paged: str
    badge_format: str
    btn_close: str
    btn_minimize: str
    btn_pin_on: str
    btn_pin_off: str


@dataclass(frozen=True, slots=True)
class AppConfig:
    """The whole configuration, one typed section per ``config.json`` section.

    Built once in ``main()`` with ``load_config()`` and passed to the widgets
    that need it; tests use ``default_config()``. Immutable: derive a variant
    with ``dataclasses.replace``.
    """

    colors: Colors
    transparency: Transparency
    spacing: Spacing
    settings: Settings
    fonts: Fonts
    shortcuts: Shortcuts
    strings: Strings

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AppConfig:
        """Build from a complete, already validated config dict."""
        return cls(
            colors=Colors(**{k: str(v) for k, v in data["colors"].items()}),
            transparency=Transparency(**{k: float(v) for k, v in data["transparency"].items()}),
            spacing=Spacing(**data["spacing"]),
            settings=Settings(**data["settings"]),
            fonts=Fonts(**{k: tuple(v) for k, v in data["fonts"].items()}),
            shortcuts=Shortcuts(**data["shortcuts"]),
            strings=Strings(**data["strings"]),
        )

    def with_available_fonts(self, families: set[str]) -> AppConfig:
        """Swap each font family that is not in *families* for its ``FONT_FALLBACKS`` entry."""
        swapped: dict[str, Font] = {}
        for name, (family, size, *styles) in (
            (f, getattr(self.fonts, f)) for f in Fonts.__dataclass_fields__
        ):
            if family in families or family not in FONT_FALLBACKS:
                continue
            fallback, extra = FONT_FALLBACKS[family]
            swapped[name] = (fallback, size, *extra, *styles)
        if not swapped:
            return self
        return replace(self, fonts=replace(self.fonts, **swapped))

    def string(self, key: str, **kwargs: Any) -> str:
        """The UI text *key*, formatted with *kwargs*.

        A template the user broke in ``config.json`` (an unknown placeholder)
        is shown as written rather than raising.
        """
        template = getattr(self.strings, key, key)
        try:
            return template.format(**kwargs) if kwargs else template
        except (KeyError, IndexError, ValueError):
            return template

    def with_settings(self, **changes: Any) -> AppConfig:
        """A copy with some ``settings`` replaced (handy in tests)."""
        return replace(self, settings=replace(self.settings, **changes))


# ──────────────────────────────────────────────
# Loading
# ──────────────────────────────────────────────


def default_config(
    tasks_file: str | os.PathLike[str] | None = None, theme: str = "light"
) -> AppConfig:
    """The built-in defaults, without reading ``config.json``.

    *tasks_file* overrides ``settings.tasks_file`` (tests point it at a
    temporary folder); otherwise it is the default path for the data folder.
    *theme* picks the colour preset.
    """
    data = copy.deepcopy(DEFAULT_CONFIG)
    _apply_theme(data, theme)
    if tasks_file is not None:
        data["settings"]["tasks_file"] = str(tasks_file)
    return AppConfig.from_dict(data)


def load_config(
    config_file: Path = CONFIG_FILE,
    paths: AppPaths = APP_PATHS,
) -> AppConfig:
    """Read *config_file* over the defaults and validate the result.

    Unknown keys are ignored with a warning. If the file can't be parsed or
    a value is invalid, the defaults are used. A relative ``tasks_file`` is
    taken from the data folder.
    """
    data = copy.deepcopy(DEFAULT_CONFIG)
    if not config_file.exists():
        logger.info("No user config at %s — using defaults", config_file)
    else:
        try:
            with open(config_file, encoding="utf-8") as fh:
                user_cfg = json.load(fh)
            if not isinstance(user_cfg, dict):
                raise TypeError(f"Config root must be a dict, got {type(user_cfg).__name__}")
            # The preset goes first, so colours set in the file override it.
            _apply_theme(data, _requested_theme(user_cfg))
            _deep_merge(data, user_cfg)
            _validate_structure(data)
            logger.info("User config loaded from %s", config_file)
        except Exception as exc:
            logger.warning("Bad config — falling back to defaults: %s", exc)
            data = copy.deepcopy(DEFAULT_CONFIG)
    _validate_contrast(data["colors"])

    settings = data["settings"]
    settings["tasks_file"] = str(paths.resolve_data_path(settings["tasks_file"]))
    logger.info("Data mode: %s — tasks file: %s", paths.mode, settings["tasks_file"])
    return AppConfig.from_dict(data)


def _requested_theme(user_cfg: dict[str, Any]) -> str:
    settings = user_cfg.get("settings")
    theme = settings.get("theme", "light") if isinstance(settings, dict) else "light"
    _validate_settings({"theme": theme})
    return theme


def _apply_theme(data: dict[str, Any], theme: str) -> None:
    """Set the colours and ``settings.theme`` of *data* to the *theme* preset."""
    _validate_settings({"theme": theme})
    data["colors"].update(THEMES[theme])
    data["settings"]["theme"] = theme


def _validate_structure(data: dict[str, Any]) -> None:
    _validate_colors(data["colors"])
    _validate_transparency(data["transparency"])
    _validate_settings(data["settings"])
    _validate_spacing(data["spacing"])
    _validate_fonts(data["fonts"])
    _validate_shortcuts(data["shortcuts"])
    _validate_strings(data["strings"])


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge *override* into *base*, ignoring unknown keys."""
    for key, value in override.items():
        if key not in base:
            logger.warning("Ignoring unknown config key: %r", key)
            continue
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            known = _KNOWN_KEYS.get(key)
            if known is not None:
                for unknown in set(value.keys()) - known:
                    logger.warning("Ignoring unknown config key: %s.%s", key, unknown)
                value = {k: v for k, v in value.items() if k in known}
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base
