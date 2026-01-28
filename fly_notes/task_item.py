import tkinter as tk
from tkinter import font as tkfont
from .config import config

class TaskItem(tk.Frame):
    def __init__(self, master, text, completed=False, on_status_change=None, on_delete=None, on_drag_start=None, on_drag_do=None, on_drag_stop=None, **kwargs):
        super().__init__(master, bg=config.item_bg, **kwargs)
        self.text = text
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
            font=self.label_font, anchor="w"
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

    def _handle_status_change(self):
        self._update_style()
        if self.on_status_change:
            self.on_status_change(self)

    def _handle_delete(self):
        if self.on_delete:
            self.on_delete(self)

    def _start_drag(self, event):
        if self.on_drag_start:
            self.on_drag_start(self, event)

    def _do_drag(self, event):
        if self.on_drag_do:
            self.on_drag_do(self, event)

    def _stop_drag(self, event):
        if self.on_drag_stop:
            self.on_drag_stop(self, event)

    def _update_style(self):
        if self.completed_var.get():
            self.label.config(font=self.strike_font, fg=config.strike_color)
        else:
            self.label.config(font=self.label_font, fg=config.text_color)

    def set_bg(self, color):
        """Recursively update background of self and all sub-widgets."""
        self.config(bg=color)
        self.label.config(bg=color)
        self.check.config(bg=color, activebackground=color)
        self.delete_btn.config(bg=color, activebackground=color)
