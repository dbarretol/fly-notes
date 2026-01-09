import tkinter as tk
from tkinter import font as tkfont
import ctypes
import json
import os

# --- GLOBAL CONFIGURATION ---
# Colors
HEADER_BG = "#FF8C00"      # Strong Orange
CONTENT_BG = "#FFDAB9"     # Pastel Orange (PeachPuff)
ITEM_BG = "#FFE4B5"        # Moccasin (Lighter pastel)
TEXT_COLOR = "#4B2E1E"     # Dark brown/black for contrast
STRIKE_COLOR = "#A0522D"   # Sienna (Muted brown)
BORDER_COLOR = "#DAA520"   # Goldenrod

# Transparency (0.0 to 1.0)
ACTIVE_ALPHA = 1.0
INACTIVE_ALPHA = 0.3       # Subtle enough not to obstruct
DRAG_HIGHLIGHT_COLOR = "#E9967A" # Dark Salmon (More subtle highlight)
# ----------------------------

class TaskItem(tk.Frame):
    def __init__(self, master, app, text, on_delete, **kwargs):
        super().__init__(master, bg=ITEM_BG, **kwargs)
        self.app = app
        self.text = text
        self.on_delete = on_delete
        self.completed = tk.BooleanVar(value=False)
        
        self.check = tk.Checkbutton(
            self, variable=self.completed, command=self.toggle_strike,
            bg=ITEM_BG, activebackground=ITEM_BG, selectcolor="white",
            fg=TEXT_COLOR
        )
        self.check.pack(side="left", padx=5)
        
        self.label_font = tkfont.Font(family="Segoe UI", size=11)
        self.strike_font = tkfont.Font(family="Segoe UI", size=11, overstrike=1)
        
        self.label = tk.Label(
            self, text=text, fg=TEXT_COLOR, bg=ITEM_BG,
            font=self.label_font, anchor="w"
        )
        self.label.pack(side="left", fill="x", expand=True)
        
        self.delete_btn = tk.Button(
            self, text="✕", command=lambda: self.on_delete(self),
            bg=ITEM_BG, fg="#D2691E", bd=0, activebackground=CONTENT_BG,
            activeforeground="#FF4500", cursor="hand2"
        )
        self.delete_btn.pack(side="right", padx=5)

        # Reordering support (Only for the item itself and label)
        self.label.bind("<Button-1>", self.start_drag)
        self.label.bind("<B1-Motion>", self.do_drag)
        self.label.bind("<ButtonRelease-1>", self.stop_drag)
        self.bind("<Button-1>", self.start_drag)
        self.bind("<B1-Motion>", self.do_drag)
        self.bind("<ButtonRelease-1>", self.stop_drag)

    def toggle_strike(self):
        if self.completed.get():
            self.label.config(font=self.strike_font, fg=STRIKE_COLOR)
        else:
            self.label.config(font=self.label_font, fg=TEXT_COLOR)
        self.app.save_tasks() # Save on status change

    def start_drag(self, event):
        self.app.start_reorder(self, event)

    def do_drag(self, event):
        self.app.do_reorder(self, event)

    def stop_drag(self, event):
        self.app.stop_reorder(self, event)

    def set_bg(self, color):
        """Recursively update background of self and all sub-widgets."""
        self.config(bg=color)
        self.label.config(bg=color)
        self.check.config(bg=color, activebackground=color)
        self.delete_btn.config(bg=color, activebackground=color)

class FlyNotesApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Fly Notes")
        self.root.geometry("300x400+100+100")
        self.root.overrideredirect(True) # Borderless
        self.root.attributes("-topmost", True) # Floating
        self.root.config(bg=CONTENT_BG)
        self.root.attributes("-alpha", ACTIVE_ALPHA)
        
        # Window movement state
        self.offset_x = 0
        self.offset_y = 0
        
        # Resizing state
        self.is_resizing = False
        self.resize_edge = None
        
        # Recursion guard for window state changes
        self.lock_taskbar_update = False
        self._was_minimized = False
        
        self.setup_ui()
        self.setup_bindings()
        self.setup_resize_handles()
        self.setup_taskbar_proxy()
        
        self.tasks_file = "tasks.json"
        self.load_tasks()

    def setup_taskbar_proxy(self):
        # A normal decorated window that will represent us in the taskbar
        self.proxy = tk.Toplevel(self.root)
        self.proxy.title("Fly Notes")

        # Keep it effectively invisible when shown/restored
        self.proxy.geometry("1x1+-32000+-32000")  # far off-screen
        self.proxy.resizable(False, False)

        # If user closes from taskbar thumbnail, close the app
        self.proxy.protocol("WM_DELETE_WINDOW", self.root.destroy)

        # We'll use this to ignore programmatic deiconify during minimize
        self._proxy_programmatic = False

        # When user restores from taskbar, this window gets mapped/focused
        self.proxy.bind("<Map>", self._proxy_restore_request)
        self.proxy.bind("<FocusIn>", self._proxy_restore_request)

        # Start with no taskbar icon
        self.proxy.withdraw()

    def _proxy_restore_request(self, event=None):
        # Ignore the map/focus events we caused ourselves while minimizing
        if getattr(self, "_proxy_programmatic", False):
            return

        if not self._was_minimized:
            return

        self._was_minimized = False

        # Hide proxy => remove taskbar button again
        self.proxy.withdraw()

        # Restore real borderless window
        self.root.deiconify()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.lift()
        self.root.focus_force()

    def setup_ui(self):
        # Header / Dragging area (Window Title)
        self.header = tk.Frame(self.root, bg=HEADER_BG, height=35)
        self.header.pack(fill="x", side="top")
        
        self.title_label = tk.Label(
            self.header, text="Fly Notes", fg="white", bg=HEADER_BG,
            font=("Segoe UI", 10, "bold")
        )
        self.title_label.pack(side="left", padx=10, pady=5)
        
        self.close_btn = tk.Button(
            self.header, text="✕", command=self.root.destroy,
            bg=HEADER_BG, fg="white", bd=0, activebackground="#FF4500",
            padx=10, font=("Segoe UI", 10, "bold")
        )
        self.close_btn.pack(side="right", fill="y")

        self.min_btn = tk.Button(
            self.header, text="—", command=self.minimize_window,
            bg=HEADER_BG, fg="white", bd=0, activebackground="#FF4500",
            padx=10, font=("Segoe UI", 10, "bold")
        )
        self.min_btn.pack(side="right", fill="y")

        # Entry area
        self.entry_frame = tk.Frame(self.root, bg=CONTENT_BG, pady=10)
        self.entry_frame.pack(fill="x")
        
        self.task_entry = tk.Entry(
            self.entry_frame, bg="white", fg=TEXT_COLOR, insertbackground=TEXT_COLOR,
            font=("Segoe UI", 11), bd=0, highlightthickness=1,
            highlightbackground=BORDER_COLOR
        )
        self.task_entry.pack(fill="x", padx=10, ipady=5)
        self.task_entry.bind("<Return>", self.add_task)

        # Task List Container
        self.list_canvas = tk.Canvas(self.root, bg=CONTENT_BG, highlightthickness=0)
        self.scroll_frame = tk.Frame(self.list_canvas, bg=CONTENT_BG)
        
        self.list_canvas.pack(fill="both", expand=True)
        self.canvas_window_id = self.list_canvas.create_window(
            (0,0), window=self.scroll_frame, anchor="nw", width=300
        )
        
        # Footer
        self.footer = tk.Frame(self.root, bg=CONTENT_BG, pady=5)
        self.footer.pack(fill="x", side="bottom")
        
        self.clear_btn = tk.Button(
            self.footer, text="Clear Completed", command=self.clear_completed,
            bg=CONTENT_BG, fg=STRIKE_COLOR, bd=0, font=("Segoe UI", 8, "bold"),
            activebackground=CONTENT_BG, activeforeground=TEXT_COLOR, cursor="hand2"
        )
        self.clear_btn.pack(side="right", padx=10)

        self.tasks = []

    def setup_bindings(self):
        # Window movement - ONLY via header/title
        self.header.bind("<Button-1>", self.start_move)
        self.header.bind("<B1-Motion>", self.do_move)
        self.title_label.bind("<Button-1>", self.start_move)
        self.title_label.bind("<B1-Motion>", self.do_move)
        
        # Transparency on focus
        self.root.bind("<FocusIn>", lambda e: self.root.attributes("-alpha", ACTIVE_ALPHA))
        self.root.bind("<FocusOut>", lambda e: self.root.attributes("-alpha", INACTIVE_ALPHA))

        # Re-apply borderless and topmost on restore (generic guard for OS events)
        self.root.bind("<Map>", lambda e: self.root.attributes("-topmost", True))

    def setup_resize_handles(self):
        # Create thin invisible frames for resizing
        self.resizer_r = tk.Frame(self.root, bg=CONTENT_BG, cursor="sb_h_double_arrow", width=5)
        self.resizer_r.place(relx=1.0, rely=0.0, relheight=1.0, anchor="ne")
        self.resizer_r.bind("<Button-1>", lambda e: self.start_resize("r", e))
        self.resizer_r.bind("<B1-Motion>", self.do_resize)

        self.resizer_b = tk.Frame(self.root, bg=CONTENT_BG, cursor="sb_v_double_arrow", height=5)
        self.resizer_b.place(relx=0.0, rely=1.0, relwidth=1.0, anchor="sw")
        self.resizer_b.bind("<Button-1>", lambda e: self.start_resize("b", e))
        self.resizer_b.bind("<B1-Motion>", self.do_resize)

        self.resizer_se = tk.Frame(self.root, bg=CONTENT_BG, cursor="size_nw_se", width=10, height=10)
        self.resizer_se.place(relx=1.0, rely=1.0, anchor="se")
        self.resizer_se.bind("<Button-1>", lambda e: self.start_resize("se", e))
        self.resizer_se.bind("<B1-Motion>", self.do_resize)

    def minimize_window(self):
        self._was_minimized = True

        # Hide the real UI window completely (don’t iconify it)
        self.root.withdraw()

        # Show a taskbar button via the proxy window, but keep it off-screen
        self._proxy_programmatic = True
        self.proxy.deiconify()
        self.proxy.after_idle(self.proxy.iconify)

        # Clear the flag shortly after iconify completes
        self.proxy.after(200, lambda: setattr(self, "_proxy_programmatic", False))

    def start_resize(self, edge, event):
        self.is_resizing = True
        self.resize_edge = edge
        self.start_x = event.x_root
        self.start_y = event.y_root
        self.start_w = self.root.winfo_width()
        self.start_h = self.root.winfo_height()

    def do_resize(self, event):
        if not self.is_resizing: return
        
        dx = event.x_root - self.start_x
        dy = event.y_root - self.start_y
        
        new_w = self.start_w
        new_h = self.start_h

        if "r" in self.resize_edge:
            new_w = max(200, self.start_w + dx)
        if "b" in self.resize_edge:
            new_h = max(150, self.start_h + dy)
        if "se" == self.resize_edge:
            new_w = max(200, self.start_w + dx)
            new_h = max(150, self.start_h + dy)

        self.root.geometry(f"{new_w}x{new_h}")
        # Use itemconfigure instead of create_window to avoid memory leak
        self.list_canvas.itemconfigure(self.canvas_window_id, width=new_w)
        self.update_canvas()

    def start_move(self, event):
        self.offset_x = event.x
        self.offset_y = event.y

    def do_move(self, event):
        x = self.root.winfo_x() + event.x - self.offset_x
        y = self.root.winfo_y() + event.y - self.offset_y
        self.root.geometry(f"+{x}+{y}")

    def add_task(self, event=None, task_text=None, completed=False):
        text = task_text if task_text else self.task_entry.get().strip()
        if text:
            item = TaskItem(self.scroll_frame, self, text, self.delete_task)
            item.completed.set(completed)
            item.toggle_strike() # Apply initial strike if needed
            item.pack(fill="x", pady=2, padx=5)
            self.tasks.append(item)
            if not task_text:
                self.task_entry.delete(0, tk.END)
                self.save_tasks() # Save on new task
            self.update_canvas()

    def delete_task(self, item):
        item.destroy()
        if item in self.tasks:
            self.tasks.remove(item)
        self.save_tasks() # Save on deletion
        self.update_canvas()

    def clear_completed(self):
        to_delete = [t for t in self.tasks if t.completed.get()]
        if to_delete:
            for t in to_delete:
                self.delete_task(t)
            # delete_task already calls save_tasks

    def save_tasks(self):
        task_data = []
        for t in self.tasks:
            task_data.append({
                "text": t.text,
                "completed": t.completed.get()
            })
        try:
            with open(self.tasks_file, "w") as f:
                json.dump(task_data, f)
        except Exception as e:
            print(f"Error saving tasks: {e}")

    def load_tasks(self):
        if os.path.exists(self.tasks_file):
            try:
                with open(self.tasks_file, "r") as f:
                    task_data = json.load(f)
                    for data in task_data:
                        self.add_task(task_text=data["text"], completed=data["completed"])
            except Exception as e:
                print(f"Error loading tasks: {e}")

    def update_canvas(self):
        self.scroll_frame.update_idletasks()
        self.list_canvas.config(scrollregion=self.list_canvas.bbox("all"))

    # Reordering Logic
    def start_reorder(self, item, event):
        self.dragging_item = item
        item.set_bg(DRAG_HIGHLIGHT_COLOR) # Unified highlight
        self.drag_start_y = event.y_root

    def stop_reorder(self, item, event):
        if self.dragging_item:
            self.dragging_item.set_bg(ITEM_BG)
            self.dragging_item = None
            self.save_tasks() # Save order after drag
        self.update_canvas()

    def do_reorder(self, item, event):
        if not self.dragging_item: return
        
        y = event.y_root
        idx = self.tasks.index(item)
        
        if y < self.drag_start_y - 20 and idx > 0:
            # Move Up
            self.tasks[idx], self.tasks[idx-1] = self.tasks[idx-1], self.tasks[idx]
            self.repack_tasks()
            self.drag_start_y = y
        elif y > self.drag_start_y + 20 and idx < len(self.tasks) - 1:
            # Move Down
            self.tasks[idx], self.tasks[idx+1] = self.tasks[idx+1], self.tasks[idx]
            self.repack_tasks()
            self.drag_start_y = y

    def repack_tasks(self):
        # Reset colors during repack to clear highlight or apply dragging highlight
        for t in self.tasks:
            t.pack_forget()
            if t == self.dragging_item:
                t.set_bg(DRAG_HIGHLIGHT_COLOR)
            else:
                t.set_bg(ITEM_BG)
        
        for t in self.tasks:
            t.pack(fill="x", pady=2, padx=5)
        self.update_canvas()

if __name__ == "__main__":
    root = tk.Tk()
    app = FlyNotesApp(root)
    root.mainloop()
