"""Main screen — library tree, detail panel, and bottom bar."""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

from src.app import SPOTIFY_GREEN, YOUTUBE_RED, get_colors, _fix_paned_cursor
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
        self._top_bar = tk.Frame(self)
        self._top_bar.pack(fill="x", padx=5, pady=5)
        top = self._top_bar

        # Right-side buttons (pack first so title can center in remaining space)
        ttk.Button(top, text="Settings", command=lambda: self.app.show_screen("settings")).pack(side="right")
        ttk.Button(top, text="Guide", command=self._toggle_guide).pack(side="right", padx=5)
        self._theme_btn = ttk.Button(top, text="\u263e", width=3, command=self._toggle_theme)
        self._theme_btn.pack(side="right", padx=5)

        # Centered app title
        title_frame = tk.Frame(top)
        title_frame.pack(expand=True)
        tk.Label(title_frame, text="\u266b", font=("TkDefaultFont", 18),
                 foreground=SPOTIFY_GREEN).pack(side="left")
        tk.Label(title_frame, text=" Spotify", font=("TkDefaultFont", 16, "bold"),
                 foreground=SPOTIFY_GREEN).pack(side="left")
        c = get_colors()
        self._title_sep = tk.Label(title_frame, text="2", font=("TkDefaultFont", 16, "bold"),
                                   foreground=c["separator"])
        self._title_sep.pack(side="left")
        tk.Label(title_frame, text="YouTube", font=("TkDefaultFont", 16, "bold"),
                 foreground=YOUTUBE_RED).pack(side="left")

        # Guide panel (hidden by default)
        self._guide_frame = tk.Frame(self)
        self._guide_visible = False
        c = get_colors()
        self._guide_text = tk.Text(self._guide_frame, wrap="word", borderwidth=0,
                                   highlightthickness=0, padx=12, pady=12, cursor="arrow",
                                   height=18, background=c["guide_bg"], foreground=c["guide_fg"])
        self._guide_text.pack(fill="x", padx=10, pady=(0, 5))
        guide_content = (
            "How to use Spotify2YouTube\n"
            "\n"
            "1. Fetch your Spotify library\n"
            "   Click \"Refresh Library\" and choose which categories to sync\n"
            "   (Playlists, Liked Songs, Saved Albums, Followed Artists), then\n"
            "   click \"Go\". The app fetches your library in the background.\n"
            "\n"
            "2. Select what to transfer\n"
            "   Your library appears as a tree with checkboxes. Check or uncheck\n"
            "   at any level \u2014 toggling a parent toggles all its children.\n"
            "   Click an item to see a detail panel on the right where you can:\n"
            "     \u2022 Rename a playlist for YouTube\n"
            "     \u2022 Set matching preference (Fuzzy / Strict / Manual)\n"
            "     \u2022 Merge into an existing YouTube playlist\n"
            "\n"
            "3. Transfer\n"
            "   Click \"Transfer Selected\" in the bottom bar. The app searches\n"
            "   YouTube for each track, scores matches, and:\n"
            "     \u2022 Playlists \u2192 creates YouTube playlists with matched tracks\n"
            "     \u2022 Liked Songs \u2192 likes the matched videos on YouTube\n"
            "     \u2022 Albums \u2192 likes each track on YouTube\n"
            "     \u2022 Artists \u2192 subscribes to their YouTube channel\n"
            "\n"
            "4. Review results\n"
            "   After transfer, a results screen shows what matched, failed, or\n"
            "   was ambiguous. For ambiguous tracks you can search YouTube\n"
            "   manually and pick the right match. You can export results to CSV.\n"
            "\n"
            "5. Re-fetch / retry\n"
            "   Click \"Refresh Library\" to re-fetch specific categories without\n"
            "   losing other data. Previously transferred tracks are skipped on\n"
            "   re-transfer."
        )
        self._guide_text.insert("1.0", guide_content)
        self._guide_text.tag_add("title", "1.0", "1.end")
        self._guide_text.tag_configure("title", font=("TkDefaultFont", 13, "bold"), foreground=c["guide_title"])
        self._guide_text.configure(state="disabled")
        guide_scroll = ttk.Scrollbar(self._guide_frame, orient="vertical", command=self._guide_text.yview)
        self._guide_text.configure(yscrollcommand=guide_scroll.set)

        # --- Library label ---
        lib_label = tk.Label(self, text="\u266a Library", font=("TkDefaultFont", 13, "bold"))
        lib_label.pack(anchor="w", padx=10, pady=(5, 0))

        # --- Stacking container for fetch panel and paned (grid + tkraise) ---
        self._stack = tk.Frame(self)
        self._stack.pack(fill="both", expand=True, padx=5, pady=5)
        self._stack.grid_rowconfigure(0, weight=1)
        self._stack.grid_columnconfigure(0, weight=1)

        # Inline fetch panel
        from src.views.fetch_dialog import FetchPanel
        self._fetch_panel = FetchPanel(self._stack, on_go=self._on_go)
        self._fetch_panel.grid(row=0, column=0, sticky="nsew")

        # Paned window: tree (left) + detail (right)
        self.paned = ttk.PanedWindow(self._stack, orient="horizontal")
        self.paned.grid(row=0, column=0, sticky="nsew")
        _fix_paned_cursor(self.paned)

        # Left: Spotify panel
        self._left_frame = tk.Frame(self.paned)
        self.paned.add(self._left_frame, weight=1)

        spotify_header = tk.Frame(self._left_frame)
        spotify_header.pack(fill="x")
        tk.Label(spotify_header, text="\u25cf Spotify Library",
                 font=("TkDefaultFont", 11, "bold"), foreground=SPOTIFY_GREEN).pack(side="left", padx=5, pady=2)
        self._refresh_btn = ttk.Button(spotify_header, text="\u21bb Refresh", command=self._show_fetch_panel)
        self._refresh_btn.pack(side="right", padx=5, pady=2)

        # Loading progress (for library fetch) — sits below header, above tree
        self._loading_frame = tk.Frame(self._left_frame)
        self.status_label = tk.Label(self._loading_frame, text="", anchor="w")
        self.status_label.pack(side="left", padx=5)
        self._cancel_btn = ttk.Button(self._loading_frame, text="Cancel", command=self._cancel_fetch)
        self.progress = ttk.Progressbar(self._loading_frame, mode="indeterminate", length=150)

        self._tree_frame = tk.Frame(self._left_frame)
        self._tree_frame.pack(fill="both", expand=True)
        tree_frame = self._tree_frame

        tree_scroll = ttk.Scrollbar(tree_frame, orient="vertical")
        tree_scroll.pack(side="right", fill="y")

        self.tree = CheckboxTreeview(tree_frame, yscrollcommand=tree_scroll.set)
        self.tree.pack(fill="both", expand=True)
        tree_scroll.config(command=self.tree.yview)

        # Transfer status indicator tags
        c = get_colors()
        self.tree.tag_configure("t_success", foreground=c["success"])
        self.tree.tag_configure("t_failed", foreground=c["summary_fail"])
        self.tree.tag_configure("t_ambiguous", foreground=c["warning"])

        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<<CheckChanged>>", self._on_check_changed)

        # Right: YouTube detail panel (no static header — DetailPanel shows its own)
        right_frame = tk.Frame(self.paned)
        self.paned.add(right_frame, weight=2)

        from src.views.detail_panel import DetailPanel
        self.detail_panel = DetailPanel(right_frame, app=self.app, main_screen=self)
        self.detail_panel.pack(fill="both", expand=True)

        # Bottom bar
        from src.views.bottom_bar import BottomBar
        self.bottom_bar = BottomBar(self, app=self.app, main_screen=self)
        self.bottom_bar.pack(fill="x", padx=5, pady=5)

        # Register for theme changes
        self.app.on_theme_change(self._on_theme_change)
        self._update_theme_button()

    # ------------------------------------------------------------------
    # Theme
    # ------------------------------------------------------------------

    def _toggle_theme(self):
        self.app.toggle_theme()
        self._update_theme_button()

    def _update_theme_button(self):
        # Sun/moon icon
        self._theme_btn.configure(text="\u2600" if self.app.is_dark else "\u263e")

    def _on_theme_change(self):
        """Update theme-dependent widgets."""
        c = get_colors()
        self._title_sep.configure(foreground=c["separator"])
        self._guide_text.configure(background=c["guide_bg"], foreground=c["guide_fg"])
        self._guide_text.tag_configure("title", foreground=c["guide_title"])
        self.tree.tag_configure("checked", foreground=SPOTIFY_GREEN)
        self.tree.tag_configure("unchecked", foreground=c["unchecked"])
        self.tree.tag_configure("tristate", foreground=c["warning"])
        self._update_theme_button()

    # ------------------------------------------------------------------
    # Show / hide helpers
    # ------------------------------------------------------------------

    def _toggle_guide(self):
        if self._guide_visible:
            self._guide_frame.pack_forget()
            self._guide_visible = False
        else:
            self._guide_frame.pack(fill="x", padx=5, after=self._top_bar)
            self._guide_visible = True

    def _show_fetch_panel_ui(self):
        """Show the inline fetch panel, hide the tree/detail paned area."""
        self._fetch_panel.reset()
        self._fetch_panel.tkraise()

    def _show_paned_ui(self):
        """Show the tree/detail paned area, hide the fetch panel."""
        self.paned.tkraise()

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

        self._loading_frame.pack(fill="x", padx=5, pady=2, before=self._tree_frame)
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
                        artists=[a["name"] for a in at["artists"] if a.get("name")],
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
            artists=[a["name"] for a in raw["artists"] if a.get("name")],
            album=raw.get("album", {}).get("name", ""),
            duration_ms=raw["duration_ms"],
        )

    # ------------------------------------------------------------------
    # Fetch callbacks
    # ------------------------------------------------------------------

    def _hide_fetch_progress(self):
        """Hide the fetch progress bar and cancel button."""
        self.progress.stop()
        self.progress.pack_forget()
        self._cancel_btn.pack_forget()
        self._loading_frame.pack_forget()

    def _cancel_fetch(self):
        """Cancel a running fetch and return to the fetch panel."""
        self._cancel_event.set()
        self._fetch_in_progress = False
        self._hide_fetch_progress()
        self.app.log("Fetch cancelled.", "info")
        self._show_fetch_panel_ui()

    def _on_fetch_done(self, library: SpotifyLibrary):
        if self._cancel_event.is_set():
            return
        self._fetch_in_progress = False
        self._hide_fetch_progress()
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
        self._hide_fetch_progress()
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

        _STATUS_SUFFIX = {
            TransferStatus.SUCCESS: " \u2713",
            TransferStatus.FAILED: " \u2717",
            TransferStatus.AMBIGUOUS: " ?",
        }
        _STATUS_TAG = {
            TransferStatus.SUCCESS: "t_success",
            TransferStatus.FAILED: "t_failed",
            TransferStatus.AMBIGUOUS: "t_ambiguous",
        }

        def _cat_label(name: str, items: list) -> str:
            total = len(items)
            remaining = sum(1 for i in items if i.transfer_status != TransferStatus.SUCCESS)
            if remaining == total:
                return f"{name} ({total})"
            return f"{name} ({remaining}/{total} remaining)"

        def _suffix(obj) -> str:
            return _STATUS_SUFFIX.get(obj.transfer_status, "")

        def _tags(obj) -> tuple:
            tag = _STATUS_TAG.get(obj.transfer_status)
            return (tag,) if tag else ()

        # Playlists
        if library.playlists:
            cat_id = self.tree.insert_item(text=_cat_label("Playlists", library.playlists), checked=False)
            self.category_ids["playlists"] = cat_id
            self.item_map[cat_id] = library.playlists
            for pl in library.playlists:
                pl_id = self.tree.insert_item(
                    parent=cat_id,
                    text=f"{pl.display_name()} ({pl.track_count} tracks){_suffix(pl)}",
                    checked=pl.selected, tags=_tags(pl))
                self.item_map[pl_id] = pl
                for track in pl.tracks:
                    t_id = self.tree.insert_item(
                        parent=pl_id,
                        text=f"{track.name} — {', '.join(track.artists)}{_suffix(track)}",
                        checked=track.selected, tags=_tags(track),
                    )
                    self.item_map[t_id] = track

        # Liked Songs
        if library.liked_tracks:
            cat_id = self.tree.insert_item(text=_cat_label("Liked Songs", library.liked_tracks), checked=False)
            self.category_ids["liked"] = cat_id
            self.item_map[cat_id] = library.liked_tracks
            for track in library.liked_tracks:
                t_id = self.tree.insert_item(
                    parent=cat_id,
                    text=f"{track.name} — {', '.join(track.artists)}{_suffix(track)}",
                    checked=track.selected, tags=_tags(track),
                )
                self.item_map[t_id] = track

        # Albums
        if library.albums:
            cat_id = self.tree.insert_item(text=_cat_label("Albums", library.albums), checked=False)
            self.category_ids["albums"] = cat_id
            self.item_map[cat_id] = library.albums
            for album in library.albums:
                a_id = self.tree.insert_item(
                    parent=cat_id,
                    text=f"{album.name} — {', '.join(album.artists)}{_suffix(album)}",
                    checked=album.selected, tags=_tags(album))
                self.item_map[a_id] = album
                for track in album.tracks:
                    t_id = self.tree.insert_item(
                        parent=a_id,
                        text=f"{track.name} — {', '.join(track.artists)}{_suffix(track)}",
                        checked=track.selected, tags=_tags(track),
                    )
                    self.item_map[t_id] = track

        # Artists
        if library.artists:
            cat_id = self.tree.insert_item(text=_cat_label("Artists", library.artists), checked=False)
            self.category_ids["artists"] = cat_id
            self.item_map[cat_id] = library.artists
            for artist in library.artists:
                ar_id = self.tree.insert_item(
                    parent=cat_id,
                    text=f"{artist.name}{_suffix(artist)}",
                    checked=artist.selected, tags=_tags(artist))
                self.item_map[ar_id] = artist

        # Cascade up from leaves so parent states reflect children
        self._fix_parent_states()

    def _fix_parent_states(self):
        """Walk the tree bottom-up so parent checkboxes match their children."""
        def _fix(item: str):
            children = self.tree.get_children(item)
            for child in children:
                _fix(child)
            if children:
                states = {self.tree.get_state(c) for c in children}
                if states == {"checked"}:
                    self.tree._set_state(item, "checked")
                elif states == {"unchecked"}:
                    self.tree._set_state(item, "unchecked")
                else:
                    self.tree._set_state(item, "tristate")

        for root_item in self.tree.get_children():
            _fix(root_item)

    def _get_transfer_action(self, item_id: str) -> str:
        """Return a human-readable label describing what the transfer will do."""
        # Walk up the tree to find which category this item belongs to
        current = item_id
        while current:
            for cat_name, cat_id in self.category_ids.items():
                if current == cat_id:
                    actions = {
                        "playlists": "Will be added to a YouTube playlist",
                        "liked": "Will be liked on YouTube",
                        "albums": "Will be liked on YouTube",
                        "artists": "Will subscribe on YouTube",
                    }
                    return actions.get(cat_name, "")
            current = self.tree.parent(current)
        return ""

    def _on_tree_select(self, event):
        """Handle tree selection — show detail panel for selected item."""
        selection = self.tree.selection()
        if not selection:
            return
        item_id = selection[0]
        obj = self.item_map.get(item_id)
        if obj is None:
            return

        action = self._get_transfer_action(item_id)
        self.detail_panel.show_item(item_id, obj, transfer_action=action)

    def _on_check_changed(self, event):
        """Sync checkbox states back to model objects."""
        self._sync_check_states()
        self.app.state_manager.save()

    def _sync_check_states(self):
        """Walk the tree and update model `selected` fields.

        For containers (Playlist, Album) tristate counts as selected
        because they have some checked tracks inside that should transfer.
        """
        for item_id, obj in self.item_map.items():
            state = self.tree.get_state(item_id)
            if isinstance(obj, (Playlist, Album)):
                # Include in transfer if checked OR tristate (has some selected tracks)
                obj.selected = state in ("checked", "tristate")
            elif isinstance(obj, (Track, Artist)):
                obj.selected = state == "checked"

    def get_selected_items(self) -> dict:
        """Return selected library items grouped by category."""
        lib = self.app.state_manager.library
        return {
            "playlists": [p for p in lib.playlists if p.selected],
            "liked_tracks": [t for t in lib.liked_tracks if t.selected],
            "albums": [a for a in lib.albums if a.selected],
            "artists": [a for a in lib.artists if a.selected],
        }
