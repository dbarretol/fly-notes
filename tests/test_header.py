"""HeaderBar: title, pin, minimize and close buttons."""

import tkinter as tk

from fly_notes.ui.header import HeaderBar


def _header(root, cfg):
    return HeaderBar(root, cfg, on_close=lambda: None, on_minimize=lambda: None)


def test_header_buttons_use_the_muted_icon_colour(root, cfg):
    header = _header(root, cfg)
    try:
        for btn in (header._close_btn, header._min_btn, header._pin_btn):
            assert btn.cget("fg") == cfg.colors.header_icon
        assert header._title_lbl.cget("fg") == cfg.colors.text_on_header
    finally:
        header.destroy()


def test_close_button_turns_white_on_red_while_hovered(root, cfg):
    win = tk.Toplevel(root)
    header = _header(win, cfg)
    header.pack(fill="x")
    win.update()
    try:
        header._close_btn.event_generate("<Enter>")
        assert header._close_btn.cget("bg") == cfg.colors.btn_close_hover_bg
        assert header._close_btn.cget("fg") == "#FFFFFF"
        header._close_btn.event_generate("<Leave>")
        assert header._close_btn.cget("bg") == cfg.colors.header_bg
        assert header._close_btn.cget("fg") == cfg.colors.header_icon
    finally:
        win.destroy()
