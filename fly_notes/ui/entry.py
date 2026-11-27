"""Task input field with placeholder behaviour."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from typing import Any

from ..config import AppConfig


class TaskEntryBar(tk.Frame):
    """Input field with placeholder behaviour."""

    def __init__(
        self,
        master: tk.Misc,
        cfg: AppConfig,
        on_submit: Callable[[str], None],
        **kwargs: Any,
    ) -> None:
        self._cfg = cfg
        super().__init__(
            master,
            bg=self._cfg.colors.content_bg,
            highlightthickness=0,
            bd=0,
            **kwargs,
        )
        self._on_submit = on_submit
        self._placeholder = self._cfg.string("entry_placeholder")

        self._entry = tk.Entry(
            self,
            bg=self._cfg.colors.entry_bg,
            fg=self._cfg.colors.text_placeholder,
            insertbackground=self._cfg.colors.text_primary,
            font=self._cfg.fonts.body,
            bd=0,
            highlightthickness=2,
            highlightbackground=self._cfg.colors.entry_border,
            highlightcolor=self._cfg.colors.border_focus,
        )
        self._entry.pack(fill="x", ipady=self._cfg.spacing.md)
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
            self._entry.config(fg=self._cfg.colors.text_primary)

    def _focus_out(self, event: tk.Event | None = None) -> None:
        if not self._entry.get().strip():
            self._entry.delete(0, tk.END)
            self._entry.insert(0, self._placeholder)
            self._entry.config(fg=self._cfg.colors.text_placeholder)

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
            self._on_submit(text[: self._cfg.settings.max_task_length])
            self.clear()
