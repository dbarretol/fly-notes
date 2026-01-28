import json
import os

# --- DEFAULT CONFIGURATION ---
DEFAULT_CONFIG = {
    "colors": {
        "header_bg": "#FF8C00",      # Strong Orange
        "content_bg": "#FFDAB9",     # Pastel Orange (PeachPuff)
        "item_bg": "#FFE4B5",        # Moccasin (Lighter pastel)
        "text_color": "#4B2E1E",     # Dark brown/black for contrast
        "strike_color": "#A0522D",   # Sienna (Muted brown)
        "border_color": "#DAA520",   # Goldenrod
        "drag_highlight": "#E9967A"  # Dark Salmon
    },
    "transparency": {
        "active": 1.0,
        "inactive": 0.3
    },
    "settings": {
        "tasks_file": "tasks.json",
        "default_width": 300,
        "default_height": 400
    }
}

CONFIG_FILE = "config.json"

class Config:
    def __init__(self):
        self.data = DEFAULT_CONFIG.copy()
        self.load()

    def load(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    user_config = json.load(f)
                    self._deep_update(self.data, user_config)
            except Exception as e:
                print(f"Error loading {CONFIG_FILE}: {e}")

    def _deep_update(self, d, u):
        for k, v in u.items():
            if isinstance(v, dict):
                d[k] = self._deep_update(d.get(k, {}), v)
            else:
                d[k] = v
        return d

    @property
    def header_bg(self): return self.data["colors"]["header_bg"]
    @property
    def content_bg(self): return self.data["colors"]["content_bg"]
    @property
    def item_bg(self): return self.data["colors"]["item_bg"]
    @property
    def text_color(self): return self.data["colors"]["text_color"]
    @property
    def strike_color(self): return self.data["colors"]["strike_color"]
    @property
    def border_color(self): return self.data["colors"]["border_color"]
    @property
    def drag_highlight_color(self): return self.data["colors"]["drag_highlight"]
    @property
    def active_alpha(self): return self.data["transparency"]["active"]
    @property
    def inactive_alpha(self): return self.data["transparency"]["inactive"]
    @property
    def tasks_file(self): return self.data["settings"]["tasks_file"]
    @property
    def default_width(self): return self.data["settings"]["default_width"]
    @property
    def default_height(self): return self.data["settings"]["default_height"]

# Global config instance
config = Config()
