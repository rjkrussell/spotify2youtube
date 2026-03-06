"""Load and save credentials.json."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

DATA_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CREDENTIALS_PATH = os.path.join(DATA_DIR, "credentials.json")

_MOCK_MODE = os.environ.get("YOUTUBE_MOCK") == "1"
_YT_TOKEN_KEY = "youtube_oauth_token_mock" if _MOCK_MODE else "youtube_oauth_token"


@dataclass
class Credentials:
    spotify_client_id: str = ""
    spotify_client_secret: str = ""
    spotify_redirect_uri: str = "http://127.0.0.1:8888/callback"
    youtube_client_id: str = ""
    youtube_client_secret: str = ""
    youtube_oauth_token: dict = field(default_factory=dict)

    def has_spotify(self) -> bool:
        return bool(self.spotify_client_id and self.spotify_client_secret)

    def has_youtube(self) -> bool:
        return bool(self.youtube_oauth_token)


class CredentialsManager:
    def __init__(self, path: str = CREDENTIALS_PATH):
        self.path = path
        self.credentials = Credentials()

    def load(self) -> Credentials:
        if os.path.exists(self.path):
            with open(self.path, "r") as f:
                data = json.load(f)
            redirect_uri = data.get("spotify_redirect_uri", "http://127.0.0.1:8888/callback")
            # Auto-migrate old default that Spotify now rejects
            if redirect_uri == "http://localhost:8888/callback":
                redirect_uri = "http://127.0.0.1:8888/callback"

            self.credentials = Credentials(
                spotify_client_id=data.get("spotify_client_id", ""),
                spotify_client_secret=data.get("spotify_client_secret", ""),
                spotify_redirect_uri=redirect_uri,
                youtube_client_id=data.get("youtube_client_id", ""),
                youtube_client_secret=data.get("youtube_client_secret", ""),
                youtube_oauth_token=data.get(_YT_TOKEN_KEY, {}),
            )
        return self.credentials

    def save(self) -> None:
        # Read-merge-write: preserve the other mode's token key
        existing = {}
        if os.path.exists(self.path):
            with open(self.path, "r") as f:
                existing = json.load(f)

        existing.update({
            "spotify_client_id": self.credentials.spotify_client_id,
            "spotify_client_secret": self.credentials.spotify_client_secret,
            "spotify_redirect_uri": self.credentials.spotify_redirect_uri,
            "youtube_client_id": self.credentials.youtube_client_id,
            "youtube_client_secret": self.credentials.youtube_client_secret,
            _YT_TOKEN_KEY: self.credentials.youtube_oauth_token,
        })

        tmp_path = self.path + ".tmp"
        with open(tmp_path, "w") as f:
            json.dump(existing, f, indent=2)
        os.replace(tmp_path, self.path)
