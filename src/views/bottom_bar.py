"""Bottom bar — dry-run checkbox, transfer button, progress bar, status."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.app import App
    from src.views.main_screen import MainScreen


class BottomBar(tk.Frame):
    def __init__(self, parent: tk.Widget, app: App, main_screen: MainScreen):
        super().__init__(parent)
        self.app = app
        self.main_screen = main_screen
        self.controller = None
        self._poll_id = None

        self._build_ui()

    def _build_ui(self):
        # Left: buttons
        btn_frame = tk.Frame(self)
        btn_frame.pack(side="left")

        self.dry_run_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(btn_frame, text="Dry Run", variable=self.dry_run_var).pack(side="left", padx=5)

        self.transfer_btn = ttk.Button(btn_frame, text="Transfer Selected", command=self._start_transfer)
        self.transfer_btn.pack(side="left", padx=5)

        self.cancel_btn = ttk.Button(btn_frame, text="Cancel", command=self._cancel_transfer, state="disabled")
        self.cancel_btn.pack(side="left", padx=5)

        # Right: progress bar + status label
        self.progress = ttk.Progressbar(self, mode="determinate", length=200)
        self.progress.pack(side="left", padx=(10, 5))

        self.status_label = tk.Label(self, text="", anchor="w")
        self.status_label.pack(side="left", fill="x", expand=True, padx=5)

    def _start_transfer(self):
        selected = self.main_screen.get_selected_items()
        total_items = (
            len(selected["playlists"])
            + len(selected["liked_tracks"])
            + len(selected["albums"])
            + len(selected["artists"])
        )
        if total_items == 0:
            messagebox.showinfo("Nothing selected", "Select items in the tree to transfer.")
            return

        dry_run = self.dry_run_var.get()
        if not dry_run:
            if not messagebox.askyesno("Confirm Transfer",
                                       f"Transfer {total_items} selected items to YouTube Music?\n"
                                       "This will create playlists and like songs on your account."):
                return

        from src.services.youtube_service import YouTubeService
        from src.services.transfer import TransferController

        yt_svc = YouTubeService(self.app.credentials_manager.credentials)
        self.controller = TransferController(yt_svc, self.app.state_manager, dry_run=dry_run)
        self.controller.start(selected)

        self.app._transfer_active = True
        self.transfer_btn.config(state="disabled")
        self.cancel_btn.config(state="normal")
        self.progress["value"] = 0
        self.status_label.config(text="Starting transfer...")

        self._poll()

    def _cancel_transfer(self):
        if self.controller:
            self.controller.cancel()
            self.status_label.config(text="Cancelling...")

    def _poll(self):
        if self.controller is None:
            return

        progress = self.controller.poll()

        if progress.total > 0:
            pct = (progress.completed / progress.total) * 100
            self.progress["value"] = pct
            self.status_label.config(
                text=f"{progress.current_item}  ({progress.completed}/{progress.total})"
            )

        if progress.done:
            self._on_transfer_done(progress)
            return

        self._poll_id = self.after(100, self._poll)

    def _on_transfer_done(self, progress):
        self.app._transfer_active = False
        self.transfer_btn.config(state="normal")
        self.cancel_btn.config(state="disabled")

        # Count results
        success = sum(1 for r in progress.results if r.status.value == "success")
        failed = len(progress.failed_tracks)
        ambiguous = len(progress.ambiguous_tracks)

        if progress.error:
            self.status_label.config(text=f"Error: {progress.error}")
        elif progress.cancelled:
            self.status_label.config(text="Transfer cancelled. Progress saved.")
        else:
            dry_label = " (dry run)" if self.controller.dry_run else ""
            self.status_label.config(
                text=f"Done{dry_label}: {success} matched, {failed} failed, {ambiguous} ambiguous"
            )

        # Always show review screen if there are any results
        if progress.results:
            from src.views.review_screen import ReviewScreen
            review = ReviewScreen(
                parent=self.app.container,
                app=self.app,
                progress=progress,
                dry_run=self.controller.dry_run,
            )
            self.app.add_screen("review", review)
            self.app.show_screen("review")
