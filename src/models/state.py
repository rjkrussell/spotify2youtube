"""Load and save state.json (selections, progress, library cache)."""

from __future__ import annotations

import json
import os
import threading

from src.models.library import SpotifyLibrary

DATA_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STATE_PATH = os.path.join(DATA_DIR, "state.json")


class StateManager:
    def __init__(self, path: str = STATE_PATH):
        self.path = path
        self.library = SpotifyLibrary()
        self._lock = threading.Lock()

    def load(self) -> SpotifyLibrary:
        if os.path.exists(self.path):
            try:
                with open(self.path, "r") as f:
                    data = json.load(f)
                self.library = SpotifyLibrary.from_dict(data.get("library", {}))
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                # Corrupted state — start fresh
                self.library = SpotifyLibrary()
        return self.library

    def save(self) -> None:
        with self._lock:
            tmp_path = self.path + ".tmp"
            data = {"library": self.library.to_dict()}
            with open(tmp_path, "w") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp_path, self.path)
