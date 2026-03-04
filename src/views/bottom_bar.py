"""Bottom bar — dry-run checkbox, transfer button, progress bar, status."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from typing import TYPE_CHECKING

from src.app import SPOTIFY_GREEN, get_colors

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
        # Top row: buttons, controls, progress
        top_row = tk.Frame(self)
        top_row.pack(fill="x")

        self.dry_run_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(top_row, text="Dry Run", variable=self.dry_run_var).pack(side="left", padx=5)

        self.transfer_btn = ttk.Button(top_row, text="Transfer Selected", command=self._start_transfer)
        self.transfer_btn.pack(side="left", padx=5)

        self.cancel_btn = ttk.Button(top_row, text="Cancel", command=self._cancel_transfer, state="disabled")
        self.cancel_btn.pack(side="left", padx=5)

        ttk.Separator(top_row, orient="vertical").pack(side="left", fill="y", padx=8)

        tk.Label(top_row, text="Halt after").pack(side="left")
        self.halt_limit_var = tk.IntVar(value=5)
        ttk.Spinbox(top_row, from_=1, to=999, width=4,
                     textvariable=self.halt_limit_var).pack(side="left", padx=2)
        tk.Label(top_row, text="errors").pack(side="left")

        self.progress = ttk.Progressbar(top_row, mode="determinate", length=200)
        self.progress.pack(side="left", padx=(10, 5))

        self.status_label = tk.Label(top_row, text="", anchor="w")
        self.status_label.pack(side="left", fill="x", expand=True, padx=5)

        # Bottom row: selected/total counts (styled text)
        self.counts_text = tk.Text(self, height=1, borderwidth=0, highlightthickness=0,
                                    wrap="none", state="disabled", cursor="arrow")
        self.counts_text.pack(fill="x", padx=8)
        self.counts_text.tag_configure("label", foreground=SPOTIFY_GREEN,
                                        font=("TkDefaultFont", 11, "bold"))
        self.counts_text.tag_configure("value", font=("Courier", 11))

    def _count_selected(self, selected: dict) -> dict:
        """Return a breakdown of selected items."""
        pl_tracks = sum(len([t for t in p.tracks if t.selected]) for p in selected["playlists"])
        album_tracks = sum(len([t for t in a.tracks if t.selected]) for a in selected["albums"])
        return {
            "playlists": len(selected["playlists"]),
            "playlist_tracks": pl_tracks,
            "liked_tracks": len(selected["liked_tracks"]),
            "albums": len(selected["albums"]),
            "album_tracks": album_tracks,
            "artists": len(selected["artists"]),
        }

    def _start_transfer(self):
        selected = self.main_screen.get_selected_items()
        counts = self._count_selected(selected)

        if all(v == 0 for v in counts.values()):
            messagebox.showinfo("Nothing selected", "Select items in the tree to transfer.")
            return

        # Build summary lines
        lines = []
        if counts["playlists"]:
            lines.append(f"  {counts['playlists']} playlists ({counts['playlist_tracks']} tracks)")
        if counts["liked_tracks"]:
            lines.append(f"  {counts['liked_tracks']} liked tracks")
        if counts["albums"]:
            lines.append(f"  {counts['albums']} albums ({counts['album_tracks']} tracks)")
        if counts["artists"]:
            lines.append(f"  {counts['artists']} artists")
        summary = "\n".join(lines)

        dry_run = self.dry_run_var.get()
        if not dry_run:
            if not messagebox.askyesno("Confirm Transfer",
                                       f"Transfer to YouTube Music:\n{summary}\n\n"
                                       "This will create playlists and like songs on your account."):
                return

        from src.services.youtube_service import YouTubeService
        from src.services.transfer import TransferController

        halt_limit = self.halt_limit_var.get()
        yt_svc = YouTubeService(self.app.credentials_manager.credentials)
        self.controller = TransferController(yt_svc, self.app.state_manager, dry_run=dry_run,
                                             max_consecutive_failures=halt_limit)
        self.controller.start(selected)

        self.app._transfer_active = True
        self.transfer_btn.config(state="disabled")
        self.cancel_btn.config(state="normal")
        self.progress["value"] = 0
        self.status_label.config(text="Starting transfer...")
        self._logged_results = 0
        self._logged_artist_results = 0
        mode = "dry run" if dry_run else "live"
        total_tracks = counts["playlist_tracks"] + counts["liked_tracks"] + counts["album_tracks"]
        self.app.log(f"Transfer started ({mode}): {total_tracks} tracks, {counts['artists']} artists, halt after {halt_limit} errors")

        self._poll()

    def _cancel_transfer(self):
        if self.controller:
            self.controller.cancel()
            self.status_label.config(text="Cancelling...")

    def _poll(self):
        if self.controller is None:
            return

        progress = self.controller.poll()

        # Log new track results
        for r in progress.results[self._logged_results:]:
            ctx = f"[{r.context}] " if r.context else ""
            name = r.track.name
            artist = r.track.artists[0] if r.track.artists else ""
            if r.status.value == "success":
                match_title = r.best_match.get("title", "") if r.best_match else ""
                self.app.log(f"{ctx}Matched: {name} — {artist} -> {match_title}", "success")
            elif r.status.value == "ambiguous":
                self.app.log(f"{ctx}Ambiguous: {name} — {artist} ({len(r.candidates or [])} candidates)", "warning")
            else:
                self.app.log(f"{ctx}Failed: {name} — {artist}" + (f" ({r.error})" if r.error else ""), "error")
        self._logged_results = len(progress.results)

        # Log new artist results
        for ar in progress.artist_results[self._logged_artist_results:]:
            if ar.status.value == "success":
                self.app.log(f"[Artist] Subscribed: {ar.artist.name} -> {ar.channel_title}", "success")
            else:
                self.app.log(f"[Artist] Failed: {ar.artist.name}" + (f" ({ar.error})" if ar.error else ""), "error")
        self._logged_artist_results = len(progress.artist_results)

        if progress.total > 0:
            pct = (progress.completed / progress.total) * 100
            self.progress["value"] = pct
            parts = []
            if progress.total_playlists:
                parts.append(f"{progress.total_playlists} pl ({progress.total_playlist_tracks} tracks)")
            if progress.total_liked:
                parts.append(f"{progress.total_liked} liked")
            if progress.total_album_tracks:
                parts.append(f"{progress.total_album_tracks} album tracks")
            if progress.total_artists:
                parts.append(f"{progress.total_artists} artists")
            totals = " | ".join(parts)
            self.status_label.config(
                text=f"{progress.current_item}  ({progress.completed}/{progress.total})  [{totals}]"
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
        artists_ok = sum(1 for r in progress.artist_results if r.status.value == "success")
        artists_fail = sum(1 for r in progress.artist_results if r.status.value != "success")

        if progress.error:
            self.status_label.config(text=f"Error: {progress.error}")
            self.app.log(f"Transfer error: {progress.error}", "error")
        elif progress.cancelled:
            self.status_label.config(text="Transfer cancelled. Progress saved.")
            self.app.log("Transfer cancelled. Progress saved.")
        else:
            dry_label = " (dry run)" if self.controller.dry_run else ""
            parts = []
            if success or failed or ambiguous:
                parts.append(f"{success} matched, {failed} failed, {ambiguous} ambiguous")
            if artists_ok or artists_fail:
                parts.append(f"{artists_ok} artists subscribed, {artists_fail} artists failed")
            summary = f"Done{dry_label}: {', '.join(parts) if parts else 'no items'}"
            self.status_label.config(text=summary)
            self.app.log(summary, "success")

        # Always show review screen if there are any results
        if progress.results or progress.artist_results:
            from src.views.review_screen import ReviewScreen
            review = ReviewScreen(
                parent=self.app.container,
                app=self.app,
                progress=progress,
                dry_run=self.controller.dry_run,
            )
            self.app.add_screen("review", review)
            self.app.show_screen("review")

    def update_selected_count(self):
        """Update the status label with selected/total counts."""
        if self.controller and not self.controller.progress.done:
            return  # Don't overwrite transfer progress
        lib = self.app.state_manager.library
        selected = self.main_screen.get_selected_items()
        counts = self._count_selected(selected)

        total_pl = len(lib.playlists)
        total_pl_tracks = sum(len(p.tracks) for p in lib.playlists)
        total_liked = len(lib.liked_tracks)
        total_albums = len(lib.albums)
        total_album_tracks = sum(len(a.tracks) for a in lib.albums)
        total_artists = len(lib.artists)

        self.counts_text.configure(state="normal")
        self.counts_text.delete("1.0", "end")

        entries = []
        if total_pl:
            entries.append(("Playlists: ", f"{counts['playlists']}/{total_pl} ({counts['playlist_tracks']}/{total_pl_tracks} tracks)"))
        if total_liked:
            entries.append(("Liked: ", f"{counts['liked_tracks']}/{total_liked}"))
        if total_albums:
            entries.append(("Albums: ", f"{counts['albums']}/{total_albums} ({counts['album_tracks']}/{total_album_tracks} tracks)"))
        if total_artists:
            entries.append(("Artists: ", f"{counts['artists']}/{total_artists}"))

        for i, (label, value) in enumerate(entries):
            if i > 0:
                self.counts_text.insert("end", "    ")
            self.counts_text.insert("end", label, "label")
            self.counts_text.insert("end", value, "value")

        self.counts_text.configure(state="disabled")
