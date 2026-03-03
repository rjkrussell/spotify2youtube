"""Wraps spotipy: auth and library fetching."""

from __future__ import annotations

import os

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials, SpotifyPKCE

from src.models.credentials import Credentials, DATA_DIR

SCOPES = "user-library-read playlist-read-private playlist-read-collaborative user-follow-read"
CACHE_PATH = os.path.join(DATA_DIR, ".spotify_token_cache")


class SpotifyService:
    def __init__(self, credentials: Credentials):
        self.credentials = credentials
        self._sp: spotipy.Spotify | None = None

    def test_credentials(self) -> str:
        """Quick validation using client credentials (no browser needed).
        Returns a confirmation string or raises on bad credentials."""
        auth_manager = SpotifyClientCredentials(
            client_id=self.credentials.spotify_client_id,
            client_secret=self.credentials.spotify_client_secret,
        )
        sp = spotipy.Spotify(auth_manager=auth_manager)
        # Any call will fail if credentials are invalid
        sp.search(q="test", type="track", limit=1)
        return "Credentials valid"

    def authenticate(self) -> spotipy.Spotify:
        auth_manager = SpotifyPKCE(
            client_id=self.credentials.spotify_client_id,
            redirect_uri=self.credentials.spotify_redirect_uri,
            scope=SCOPES,
            cache_path=CACHE_PATH,
            open_browser=True,
        )
        self._sp = spotipy.Spotify(auth_manager=auth_manager)
        return self._sp

    @property
    def sp(self) -> spotipy.Spotify:
        if self._sp is None:
            self.authenticate()
        return self._sp

    def test_connection(self) -> str:
        """Full connection test (requires user OAuth). Returns display name."""
        user = self.sp.current_user()
        return user["display_name"] or user["id"]

    def get_playlists(self) -> list[dict]:
        results = []
        resp = self.sp.current_user_playlists(limit=50)
        while resp:
            results.extend(resp["items"])
            resp = self.sp.next(resp) if resp["next"] else None
        return results

    def get_playlist_tracks(self, playlist_id: str) -> list[dict]:
        results = []
        resp = self.sp.playlist_tracks(playlist_id, limit=100)
        while resp:
            for item in resp["items"]:
                track = item.get("track")
                if track and track.get("id") and not track.get("is_local"):
                    results.append(track)
            resp = self.sp.next(resp) if resp["next"] else None
        return results

    def get_liked_tracks(self) -> list[dict]:
        results = []
        resp = self.sp.current_user_saved_tracks(limit=50)
        while resp:
            for item in resp["items"]:
                track = item.get("track")
                if track and track.get("id"):
                    results.append(track)
            resp = self.sp.next(resp) if resp["next"] else None
        return results

    def get_saved_albums(self) -> list[dict]:
        results = []
        resp = self.sp.current_user_saved_albums(limit=50)
        while resp:
            results.extend(item["album"] for item in resp["items"])
            resp = self.sp.next(resp) if resp["next"] else None
        return results

    def get_album_tracks(self, album_id: str) -> list[dict]:
        results = []
        resp = self.sp.album_tracks(album_id, limit=50)
        while resp:
            results.extend(resp["items"])
            resp = self.sp.next(resp) if resp["next"] else None
        return results

    def get_followed_artists(self) -> list[dict]:
        results = []
        after = None
        while True:
            resp = self.sp.current_user_followed_artists(limit=50, after=after)
            artists = resp["artists"]
            results.extend(artists["items"])
            if artists["cursors"]["after"]:
                after = artists["cursors"]["after"]
            else:
                break
        return results
