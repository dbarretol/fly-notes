import json
import os

class TaskManager:
    def __init__(self, tasks_file="tasks.json", error_callback=None):
        self.tasks_file = tasks_file
        self.error_callback = error_callback
        self.tasks = []
        self.load_tasks()

    def add_task(self, text, completed=False):
        task = {"text": text, "completed": completed}
        self.tasks.append(task)
        self.save_tasks()
        return task

    def delete_task(self, index):
        if 0 <= index < len(self.tasks):
            removed = self.tasks.pop(index)
            self.save_tasks()
            return removed
        return None

    def toggle_task(self, index):
        if 0 <= index < len(self.tasks):
            self.tasks[index]["completed"] = not self.tasks[index]["completed"]
            self.save_tasks()
            return self.tasks[index]
        return None

    def reorder_tasks(self, old_index, new_index):
        if 0 <= old_index < len(self.tasks) and 0 <= new_index < len(self.tasks):
            task = self.tasks.pop(old_index)
            self.tasks.insert(new_index, task)
            self.save_tasks()
            return True
        return False

    def clear_completed(self):
        self.tasks = [t for t in self.tasks if not t["completed"]]
        self.save_tasks()

    def save_tasks(self):
        try:
            with open(self.tasks_file, "w") as f:
                json.dump(self.tasks, f)
        except Exception as e:
            msg = f"Error saving tasks: {e}"
            if self.error_callback:
                self.error_callback(msg)
            else:
                print(msg)

    def load_tasks(self):
        if os.path.exists(self.tasks_file):
            try:
                with open(self.tasks_file, "r") as f:
                    self.tasks = json.load(f)
            except Exception as e:
                msg = f"Error loading tasks: {e}"
                if self.error_callback:
                    self.error_callback(msg)
                else:
                    print(msg)
                self.tasks = []
        else:
            self.tasks = []
