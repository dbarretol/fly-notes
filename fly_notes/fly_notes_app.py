import tkinter as tk
from tkinter import messagebox
from typing import List, Optional, Any, Dict
from .config import config
from .task_manager import TaskManager
from .task_item import TaskItem
from .window_controller import WindowController

class FlyNotesApp:
    """
    Main application class for Fly Notes. 
    Orchestrates UI components and data management.
    """
    
    def __init__(self, root: tk.Tk):
        """Initializes the application window and components."""
        self.root = root
        self.root.title("Fly Notes")
        self.root.geometry(f"{config.default_width}x{config.default_height}+100+100")
        self.root.overrideredirect(True) # Borderless
        self.root.attributes("-topmost", True) # Floating
        self.root.config(bg=config.content_bg)
        self.root.attributes("-alpha", config.active_alpha)
        
        # Managers
        self.manager = TaskManager(
            tasks_file=config.tasks_file,
            error_callback=self.handle_error
        )
        self.window_ctrl = WindowController(self.root, on_resize_callback=self.on_window_resize)
        
        # State
        self.dragging_item: Optional[TaskItem] = None
        self.drag_start_y: int = 0
        self.tasks_ui: List[TaskItem] = []
        
        self.setup_ui()
        self.setup_bindings()
        self.window_ctrl.setup_resize_handles(config.content_bg)
        self.load_initial_tasks()

    def on_window_resize(self) -> None:
        """Handles canvas adjustment when the window resize is triggered."""
        new_w = self.root.winfo_width()
        self.list_canvas.itemconfigure(self.canvas_window_id, width=new_w)
        self.update_canvas()

    def setup_ui(self) -> None:
        """Builds the main UI layout fragments."""
        # Header
        self.header = tk.Frame(self.root, bg=config.header_bg, height=35)
        self.header.pack(fill="x", side="top")
        
        self.title_label = tk.Label(
            self.header, text="Fly Notes", fg="white", bg=config.header_bg,
            font=config.font_header
        )
        self.title_label.pack(side="left", padx=10, pady=5)
        
        self.close_btn = tk.Button(
            self.header, text="✕", command=self.root.destroy,
            bg=config.header_bg, fg="white", bd=0, activebackground="#FF4500",
            padx=10, font=config.font_header
        )
        self.close_btn.pack(side="right", fill="y")

        self.min_btn = tk.Button(
            self.header, text="—", command=self.window_ctrl.minimize_window,
            bg=config.header_bg, fg="white", bd=0, activebackground="#FF4500",
            padx=10, font=config.font_header
        )
        self.min_btn.pack(side="right", fill="y")

        # Entry area
        self.entry_frame = tk.Frame(self.root, bg=config.content_bg, pady=10)
        self.entry_frame.pack(fill="x")
        
        self.task_entry = tk.Entry(
            self.entry_frame, bg="white", fg=config.text_color, insertbackground=config.text_color,
            font=config.font_body, bd=0, highlightthickness=1,
            highlightbackground=config.border_color
        )
        self.task_entry.pack(fill="x", padx=10, ipady=5)
        self.task_entry.bind("<Return>", lambda e: self.add_new_task())

        # Task List Container
        self.list_canvas = tk.Canvas(self.root, bg=config.content_bg, highlightthickness=0)
        self.scroll_frame = tk.Frame(self.list_canvas, bg=config.content_bg)
        
        self.list_canvas.pack(fill="both", expand=True)
        self.canvas_window_id = self.list_canvas.create_window(
            (0,0), window=self.scroll_frame, anchor="nw", width=config.default_width
        )
        
        # Footer
        self.footer = tk.Frame(self.root, bg=config.content_bg, pady=5)
        self.footer.pack(fill="x", side="bottom")
        
        self.clear_btn = tk.Button(
            self.footer, text="Clear Completed", command=self.clear_completed,
            bg=config.content_bg, fg=config.strike_color, bd=0, font=config.font_footer,
            activebackground=config.content_bg, activeforeground=config.text_color, cursor="hand2"
        )
        self.clear_btn.pack(side="right", padx=10)

    def setup_bindings(self) -> None:
        """Sets up window-level event bindings."""
        self.window_ctrl.bind_drag(self.header)
        self.window_ctrl.bind_drag(self.title_label)
        
        self.root.bind("<FocusIn>", lambda e: self.root.attributes("-alpha", config.active_alpha))
        self.root.bind("<FocusOut>", lambda e: self.root.attributes("-alpha", config.inactive_alpha))
        self.root.bind("<Map>", lambda e: self.root.attributes("-topmost", True))

    def add_new_task(self) -> None:
        """Adds a new task using granular UI update."""
        text = self.task_entry.get().strip()
        if text:
            task = self.manager.add_task(text)
            self.task_entry.delete(0, tk.END)
            self._create_task_widget(task)
            self.update_canvas()

    def _create_task_widget(self, task: Dict[str, Any]) -> TaskItem:
        """Helper to instantiate and pack a single task widget."""
        ui_item = TaskItem(
            self.scroll_frame,
            text=task["text"],
            completed=task["completed"],
            on_status_change=self.toggle_task,
            on_delete=self.delete_task,
            on_drag_start=self.start_reorder,
            on_drag_do=self.do_reorder,
            on_drag_stop=self.stop_reorder
        )
        ui_item.pack(fill="x", pady=2, padx=5)
        self.tasks_ui.append(ui_item)
        return ui_item

    def delete_task(self, ui_item: TaskItem) -> None:
        """Removes a specific task widget and updates data layer."""
        try:
            idx = self.tasks_ui.index(ui_item)
            self.manager.delete_task(idx)
            self.tasks_ui.pop(idx)
            ui_item.destroy()
            self.update_canvas()
        except ValueError:
            pass

    def toggle_task(self, ui_item: TaskItem) -> None:
        """Toggles the task status in the data layer."""
        try:
            idx = self.tasks_ui.index(ui_item)
            self.manager.toggle_task(idx)
        except ValueError:
            pass

    def clear_completed(self) -> None:
        """Removes completed tasks from UI and manager."""
        self.manager.clear_completed()
        # Filter UI items that are completed
        to_remove = [item for item in self.tasks_ui if item.completed_var.get()]
        for item in to_remove:
            self.tasks_ui.remove(item)
            item.destroy()
        self.update_canvas()

    def load_initial_tasks(self) -> None:
        """Initial task load on startup."""
        for task in self.manager.tasks:
            self._create_task_widget(task)
        self.update_canvas()

    def refresh_list(self) -> None:
        """Full rebuild (rarely used now, kept for fallback)."""
        for item in self.tasks_ui:
            item.destroy()
        self.tasks_ui = []
        self.load_initial_tasks()

    def update_canvas(self) -> None:
        """Updates the scroll region of the list canvas."""
        self.scroll_frame.update_idletasks()
        self.list_canvas.config(scrollregion=self.list_canvas.bbox("all"))

    def repack_tasks(self) -> None:
        """Efficiency helper to update packing order without recreation."""
        for t in self.tasks_ui:
            t.pack_forget()
        for t in self.tasks_ui:
            t.pack(fill="x", pady=2, padx=5)
        self.update_canvas()

    def handle_error(self, message: str) -> None:
        """Displays error messages in a standard OS dialog."""
        messagebox.showerror("Fly Notes Error", message)

    def start_reorder(self, item: TaskItem, event: tk.Event) -> None:
        """Initiates a drag-and-drop reorder operation."""
        self.dragging_item = item
        item.set_bg(config.drag_highlight_color)
        self.drag_start_y = event.y_root

    def stop_reorder(self, item: TaskItem, event: tk.Event) -> None:
        """Finalizes a drag-and-drop operation."""
        if self.dragging_item:
            self.dragging_item.set_bg(config.item_bg)
            self.dragging_item = None
        self.update_canvas()

    def do_reorder(self, item: TaskItem, event: tk.Event) -> None:
        """Determines if items should be swapped during active dragging."""
        if not self.dragging_item: return
        
        y = event.y_root
        try:
            idx = self.tasks_ui.index(item)
            if y < self.drag_start_y - config.drag_threshold and idx > 0:
                # Move Up
                if self.manager.reorder_tasks(idx, idx-1):
                    self.tasks_ui[idx], self.tasks_ui[idx-1] = self.tasks_ui[idx-1], self.tasks_ui[idx]
                    self.repack_tasks()
                    self.drag_start_y = y
            elif y > self.drag_start_y + config.drag_threshold and idx < len(self.tasks_ui) - 1:
                # Move Down
                if self.manager.reorder_tasks(idx, idx+1):
                    self.tasks_ui[idx], self.tasks_ui[idx+1] = self.tasks_ui[idx+1], self.tasks_ui[idx]
                    self.repack_tasks()
                    self.drag_start_y = y
        except ValueError:
            pass
