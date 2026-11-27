"""Canvas drawing and colour helpers shared by the widgets."""

from __future__ import annotations

import tkinter as tk
from typing import NamedTuple


class RoundedRect(NamedTuple):
    """Canvas item ids of one rounded rectangle, grouped by the colours they take."""

    corners: tuple[int, int, int, int]  # arcs: fill + outline
    body: tuple[int, int]  # centre rectangles: fill only (outline = fill)
    border: int  # outline only


def draw_rounded_rect(
    canvas: tk.Canvas,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    r: float,
    fill: str,
    outline: str,
    width: float,
    tags: tuple[str, ...] = (),
) -> RoundedRect:
    """Draw a rounded rectangle on *canvas* using arcs + fill rects.

    Shared by ``CustomCheckbox`` and ``TaskItem``'s card background so the
    same corner-drawing logic isn't duplicated per widget. Returns the item
    ids, so the colours can be changed later with ``recolor_rounded_rect``.
    """
    d = r * 2
    a0 = canvas.create_arc(
        x1,
        y1,
        x1 + d,
        y1 + d,
        start=90,
        extent=90,
        fill=fill,
        outline=outline,
        width=width,
        style="pieslice",
        tags=tags,
    )
    a1 = canvas.create_arc(
        x2 - d,
        y1,
        x2,
        y1 + d,
        start=0,
        extent=90,
        fill=fill,
        outline=outline,
        width=width,
        style="pieslice",
        tags=tags,
    )
    a2 = canvas.create_arc(
        x1,
        y2 - d,
        x1 + d,
        y2,
        start=180,
        extent=90,
        fill=fill,
        outline=outline,
        width=width,
        style="pieslice",
        tags=tags,
    )
    a3 = canvas.create_arc(
        x2 - d,
        y2 - d,
        x2,
        y2,
        start=270,
        extent=90,
        fill=fill,
        outline=outline,
        width=width,
        style="pieslice",
        tags=tags,
    )
    # Fill center regions
    b0 = canvas.create_rectangle(x1 + r, y1, x2 - r, y2, fill=fill, outline=fill, tags=tags)
    b1 = canvas.create_rectangle(x1, y1 + r, x2, y2 - r, fill=fill, outline=fill, tags=tags)
    # Clean border on top
    border = canvas.create_rectangle(
        x1, y1, x2, y2, fill="", outline=outline, width=width, tags=tags
    )
    return RoundedRect((a0, a1, a2, a3), (b0, b1), border)


def recolor_rounded_rect(
    canvas: tk.Canvas, rect: RoundedRect, fill: str, outline: str, width: float
) -> None:
    """Change the colours of a rounded rectangle in place, without recreating it."""
    for item in rect.corners:
        canvas.itemconfigure(item, fill=fill, outline=outline, width=width)
    for item in rect.body:
        canvas.itemconfigure(item, fill=fill, outline=fill)
    canvas.itemconfigure(rect.border, outline=outline, width=width)


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
