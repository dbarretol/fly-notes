import tkinter as tk
from tkinter import font as tkfont

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
        self.bind("<Button-1>", self.start_drag)
        self.bind("<B1-Motion>", self.do_drag)

    def toggle_strike(self):
        if self.completed.get():
            self.label.config(font=self.strike_font, fg=STRIKE_COLOR)
        else:
            self.label.config(font=self.label_font, fg=TEXT_COLOR)

    def start_drag(self, event):
        self.app.start_reorder(self, event)

    def do_drag(self, event):
        self.app.do_reorder(self, event)

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
        
        # Task reordering state
        self.dragging_item = None
        
        self.setup_ui()
        self.setup_bindings()

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
        self.list_canvas.create_window((0,0), window=self.scroll_frame, anchor="nw", width=300)
        
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

    def start_move(self, event):
        self.offset_x = event.x
        self.offset_y = event.y

    def do_move(self, event):
        x = self.root.winfo_x() + event.x - self.offset_x
        y = self.root.winfo_y() + event.y - self.offset_y
        self.root.geometry(f"+{x}+{y}")

    def add_task(self, event=None):
        text = self.task_entry.get().strip()
        if text:
            item = TaskItem(self.scroll_frame, self, text, self.delete_task)
            item.pack(fill="x", pady=2, padx=5)
            self.tasks.append(item)
            self.task_entry.delete(0, tk.END)
            self.update_canvas()

    def delete_task(self, item):
        item.destroy()
        if item in self.tasks:
            self.tasks.remove(item)
        self.update_canvas()

    def clear_completed(self):
        to_delete = [t for t in self.tasks if t.completed.get()]
        for t in to_delete:
            self.delete_task(t)

    def update_canvas(self):
        self.scroll_frame.update_idletasks()
        self.list_canvas.config(scrollregion=self.list_canvas.bbox("all"))

    # Reordering Logic
    def start_reorder(self, item, event):
        self.dragging_item = item
        item.set_bg(DRAG_HIGHLIGHT_COLOR) # Unified highlight
        self.drag_start_y = event.y_root

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
