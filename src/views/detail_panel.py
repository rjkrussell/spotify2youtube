"""Detail panel — contextual per-item configuration controls."""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

from src.models.library import (
    Track, Playlist, Album, Artist,
    MatchingPreference,
)

if TYPE_CHECKING:
    from src.app import App
    from src.views.main_screen import MainScreen


class DetailPanel(tk.Frame):
    def __init__(self, parent: tk.Widget, app: App, main_screen: MainScreen):
        super().__init__(parent)
        self.app = app
        self.main_screen = main_screen
        self.current_item_id: str | None = None
        self.current_obj = None
        self._yt_playlists: list[dict] | None = None
        self._yt_playlists_loading = False
        self._save_job: str | None = None  # For debounced saves

        self._placeholder = tk.Label(self, text="Select an item to see details",
                                     anchor="center", foreground="gray")
        self._placeholder.pack(expand=True)

    def show_item(self, item_id: str, obj, transfer_action: str = ""):
        """Show the appropriate detail panel for the given object."""
        self.current_item_id = item_id
        self.current_obj = obj

        # Clear existing content
        for w in self.winfo_children():
            w.destroy()

        # Show transfer action label at the top (categories handle it inline)
        if transfer_action and not isinstance(obj, list):
            from src.app import get_colors
            action_label = tk.Label(self, text=transfer_action,
                                    foreground=get_colors()["action"],
                                    font=("TkDefaultFont", 12, "italic"))
            action_label.pack(anchor="w", padx=10, pady=(5, 0))

        if isinstance(obj, Playlist):
            self._show_playlist(obj)
        elif isinstance(obj, Album):
            self._show_album(obj)
        elif isinstance(obj, Artist):
            self._show_artist(obj)
        elif isinstance(obj, Track):
            self._show_track(obj)
        elif isinstance(obj, list):
            self._show_category(obj, transfer_action)

    # --- Playlist detail ---
    def _show_playlist(self, pl: Playlist):
        header = tk.Frame(self)
        header.pack(fill="x", padx=10, pady=5)

        tk.Label(header, text="Playlist", font=("TkDefaultFont", 12, "bold")).pack(anchor="w")
        tk.Label(header, text=pl.name, font=("TkDefaultFont", 11)).pack(anchor="w")
        if pl.description:
            tk.Label(header, text=pl.description, wraplength=400, foreground="gray").pack(anchor="w")

        config = tk.Frame(self)
        config.pack(fill="x", padx=10, pady=5)

        # Rename
        tk.Label(config, text="Rename to:").grid(row=0, column=0, sticky="w", pady=2)
        rename_var = tk.StringVar(value=pl.rename)
        rename_entry = ttk.Entry(config, textvariable=rename_var, width=40)
        rename_entry.grid(row=0, column=1, padx=5, pady=2)
        rename_var.trace_add("write", lambda *_: self._debounced_rename(pl, rename_var.get()))

        # Matching preference
        tk.Label(config, text="Matching:").grid(row=1, column=0, sticky="w", pady=2)
        match_var = tk.StringVar(value=pl.matching_pref.value)
        match_combo = ttk.Combobox(config, textvariable=match_var, values=["fuzzy", "strict", "manual"],
                                   state="readonly", width=15)
        match_combo.grid(row=1, column=1, sticky="w", padx=5, pady=2)
        match_var.trace_add("write", lambda *_: self._update_matching_pref(pl, match_var.get()))

        # Merge target
        tk.Label(config, text="Merge into YT playlist:").grid(row=2, column=0, sticky="w", pady=2)
        self._merge_var = tk.StringVar(value="(create new)")
        self._merge_combo = ttk.Combobox(config, textvariable=self._merge_var, width=40, state="readonly")
        self._merge_combo.grid(row=2, column=1, padx=5, pady=2)
        self._merge_combo["values"] = ["(create new)", "Loading..."]
        if not pl.merge_into_yt_id:
            self._merge_combo.set("(create new)")
        self._merge_var.trace_add("write", lambda *_: self._update_merge(pl, self._merge_var.get()))

        # Load YT playlists in background
        self._load_yt_playlists_async(pl)

        # Track list with reorder
        tk.Label(self, text="Tracks:", font=("TkDefaultFont", 10, "bold")).pack(anchor="w", padx=10, pady=(10, 0))

        track_frame = tk.Frame(self)
        track_frame.pack(fill="both", expand=True, padx=10, pady=5)

        scrollbar = ttk.Scrollbar(track_frame, orient="vertical")
        scrollbar.pack(side="right", fill="y")

        self._track_listbox = tk.Listbox(track_frame, selectmode="single", yscrollcommand=scrollbar.set)
        self._track_listbox.pack(fill="both", expand=True)
        scrollbar.config(command=self._track_listbox.yview)

        for t in pl.tracks:
            prefix = "\u2611" if t.selected else "\u2610"
            self._track_listbox.insert(tk.END, f"{prefix} {t.name} — {', '.join(t.artists)}")

        self._track_listbox.bind("<Double-Button-1>", lambda e: self._toggle_track_in_list(pl))

        btn_frame = tk.Frame(self)
        btn_frame.pack(fill="x", padx=10, pady=5)
        ttk.Button(btn_frame, text="Move Up", command=lambda: self._move_track(pl, -1)).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Move Down", command=lambda: self._move_track(pl, 1)).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Toggle Selected", command=lambda: self._toggle_track_in_list(pl)).pack(side="left", padx=2)

    # --- Album detail ---
    def _show_album(self, album: Album):
        header = tk.Frame(self)
        header.pack(fill="x", padx=10, pady=5)

        tk.Label(header, text="Album", font=("TkDefaultFont", 12, "bold")).pack(anchor="w")
        tk.Label(header, text=f"{album.name} — {', '.join(album.artists)}", font=("TkDefaultFont", 11)).pack(anchor="w")

        config = tk.Frame(self)
        config.pack(fill="x", padx=10, pady=5)

        tk.Label(config, text="Matching:").grid(row=0, column=0, sticky="w", pady=2)
        match_var = tk.StringVar(value=album.matching_pref.value)
        match_combo = ttk.Combobox(config, textvariable=match_var, values=["fuzzy", "strict", "manual"],
                                   state="readonly", width=15)
        match_combo.grid(row=0, column=1, sticky="w", padx=5, pady=2)
        match_var.trace_add("write", lambda *_: self._update_matching_pref(album, match_var.get()))

        tk.Label(self, text="Tracks:", font=("TkDefaultFont", 10, "bold")).pack(anchor="w", padx=10, pady=(10, 0))

        track_frame = tk.Frame(self)
        track_frame.pack(fill="both", expand=True, padx=10, pady=5)

        scrollbar = ttk.Scrollbar(track_frame, orient="vertical")
        scrollbar.pack(side="right", fill="y")

        self._track_listbox = tk.Listbox(track_frame, selectmode="single", yscrollcommand=scrollbar.set)
        self._track_listbox.pack(fill="both", expand=True)
        scrollbar.config(command=self._track_listbox.yview)

        for t in album.tracks:
            prefix = "\u2611" if t.selected else "\u2610"
            self._track_listbox.insert(tk.END, f"{prefix} {t.name} — {', '.join(t.artists)}")

        self._track_listbox.bind("<Double-Button-1>", lambda e: self._toggle_track_in_list(album))

    # --- Artist detail ---
    def _show_artist(self, artist: Artist):
        header = tk.Frame(self)
        header.pack(fill="x", padx=10, pady=5)

        tk.Label(header, text="Artist", font=("TkDefaultFont", 12, "bold")).pack(anchor="w")
        tk.Label(header, text=artist.name, font=("TkDefaultFont", 14)).pack(anchor="w")
        if artist.genres:
            tk.Label(header, text=f"Genres: {', '.join(artist.genres)}", foreground="gray").pack(anchor="w")

        tk.Label(header, text=f"Subscribe: {'Yes' if artist.selected else 'No'}").pack(anchor="w", pady=5)

    # --- Track detail ---
    def _show_track(self, track: Track):
        header = tk.Frame(self)
        header.pack(fill="x", padx=10, pady=5)

        tk.Label(header, text="Track", font=("TkDefaultFont", 12, "bold")).pack(anchor="w")
        tk.Label(header, text=track.name, font=("TkDefaultFont", 11)).pack(anchor="w")
        tk.Label(header, text=f"Artists: {', '.join(track.artists)}").pack(anchor="w")
        tk.Label(header, text=f"Album: {track.album}").pack(anchor="w")
        mins, secs = divmod(track.duration_ms // 1000, 60)
        tk.Label(header, text=f"Duration: {mins}:{secs:02d}").pack(anchor="w")

        config = tk.Frame(self)
        config.pack(fill="x", padx=10, pady=5)

        tk.Label(config, text="Matching:").grid(row=0, column=0, sticky="w", pady=2)
        match_var = tk.StringVar(value=track.matching_pref.value)
        match_combo = ttk.Combobox(config, textvariable=match_var, values=["fuzzy", "strict", "manual"],
                                   state="readonly", width=15)
        match_combo.grid(row=0, column=1, sticky="w", padx=5, pady=2)
        match_var.trace_add("write", lambda *_: self._update_matching_pref(track, match_var.get()))

        if track.yt_video_id:
            tk.Label(config, text=f"Matched: {track.yt_video_id}", foreground="green").grid(row=1, column=0, columnspan=2, sticky="w", pady=2)

    # --- Category header ---
    def _show_category(self, items: list, transfer_action: str = ""):
        # Single compact header row — matches LHS "● Spotify Library" header padding
        header = tk.Frame(self)
        header.pack(fill="x")

        # Determine category label
        if items and isinstance(items[0], Playlist):
            label = f"\u25b6 Playlists ({len(items)})"
        elif items and isinstance(items[0], Album):
            label = f"\u25b6 Albums ({len(items)})"
        elif items and isinstance(items[0], Artist):
            label = f"\u25b6 Artists ({len(items)})"
        elif items and isinstance(items[0], Track):
            label = f"\u25b6 Liked Songs ({len(items)})"
        else:
            label = f"\u25b6 {len(items)} items"

        from src.app import YOUTUBE_RED, get_colors
        tk.Label(header, text=label, font=("TkDefaultFont", 11, "bold"),
                 foreground=YOUTUBE_RED).pack(side="left", padx=5, pady=2)

        if transfer_action:
            tk.Label(header, text=transfer_action,
                     foreground=get_colors()["action"],
                     font=("TkDefaultFont", 10, "italic")).pack(side="left")

        # Matching preference on the right side of the same row
        match_var = tk.StringVar(value="fuzzy")
        match_combo = ttk.Combobox(header, textvariable=match_var, values=["fuzzy", "strict", "manual"],
                                   state="readonly", width=10)
        match_combo.pack(side="right", padx=5, pady=2)
        tk.Label(header, text="Matching:").pack(side="right", pady=2)
        match_var.trace_add("write", lambda *_: self._bulk_set_matching(items, match_var.get()))

        # Show items in an expandable tree
        if not items:
            return

        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True)

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical")
        scrollbar.pack(side="right", fill="y")

        cat_tree = ttk.Treeview(tree_frame, show="tree", yscrollcommand=scrollbar.set)
        cat_tree.pack(fill="both", expand=True)
        scrollbar.config(command=cat_tree.yview)

        def _prefix(selected: bool) -> str:
            return "\u2611" if selected else "\u2610"

        if isinstance(items[0], Playlist):
            for pl in items:
                pl_id = cat_tree.insert("", "end",
                    text=f"{_prefix(pl.selected)} {pl.display_name()} ({pl.track_count} tracks)")
                for t in pl.tracks:
                    cat_tree.insert(pl_id, "end",
                        text=f"{_prefix(t.selected)} {t.name} \u2014 {', '.join(t.artists)}")
        elif isinstance(items[0], Album):
            for alb in items:
                alb_id = cat_tree.insert("", "end",
                    text=f"{_prefix(alb.selected)} {alb.name} \u2014 {', '.join(alb.artists)} ({alb.track_count} tracks)")
                for t in alb.tracks:
                    cat_tree.insert(alb_id, "end",
                        text=f"{_prefix(t.selected)} {t.name} \u2014 {', '.join(t.artists)}")
        elif isinstance(items[0], Artist):
            for art in items:
                genres = f" ({', '.join(art.genres)})" if art.genres else ""
                cat_tree.insert("", "end",
                    text=f"{_prefix(art.selected)} {art.name}{genres}")
        elif isinstance(items[0], Track):
            for t in items:
                cat_tree.insert("", "end",
                    text=f"{_prefix(t.selected)} {t.name} \u2014 {', '.join(t.artists)}")

    # --- Helper methods ---
    def _debounced_rename(self, pl: Playlist, name: str):
        """Update rename with a 500ms debounce to avoid saving on every keystroke."""
        pl.rename = name.strip()
        if self._save_job is not None:
            self.after_cancel(self._save_job)
        self._save_job = self.after(500, self._auto_save)

    def _update_matching_pref(self, obj, value: str):
        pref = MatchingPreference(value)
        obj.matching_pref = pref
        self._auto_save()

    def _update_merge(self, pl: Playlist, value: str):
        if value in ("(create new)", "Loading..."):
            pl.merge_into_yt_id = None
        else:
            if self._yt_playlists:
                for ytp in self._yt_playlists:
                    if ytp.get("title") == value:
                        pl.merge_into_yt_id = ytp.get("playlistId")
                        break
        self._auto_save()

    def _bulk_set_matching(self, items: list, value: str):
        pref = MatchingPreference(value)
        for item in items:
            if hasattr(item, "matching_pref"):
                item.matching_pref = pref
        self._auto_save()

    def _toggle_track_in_list(self, container):
        """Toggle selected track in the track listbox."""
        sel = self._track_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        track = container.tracks[idx]
        track.selected = not track.selected
        prefix = "\u2611" if track.selected else "\u2610"
        self._track_listbox.delete(idx)
        self._track_listbox.insert(idx, f"{prefix} {track.name} — {', '.join(track.artists)}")
        self._track_listbox.selection_set(idx)
        self._auto_save()

    def _move_track(self, pl: Playlist, direction: int):
        """Move the selected track up (-1) or down (+1)."""
        sel = self._track_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        new_idx = idx + direction
        if new_idx < 0 or new_idx >= len(pl.tracks):
            return

        pl.tracks[idx], pl.tracks[new_idx] = pl.tracks[new_idx], pl.tracks[idx]

        text = self._track_listbox.get(idx)
        self._track_listbox.delete(idx)
        self._track_listbox.insert(new_idx, text)
        self._track_listbox.selection_set(new_idx)
        self._auto_save()

    def _load_yt_playlists_async(self, pl: Playlist):
        """Load YT Music playlists in a background thread for the merge dropdown."""
        if self._yt_playlists is not None:
            # Already cached — populate immediately
            names = ["(create new)"] + [p.get("title", "") for p in self._yt_playlists]
            self._merge_combo["values"] = names
            if pl.merge_into_yt_id:
                for ytp in self._yt_playlists:
                    if ytp.get("playlistId") == pl.merge_into_yt_id:
                        self._merge_combo.set(ytp.get("title", ""))
                        break
            return

        if self._yt_playlists_loading:
            return
        self._yt_playlists_loading = True

        def _fetch():
            try:
                from src.services.youtube_service import YouTubeService
                svc = YouTubeService(self.app.credentials_manager.credentials)
                playlists = svc.get_library_playlists()
                self.after(0, lambda: self._on_yt_playlists_loaded(playlists, pl))
            except Exception:
                self.after(0, lambda: self._on_yt_playlists_loaded([], pl))

        threading.Thread(target=_fetch, daemon=True).start()

    def _on_yt_playlists_loaded(self, playlists: list[dict], pl: Playlist):
        """Callback when YT playlists are fetched."""
        self._yt_playlists = playlists
        self._yt_playlists_loading = False
        if hasattr(self, "_merge_combo") and self._merge_combo.winfo_exists():
            names = ["(create new)"] + [p.get("title", "") for p in playlists]
            self._merge_combo["values"] = names
            if pl.merge_into_yt_id:
                for ytp in playlists:
                    if ytp.get("playlistId") == pl.merge_into_yt_id:
                        self._merge_combo.set(ytp.get("title", ""))
                        break

    def _auto_save(self):
        self._save_job = None
        self.app.state_manager.save()
