import tkinter as tk
from tkinter import messagebox
from typing import List, Optional, Any
from .config import config
from .task_manager import TaskManager
from .task_item import TaskItem

# Constants for internal logic thresholds
DRAG_THRESHOLD_PX = 20
MIN_WINDOW_WIDTH = 200
MIN_WINDOW_HEIGHT = 150

class FlyNotesApp:
    """
    Main application class for Fly Notes. 
    Orchestrates UI components and data management.
    """
    
    def __init__(self, root: tk.Tk):
        """
        Initializes the application window and components.
        
        Args:
            root: The Tkinter root window instance.
        """
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
        
        # State
        self.offset_x: int = 0
        self.offset_y: int = 0
        self.is_resizing: bool = False
        self.resize_edge: Optional[str] = None
        self.dragging_item: Optional[TaskItem] = None
        self.drag_start_y: int = 0
        self._was_minimized: bool = False
        self._proxy_programmatic: bool = False
        
        self.tasks_ui: List[TaskItem] = []
        
        self.setup_ui()
        self.setup_bindings()
        self.setup_resize_handles()
        self.setup_taskbar_proxy()
        self.load_initial_tasks()

    def setup_taskbar_proxy(self) -> None:
        """Creates a hidden proxy window to enable taskbar presence for the borderless main window."""
        self.proxy = tk.Toplevel(self.root)
        self.proxy.title("Fly Notes")
        self.proxy.geometry("1x1+-32000+-32000")
        self.proxy.resizable(False, False)
        self.proxy.protocol("WM_DELETE_WINDOW", self.root.destroy)
        self.proxy.bind("<Map>", self._proxy_restore_request)
        self.proxy.bind("<FocusIn>", self._proxy_restore_request)
        self.proxy.withdraw()

    def _proxy_restore_request(self, event: Optional[tk.Event] = None) -> None:
        """Handles restoration from the taskbar proxy."""
        if self._proxy_programmatic:
            return
        if not self._was_minimized:
            return
        self._was_minimized = False
        self.proxy.withdraw()
        self.root.deiconify()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.lift()
        self.root.focus_force()

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
            self.header, text="—", command=self.minimize_window,
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
        self.header.bind("<Button-1>", self.start_move)
        self.header.bind("<B1-Motion>", self.do_move)
        self.title_label.bind("<Button-1>", self.start_move)
        self.title_label.bind("<B1-Motion>", self.do_move)
        
        self.root.bind("<FocusIn>", lambda e: self.root.attributes("-alpha", config.active_alpha))
        self.root.bind("<FocusOut>", lambda e: self.root.attributes("-alpha", config.inactive_alpha))
        self.root.bind("<Map>", lambda e: self.root.attributes("-topmost", True))

    def setup_resize_handles(self) -> None:
        """Creates invisible frames for window resizing interaction."""
        self.resizer_r = tk.Frame(self.root, bg=config.content_bg, cursor="sb_h_double_arrow", width=5)
        self.resizer_r.place(relx=1.0, rely=0.0, relheight=1.0, anchor="ne")
        self.resizer_r.bind("<Button-1>", lambda e: self.start_resize("r", e))
        self.resizer_r.bind("<B1-Motion>", self.do_resize)

        self.resizer_b = tk.Frame(self.root, bg=config.content_bg, cursor="sb_v_double_arrow", height=5)
        self.resizer_b.place(relx=0.0, rely=1.0, relwidth=1.0, anchor="sw")
        self.resizer_b.bind("<Button-1>", lambda e: self.start_resize("b", e))
        self.resizer_b.bind("<B1-Motion>", self.do_resize)

        self.resizer_se = tk.Frame(self.root, bg=config.content_bg, cursor="size_nw_se", width=10, height=10)
        self.resizer_se.place(relx=1.0, rely=1.0, anchor="se")
        self.resizer_se.bind("<Button-1>", lambda e: self.start_resize("se", e))
        self.resizer_se.bind("<B1-Motion>", self.do_resize)

    def minimize_window(self) -> None:
        """Withdraws the main window and shows it in the taskbar via the proxy."""
        self._was_minimized = True
        self.root.withdraw()
        self._proxy_programmatic = True
        self.proxy.deiconify()
        self.proxy.after_idle(self.proxy.iconify)
        self.proxy.after(200, lambda: setattr(self, "_proxy_programmatic", False))

    def start_resize(self, edge: str, event: tk.Event) -> None:
        """Caches state for the start of a resize operation."""
        self.is_resizing = True
        self.resize_edge = edge
        self.start_x = event.x_root
        self.start_y = event.y_root
        self.start_w = self.root.winfo_width()
        self.start_h = self.root.winfo_height()

    def do_resize(self, event: tk.Event) -> None:
        """Handles active resizing mouse motion."""
        if not self.is_resizing: return
        dx = event.x_root - self.start_x
        dy = event.y_root - self.start_y
        new_w = self.start_w
        new_h = self.start_h
        if "r" in self.resize_edge:
            new_w = max(MIN_WINDOW_WIDTH, self.start_w + dx)
        if "b" in self.resize_edge:
            new_h = max(MIN_WINDOW_HEIGHT, self.start_h + dy)
        if "se" == self.resize_edge:
            new_w = max(MIN_WINDOW_WIDTH, self.start_w + dx)
            new_h = max(MIN_WINDOW_HEIGHT, self.start_h + dy)
        self.root.geometry(f"{new_w}x{new_h}")
        self.list_canvas.itemconfigure(self.canvas_window_id, width=new_w)
        self.update_canvas()

    def start_move(self, event: tk.Event) -> None:
        """Caches offset for window movement."""
        self.offset_x = event.x
        self.offset_y = event.y

    def do_move(self, event: tk.Event) -> None:
        """Handles active window dragging."""
        x = self.root.winfo_x() + event.x - self.offset_x
        y = self.root.winfo_y() + event.y - self.offset_y
        self.root.geometry(f"+{x}+{y}")

    def add_new_task(self) -> None:
        """Adds a new task from the entry field."""
        text = self.task_entry.get().strip()
        if text:
            self.manager.add_task(text)
            self.task_entry.delete(0, tk.END)
            self.refresh_list()

    def delete_task(self, ui_item: TaskItem) -> None:
        """Removes a task from the list."""
        try:
            idx = self.tasks_ui.index(ui_item)
            self.manager.delete_task(idx)
            self.refresh_list()
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
        """Asks the manager to clear all completed tasks and updates the UI."""
        self.manager.clear_completed()
        self.refresh_list()

    def load_initial_tasks(self) -> None:
        """Initial task load on startup."""
        self.refresh_list()

    def refresh_list(self) -> None:
        """Clears and rebuilds the entire task list UI from stored state."""
        for item in self.tasks_ui:
            item.destroy()
        self.tasks_ui = []
        
        for task in self.manager.tasks:
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
        
        self.update_canvas()

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
            if y < self.drag_start_y - DRAG_THRESHOLD_PX and idx > 0:
                # Move Up
                if self.manager.reorder_tasks(idx, idx-1):
                    self.tasks_ui[idx], self.tasks_ui[idx-1] = self.tasks_ui[idx-1], self.tasks_ui[idx]
                    self.repack_tasks()
                    self.drag_start_y = y
            elif y > self.drag_start_y + DRAG_THRESHOLD_PX and idx < len(self.tasks_ui) - 1:
                # Move Down
                if self.manager.reorder_tasks(idx, idx+1):
                    self.tasks_ui[idx], self.tasks_ui[idx+1] = self.tasks_ui[idx+1], self.tasks_ui[idx]
                    self.repack_tasks()
                    self.drag_start_y = y
        except ValueError:
            pass
