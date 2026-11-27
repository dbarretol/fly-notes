"""Footer: status badge, "Clear completed" link and the undo notice."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from typing import Any

from ..config import config


class FooterBar(tk.Frame):
    """Status badge, 'clear completed' link and the temporary undo notice."""

    def __init__(
        self,
        master: tk.Widget,
        on_clear: Callable[[], None],
        on_undo: Callable[[], None] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            master,
            bg=config.footer_bg,
            height=config.footer_height,
            highlightthickness=0,
            bd=0,
            **kwargs,
        )
        self.pack_propagate(False)
        self._on_clear = on_clear
        self._on_undo = on_undo
        self._undo_after_id: str | None = None

        self._badge_label = tk.Label(
            self,
            text="",
            fg=config.text_secondary,
            bg=config.footer_bg,
            font=config.font_badge,
        )
        self._badge_label.pack(side="left", padx=config.spacing_lg)

        self._clear_btn = tk.Label(
            self,
            text=config.string("clear_completed_zero"),
            fg=config.link_color,
            bg=config.footer_bg,
            font=config.font_footer,
            cursor="hand2",
        )
        self._clear_btn.bind("<Button-1>", lambda _: self._on_clear())
        self._clear_btn.bind("<Enter>", self._on_hover)
        self._clear_btn.bind("<Leave>", self._on_leave)

        # Undo notice: replaces the badge for a few seconds after a deletion.
        self._undo_frame = tk.Frame(self, bg=config.footer_bg, bd=0, highlightthickness=0)
        self._undo_msg = tk.Label(
            self._undo_frame,
            text="",
            fg=config.text_secondary,
            bg=config.footer_bg,
            font=config.font_badge,
        )
        self._undo_msg.pack(side="left")
        self._undo_btn = tk.Label(
            self._undo_frame,
            text=config.string("undo_action"),
            fg=config.link_color,
            bg=config.footer_bg,
            font=(*config.font_footer[:2], "bold"),
            cursor="hand2",
        )
        self._undo_btn.pack(side="left", padx=(config.spacing_sm, 0))
        self._undo_btn.bind("<Button-1>", lambda _: self._undo_clicked())
        self._undo_visible = False

    @property
    def undo_visible(self) -> bool:
        return self._undo_visible

    def show_undo(self, message: str) -> None:
        """Show "<message> · Undo" in place of the badge, for ``undo_timeout_ms``."""
        self._cancel_undo_timer()
        self._undo_msg.config(text=message)
        if not self._undo_visible:
            self._badge_label.pack_forget()
            self._undo_frame.pack(side="left", padx=config.spacing_lg)
            self._undo_visible = True
        self._undo_after_id = self.after(config.undo_timeout_ms, self.hide_undo)

    def hide_undo(self) -> None:
        self._cancel_undo_timer()
        if self._undo_visible:
            self._undo_frame.pack_forget()
            self._badge_label.pack(side="left", padx=config.spacing_lg)
            self._undo_visible = False

    def _cancel_undo_timer(self) -> None:
        if self._undo_after_id is not None:
            self.after_cancel(self._undo_after_id)
            self._undo_after_id = None

    def _undo_clicked(self) -> None:
        if self._on_undo:
            self._on_undo()

    def update_counts(self, total: int, done: int) -> None:
        if total == 0:
            self._badge_label.config(text="")
        else:
            self._badge_label.config(text=config.string("badge_format", done=done, total=total))
        if done > 0:
            self._clear_btn.config(text=config.string("clear_completed", count=done))
            self._clear_btn.pack(side="right", padx=config.spacing_lg)
        else:
            self._clear_btn.pack_forget()

    def _on_hover(self, event: tk.Event | None = None) -> None:
        self._clear_btn.config(
            fg=config.link_hover,
            font=(*config.font_footer[:2], "underline"),
        )

    def _on_leave(self, event: tk.Event | None = None) -> None:
        self._clear_btn.config(fg=config.link_color, font=config.font_footer)
