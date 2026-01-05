import tkinter as tk
from tkinter import font as tkfont

class TaskItem(tk.Frame):
    def __init__(self, master, text, on_delete, **kwargs):
        super().__init__(master, bg="#2d2d2d", **kwargs)
        self.text = text
        self.on_delete = on_delete
        self.completed = tk.BooleanVar(value=False)
        
        self.check = tk.Checkbutton(
            self, variable=self.completed, command=self.toggle_strike,
            bg="#2d2d2d", activebackground="#2d2d2d", selectcolor="#444444",
            fg="white"
        )
        self.check.pack(side="left", padx=5)
        
        self.label_font = tkfont.Font(family="Segoe UI", size=11)
        self.strike_font = tkfont.Font(family="Segoe UI", size=11, overstrike=1)
        
        self.label = tk.Label(
            self, text=text, fg="white", bg="#2d2d2d",
            font=self.label_font, anchor="w"
        )
        self.label.pack(side="left", fill="x", expand=True)
        
        self.delete_btn = tk.Button(
            self, text="✕", command=lambda: self.on_delete(self),
            bg="#2d2d2d", fg="#ff5555", bd=0, activebackground="#3d3d3d",
            activeforeground="#ff5555", cursor="hand2"
        )
        self.delete_btn.pack(side="right", padx=5)

        # Reordering support
        self.bind("<Button-1>", self.start_drag)
        self.bind("<B1-Motion>", self.do_drag)
        self.label.bind("<Button-1>", self.start_drag)
        self.label.bind("<B1-Motion>", self.do_drag)

    def toggle_strike(self):
        if self.completed.get():
            self.label.config(font=self.strike_font, fg="#888888")
        else:
            self.label.config(font=self.label_font, fg="white")

    def start_drag(self, event):
        self.master.start_reorder(self, event)

    def do_drag(self, event):
        self.master.do_reorder(self, event)

class FlyNotesApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Fly Notes")
        self.root.geometry("300x400+100+100")
        self.root.overrideredirect(True) # Borderless
        self.root.attributes("-topmost", True) # Floating
        self.root.config(bg="#1e1e1e")
        self.root.attributes("-alpha", 1.0)
        
        # Window movement state
        self.offset_x = 0
        self.offset_y = 0
        
        # Task reordering state
        self.dragging_item = None
        
        self.setup_ui()
        self.setup_bindings()

    def setup_ui(self):
        # Header / Dragging area
        self.header = tk.Frame(self.root, bg="#333333", height=30)
        self.header.pack(fill="x", side="top")
        
        self.title_label = tk.Label(
            self.header, text="Fly Notes", fg="#aaaaaa", bg="#333333",
            font=("Segoe UI", 9, "bold")
        )
        self.title_label.pack(side="left", padx=10)
        
        self.close_btn = tk.Button(
            self.header, text="✕", command=self.root.destroy,
            bg="#333333", fg="white", bd=0, activebackground="#ff5555",
            padx=10
        )
        self.close_btn.pack(side="right")

        # Entry area
        self.entry_frame = tk.Frame(self.root, bg="#1e1e1e", pady=10)
        self.entry_frame.pack(fill="x")
        
        self.task_entry = tk.Entry(
            self.entry_frame, bg="#2d2d2d", fg="white", insertbackground="white",
            font=("Segoe UI", 11), bd=0, highlightthickness=1,
            highlightbackground="#444444"
        )
        self.task_entry.pack(fill="x", padx=10, ipady=5)
        self.task_entry.bind("<Return>", self.add_task)

        # Task List Container
        self.list_canvas = tk.Canvas(self.root, bg="#1e1e1e", highlightthickness=0)
        self.scroll_frame = tk.Frame(self.list_canvas, bg="#1e1e1e")
        
        self.list_canvas.pack(fill="both", expand=True)
        self.list_canvas.create_window((0,0), window=self.scroll_frame, anchor="nw", width=300)
        
        # Footer
        self.footer = tk.Frame(self.root, bg="#1e1e1e", pady=5)
        self.footer.pack(fill="x", side="bottom")
        
        self.clear_btn = tk.Button(
            self.footer, text="Clear Completed", command=self.clear_completed,
            bg="#1e1e1e", fg="#888888", bd=0, font=("Segoe UI", 8),
            activebackground="#1e1e1e", activeforeground="white"
        )
        self.clear_btn.pack(side="right", padx=10)

        self.tasks = []

    def setup_bindings(self):
        # Global dragging
        self.root.bind("<Button-1>", self.start_move)
        self.root.bind("<B1-Motion>", self.do_move)
        
        # Transparency on focus
        self.root.bind("<FocusIn>", lambda e: self.root.attributes("-alpha", 1.0))
        self.root.bind("<FocusOut>", lambda e: self.root.attributes("-alpha", 0.7))

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
            item = TaskItem(self.scroll_frame, text, self.delete_task)
            item.pack(fill="x", pady=1)
            self.tasks.append(item)
            self.task_entry.delete(0, tk.END)
            self.update_canvas()

    def delete_task(self, item):
        item.destroy()
        self.tasks.remove(item)
        self.update_canvas()

    def clear_completed(self):
        to_delete = [t for t in self.tasks if t.completed.get()]
        for t in to_delete:
            self.delete_task(t)

    def update_canvas(self):
        # Adjust scroll region (though we haven't implemented a scrollbar yet for simplicity)
        self.scroll_frame.update_idletasks()
        self.list_canvas.config(scrollregion=self.list_canvas.bbox("all"))

    # Reordering Logic
    def start_reorder(self, item, event):
        self.dragging_item = item
        item.config(bg="#3d3d3d") # Highlight
        self.drag_start_y = event.y_root

    def do_reorder(self, item, event):
        if not self.dragging_item: return
        
        # Simple swap logic based on Y position
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
        for t in self.tasks:
            t.pack_forget()
        for t in self.tasks:
            t.pack(fill="x", pady=1)
        self.update_canvas()

if __name__ == "__main__":
    root = tk.Tk()
    app = FlyNotesApp(root)
    root.mainloop()
