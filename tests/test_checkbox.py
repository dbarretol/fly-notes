"""CustomCheckbox: the canvas-drawn checkbox."""

from fly_notes.ui.checkbox import CustomCheckbox


def test_checkbox_box_uses_checkbox_bg(root):
    box = CustomCheckbox(root, bg="#FFFFFF", box_color="#123456")
    fills = {box.itemcget(i, "fill") for i in box.find_all()}
    assert "#123456" in fills
    box.destroy()


def test_round_checkbox_draws_a_circle(root):
    box = CustomCheckbox(root, round_box=True)
    kinds = {box.type(i) for i in box.find_all()}
    assert "oval" in kinds
    assert "arc" not in kinds
    box.destroy()


def test_square_checkbox_draws_rounded_corners(root):
    box = CustomCheckbox(root, round_box=False)
    kinds = {box.type(i) for i in box.find_all()}
    assert "arc" in kinds
    assert "oval" not in kinds
    box.destroy()
