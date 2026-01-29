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
        "default_height": 400,
        "drag_threshold": 20,
        "min_width": 200,
        "min_height": 150
    },
    "fonts": {
        "header": ["Segoe UI", 10, "bold"],
        "body": ["Segoe UI", 11],
        "body_strike": ["Segoe UI", 11, "overstrike"],
        "footer": ["Segoe UI", 8, "bold"]
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
    @property
    def drag_threshold(self): return self.data["settings"].get("drag_threshold", 20)
    @property
    def min_width(self): return self.data["settings"].get("min_width", 200)
    @property
    def min_height(self): return self.data["settings"].get("min_height", 150)
    @property
    def font_header(self): return tuple(self.data["fonts"]["header"])
    @property
    def font_body(self): return tuple(self.data["fonts"]["body"])
    @property
    def font_body_strike(self): return tuple(self.data["fonts"]["body_strike"])
    @property
    def font_footer(self): return tuple(self.data["fonts"]["footer"])

# Global config instance
config = Config()
