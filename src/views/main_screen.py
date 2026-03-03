"""Main screen — library tree, detail panel, and bottom bar."""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

from src.models.library import (
    Track, Playlist, Album, Artist, SpotifyLibrary,
    MatchingPreference, TransferStatus,
)
from src.views.library_tree import CheckboxTreeview

if TYPE_CHECKING:
    from src.app import App


class MainScreen(tk.Frame):
    def __init__(self, parent: tk.Widget, app: App):
        super().__init__(parent)
        self.app = app

        # Map tree item IDs to model objects
        self.item_map: dict[str, object] = {}
        # Category header IDs
        self.category_ids: dict[str, str] = {}

        self._fetch_in_progress = False
        self._cancel_event = threading.Event()

        self._build_ui()

    def _build_ui(self):
        # Top bar
        top = tk.Frame(self)
        top.pack(fill="x", padx=5, pady=5)

        tk.Label(top, text="spotify2youtube.py", font=("TkDefaultFont", 14, "bold")).pack(side="left")

        ttk.Button(top, text="Settings", command=lambda: self.app.show_screen("settings")).pack(side="right")
        self._refresh_btn = ttk.Button(top, text="Refresh Library", command=self._show_fetch_panel)
        self._refresh_btn.pack(side="right", padx=5)

        # --- Inline fetch panel (shown when no data) ---
        from src.views.fetch_dialog import FetchPanel
        self._fetch_panel = FetchPanel(self, on_go=self._on_go)

        # --- Paned window: tree (left) + detail (right) ---
        self.paned = ttk.PanedWindow(self, orient="horizontal")

        # Left: tree with scrollbar
        tree_frame = tk.Frame(self.paned)
        self.paned.add(tree_frame, weight=1)

        tree_scroll = ttk.Scrollbar(tree_frame, orient="vertical")
        tree_scroll.pack(side="right", fill="y")

        self.tree = CheckboxTreeview(tree_frame, yscrollcommand=tree_scroll.set)
        self.tree.pack(fill="both", expand=True)
        tree_scroll.config(command=self.tree.yview)

        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<<CheckChanged>>", self._on_check_changed)

        # Right: detail panel
        from src.views.detail_panel import DetailPanel
        self.detail_panel = DetailPanel(self.paned, app=self.app, main_screen=self)
        self.paned.add(self.detail_panel, weight=2)

        # Bottom bar
        from src.views.bottom_bar import BottomBar
        self.bottom_bar = BottomBar(self, app=self.app, main_screen=self)
        self.bottom_bar.pack(fill="x", padx=5, pady=5)

        # Loading progress bar (for library fetch)
        self._loading_frame = tk.Frame(self)
        self.status_label = tk.Label(self._loading_frame, text="", anchor="w")
        self.status_label.pack(side="left")
        self.progress = ttk.Progressbar(self._loading_frame, mode="indeterminate", length=200)
        self._cancel_btn = ttk.Button(self._loading_frame, text="Cancel", command=self._cancel_fetch)

    # ------------------------------------------------------------------
    # Show / hide helpers
    # ------------------------------------------------------------------

    def _show_fetch_panel_ui(self):
        """Show the inline fetch panel, hide the tree/detail paned area."""
        self.paned.pack_forget()
        self._fetch_panel.reset()
        self._fetch_panel.pack(fill="both", expand=True, padx=5, pady=5)

    def _show_paned_ui(self):
        """Show the tree/detail paned area, hide the fetch panel."""
        self._fetch_panel.pack_forget()
        self.paned.pack(fill="both", expand=True, padx=5, pady=5)

    # ------------------------------------------------------------------
    # Screen lifecycle
    # ------------------------------------------------------------------

    def on_show(self):
        """Called when this screen is raised."""
        lib = self.app.state_manager.library
        has_data = lib.playlists or lib.liked_tracks or lib.albums or lib.artists
        if has_data:
            self._show_paned_ui()
            self._populate_tree(lib)
        elif not self._fetch_in_progress:
            self._show_fetch_panel_ui()
        # If fetch is in progress, leave the current UI (progress bar) alone.

    def _show_fetch_panel(self):
        """Refresh Library button handler — show the panel for a new selection."""
        if self._fetch_in_progress:
            return
        self._show_fetch_panel_ui()

    def _on_go(self, categories: dict[str, bool]):
        """Callback from FetchPanel when the user clicks Go."""
        self._show_paned_ui()
        self._fetch_library(categories)

    # ------------------------------------------------------------------
    # Fetch logic
    # ------------------------------------------------------------------

    def _fetch_library(self, categories: dict[str, bool] | None = None):
        """Fetch the Spotify library in a background thread."""
        if self._fetch_in_progress:
            return
        if categories is None:
            categories = {"playlists": True, "liked_tracks": True, "albums": True, "artists": True}

        self._fetch_in_progress = True
        self._cancel_event.clear()

        names = [k.replace("_", " ").title() for k, v in categories.items() if v]
        status_text = f"Fetching: {', '.join(names)}..."

        self._loading_frame.pack(fill="x", padx=5, pady=2)
        self.status_label.config(text=status_text)
        self.progress.pack(side="right", padx=5)
        self._cancel_btn.pack(side="right", padx=(5, 0))
        self.progress.start(10)
        self.app.log(status_text)

        def _run():
            try:
                from src.services.spotify_service import SpotifyService
                svc = SpotifyService(self.app.credentials_manager.credentials)
                new_data = self._fetch_all(svc, categories)

                if self._cancel_event.is_set():
                    return

                self._merge_library(new_data, categories)
                self.app.state_manager.save()
                library = self.app.state_manager.library
                self.after(0, lambda: self._on_fetch_done(library))
            except Exception as e:
                if self._cancel_event.is_set():
                    return
                msg = str(e)
                self.after(0, lambda: self._on_fetch_error(msg))

        threading.Thread(target=_run, daemon=True).start()

    def _fetch_all(self, svc, categories: dict[str, bool]) -> SpotifyLibrary:
        """Fetch only the selected categories from Spotify."""
        library = SpotifyLibrary()

        if self._cancel_event.is_set():
            return library

        if categories.get("playlists"):
            raw_playlists = svc.get_playlists()
            for rp in raw_playlists:
                if self._cancel_event.is_set():
                    return library
                tracks_raw = svc.get_playlist_tracks(rp["id"])
                tracks = [self._raw_track_to_model(t) for t in tracks_raw]
                library.playlists.append(Playlist(
                    spotify_id=rp["id"],
                    name=rp["name"],
                    description=rp.get("description") or "",
                    track_count=rp["tracks"]["total"],
                    tracks=tracks,
                ))

        if self._cancel_event.is_set():
            return library

        if categories.get("liked_tracks"):
            liked_raw = svc.get_liked_tracks()
            library.liked_tracks = [self._raw_track_to_model(t) for t in liked_raw]

        if self._cancel_event.is_set():
            return library

        if categories.get("albums"):
            albums_raw = svc.get_saved_albums()
            for ra in albums_raw:
                if self._cancel_event.is_set():
                    return library
                album_tracks_raw = svc.get_album_tracks(ra["id"])
                tracks = []
                for at in album_tracks_raw:
                    tracks.append(Track(
                        spotify_id=at["id"],
                        name=at["name"],
                        artists=[a["name"] for a in at["artists"]],
                        album=ra["name"],
                        duration_ms=at["duration_ms"],
                    ))
                library.albums.append(Album(
                    spotify_id=ra["id"],
                    name=ra["name"],
                    artists=[a["name"] for a in ra["artists"]],
                    track_count=ra["total_tracks"],
                    tracks=tracks,
                ))

        if self._cancel_event.is_set():
            return library

        if categories.get("artists"):
            artists_raw = svc.get_followed_artists()
            for ra in artists_raw:
                library.artists.append(Artist(
                    spotify_id=ra["id"],
                    name=ra["name"],
                    genres=ra.get("genres", []),
                ))

        return library

    def _merge_library(self, new_data: SpotifyLibrary, categories: dict[str, bool]):
        """Overwrite only the categories that were fetched, preserving the rest."""
        lib = self.app.state_manager.library
        if categories.get("playlists"):
            lib.playlists = new_data.playlists
        if categories.get("liked_tracks"):
            lib.liked_tracks = new_data.liked_tracks
        if categories.get("albums"):
            lib.albums = new_data.albums
        if categories.get("artists"):
            lib.artists = new_data.artists

    @staticmethod
    def _raw_track_to_model(raw: dict) -> Track:
        return Track(
            spotify_id=raw["id"],
            name=raw["name"],
            artists=[a["name"] for a in raw["artists"]],
            album=raw.get("album", {}).get("name", ""),
            duration_ms=raw["duration_ms"],
        )

    # ------------------------------------------------------------------
    # Fetch callbacks
    # ------------------------------------------------------------------

    def _cancel_fetch(self):
        """Cancel a running fetch and return to the fetch panel."""
        self._cancel_event.set()
        self._fetch_in_progress = False
        self.progress.stop()
        self._cancel_btn.pack_forget()
        self._loading_frame.pack_forget()
        self.app.log("Fetch cancelled.", "info")
        self._show_fetch_panel_ui()

    def _on_fetch_done(self, library: SpotifyLibrary):
        if self._cancel_event.is_set():
            return
        self._fetch_in_progress = False
        self.progress.stop()
        self._cancel_btn.pack_forget()
        self._loading_frame.pack_forget()
        summary = (f"Library: {len(library.playlists)} playlists, "
                   f"{len(library.liked_tracks)} liked, "
                   f"{len(library.albums)} albums, "
                   f"{len(library.artists)} artists")
        self.bottom_bar.status_label.config(text=summary)
        self.app.log(summary, "success")
        self._populate_tree(library)

    def _on_fetch_error(self, error: str):
        if self._cancel_event.is_set():
            return
        self._fetch_in_progress = False
        self.progress.stop()
        self._cancel_btn.pack_forget()
        self._loading_frame.pack_forget()
        self.bottom_bar.status_label.config(text=f"Fetch error: {error}")
        self.app.log(f"Fetch error: {error}", "error")

    # ------------------------------------------------------------------
    # Tree population & interaction
    # ------------------------------------------------------------------

    def _populate_tree(self, library: SpotifyLibrary):
        """Build the tree from the library model."""
        self.tree.delete(*self.tree.get_children())
        self.item_map.clear()
        self.category_ids.clear()

        # Playlists
        if library.playlists:
            cat_id = self.tree.insert_item(text="Playlists", checked=True)
            self.category_ids["playlists"] = cat_id
            self.item_map[cat_id] = library.playlists
            for pl in library.playlists:
                pl_id = self.tree.insert_item(parent=cat_id, text=f"{pl.display_name()} ({pl.track_count} tracks)",
                                              checked=pl.selected)
                self.item_map[pl_id] = pl
                for track in pl.tracks:
                    t_id = self.tree.insert_item(
                        parent=pl_id,
                        text=f"{track.name} — {', '.join(track.artists)}",
                        checked=track.selected,
                    )
                    self.item_map[t_id] = track

        # Liked Songs
        if library.liked_tracks:
            cat_id = self.tree.insert_item(text=f"Liked Songs ({len(library.liked_tracks)})", checked=True)
            self.category_ids["liked"] = cat_id
            self.item_map[cat_id] = library.liked_tracks
            for track in library.liked_tracks:
                t_id = self.tree.insert_item(
                    parent=cat_id,
                    text=f"{track.name} — {', '.join(track.artists)}",
                    checked=track.selected,
                )
                self.item_map[t_id] = track

        # Albums
        if library.albums:
            cat_id = self.tree.insert_item(text="Albums", checked=True)
            self.category_ids["albums"] = cat_id
            self.item_map[cat_id] = library.albums
            for album in library.albums:
                a_id = self.tree.insert_item(parent=cat_id,
                                             text=f"{album.name} — {', '.join(album.artists)}",
                                             checked=album.selected)
                self.item_map[a_id] = album
                for track in album.tracks:
                    t_id = self.tree.insert_item(
                        parent=a_id,
                        text=f"{track.name} — {', '.join(track.artists)}",
                        checked=track.selected,
                    )
                    self.item_map[t_id] = track

        # Artists
        if library.artists:
            cat_id = self.tree.insert_item(text="Artists", checked=True)
            self.category_ids["artists"] = cat_id
            self.item_map[cat_id] = library.artists
            for artist in library.artists:
                ar_id = self.tree.insert_item(parent=cat_id,
                                              text=f"{artist.name}",
                                              checked=artist.selected)
                self.item_map[ar_id] = artist

    def _on_tree_select(self, event):
        """Handle tree selection — show detail panel for selected item."""
        selection = self.tree.selection()
        if not selection:
            return
        item_id = selection[0]
        obj = self.item_map.get(item_id)
        if obj is None:
            return

        self.detail_panel.show_item(item_id, obj)

    def _on_check_changed(self, event):
        """Sync checkbox states back to model objects."""
        self._sync_check_states()
        self.app.state_manager.save()

    def _sync_check_states(self):
        """Walk the tree and update model `selected` fields."""
        for item_id, obj in self.item_map.items():
            checked = self.tree.is_checked(item_id)
            if isinstance(obj, (Track, Playlist, Album, Artist)):
                obj.selected = checked

    def get_selected_items(self) -> dict:
        """Return selected library items grouped by category."""
        lib = self.app.state_manager.library
        return {
            "playlists": [p for p in lib.playlists if p.selected],
            "liked_tracks": [t for t in lib.liked_tracks if t.selected],
            "albums": [a for a in lib.albums if a.selected],
            "artists": [a for a in lib.artists if a.selected],
        }
