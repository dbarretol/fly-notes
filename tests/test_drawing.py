"""Colour helpers in ui/drawing.py (no Tk)."""

import tkinter as tk

from fly_notes.ui.drawing import blend_alpha_hex, draw_rounded_rect, recolor_rounded_rect

# ── Scroll affordance ─────────────────────────


def test_blend_alpha_hex_flattens_alpha_onto_background():
    """shadow_color (#00000015, ~8% black) over a white background should
    land close to white, tinted slightly darker — not pure black and not
    unchanged."""
    result = blend_alpha_hex("#00000015", "#FFFFFF")
    r, g, b = int(result[1:3], 16), int(result[3:5], 16), int(result[5:7], 16)
    assert r == g == b
    assert 220 < r < 255  # slightly darkened, not unchanged, not black


def test_blend_alpha_hex_passes_through_opaque_colors():
    assert blend_alpha_hex("#B35C00", "#FFFFFF") == "#B35C00"


def test_rounded_rect_returns_its_items_and_can_be_recoloured(root):
    canvas = tk.Canvas(root, width=100, height=60)
    try:
        rect = draw_rounded_rect(
            canvas, 0, 0, 100, 60, 8, fill="#ffffff", outline="#000000", width=1
        )
        assert len(canvas.find_all()) == 7
        assert sorted((*rect.corners, *rect.body, rect.border)) == sorted(canvas.find_all())

        recolor_rounded_rect(canvas, rect, fill="#ff0000", outline="#00ff00", width=2)

        assert len(canvas.find_all()) == 7
        for item in (*rect.corners, *rect.body):
            assert canvas.itemcget(item, "fill") == "#ff0000"
        assert canvas.itemcget(rect.corners[0], "outline") == "#00ff00"
        assert canvas.itemcget(rect.body[0], "outline") == "#ff0000"
        assert canvas.itemcget(rect.border, "outline") == "#00ff00"
        assert canvas.itemcget(rect.border, "fill") == ""
        assert float(canvas.itemcget(rect.border, "width")) == 2
    finally:
        canvas.destroy()
