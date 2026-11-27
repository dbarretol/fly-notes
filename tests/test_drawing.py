"""Colour helpers in ui/drawing.py (no Tk)."""

from fly_notes.ui.drawing import blend_alpha_hex

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
