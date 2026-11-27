"""CustomCheckbox: the canvas-drawn checkbox."""

from fly_notes.ui.checkbox import CustomCheckbox


def test_checkbox_box_uses_checkbox_bg(root):
    box = CustomCheckbox(root, bg="#FFFFFF", box_color="#123456")
    fills = {box.itemcget(i, "fill") for i in box.find_all()}
    assert "#123456" in fills
    box.destroy()
