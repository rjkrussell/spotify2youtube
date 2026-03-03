"""Root application window and screen management."""

from __future__ import annotations

import datetime
import tkinter as tk
from tkinter import ttk, messagebox

from src.models.credentials import CredentialsManager
from src.models.state import StateManager


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("spotify2youtube.py")
        self.geometry("1000x700")
        self.minsize(800, 550)

        self._transfer_active = False

        self.credentials_manager = CredentialsManager()
        self.credentials_manager.load()

        self.state_manager = StateManager()
        self.state_manager.load()

        # Vertical paned window: screens on top, log on bottom
        self._paned = ttk.PanedWindow(self, orient="vertical")
        self._paned.pack(fill="both", expand=True)

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

    def _build_log_panel(self):
        log_frame = ttk.LabelFrame(self._paned, text="Log", padding=4)
        self._paned.add(log_frame, weight=0)

        scrollbar = ttk.Scrollbar(log_frame, orient="vertical")
        scrollbar.pack(side="right", fill="y")

        self._log_text = tk.Text(
            log_frame, height=4, wrap="word", state="disabled",
            borderwidth=0, highlightthickness=0, font=("TkFixedFont", 10),
        )
        self._log_text.pack(fill="both", expand=True)
        self._log_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.configure(command=self._log_text.yview)

        self._log_text.tag_configure("timestamp", foreground="gray")
        self._log_text.tag_configure("error", foreground="red")
        self._log_text.tag_configure("success", foreground="green")
        self._log_text.tag_configure("info", foreground="blue")

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
