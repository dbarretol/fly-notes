"""
Centralised, validated configuration with deep-merge support and
WCAG-compliant colour tokens organised in a semantic design system.
"""

from __future__ import annotations

import copy
import json
import logging
import os
from typing import Any, Dict, Tuple

logger = logging.getLogger(__name__)

_PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_PACKAGE_DIR)
CONFIG_FILE = os.path.join(_PROJECT_ROOT, "config.json")
DEFAULT_TASKS_FILE = os.path.join(_PROJECT_ROOT, "tasks.json")

DEFAULT_CONFIG: Dict[str, Any] = {
    "colors": {
        # Surfaces
        "header_bg":            "#B35C00",
        "content_bg":           "#FFF4E6",
        "item_bg":              "#FFFFFF",
        "item_bg_completed":    "#E8E0D8",
        "footer_bg":            "#F0E6D8",         # ← Ligeramente más oscuro para separación
        "separator_color":      "#E0D0C0",         # ← NUEVO: línea divisoria sutil

        # Text
        "text_primary":         "#2D1810",
        "text_secondary":       "#5C4033",
        "text_completed":       "#6B5B4E",
        "text_on_header":       "#FFFFFF",
        "text_placeholder":     "#8C7E72",

        # Interactive
        "border_color":         "#D4B896",
        "border_focus":         "#B35C00",
        "btn_danger_bg":        "#DC3545",
        "btn_danger_hover":     "#C82333",
        "btn_close_hover_bg":   "#FF4500",
        "btn_header_hover_bg":  "#8B4500",
        "link_color":           "#8B4D00",
        "link_hover":           "#B35C00",

        # Feedback
        "drag_highlight":       "#FFE0B2",
        "drag_border":          "#B35C00",
        "checkbox_check":       "#B35C00",
        "checkbox_bg":          "#FFFFFF",
        "checkbox_border":      "#B0977A",         # ← NUEVO: borde más visible para unchecked
        "checkbox_hover_bg":    "#FFF0E0",         # ← NUEVO: hover suave en checkbox
        "scrollbar_thumb":      "#C4956A",
        "scrollbar_track":      "#FFF4E6",

        # State
        "shadow_color":         "#00000015",
        "empty_state_fg":       "#887868",
    },

    "transparency": {
        "active":   1.0,
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
        "tasks_file":           DEFAULT_TASKS_FILE,
        "default_width":        320,
        "default_height":       440,
        "drag_threshold":       18,
        "min_width":            240,
        "min_height":           180,
        "max_task_length":      300,
        "item_padding_y":       7,
        "item_padding_x":       10,
        "header_height":        38,
        "footer_height":        32,
        "border_radius":        6,
        "animation_ms":         150,
        "confirm_delete":       False,
        "max_visible_tasks":    100,
        "checkbox_size":        18,
        "group_completed":      True,              # ← NUEVO: agrupar completados abajo
        "separator_height":     1,                 # ← NUEVO
        "scrollbar_width":      6,                 # ← NUEVO: thin scrollbar
    },

    "fonts": {
        "header":       ["Segoe UI", 10, "bold"],
        "body":         ["Segoe UI", 11],
        "body_strike":  ["Segoe UI", 11, "overstrike"],
        "footer":       ["Segoe UI", 9],
        "empty_hint":   ["Segoe UI", 10, "italic"],
        "badge":        ["Segoe UI", 8, "bold"],
        "section":      ["Segoe UI", 8],           # ← NUEVO: section header font
    },

    "shortcuts": {
        "new_task":         "<Control-n>",
        "delete_completed": "<Control-d>",
        "close":            "<Escape>",
        "focus_entry":      "<Control-l>",
    },

    "strings": {
        "app_title":            "Fly Notes",
        "entry_placeholder":    "Add a new task…",
        "clear_completed":      "Clear completed ({count})",
        "clear_completed_zero": "Clear completed",
        "empty_state":          "No tasks yet — type above to start!",
        "confirm_delete_title": "Delete Task",
        "confirm_delete_msg":   "Remove this task permanently?",
        "confirm_clear_title":  "Clear Completed",
        "confirm_clear_msg":    "Remove {count} completed task(s)?",
        "section_pending":      "To Do ({count})",        # ← Title case + counter
        "section_completed":    "Completed ({count})",    # ← Title case + counter
    },
}


# ──────────────────────────────────────────────
# Contrast validation (WCAG AA)
# ──────────────────────────────────────────────
def _hex_to_rgb(hex_color: str) -> tuple:
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
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


_CONTRAST_PAIRS = [
    ("text_primary",     "item_bg",           4.5),
    ("text_completed",   "item_bg_completed", 4.5),
    ("text_on_header",   "header_bg",         4.5),
    ("text_secondary",   "content_bg",        4.5),
    ("text_placeholder", "item_bg",           3.0),
    ("link_color",       "footer_bg",         4.5),
    ("empty_state_fg",   "content_bg",        3.0),
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


def _validate_colors(colors: Dict[str, str]) -> None:
    for key, val in colors.items():
        if not _is_color(val):
            raise ValueError(f"colors.{key}: '{val}' is not a valid hex colour")


def _validate_contrast(colors: Dict[str, str]) -> None:
    for fg_key, bg_key, min_ratio in _CONTRAST_PAIRS:
        fg, bg = colors.get(fg_key), colors.get(bg_key)
        if not fg or not bg:
            continue
        try:
            ratio = _contrast_ratio(fg, bg)
            if ratio < min_ratio:
                logger.warning(
                    "WCAG contrast fail: %s (%s) on %s (%s) = %.2f:1 (need %.1f:1)",
                    fg_key, fg, bg_key, bg, ratio, min_ratio,
                )
        except Exception:
            pass


def _validate_transparency(trans: Dict[str, float]) -> None:
    for key in ("active", "inactive"):
        val = trans.get(key)
        if not isinstance(val, (int, float)) or not (0.0 <= val <= 1.0):
            raise ValueError(f"transparency.{key}: must be float 0.0-1.0, got {val!r}")


def _validate_settings(settings: Dict[str, Any]) -> None:
    int_keys = (
        "default_width", "default_height", "drag_threshold",
        "min_width", "min_height", "max_task_length",
        "item_padding_y", "item_padding_x", "header_height",
        "footer_height", "border_radius", "animation_ms",
        "max_visible_tasks", "checkbox_size",
    )
    for key in int_keys:
        val = settings.get(key)
        if val is not None and (not isinstance(val, int) or val < 0):
            raise ValueError(f"settings.{key}: must be a positive int, got {val!r}")


def _validate_fonts(fonts: Dict[str, list]) -> None:
    for key, val in fonts.items():
        if not isinstance(val, list) or len(val) < 2:
            raise ValueError(f"fonts.{key}: expected [family, size, ...], got {val!r}")


class Config:
    """Immutable-after-load application configuration."""

    def __init__(self) -> None:
        self._data: Dict[str, Any] = copy.deepcopy(DEFAULT_CONFIG)
        self._load()

    def _load(self) -> None:
        if not os.path.exists(CONFIG_FILE):
            logger.info("No user config at %s — using defaults", CONFIG_FILE)
            self._post_validate()
            return
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as fh:
                user_cfg = json.load(fh)
            self._deep_merge(self._data, user_cfg)
            self._validate_structure()
            self._post_validate()
            logger.info("User config loaded from %s", CONFIG_FILE)
        except Exception as exc:
            logger.warning("Bad config — falling back to defaults: %s", exc)
            self._data = copy.deepcopy(DEFAULT_CONFIG)

    def _validate_structure(self) -> None:
        _validate_colors(self._data["colors"])
        _validate_transparency(self._data["transparency"])
        _validate_settings(self._data["settings"])
        _validate_fonts(self._data["fonts"])

    def _post_validate(self) -> None:
        _validate_contrast(self._data["colors"])

    @staticmethod
    def _deep_merge(base: dict, override: dict) -> dict:
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(base.get(key), dict):
                Config._deep_merge(base[key], value)
            else:
                base[key] = value
        return base

    # -- Colours -------------------------------
    @property
    def header_bg(self) -> str: return self._data["colors"]["header_bg"]
    @property
    def content_bg(self) -> str: return self._data["colors"]["content_bg"]
    @property
    def item_bg(self) -> str: return self._data["colors"]["item_bg"]
    @property
    def item_bg_completed(self) -> str: return self._data["colors"]["item_bg_completed"]
    @property
    def footer_bg(self) -> str: return self._data["colors"]["footer_bg"]
    @property
    def text_primary(self) -> str: return self._data["colors"]["text_primary"]
    @property
    def text_secondary(self) -> str: return self._data["colors"]["text_secondary"]
    @property
    def text_completed(self) -> str: return self._data["colors"]["text_completed"]
    @property
    def text_on_header(self) -> str: return self._data["colors"]["text_on_header"]
    @property
    def text_placeholder(self) -> str: return self._data["colors"]["text_placeholder"]
    @property
    def border_color(self) -> str: return self._data["colors"]["border_color"]
    @property
    def border_focus(self) -> str: return self._data["colors"]["border_focus"]
    @property
    def btn_danger_bg(self) -> str: return self._data["colors"]["btn_danger_bg"]
    @property
    def btn_danger_hover(self) -> str: return self._data["colors"]["btn_danger_hover"]
    @property
    def btn_close_hover_bg(self) -> str: return self._data["colors"]["btn_close_hover_bg"]
    @property
    def btn_header_hover_bg(self) -> str: return self._data["colors"]["btn_header_hover_bg"]
    @property
    def link_color(self) -> str: return self._data["colors"]["link_color"]
    @property
    def link_hover(self) -> str: return self._data["colors"]["link_hover"]
    @property
    def drag_highlight_color(self) -> str: return self._data["colors"]["drag_highlight"]
    @property
    def drag_border(self) -> str: return self._data["colors"]["drag_border"]
    @property
    def checkbox_check(self) -> str: return self._data["colors"]["checkbox_check"]
    @property
    def checkbox_bg(self) -> str: return self._data["colors"]["checkbox_bg"]
    @property
    def scrollbar_thumb(self) -> str: return self._data["colors"]["scrollbar_thumb"]
    @property
    def scrollbar_track(self) -> str: return self._data["colors"]["scrollbar_track"]
    @property
    def empty_state_fg(self) -> str: return self._data["colors"]["empty_state_fg"]
    @property
    def separator_color(self) -> str: return self._data["colors"]["separator_color"]
    @property
    def checkbox_border(self) -> str: return self._data["colors"]["checkbox_border"]
    @property
    def checkbox_hover_bg(self) -> str: return self._data["colors"]["checkbox_hover_bg"]
    # -- Transparency --------------------------
    @property
    def active_alpha(self) -> float: return float(self._data["transparency"]["active"])
    @property
    def inactive_alpha(self) -> float: return float(self._data["transparency"]["inactive"])

    # -- Spacing -------------------------------
    @property
    def spacing_xs(self) -> int: return self._data["spacing"]["xs"]
    @property
    def spacing_sm(self) -> int: return self._data["spacing"]["sm"]
    @property
    def spacing_md(self) -> int: return self._data["spacing"]["md"]
    @property
    def spacing_lg(self) -> int: return self._data["spacing"]["lg"]
    @property
    def spacing_xl(self) -> int: return self._data["spacing"]["xl"]
    @property
    def spacing_xxl(self) -> int: return self._data["spacing"]["xxl"]

    # -- Settings ------------------------------
    @property
    def tasks_file(self) -> str: return self._data["settings"]["tasks_file"]
    @property
    def default_width(self) -> int: return int(self._data["settings"]["default_width"])
    @property
    def default_height(self) -> int: return int(self._data["settings"]["default_height"])
    @property
    def drag_threshold(self) -> int: return int(self._data["settings"].get("drag_threshold", 18))
    @property
    def min_width(self) -> int: return int(self._data["settings"].get("min_width", 240))
    @property
    def min_height(self) -> int: return int(self._data["settings"].get("min_height", 180))
    @property
    def max_task_length(self) -> int: return int(self._data["settings"].get("max_task_length", 300))
    @property
    def item_padding_y(self) -> int: return int(self._data["settings"].get("item_padding_y", 7))
    @property
    def item_padding_x(self) -> int: return int(self._data["settings"].get("item_padding_x", 10))
    @property
    def header_height(self) -> int: return int(self._data["settings"].get("header_height", 38))
    @property
    def footer_height(self) -> int: return int(self._data["settings"].get("footer_height", 32))
    @property
    def animation_ms(self) -> int: return int(self._data["settings"].get("animation_ms", 150))
    @property
    def confirm_delete(self) -> bool: return bool(self._data["settings"].get("confirm_delete", False))
    @property
    def max_visible_tasks(self) -> int: return int(self._data["settings"].get("max_visible_tasks", 100))
    @property
    def checkbox_size(self) -> int: return int(self._data["settings"].get("checkbox_size", 18))
    @property
    def group_completed(self) -> bool: return bool(self._data["settings"].get("group_completed", True))
    @property
    def separator_height(self) -> int: return int(self._data["settings"].get("separator_height", 1))
    @property
    def scrollbar_width(self) -> int: return int(self._data["settings"].get("scrollbar_width", 6))
    # -- Fonts ---------------------------------
    @property
    def font_header(self) -> Tuple[str, ...]: return tuple(self._data["fonts"]["header"])
    @property
    def font_body(self) -> Tuple[str, ...]: return tuple(self._data["fonts"]["body"])
    @property
    def font_body_strike(self) -> Tuple[str, ...]: return tuple(self._data["fonts"]["body_strike"])
    @property
    def font_footer(self) -> Tuple[str, ...]: return tuple(self._data["fonts"]["footer"])
    @property
    def font_empty_hint(self) -> Tuple[str, ...]: return tuple(self._data["fonts"]["empty_hint"])
    @property
    def font_badge(self) -> Tuple[str, ...]: return tuple(self._data["fonts"]["badge"])
    @property
    def font_section(self) -> Tuple[str, ...]: return tuple(self._data["fonts"]["section"])
    # -- Shortcuts -----------------------------
    @property
    def shortcut_new_task(self) -> str: return self._data["shortcuts"]["new_task"]
    @property
    def shortcut_delete_completed(self) -> str: return self._data["shortcuts"]["delete_completed"]
    @property
    def shortcut_close(self) -> str: return self._data["shortcuts"]["close"]
    @property
    def shortcut_focus_entry(self) -> str: return self._data["shortcuts"]["focus_entry"]

    # -- Strings (i18n) ------------------------
    def string(self, key: str, **kwargs: Any) -> str:
        template = self._data["strings"].get(key, key)
        try:
            return template.format(**kwargs) if kwargs else template
        except (KeyError, IndexError):
            return template


config = Config()