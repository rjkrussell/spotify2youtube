"""YouTube Music operations via the YouTube Data API v3.

Uses the official Data API instead of the internal youtubei API because
YouTube's server-side changes broke custom-OAuth-client access to the
internal endpoint (ytmusicapi issue #676).  The user's OAuth token works
perfectly with the public Data API.
"""

from __future__ import annotations

import json
import os
import time
import webbrowser

import requests
from ytmusicapi.auth.oauth import OAuthCredentials

from src.models.credentials import Credentials, DATA_DIR

OAUTH_PATH = os.path.join(DATA_DIR, "youtube_oauth.json")

if os.environ.get("YOUTUBE_MOCK") == "1":
    API_BASE = os.environ.get("YOUTUBE_API_BASE", "http://127.0.0.1:8444/youtube/v3")
    TOKEN_URL = os.environ.get("YOUTUBE_TOKEN_URL", "http://127.0.0.1:8444/oauth2/token")
else:
    API_BASE = os.environ.get("YOUTUBE_API_BASE", "https://www.googleapis.com/youtube/v3")
    TOKEN_URL = os.environ.get("YOUTUBE_TOKEN_URL", "https://oauth2.googleapis.com/token")


class YouTubeService:
    def __init__(self, credentials: Credentials):
        self.credentials = credentials
        self._session = requests.Session()

    # ------------------------------------------------------------------
    # Token management
    # ------------------------------------------------------------------

    def _get_access_token(self) -> str:
        """Return a valid access token, refreshing if expired."""
        token = self.credentials.youtube_oauth_token
        if not token:
            raise ValueError("No YouTube OAuth token. Run the OAuth flow first.")

        if token.get("expires_at", 0) < time.time() + 60:
            token = self._refresh_token(token)

        return token["access_token"]

    def _refresh_token(self, token: dict) -> dict:
        """Use the refresh_token to get a fresh access_token."""
        resp = self._session.post(TOKEN_URL, data={
            "client_id": self.credentials.youtube_client_id,
            "client_secret": self.credentials.youtube_client_secret,
            "refresh_token": token["refresh_token"],
            "grant_type": "refresh_token",
        })
        resp.raise_for_status()
        new = resp.json()

        token["access_token"] = new["access_token"]
        token["expires_at"] = int(time.time()) + new.get("expires_in", 3600)
        token["expires_in"] = new.get("expires_in", 3600)

        # Persist refreshed token
        self.credentials.youtube_oauth_token = token
        with open(OAUTH_PATH, "w") as f:
            json.dump(token, f)

        return token

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._get_access_token()}"}

    def _api_get(self, endpoint: str, params: dict) -> dict:
        resp = self._session.get(
            f"{API_BASE}/{endpoint}",
            params=params,
            headers=self._auth_headers(),
        )
        self._check_response(resp)
        return resp.json()

    def _api_post(self, endpoint: str, body: dict, params: dict | None = None) -> dict:
        resp = self._session.post(
            f"{API_BASE}/{endpoint}",
            params=params or {},
            json=body,
            headers=self._auth_headers(),
        )
        self._check_response(resp)
        return resp.json()

    @staticmethod
    def _check_response(resp: requests.Response) -> None:
        if resp.status_code == 403:
            try:
                detail = resp.json()
                reason = detail.get("error", {}).get("errors", [{}])[0].get("reason", "")
            except Exception:
                reason = ""
            if reason == "quotaExceeded":
                raise PermissionError(
                    "YouTube API quota exceeded (resets at midnight PT)"
                )
            if reason == "accessNotConfigured" or "API has not been used" in resp.text:
                raise PermissionError(
                    'YouTube Data API v3 is not enabled. Go to '
                    'console.cloud.google.com → APIs & Services → '
                    'Library → search "YouTube Data API v3" → Enable.'
                )
            raise PermissionError(
                f"YouTube API returned 403 Forbidden ({reason or 'check API is enabled and scopes are correct'})"
            )
        resp.raise_for_status()

    # ------------------------------------------------------------------
    # OAuth flow (still uses ytmusicapi's OAuthCredentials for device-code)
    # ------------------------------------------------------------------

    def start_oauth_flow(self) -> tuple[OAuthCredentials, dict, str]:
        """Start the device-code OAuth flow.

        Returns (oauth_credentials, code_response, verification_url).
        """
        oauth_creds = OAuthCredentials(
            client_id=self.credentials.youtube_client_id,
            client_secret=self.credentials.youtube_client_secret,
        )
        code = oauth_creds.get_code()
        url = f"{code['verification_url']}?user_code={code['user_code']}"
        webbrowser.open(url)
        return oauth_creds, code, url

    def finish_oauth_flow(self, oauth_creds: OAuthCredentials, code: dict) -> dict:
        """Exchange the device code for a token after user completes login."""
        from ytmusicapi.auth.oauth.token import RefreshingToken
        from pathlib import Path

        raw_token = oauth_creds.token_from_code(code["device_code"])
        if "error" in raw_token:
            raise RuntimeError(f"Google rejected the auth request: {raw_token['error']}")
        ref_token = RefreshingToken(credentials=oauth_creds, **raw_token)
        ref_token.update(ref_token.as_dict())
        ref_token.local_cache = Path(OAUTH_PATH)
        token_data = ref_token.as_dict()

        with open(OAUTH_PATH, "w") as f:
            json.dump(token_data, f)

        return token_data

    # ------------------------------------------------------------------
    # Public API methods (YouTube Data API v3)
    # ------------------------------------------------------------------

    def test_connection(self) -> str:
        """Verify the token works. Returns the channel title."""
        data = self._api_get("channels", {"part": "snippet", "mine": "true"})
        items = data.get("items", [])
        if items:
            return items[0]["snippet"]["title"]
        return "Connected"

    def search_tracks(self, query: str, limit: int = 5) -> list[dict]:
        """Search YouTube for music videos. Returns simplified results."""
        data = self._api_get("search", {
            "part": "snippet",
            "q": query,
            "type": "video",
            "videoCategoryId": "10",  # Music category
            "maxResults": limit,
        })
        results = []
        for item in data.get("items", []):
            results.append({
                "videoId": item["id"]["videoId"],
                "title": item["snippet"]["title"],
                "artists": [{"name": item["snippet"]["channelTitle"]}],
                "duration_seconds": None,  # Would need another API call
            })
        return results

    def get_library_playlists(self) -> list[dict]:
        """Get the user's playlists. Returns normalized dicts with 'playlistId' and 'title'."""
        data = self._api_get("playlists", {
            "part": "snippet,contentDetails",
            "mine": "true",
            "maxResults": 50,
        })
        results = []
        for item in data.get("items", []):
            results.append({
                "playlistId": item["id"],
                "title": item.get("snippet", {}).get("title", ""),
                "itemCount": item.get("contentDetails", {}).get("itemCount", 0),
            })
        return results

    def create_playlist(self, title: str, description: str = "", video_ids: list[str] | None = None) -> str:
        """Create a playlist. Returns the playlist ID."""
        body = {
            "snippet": {"title": title, "description": description},
            "status": {"privacyStatus": "private"},
        }
        data = self._api_post("playlists", body, params={"part": "snippet,status"})
        playlist_id = data["id"]

        if video_ids:
            for vid in video_ids:
                self.add_playlist_items(playlist_id, [vid])

        return playlist_id

    def add_playlist_items(self, playlist_id: str, video_ids: list[str]) -> dict:
        """Add videos to a playlist."""
        last_resp = {}
        for vid in video_ids:
            body = {
                "snippet": {
                    "playlistId": playlist_id,
                    "resourceId": {"kind": "youtube#video", "videoId": vid},
                }
            }
            last_resp = self._api_post("playlistItems", body, params={"part": "snippet"})
        return last_resp

    def rate_song(self, video_id: str, rating: str = "like") -> dict:
        """Rate (like) a video."""
        resp = self._session.post(
            f"{API_BASE}/videos/rate",
            params={"id": video_id, "rating": rating},
            headers=self._auth_headers(),
        )
        resp.raise_for_status()
        return {"status": "ok"}

    def search_channels(self, query: str, limit: int = 1) -> list[dict]:
        """Search for YouTube channels by name."""
        data = self._api_get("search", {
            "part": "snippet",
            "q": query,
            "type": "channel",
            "maxResults": limit,
        })
        results = []
        for item in data.get("items", []):
            results.append({
                "channelId": item["snippet"]["channelId"],
                "title": item["snippet"]["title"],
            })
        return results

    def subscribe_artist(self, channel_id: str) -> dict:
        """Subscribe to a YouTube channel."""
        body = {
            "snippet": {
                "resourceId": {"kind": "youtube#channel", "channelId": channel_id}
            }
        }
        return self._api_post("subscriptions", body, params={"part": "snippet"})
