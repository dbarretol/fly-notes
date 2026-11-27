"""TaskItem: one task row (card, wrapping, inline edit, focus ring)."""

import tkinter as tk
import types
from typing import cast

from fly_notes.ui import task_item as task_item_module
from fly_notes.ui.task_item import TaskItem
from fly_notes.ui.task_list import TaskListView

# ── State, hover and drag callbacks ───────────


def test_task_item_initial_state(root, cfg):
    item = TaskItem(root, cfg, task_id="123", text="Test Task", completed=False)
    assert item.task_id == "123"
    assert item.task_text == "Test Task"
    assert item.completed_var.get() is False
    # Check initial label style
    assert item._label.cget("text") == "Test Task"
    assert item._label.cget("fg") == cfg.colors.text_primary
    item.destroy()


def test_task_item_toggle_style(root, cfg):
    item = TaskItem(root, cfg, task_id="123", text="Test Task", completed=False)

    # Simulate status change
    item._check.checked = True
    item._handle_status_change()

    assert item.completed_var.get() is True
    assert item._label.cget("fg") == cfg.colors.text_completed

    item.destroy()


def test_task_item_drag_callbacks(root, cfg):
    start_called = False
    stop_called = False

    def on_start(item, event):
        nonlocal start_called
        start_called = True

    def on_stop(item, event):
        nonlocal stop_called
        stop_called = True

    item = TaskItem(
        root, cfg, task_id="123", text="Drag Task", on_drag_start=on_start, on_drag_stop=on_stop
    )

    event = cast(tk.Event, types.SimpleNamespace(x_root=0, y_root=0))
    item._start_drag(event)
    assert start_called is True

    item._stop_drag(event)
    assert stop_called is True
    item.destroy()


def test_task_item_hover_logic(root, cfg):
    item = TaskItem(root, cfg, task_id="123", text="Hover Task")

    # Test enter
    item._on_enter()
    assert item._is_hovered is True
    assert item._delete_visible is True

    # Test leave (pointer inside, so should remain hovered)
    # Mocking pointer_still_inside because it's hard to test GUI coordinates
    item._pointer_still_inside = lambda: True
    item._on_leave()
    assert item._is_hovered is True

    # Test actual leave
    item._pointer_still_inside = lambda: False
    item._on_leave()
    assert item._is_hovered is False
    assert item._delete_visible is False

    item.destroy()


# ── Rounded card + shadow ─────────────────────


def test_task_item_card_canvas_gets_real_size_and_draws_rounded_shapes(root, cfg):
    """Regression for 'border_radius/shadow_color declared but never
    applied': the card canvas must end up with a real pixel size and both
    the shadow + main rounded rect drawn (14 tagged shapes: 2 x [4 arcs +
    2 fill rects + 1 border rect])."""
    win = tk.Toplevel(root)
    try:
        win.geometry("320x100+0+0")
        item = TaskItem(win, cfg, task_id="1", text="Sample task")
        item.pack(fill="x")
        win.update_idletasks()

        assert item._card_canvas.winfo_width() > 1
        assert item._card_canvas.winfo_height() > 1
        assert len(item._card_canvas.find_withtag("card")) == 14

        item.destroy()
    finally:
        win.destroy()


def test_task_item_hover_and_status_change_update_card_fill(root, cfg):
    win = tk.Toplevel(root)
    try:
        win.geometry("320x100+0+0")
        item = TaskItem(win, cfg, task_id="1", text="Sample task")
        item.pack(fill="x")
        win.update_idletasks()

        assert item._card_fill == cfg.colors.item_bg

        item._on_enter()
        assert item._card_fill == cfg.colors.drag_highlight

        item._on_leave()
        assert item._card_fill == cfg.colors.item_bg

        item._check.checked = True
        item._handle_status_change()
        assert item._card_fill == cfg.colors.item_bg_completed

        item.destroy()
    finally:
        win.destroy()


def test_task_item_drag_active_toggles_outline_without_error(root, cfg):
    win = tk.Toplevel(root)
    try:
        win.geometry("320x100+0+0")
        item = TaskItem(win, cfg, task_id="1", text="Sample task")
        item.pack(fill="x")
        win.update_idletasks()

        item.set_drag_active(True)
        assert item._drag_active is True
        item.set_drag_active(False)
        assert item._drag_active is False

        item.destroy()
    finally:
        win.destroy()


def test_task_item_card_resizes_with_row_width(root, cfg):
    """The card canvas must track the row's actual allotted width (not
    just its own natural label-text width) -- otherwise the rounded card
    wouldn't stretch to fill the list the way the old square row did."""
    win = tk.Toplevel(root)
    try:
        win.geometry("320x100+0+0")
        canvas = tk.Canvas(win, highlightthickness=0, bd=0)
        canvas.pack(fill="both", expand=True)
        inner = tk.Frame(canvas)
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw", width=320)

        item = TaskItem(inner, cfg, task_id="1", text="Sample task")
        item.pack(fill="x")
        win.update()

        narrow_width = item._card_canvas.winfo_width()

        canvas.itemconfigure(win_id, width=500)
        win.update()

        assert item._card_canvas.winfo_width() > narrow_width

        item.destroy()
    finally:
        win.destroy()


# ── Long task text wraps (#8) ─────────────────


LONG_TEXT = " ".join(["wrapping"] * 25)  # ~225 characters


def _item_in_list_of_width(root, cfg, text, width):
    """A TaskItem inside a canvas-window inner frame, like TaskListView's rows."""
    win = tk.Toplevel(root)
    win.geometry(f"{width}x400+0+0")
    canvas = tk.Canvas(win, highlightthickness=0, bd=0)
    canvas.pack(fill="both", expand=True)
    inner = tk.Frame(canvas)
    win_id = canvas.create_window((0, 0), window=inner, anchor="nw", width=width)
    item = TaskItem(inner, cfg, task_id="1", text=text)
    item.pack(fill="x")
    win.update()
    return win, canvas, win_id, item


def test_long_task_text_wraps_to_fit_the_default_width(root, cfg):
    win, _, _, item = _item_in_list_of_width(root, cfg, LONG_TEXT, cfg.settings.default_width)
    try:
        short_win, _, _, short_item = _item_in_list_of_width(
            root, cfg, "Short", cfg.settings.default_width
        )
        try:
            short_height = short_item._card_canvas.winfo_height()
        finally:
            short_win.destroy()

        wrap = int(item._label.cget("wraplength"))
        assert 0 < wrap < cfg.settings.default_width
        # The whole text fits in the label's width: nothing is clipped at the edge.
        assert item._label.winfo_reqwidth() <= item._label.winfo_width() + 1
        assert item._card_canvas.winfo_height() > 2 * short_height - 20
        assert len(item._card_canvas.find_withtag("card")) == 14
    finally:
        win.destroy()


def test_long_task_text_rewraps_when_the_list_is_resized(root, cfg):
    win, canvas, win_id, item = _item_in_list_of_width(root, cfg, LONG_TEXT, 500)
    try:
        wide_wrap = int(item._label.cget("wraplength"))
        wide_height = item._card_canvas.winfo_height()

        win.geometry("250x400+0+0")
        canvas.itemconfigure(win_id, width=250)
        win.update()

        assert int(item._label.cget("wraplength")) < wide_wrap
        assert item._card_canvas.winfo_height() > wide_height
    finally:
        win.destroy()


def test_revealing_the_delete_button_does_not_rewrap_the_text(root, cfg):
    win, _, _, item = _item_in_list_of_width(root, cfg, LONG_TEXT, cfg.settings.default_width)
    try:
        wrap = item._label.cget("wraplength")
        height = item._card_canvas.winfo_height()

        item._show_delete_btn()
        win.update()

        assert item._label.cget("wraplength") == wrap
        assert item._card_canvas.winfo_height() == height
    finally:
        win.destroy()


def test_scroll_region_and_increment_follow_wrapped_rows(root, cfg):
    win = tk.Toplevel(root)
    try:
        win.geometry("320x150+0+0")
        task_list = TaskListView(win, cfg)
        task_list.pack(fill="both", expand=True)
        texts = [LONG_TEXT] + [f"Task {i}" for i in range(5)]
        widgets = []
        for i, text in enumerate(texts):
            w = TaskItem(task_list.inner_frame, cfg, task_id=str(i), text=text)
            task_list.add_widget(w)
            widgets.append(w)
        task_list.update_canvas_width(320)
        task_list.repack()
        win.update()

        long_row, short_row = widgets[0], widgets[1]
        assert long_row.winfo_height() > short_row.winfo_height()

        # Step = shortest row, so a wheel notch never skips a single-line task.
        expected = short_row.winfo_reqheight() + 2 * cfg.spacing.xs
        assert int(task_list._canvas["yscrollincrement"]) == expected

        # The scroll region covers the wrapped (taller) row too.
        scroll_bottom = int(str(task_list._canvas.cget("scrollregion")).split()[3])
        assert scroll_bottom >= task_list.inner_frame.winfo_height()
    finally:
        win.destroy()


# ── Inline edit (#10) ─────────────────────────


def _editable_item(root, cfg, text="Original", on_text_change=None):
    win = tk.Toplevel(root)
    win.geometry("320x120+0+0")
    item = TaskItem(win, cfg, task_id="1", text=text, on_text_change=on_text_change)
    item.pack(fill="x")
    win.update()
    return win, item


def _editor(item):
    """The inline editor of an item that is being edited."""
    assert item._editor is not None
    return item._editor


def test_begin_edit_swaps_label_for_entry_with_the_task_text(root, cfg):
    win, item = _editable_item(root, cfg)
    try:
        item.begin_edit()
        assert item.is_editing
        assert _editor(item).get() == "Original"
        assert not item._label.winfo_manager()
        item.begin_edit()  # second call is a no-op
        assert _editor(item).get() == "Original"
    finally:
        win.destroy()


def test_enter_saves_the_edit_through_the_callback(root, cfg):
    calls = []

    def on_change(item, text):
        calls.append(text)
        return text.strip()

    win, item = _editable_item(root, cfg, on_text_change=on_change)
    try:
        item.begin_edit()
        _editor(item).delete(0, tk.END)
        _editor(item).insert(0, " Fixed ")
        assert item._commit_edit_event() == "break"

        assert calls == [" Fixed "]
        assert not item.is_editing
        assert item._label.cget("text") == "Fixed"
        assert item.task_text == "Fixed"
        assert item._label.winfo_manager() == "pack"
    finally:
        win.destroy()


def test_escape_cancels_the_edit_without_calling_back(root, cfg):
    calls = []
    win, item = _editable_item(root, cfg, on_text_change=lambda i, t: calls.append(t) or t)
    try:
        item.begin_edit()
        _editor(item).delete(0, tk.END)
        _editor(item).insert(0, "changed")
        assert item._cancel_edit_event() == "break"

        assert calls == []
        assert item._label.cget("text") == "Original"
        assert not item.is_editing
    finally:
        win.destroy()


def test_rejected_edit_keeps_the_original_text(root, cfg):
    """The app returns None for empty/unchanged text: the label must not change."""
    win, item = _editable_item(root, cfg, on_text_change=lambda i, t: None)
    try:
        item.begin_edit()
        _editor(item).delete(0, tk.END)
        item.commit_edit()

        assert item._label.cget("text") == "Original"
        assert not item.is_editing
    finally:
        win.destroy()


def test_edited_text_rewraps_the_card(root, cfg):
    win, item = _editable_item(root, cfg, on_text_change=lambda i, t: t)
    try:
        short_height = item._card_canvas.winfo_height()
        item.begin_edit()
        _editor(item).insert(tk.END, " " + LONG_TEXT)
        item.commit_edit()
        win.update()

        assert item._card_canvas.winfo_height() > short_height
    finally:
        win.destroy()


def test_double_click_on_label_starts_editing(root, cfg):
    win, item = _editable_item(root, cfg)
    try:
        win.deiconify()
        win.update()
        # Tk can't synthesize "<Double-...>" directly: two quick clicks make one.
        for _ in range(2):
            item._label.event_generate("<ButtonPress-1>", x=5, y=5)
            item._label.event_generate("<ButtonRelease-1>", x=5, y=5)
        win.update()
        assert item.is_editing
    finally:
        win.destroy()


def test_contains_does_not_match_a_sibling_with_a_longer_name(root, cfg):
    win = tk.Toplevel(root)
    try:
        first = TaskItem(win, cfg, task_id="1", text="1", name="row1")
        tenth = TaskItem(win, cfg, task_id="10", text="10", name="row10")
        assert str(tenth).startswith(str(first))  # the trap: ".row1" is a prefix of ".row10"
        assert first.contains(first._label)
        assert not first.contains(tenth._label)
        assert not first.contains(None)
    finally:
        win.destroy()


# ── Keyboard navigation (#13) ─────────────────


def test_focused_row_draws_a_focus_ring(root, cfg):
    win = tk.Toplevel(root)
    try:
        win.geometry("320x100+0+0")
        item = TaskItem(win, cfg, task_id="1", text="Sample task")
        item.pack(fill="x")
        win.update_idletasks()

        def outlines():
            return {
                item._card_canvas.itemcget(i, "outline")
                for i in item._card_canvas.find_withtag("card")
            }

        assert cfg.colors.border_focus not in outlines()
        item._on_focus_in()
        assert item.has_focus
        assert cfg.colors.border_focus in outlines()
        item._on_focus_out()
        assert cfg.colors.border_focus not in outlines()
    finally:
        win.destroy()


# ── Config values that used to be ignored or crash (#18) ───


def test_pressed_delete_button_uses_btn_danger_hover(root, cfg):
    item = TaskItem(root, cfg, task_id="1", text="Task")
    assert item._delete_btn.cget("activebackground") == cfg.colors.btn_danger_hover
    item.destroy()


# ── Cheap card redraws (#27) ──────────────────


def _drawn_item(root, cfg):
    win = tk.Toplevel(root)
    win.geometry("320x100+0+0")
    item = TaskItem(win, cfg, task_id="1", text="Sample task")
    item.pack(fill="x")
    win.update_idletasks()
    assert item._card is not None, "the card should be drawn once the row has a size"
    return win, item


def test_hover_and_focus_recolour_the_card_without_recreating_it(root, cfg):
    win, item = _drawn_item(root, cfg)
    try:
        canvas = item._card_canvas
        items = canvas.find_withtag("card")
        card = item._card
        assert card is not None

        item._on_enter()
        item.set_drag_active(True)
        item.set_drag_active(False)
        item._on_leave()
        item._on_enter()

        assert canvas.find_withtag("card") == items
        assert canvas.itemcget(card.body[0], "fill") == cfg.colors.drag_highlight
        assert canvas.itemcget(card.corners[0], "fill") == cfg.colors.drag_highlight
    finally:
        win.destroy()


def test_focus_ring_is_recoloured_in_place(root, cfg):
    win, item = _drawn_item(root, cfg)
    try:
        card = item._card
        assert card is not None
        item._has_focus = True
        item._redraw_card()
        assert item._card is card
        assert item._card_canvas.itemcget(card.border, "outline") == cfg.colors.border_focus
        assert float(item._card_canvas.itemcget(card.border, "width")) == 2
    finally:
        win.destroy()


def test_a_new_size_redraws_the_card(root, cfg):
    win, item = _drawn_item(root, cfg)
    try:
        before = item._card
        w, h = item._card_size
        item._redraw_card(w + 40, h)
        after = item._card
        assert after is not None and after is not before
        assert item._card_size == (w + 40, h)
        x1, _, x2, _ = item._card_canvas.coords(after.border)
        assert x2 - x1 == w + 40 - item._shadow_px
    finally:
        win.destroy()


def test_shadow_colour_is_flattened_once(root, cfg, monkeypatch):
    win, item = _drawn_item(root, cfg)
    try:
        calls = []
        monkeypatch.setattr(task_item_module, "blend_alpha_hex", lambda *a: calls.append(a))
        w, h = item._card_size
        item._redraw_card(w + 10, h)
        item._on_enter()
        assert calls == []
    finally:
        win.destroy()
