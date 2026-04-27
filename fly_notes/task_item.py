import tkinter as tk
from tkinter import font as tkfont
from typing import Optional, Callable
from .config import config

class TaskItem(tk.Frame):
    """
    A UI component representing a single task item in the list.
    Handles its own styling and delegates events via callbacks.
    """
    
    def __init__(self, 
                 master: tk.Widget, 
                 text: str, 
                 completed: bool = False, 
                 on_status_change: Optional[Callable[['TaskItem'], None]] = None, 
                 on_delete: Optional[Callable[['TaskItem'], None]] = None, 
                 on_drag_start: Optional[Callable[['TaskItem', tk.Event], None]] = None, 
                 on_drag_do: Optional[Callable[['TaskItem', tk.Event], None]] = None, 
                 on_drag_stop: Optional[Callable[['TaskItem', tk.Event], None]] = None, 
                 **kwargs):
        """
        Initializes the TaskItem with specified text and callbacks.
        
        Args:
            master: Parent container.
            text: Task text content.
            completed: Initial completion state.
            on_status_change: Called when the checkbox is toggled.
            on_delete: Called when the delete button is clicked.
            on_drag_start: Called when a drag operation begins.
            on_drag_do: Called during active dragging.
            on_drag_stop: Called when the drag operation ends.
        """
        super().__init__(master, bg=config.item_bg, **kwargs)
        self.text: str = text
        self.on_status_change = on_status_change
        self.on_delete = on_delete
        self.on_drag_start = on_drag_start
        self.on_drag_do = on_drag_do
        self.on_drag_stop = on_drag_stop
        
        self.completed_var = tk.BooleanVar(value=completed)
        
        self.check = tk.Checkbutton(
            self, variable=self.completed_var, command=self._handle_status_change,
            bg=config.item_bg, activebackground=config.item_bg, selectcolor="white",
            fg=config.text_color
        )
        self.check.pack(side="left", padx=5)
        
        self.label_font = tkfont.Font(family="Segoe UI", size=11)
        self.strike_font = tkfont.Font(family="Segoe UI", size=11, overstrike=1)
        
        self.label = tk.Label(
            self, text=text, fg=config.text_color, bg=config.item_bg,
            font=config.font_body, anchor="w"
        )
        self.label.pack(side="left", fill="x", expand=True)
        
        self.delete_btn = tk.Button(
            self, text="✕", command=self._handle_delete,
            bg=config.item_bg, fg="#D2691E", bd=0, activebackground=config.content_bg,
            activeforeground="#FF4500", cursor="hand2"
        )
        self.delete_btn.pack(side="right", padx=5)

        # Reordering bindings
        for widget in (self, self.label):
            widget.bind("<Button-1>", self._start_drag)
            widget.bind("<B1-Motion>", self._do_drag)
            widget.bind("<ButtonRelease-1>", self._stop_drag)

        self._update_style()

    def _handle_status_change(self) -> None:
        """Internal handler for status changes, updates UI and notifies parent."""
        self._update_style()
        if self.on_status_change:
            self.on_status_change(self)

    def _handle_delete(self) -> None:
        """Internal handler for deletion button."""
        if self.on_delete:
            self.on_delete(self)

    def _start_drag(self, event: tk.Event) -> None:
        """Internal handler for reorder start."""
        if self.on_drag_start:
            self.on_drag_start(self, event)

    def _do_drag(self, event: tk.Event) -> None:
        """Internal handler for reorder motion."""
        if self.on_drag_do:
            self.on_drag_do(self, event)

    def _stop_drag(self, event: tk.Event) -> None:
        """Internal handler for reorder release."""
        if self.on_drag_stop:
            self.on_drag_stop(self, event)

    def _update_style(self) -> None:
        """Updates font and color based on completion state."""
        if self.completed_var.get():
            self.label.config(font=config.font_body_strike, fg=config.strike_color)
        else:
            self.label.config(font=config.font_body, fg=config.text_color)

    def set_bg(self, color: str) -> None:
        """Recursively update background of self and all sub-widgets."""
        self.config(bg=color)
        self.label.config(bg=color)
        self.check.config(bg=color, activebackground=color)
        self.delete_btn.config(bg=color, activebackground=color)
