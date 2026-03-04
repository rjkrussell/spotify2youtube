"""Inline panel for selecting which Spotify library categories to fetch."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

CATEGORIES = [
    ("playlists", "Playlists"),
    ("liked_tracks", "Liked Songs"),
    ("albums", "Saved Albums"),
    ("artists", "Followed Artists"),
]


class FetchPanel(tk.Frame):
    """Inline panel shown when no library data is cached.

    Displays a 'connections established' message, category checkboxes,
    and a Go button.  Calls *on_go(categories)* with a ``dict[str, bool]``
    when the user clicks Go.
    """

    def __init__(self, parent: tk.Widget, on_go: Callable[[dict[str, bool]], None]):
        super().__init__(parent)
        self._on_go = on_go
        self._vars: dict[str, tk.BooleanVar] = {}
        self._build_ui()

    def _build_ui(self):
        # Centre the content vertically and horizontally
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        inner = tk.Frame(self)
        inner.grid(row=1, column=0)

        # Header
        tk.Label(
            inner,
            text="Connections established",
            font=("TkDefaultFont", 16, "bold"),
            foreground="green",
        ).pack(pady=(0, 4))

        tk.Label(
            inner,
            text="Choose what to sync from Spotify:",
            font=("TkDefaultFont", 11),
        ).pack(pady=(0, 12))

        # Category checkboxes
        cb_frame = tk.Frame(inner)
        cb_frame.pack(anchor="center", pady=(0, 6))

        for key, label in CATEGORIES:
            var = tk.BooleanVar(value=True)
            self._vars[key] = var
            ttk.Checkbutton(cb_frame, text=label, variable=var).pack(anchor="w", padx=20, pady=3)

        # Validation error (hidden until needed)
        self._error_label = tk.Label(inner, text="", foreground="red")
        self._error_label.pack(pady=(4, 0))

        # Go button
        ttk.Button(inner, text="Go", command=self._go).pack(pady=(10, 0))

    def _go(self):
        selected = {key: var.get() for key, var in self._vars.items()}
        if not any(selected.values()):
            self._error_label.config(text="Select at least one category.")
            return
        self._error_label.config(text="")
        self._on_go(selected)

    def reset(self):
        """Re-check all boxes and clear any error text."""
        for var in self._vars.values():
            var.set(True)
        self._error_label.config(text="")
