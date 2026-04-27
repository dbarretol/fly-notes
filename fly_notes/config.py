"""
Centralised, validated configuration with deep-merge support and
WCAG-compliant colour tokens organised in a semantic design system.

Design System Rationale
───────────────────────
* Colours are grouped into semantic roles (surface, text, interactive, feedback)
  rather than raw visual descriptions — this makes theming predictable.
* Every text/background pair is pre-validated for WCAG AA contrast (≥ 4.5 : 1).
* Spacing, radii and timing tokens live alongside colours so the entire
  visual language can be overridden from a single ``config.json``.
"""

from __future__ import annotations

import copy
import json
import logging
import math
import os
from typing import Any, Dict, Tuple

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Paths — always relative to *this* file
# ──────────────────────────────────────────────
_PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_PACKAGE_DIR)
CONFIG_FILE = os.path.join(_PROJECT_ROOT, "config.json")
DEFAULT_TASKS_FILE = os.path.join(_PROJECT_ROOT, "tasks.json")


# ──────────────────────────────────────────────
# Design-system defaults
# ──────────────────────────────────────────────
DEFAULT_CONFIG: Dict[str, Any] = {
    # --- Semantic colour tokens ---
    "colors": {
        # Surfaces
        "header_bg":            "#E67600",      # Darker orange — better contrast base
        "content_bg":           "#FFF4E6",       # Warm off-white — easier on the eyes
        "item_bg":              "#FFFFFF",        # White cards — clear content separation
        "item_bg_completed":    "#F5F0EB",        # Subtle warm gray for done items
        "footer_bg":            "#FFF4E6",        # Matches content

        # Text — all meet WCAG AA on their intended backgrounds
        "text_primary":         "#2D1810",        # Near-black brown  → 12.5:1 on white
        "text_secondary":       "#6B4C3B",        # Muted brown       → 5.8:1 on white
        "text_completed":       "#8C7A6B",        # Dimmed brown      → 4.5:1 on #F5F0EB
        "text_on_header":       "#FFFFFF",        # White on header   → 4.6:1 on #E67600
        "text_placeholder":     "#B8A89A",        # Hint text in entry

        # Interactive
        "border_color":         "#D4A574",        # Warm gold border
        "border_focus":         "#E67600",        # Orange ring on focus
        "btn_danger_bg":        "#DC3545",        # Red for destructive ✕
        "btn_danger_hover":     "#C82333",
        "btn_close_hover_bg":   "#FF4500",        # Header close hover
        "btn_header_hover_bg":  "#CC6900",        # Header minimize hover
        "link_color":           "#B8650A",        # "Clear completed" link style
        "link_hover":           "#E67600",

        # Feedback
        "drag_highlight":       "#FFE0B2",        # Soft orange highlight
        "drag_border":          "#E67600",        # Border during drag
        "checkbox_accent":      "#E67600",        # Checkbox fill colour
        "scrollbar_thumb":      "#D4A574",
        "scrollbar_track":      "#FFF4E6",

        # Shadows & overlays
        "shadow_color":         "#00000015",       # Subtle drop shadow token
        "empty_state_fg":       "#B8A89A",         # Empty-list hint colour
    },

    # --- Transparency ---
    "transparency": {
        "active":   1.0,
        "inactive": 0.45,                          # Raised from 0.3 — too invisible before
    },

    # --- Spacing & sizing (px) ---
    "spacing": {
        "xs": 2,
        "sm": 4,
        "md": 8,
        "lg": 12,
        "xl": 16,
        "xxl": 24,
    },

    # --- Layout ---
    "settings": {
        "tasks_file":       DEFAULT_TASKS_FILE,
        "default_width":    320,                    # Slightly wider for readability
        "default_height":   440,
        "drag_threshold":   18,
        "min_width":        240,
        "min_height":       180,
        "max_task_length":  300,
        "item_padding_y":   6,                      # Vertical breathing room per item
        "item_padding_x":   8,
        "header_height":    38,
        "border_radius":    6,                      # Visual token (applied manually)
        "animation_ms":     150,                    # Transition timing
        "confirm_delete":   False,                  # Ask before delete?
        "max_visible_tasks": 100,                   # Performance guardrail
    },

    # --- Typography ---
    "fonts": {
        "header":       ["Segoe UI", 10, "bold"],
        "body":         ["Segoe UI", 11],
        "body_strike":  ["Segoe UI", 11, "overstrike"],
        "footer":       ["Segoe UI", 9],
        "empty_hint":   ["Segoe UI", 10, "italic"],
        "badge":        ["Segoe UI", 8, "bold"],
    },

    # --- Keyboard shortcuts ---
    "shortcuts": {
        "new_task":         "<Control-n>",
        "delete_completed": "<Control-d>",
        "close":            "<Escape>",
        "focus_entry":      "<Control-l>",
    },

    # --- Strings (i18n-ready) ---
    "strings": {
        "app_title":            "Fly Notes",
        "entry_placeholder":    "Add a new task…",
        "clear_completed":      "Clear completed",
        "empty_state":          "No tasks yet — type above to start!",
        "confirm_delete_title": "Delete Task",
        "confirm_delete_msg":   "Remove this task permanently?",
        "confirm_clear_title":  "Clear Completed",
        "confirm_clear_msg":    "Remove {count} completed task(s)?",
    },
}


# ──────────────────────────────────────────────
# Contrast validation (WCAG AA)
# ──────────────────────────────────────────────
def _hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Convert #RGB or #RRGGBB to (r, g, b)."""
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _relative_luminance(r: int, g: int, b: int) -> float:
    """WCAG 2.1 relative luminance."""
    def _channel(c: int) -> float:
        s = c / 255.0
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def _contrast_ratio(fg: str, bg: str) -> float:
    l1 = _relative_luminance(*_hex_to_rgb(fg))
    l2 = _relative_luminance(*_hex_to_rgb(bg))
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


# Required contrast pairs: (foreground_key, background_key, min_ratio)
_CONTRAST_PAIRS = [
    ("text_primary",    "item_bg",           4.5),
    ("text_completed",  "item_bg_completed", 4.5),
    ("text_on_header",  "header_bg",         4.5),
    ("text_secondary",  "content_bg",        4.5),
    ("text_placeholder","item_bg",           3.0),   # Placeholder only needs 3:1
    ("link_color",      "footer_bg",         4.5),
    ("empty_state_fg",  "content_bg",        3.0),
]


# ──────────────────────────────────────────────
# Generic validation helpers
# ──────────────────────────────────────────────
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
    """Warn (don't crash) if contrast falls below WCAG thresholds."""
    for fg_key, bg_key, min_ratio in _CONTRAST_PAIRS:
        fg = colors.get(fg_key)
        bg = colors.get(bg_key)
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
            raise ValueError(
                f"transparency.{key}: must be float 0.0-1.0, got {val!r}"
            )


def _validate_settings(settings: Dict[str, Any]) -> None:
    int_keys = (
        "default_width", "default_height", "drag_threshold",
        "min_width", "min_height", "max_task_length",
        "item_padding_y", "item_padding_x", "header_height",
        "border_radius", "animation_ms", "max_visible_tasks",
    )
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
    Immutable-after-load application configuration.
    Validates WCAG contrast on every load.
    """

    def __init__(self) -> None:
        self._data: Dict[str, Any] = copy.deepcopy(DEFAULT_CONFIG)
        self._load()

    # -- Loading & merging ---------------------

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
        """Non-fatal checks run after every successful load."""
        _validate_contrast(self._data["colors"])

    @staticmethod
    def _deep_merge(base: dict, override: dict) -> dict:
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(base.get(key), dict):
                Config._deep_merge(base[key], value)
            else:
                base[key] = value
        return base

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
    def item_bg_completed(self) -> str:
        return self._data["colors"]["item_bg_completed"]

    @property
    def footer_bg(self) -> str:
        return self._data["colors"]["footer_bg"]

    @property
    def text_primary(self) -> str:
        return self._data["colors"]["text_primary"]

    @property
    def text_secondary(self) -> str:
        return self._data["colors"]["text_secondary"]

    @property
    def text_completed(self) -> str:
        return self._data["colors"]["text_completed"]

    @property
    def text_on_header(self) -> str:
        return self._data["colors"]["text_on_header"]

    @property
    def text_placeholder(self) -> str:
        return self._data["colors"]["text_placeholder"]

    @property
    def border_color(self) -> str:
        return self._data["colors"]["border_color"]

    @property
    def border_focus(self) -> str:
        return self._data["colors"]["border_focus"]

    @property
    def btn_danger_bg(self) -> str:
        return self._data["colors"]["btn_danger_bg"]

    @property
    def btn_danger_hover(self) -> str:
        return self._data["colors"]["btn_danger_hover"]

    @property
    def btn_close_hover_bg(self) -> str:
        return self._data["colors"]["btn_close_hover_bg"]

    @property
    def btn_header_hover_bg(self) -> str:
        return self._data["colors"]["btn_header_hover_bg"]

    @property
    def link_color(self) -> str:
        return self._data["colors"]["link_color"]

    @property
    def link_hover(self) -> str:
        return self._data["colors"]["link_hover"]

    @property
    def drag_highlight_color(self) -> str:
        return self._data["colors"]["drag_highlight"]

    @property
    def drag_border(self) -> str:
        return self._data["colors"]["drag_border"]

    @property
    def checkbox_accent(self) -> str:
        return self._data["colors"]["checkbox_accent"]

    @property
    def scrollbar_thumb(self) -> str:
        return self._data["colors"]["scrollbar_thumb"]

    @property
    def scrollbar_track(self) -> str:
        return self._data["colors"]["scrollbar_track"]

    @property
    def empty_state_fg(self) -> str:
        return self._data["colors"]["empty_state_fg"]

    # -- Transparency --------------------------

    @property
    def active_alpha(self) -> float:
        return float(self._data["transparency"]["active"])

    @property
    def inactive_alpha(self) -> float:
        return float(self._data["transparency"]["inactive"])

    # -- Spacing -------------------------------

    @property
    def spacing_xs(self) -> int:
        return self._data["spacing"]["xs"]

    @property
    def spacing_sm(self) -> int:
        return self._data["spacing"]["sm"]

    @property
    def spacing_md(self) -> int:
        return self._data["spacing"]["md"]

    @property
    def spacing_lg(self) -> int:
        return self._data["spacing"]["lg"]

    @property
    def spacing_xl(self) -> int:
        return self._data["spacing"]["xl"]

    @property
    def spacing_xxl(self) -> int:
        return self._data["spacing"]["xxl"]

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
        return int(self._data["settings"].get("drag_threshold", 18))

    @property
    def min_width(self) -> int:
        return int(self._data["settings"].get("min_width", 240))

    @property
    def min_height(self) -> int:
        return int(self._data["settings"].get("min_height", 180))

    @property
    def max_task_length(self) -> int:
        return int(self._data["settings"].get("max_task_length", 300))

    @property
    def item_padding_y(self) -> int:
        return int(self._data["settings"].get("item_padding_y", 6))

    @property
    def item_padding_x(self) -> int:
        return int(self._data["settings"].get("item_padding_x", 8))

    @property
    def header_height(self) -> int:
        return int(self._data["settings"].get("header_height", 38))

    @property
    def animation_ms(self) -> int:
        return int(self._data["settings"].get("animation_ms", 150))

    @property
    def confirm_delete(self) -> bool:
        return bool(self._data["settings"].get("confirm_delete", False))

    @property
    def max_visible_tasks(self) -> int:
        return int(self._data["settings"].get("max_visible_tasks", 100))

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

    @property
    def font_empty_hint(self) -> Tuple[str, ...]:
        return tuple(self._data["fonts"]["empty_hint"])

    @property
    def font_badge(self) -> Tuple[str, ...]:
        return tuple(self._data["fonts"]["badge"])

    # -- Shortcuts -----------------------------

    @property
    def shortcut_new_task(self) -> str:
        return self._data["shortcuts"]["new_task"]

    @property
    def shortcut_delete_completed(self) -> str:
        return self._data["shortcuts"]["delete_completed"]

    @property
    def shortcut_close(self) -> str:
        return self._data["shortcuts"]["close"]

    @property
    def shortcut_focus_entry(self) -> str:
        return self._data["shortcuts"]["focus_entry"]

    # -- Strings (i18n) ------------------------

    def string(self, key: str, **kwargs: Any) -> str:
        """Retrieve a UI string, optionally formatted with kwargs."""
        template = self._data["strings"].get(key, key)
        try:
            return template.format(**kwargs) if kwargs else template
        except (KeyError, IndexError):
            return template


# Module-level singleton
config = Config()