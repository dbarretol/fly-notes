import tkinter as tk
from typing import Optional, Callable
from .config import config

class WindowController:
    """
    Handles borderless window logic: dragging, resizing, and taskbar proxy.
    """
    
    def __init__(self, root: tk.Tk, on_resize_callback: Optional[Callable[[], None]] = None):
        self.root = root
        self.on_resize_callback = on_resize_callback
        
        # Internal state for dragging/resizing
        self.offset_x: int = 0
        self.offset_y: int = 0
        self.is_resizing: bool = False
        self.resize_edge: Optional[str] = None
        self.start_x: int = 0
        self.start_y: int = 0
        self.start_w: int = 0
        self.start_h: int = 0
        
        # Taskbar proxy state
        self._was_minimized: bool = False
        self._proxy_programmatic: bool = False
        
        self.setup_taskbar_proxy()

    def setup_taskbar_proxy(self) -> None:
        """Creates a hidden proxy window to enable taskbar presence."""
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

    def minimize_window(self) -> None:
        """Withdraws main window and shows it in taskbar via proxy."""
        self._was_minimized = True
        self.root.withdraw()
        self._proxy_programmatic = True
        self.proxy.deiconify()
        self.proxy.after_idle(self.proxy.iconify)
        self.proxy.after(200, lambda: setattr(self, "_proxy_programmatic", False))

    def bind_drag(self, widget: tk.Widget) -> None:
        """Binds a widget to move the window."""
        widget.bind("<Button-1>", self.start_move)
        widget.bind("<B1-Motion>", self.do_move)

    def start_move(self, event: tk.Event) -> None:
        self.offset_x = event.x
        self.offset_y = event.y

    def do_move(self, event: tk.Event) -> None:
        x = self.root.winfo_x() + event.x - self.offset_x
        y = self.root.winfo_y() + event.y - self.offset_y
        self.root.geometry(f"+{x}+{y}")

    def setup_resize_handles(self, bg_color: str) -> None:
        """Creates invisible frames for window resizing."""
        self._create_resizer("r", 1.0, 0.0, 1.0, "ne", "sb_h_double_arrow", bg_color, width=5)
        self._create_resizer("b", 0.0, 1.0, 1.0, "sw", "sb_v_double_arrow", bg_color, height=5)
        self._create_resizer("se", 1.0, 1.0, None, "se", "size_nw_se", bg_color, width=10, height=10)

    def _create_resizer(self, edge: str, relx: float, rely: float, relsize: Optional[float], 
                        anchor: str, cursor: str, bg_color: str, **kwargs) -> None:
        resizer = tk.Frame(self.root, bg=bg_color, cursor=cursor, **kwargs)
        if "r" in edge and relsize:
            resizer.place(relx=relx, rely=rely, relheight=relsize, anchor=anchor)
        elif "b" in edge and relsize:
            resizer.place(relx=relx, rely=rely, relwidth=relsize, anchor=anchor)
        else:
            resizer.place(relx=relx, rely=rely, anchor=anchor)
        
        resizer.bind("<Button-1>", lambda e: self.start_resize(edge, e))
        resizer.bind("<B1-Motion>", self.do_resize)

    def start_resize(self, edge: str, event: tk.Event) -> None:
        self.is_resizing = True
        self.resize_edge = edge
        self.start_x = event.x_root
        self.start_y = event.y_root
        self.start_w = self.root.winfo_width()
        self.start_h = self.root.winfo_height()

    def do_resize(self, event: tk.Event) -> None:
        if not self.is_resizing: return
        dx = event.x_root - self.start_x
        dy = event.y_root - self.start_y
        new_w = self.start_w
        new_h = self.start_h
        
        if "r" in self.resize_edge:
            new_w = max(config.min_width, self.start_w + dx)
        if "b" in self.resize_edge:
            new_h = max(config.min_height, self.start_h + dy)
        if "se" == self.resize_edge:
            new_w = max(config.min_width, self.start_w + dx)
            new_h = max(config.min_height, self.start_h + dy)
            
        self.root.geometry(f"{new_w}x{new_h}")
        if self.on_resize_callback:
            self.on_resize_callback()
