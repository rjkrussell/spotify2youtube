"""Root application window and screen management."""

from __future__ import annotations

import datetime
import json
import os
import tkinter as tk
from tkinter import ttk, messagebox

import sv_ttk

from src.models.credentials import CredentialsManager, DATA_DIR
from src.models.state import StateManager

# Brand colors (constant across themes)
SPOTIFY_GREEN = "#1DB954"
YOUTUBE_RED = "#FF0000"

# Theme-dependent color palettes
THEME_COLORS = {
    "dark": {
        "bg": "#1c1c1c",
        "fg": "#cccccc",
        "fg_muted": "#777777",
        "separator": "#aaaaaa",
        "error": "#ff6b6b",
        "success": SPOTIFY_GREEN,
        "info": "#6baaff",
        "warning": "#e8a838",
        "guide_bg": "#2a2a2a",
        "guide_fg": "#cccccc",
        "guide_title": "#ffffff",
        "unchecked": "#666666",
        "action": "#6baaff",
        "summary_fail": "#ff6b6b",
        "summary_skip": "#777777",
        "grad_start": "#1DB954",
        "grad_end": "#FF0000",
    },
    "light": {
        "bg": "#ffffff",
        "fg": "#222222",
        "fg_muted": "#999999",
        "separator": "#666666",
        "error": "#d32f2f",
        "success": "#1a873a",
        "info": "#1565c0",
        "warning": "#e07800",
        "guide_bg": "#f5f5f5",
        "guide_fg": "#333333",
        "guide_title": "#111111",
        "unchecked": "#aaaaaa",
        "action": "#1565c0",
        "summary_fail": "#d32f2f",
        "summary_skip": "#999999",
        "grad_start": "#1DB954",
        "grad_end": "#FF0000",
    },
}

MOCK_MODE = os.environ.get("YOUTUBE_MOCK") == "1"
YT_LABEL = "YouTube Music [mock]" if MOCK_MODE else "YouTube Music"

PREFS_PATH = os.path.join(DATA_DIR, "preferences.json")


def get_colors() -> dict[str, str]:
    """Return the color palette for the current theme."""
    return THEME_COLORS.get(sv_ttk.get_theme(), THEME_COLORS["dark"])


class GradientBar(tk.Canvas):
    """Thin horizontal gradient strip from Spotify green to YouTube blue."""

    BANDS = 80

    def __init__(self, parent, height=4, **kwargs):
        kwargs.setdefault("highlightthickness", 0)
        kwargs.setdefault("borderwidth", 0)
        kwargs.setdefault("height", height)
        super().__init__(parent, **kwargs)
        self._drawn_w = 0
        self.bind("<Configure>", self._on_configure)

    def _on_configure(self, event=None):
        w = self.winfo_width()
        if w == self._drawn_w or w < 2:
            return
        self._drawn_w = w
        self._draw(w)

    def _draw(self, width):
        self.delete("grad")
        h = self.winfo_height()
        c = get_colors()
        r1, g1, b1 = _hex_to_rgb(c["grad_start"])
        r2, g2, b2 = _hex_to_rgb(c["grad_end"])
        band_w = max(width / self.BANDS, 1)
        for i in range(self.BANDS):
            t = i / max(self.BANDS - 1, 1)
            r = int(r1 + (r2 - r1) * t)
            g = int(g1 + (g2 - g1) * t)
            b = int(b1 + (b2 - b1) * t)
            x = int(i * band_w)
            self.create_rectangle(
                x, 0, int(x + band_w) + 1, h,
                fill=f"#{r:02x}{g:02x}{b:02x}", outline="", tags="grad",
            )

    def refresh(self):
        """Redraw with current theme colors."""
        self._drawn_w = 0
        self._on_configure()


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    return int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)


def _fix_paned_cursor(paned: ttk.PanedWindow):
    """Work around macOS ttk PanedWindow sticky-cursor bug.

    When the mouse leaves the sash area (including into child panes),
    the resize cursor lingers. Fix by resetting the cursor on the paned
    widget whenever the mouse enters any child pane or leaves the paned.
    """
    def _reset_cursor(event=None):
        paned.configure(cursor="")

    paned.bind("<Leave>", _reset_cursor)

    # Also reset when entering any child pane (scheduled after idle
    # so child widgets exist when this is called)
    def _bind_children():
        for pane_id in paned.panes():
            try:
                child = paned.nametowidget(pane_id)
                child.bind("<Enter>", _reset_cursor)
            except Exception:
                pass

    paned.after(100, _bind_children)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"\u266b Spotify \u2192 {YT_LABEL}")
        self.geometry("1100x750")
        self.minsize(900, 600)

        # Load saved theme preference, default to dark
        self._theme = self._load_theme_pref()
        sv_ttk.set_theme(self._theme)

        self._transfer_active = False
        self._theme_listeners: list = []

        self.credentials_manager = CredentialsManager()
        self.credentials_manager.load()

        self.state_manager = StateManager()
        self.state_manager.load()

        # Vertical paned window: screens on top, log on bottom
        self._paned = ttk.PanedWindow(self, orient="vertical")
        self._paned.pack(fill="both", expand=True)
        _fix_paned_cursor(self._paned)

        # Container for stacked screens
        self.container = tk.Frame(self._paned)
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)
        self._paned.add(self.container, weight=1)

        self.screens: dict[str, tk.Frame] = {}

        # Log panel (always visible, below screens)
        self._build_log_panel()

        # Close-during-transfer warning
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Only build the screen we actually need at startup
        if self.credentials_manager.credentials.has_spotify() and self.credentials_manager.credentials.has_youtube():
            self.show_screen("main")
        else:
            self.show_screen("settings")

        # Position the sash so the log panel starts small (~100px)
        self.after(50, lambda: self._paned.sashpos(0, self.winfo_height() - 100))

    def _load_theme_pref(self) -> str:
        try:
            with open(PREFS_PATH) as f:
                return json.load(f).get("theme", "dark")
        except (FileNotFoundError, json.JSONDecodeError):
            return "dark"

    def _save_theme_pref(self):
        try:
            with open(PREFS_PATH) as f:
                prefs = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            prefs = {}
        prefs["theme"] = self._theme
        with open(PREFS_PATH, "w") as f:
            json.dump(prefs, f, indent=2)

    def toggle_theme(self):
        """Switch between dark and light themes."""
        self._theme = "light" if self._theme == "dark" else "dark"
        sv_ttk.set_theme(self._theme)
        self._apply_theme_colors()
        self._save_theme_pref()

    @property
    def is_dark(self) -> bool:
        return self._theme == "dark"

    def _apply_theme_colors(self):
        """Update all theme-dependent widgets."""
        c = get_colors()
        self._log_text.configure(background=c["bg"], foreground=c["fg"],
                                 insertbackground=c["fg"])
        self._log_text.tag_configure("timestamp", foreground=c["fg_muted"])
        self._log_text.tag_configure("error", foreground=c["error"])
        self._log_text.tag_configure("success", foreground=c["success"])
        self._log_text.tag_configure("info", foreground=c["info"])
        # Notify all registered listeners
        for listener in self._theme_listeners:
            try:
                listener()
            except Exception:
                pass

    def on_theme_change(self, callback):
        """Register a callback to be notified on theme changes."""
        self._theme_listeners.append(callback)

    def _build_log_panel(self):
        log_frame = ttk.LabelFrame(self._paned, text="Log", padding=4)
        self._paned.add(log_frame, weight=0)

        scrollbar = ttk.Scrollbar(log_frame, orient="vertical")
        scrollbar.pack(side="right", fill="y")

        c = get_colors()
        self._log_text = tk.Text(
            log_frame, height=4, wrap="word", state="disabled",
            borderwidth=0, highlightthickness=0, font=("TkFixedFont", 10),
            background=c["bg"], foreground=c["fg"], insertbackground=c["fg"],
        )
        self._log_text.pack(fill="both", expand=True)
        self._log_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.configure(command=self._log_text.yview)

        self._log_text.tag_configure("timestamp", foreground=c["fg_muted"])
        self._log_text.tag_configure("error", foreground=c["error"])
        self._log_text.tag_configure("success", foreground=c["success"])
        self._log_text.tag_configure("info", foreground=c["info"])

    def log(self, message: str, level: str = "info"):
        """Append a timestamped message to the log panel.

        level: 'info', 'success', 'error', or 'timestamp' (for tag color).
        """
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self._log_text.configure(state="normal")
        self._log_text.insert("end", f"[{timestamp}] ", "timestamp")
        self._log_text.insert("end", f"{message}\n", level if level != "info" else "")
        self._log_text.configure(state="disabled")
        self._log_text.see("end")


    def _get_or_create_screen(self, name: str) -> tk.Frame:
        """Lazily create screens on first access."""
        if name not in self.screens:
            if name == "settings":
                from src.views.settings_screen import SettingsScreen
                screen = SettingsScreen(parent=self.container, app=self)
            elif name == "main":
                from src.views.main_screen import MainScreen
                screen = MainScreen(parent=self.container, app=self)
            else:
                raise ValueError(f"Unknown screen: {name}")
            screen.grid(row=0, column=0, sticky="nsew")
            self.screens[name] = screen
        return self.screens[name]

    def show_screen(self, name: str):
        screen = self._get_or_create_screen(name)
        if hasattr(screen, "on_show"):
            screen.on_show()
        screen.tkraise()

    def add_screen(self, name: str, screen: tk.Frame):
        screen.grid(row=0, column=0, sticky="nsew")
        self.screens[name] = screen

    def _on_close(self):
        if self._transfer_active:
            if not messagebox.askyesno(
                "Transfer in Progress",
                "A transfer is currently running. Progress has been saved.\n\n"
                "Are you sure you want to quit?",
            ):
                return
        self.destroy()
