"""Task input field with placeholder behaviour."""

from __future__ import annotations

import tkinter as tk
from typing import Any

from ..config import config


class TaskEntryBar(tk.Frame):
    """Input field with placeholder behaviour."""

    def __init__(
        self,
        master: tk.Widget,
        on_submit: callable,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            master,
            bg=config.content_bg,
            highlightthickness=0,
            bd=0,
            **kwargs,
        )
        self._on_submit = on_submit
        self._placeholder = config.string("entry_placeholder")

        self._entry = tk.Entry(
            self,
            bg="#FFFFFF",
            fg=config.text_placeholder,
            insertbackground=config.text_primary,
            font=config.font_body,
            bd=0,
            highlightthickness=2,
            highlightbackground=config.border_color,
            highlightcolor=config.border_focus,
        )
        self._entry.pack(fill="x", ipady=config.spacing_md)
        self._entry.insert(0, self._placeholder)
        self._entry.bind("<FocusIn>", self._focus_in)
        self._entry.bind("<FocusOut>", self._focus_out)
        self._entry.bind("<Return>", lambda _: self._submit())
        self._entry.bind("<Escape>", self._cancel)

    @property
    def entry_widget(self) -> tk.Entry:
        return self._entry

    def focus_entry(self) -> None:
        self._entry.focus_set()
        self._focus_in()

    def get_text(self) -> str:
        """Return stripped text, or empty string if placeholder."""
        raw = self._entry.get().strip()
        if raw == self._placeholder:
            return ""
        return raw

    def clear(self) -> None:
        self._entry.delete(0, tk.END)

    # ── Placeholder ──────────────────────────

    def _focus_in(self, event: tk.Event | None = None) -> None:
        if self._entry.get() == self._placeholder:
            self._entry.delete(0, tk.END)
            self._entry.config(fg=config.text_primary)

    def _focus_out(self, event: tk.Event | None = None) -> None:
        if not self._entry.get().strip():
            self._entry.delete(0, tk.END)
            self._entry.insert(0, self._placeholder)
            self._entry.config(fg=config.text_placeholder)

    def _cancel(self, event: tk.Event | None = None) -> str:
        """Escape: discard the typed text and leave the field.

        Returns ``"break"`` so the key never reaches window-level bindings
        (e.g. a user-configured ``<Escape>`` close shortcut).
        """
        self.clear()
        self.winfo_toplevel().focus_set()
        self._focus_out()
        return "break"

    def _submit(self) -> None:
        text = self.get_text()
        if text:
            self._on_submit(text[: config.max_task_length])
            self.clear()
