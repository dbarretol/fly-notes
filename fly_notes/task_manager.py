import json
import os
import logging
from typing import List, Dict, Optional, Callable, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TaskManager:
    """
    Manages the lifecycle of tasks, including persistence to a JSON file.
    
    Attributes:
        tasks_file (str): Path to the JSON file where tasks are stored.
        error_callback (Callable[[str], None]): Callback for reporting errors to the UI.
        tasks (List[Dict[str, Any]]): In-memory list of task objects.
    """

    def __init__(self, tasks_file: str = "tasks.json", error_callback: Optional[Callable[[str], None]] = None):
        """
        Initializes the TaskManager and loads tasks from the specified file.
        
        Args:
            tasks_file: Path to the storage file.
            error_callback: Optional function to call when an error occurs.
        """
        self.tasks_file: str = tasks_file
        self.error_callback: Optional[Callable[[str], None]] = error_callback
        self.tasks: List[Dict[str, Any]] = []
        self.load_tasks()

    def add_task(self, text: str, completed: bool = False) -> Dict[str, Any]:
        """
        Adds a new task to the list and saves.
        
        Args:
            text: The content of the task.
            completed: Initial completion status.
            
        Returns:
            The created task dictionary.
        """
        task = {"text": text, "completed": completed}
        self.tasks.append(task)
        self.save_tasks()
        logger.info(f"Task added: {text}")
        return task

    def delete_task(self, index: int) -> Optional[Dict[str, Any]]:
        """
        Removes a task at the specified index.
        
        Args:
            index: The 0-based index of the task to remove.
            
        Returns:
            The removed task dictionary, or None if index is out of bounds.
        """
        if 0 <= index < len(self.tasks):
            removed = self.tasks.pop(index)
            self.save_tasks()
            logger.info(f"Task deleted at index {index}")
            return removed
        logger.warning(f"Attempted to delete task at out-of-bounds index {index}")
        return None

    def toggle_task(self, index: int) -> Optional[Dict[str, Any]]:
        """
        Toggles the completion status of a task.
        
        Args:
            index: The index of the task to toggle.
            
        Returns:
            The updated task dictionary, or None if index is out of bounds.
        """
        if 0 <= index < len(self.tasks):
            self.tasks[index]["completed"] = not self.tasks[index]["completed"]
            self.save_tasks()
            logger.info(f"Task toggled at index {index}: {self.tasks[index]['completed']}")
            return self.tasks[index]
        return None

    def reorder_tasks(self, old_index: int, new_index: int) -> bool:
        """
        Moves a task from one position to another.
        
        Args:
            old_index: Current index.
            new_index: Target index.
            
        Returns:
            True if successful, False otherwise.
        """
        if 0 <= old_index < len(self.tasks) and 0 <= new_index < len(self.tasks):
            task = self.tasks.pop(old_index)
            self.tasks.insert(new_index, task)
            self.save_tasks()
            logger.info(f"Task reordered from {old_index} to {new_index}")
            return True
        return False

    def clear_completed(self) -> None:
        """Removes all tasks marked as completed."""
        initial_count = len(self.tasks)
        self.tasks = [t for t in self.tasks if not t["completed"]]
        self.save_tasks()
        logger.info(f"Cleared {initial_count - len(self.tasks)} completed tasks")

    def save_tasks(self) -> None:
        """Persists the current task list to the JSON file."""
        try:
            with open(self.tasks_file, "w") as f:
                json.dump(self.tasks, f)
        except Exception as e:
            msg = f"Error saving tasks: {e}"
            logger.error(msg, exc_info=True)
            if self.error_callback:
                self.error_callback(msg)

    def load_tasks(self) -> None:
        """Loads tasks from the storage file if it exists."""
        if os.path.exists(self.tasks_file):
            try:
                with open(self.tasks_file, "r") as f:
                    self.tasks = json.load(f)
                logger.info(f"Loaded {len(self.tasks)} tasks from {self.tasks_file}")
            except Exception as e:
                msg = f"Error loading tasks: {e}"
                logger.error(msg, exc_info=True)
                if self.error_callback:
                    self.error_callback(msg)
                self.tasks = []
        else:
            logger.info(f"No tasks file found at {self.tasks_file}, starting fresh")
            self.tasks = []
