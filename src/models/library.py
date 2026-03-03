"""Domain dataclasses for the Spotify library."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field


class MatchingPreference(enum.Enum):
    FUZZY = "fuzzy"
    STRICT = "strict"
    MANUAL = "manual"


class TransferStatus(enum.Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    AMBIGUOUS = "ambiguous"
    SKIPPED = "skipped"


@dataclass
class Track:
    spotify_id: str
    name: str
    artists: list[str]
    album: str
    duration_ms: int
    selected: bool = True
    matching_pref: MatchingPreference = MatchingPreference.FUZZY
    transfer_status: TransferStatus = TransferStatus.PENDING
    yt_video_id: str | None = None
    yt_candidates: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "spotify_id": self.spotify_id,
            "name": self.name,
            "artists": self.artists,
            "album": self.album,
            "duration_ms": self.duration_ms,
            "selected": self.selected,
            "matching_pref": self.matching_pref.value,
            "transfer_status": self.transfer_status.value,
            "yt_video_id": self.yt_video_id,
            "yt_candidates": self.yt_candidates,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Track:
        return cls(
            spotify_id=d["spotify_id"],
            name=d["name"],
            artists=d["artists"],
            album=d["album"],
            duration_ms=d["duration_ms"],
            selected=d.get("selected", True),
            matching_pref=MatchingPreference(d.get("matching_pref", "fuzzy")),
            transfer_status=TransferStatus(d.get("transfer_status", "pending")),
            yt_video_id=d.get("yt_video_id"),
            yt_candidates=d.get("yt_candidates", []),
        )


@dataclass
class Playlist:
    spotify_id: str
    name: str
    description: str
    track_count: int
    tracks: list[Track] = field(default_factory=list)
    selected: bool = True
    rename: str = ""
    matching_pref: MatchingPreference = MatchingPreference.FUZZY
    merge_into_yt_id: str | None = None
    transfer_status: TransferStatus = TransferStatus.PENDING
    yt_playlist_id: str | None = None

    def display_name(self) -> str:
        return self.rename if self.rename else self.name

    def to_dict(self) -> dict:
        return {
            "spotify_id": self.spotify_id,
            "name": self.name,
            "description": self.description,
            "track_count": self.track_count,
            "tracks": [t.to_dict() for t in self.tracks],
            "selected": self.selected,
            "rename": self.rename,
            "matching_pref": self.matching_pref.value,
            "merge_into_yt_id": self.merge_into_yt_id,
            "transfer_status": self.transfer_status.value,
            "yt_playlist_id": self.yt_playlist_id,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Playlist:
        return cls(
            spotify_id=d["spotify_id"],
            name=d["name"],
            description=d.get("description", ""),
            track_count=d.get("track_count", 0),
            tracks=[Track.from_dict(t) for t in d.get("tracks", [])],
            selected=d.get("selected", True),
            rename=d.get("rename", ""),
            matching_pref=MatchingPreference(d.get("matching_pref", "fuzzy")),
            merge_into_yt_id=d.get("merge_into_yt_id"),
            transfer_status=TransferStatus(d.get("transfer_status", "pending")),
            yt_playlist_id=d.get("yt_playlist_id"),
        )


@dataclass
class Album:
    spotify_id: str
    name: str
    artists: list[str]
    track_count: int
    tracks: list[Track] = field(default_factory=list)
    selected: bool = True
    matching_pref: MatchingPreference = MatchingPreference.FUZZY
    transfer_status: TransferStatus = TransferStatus.PENDING

    def to_dict(self) -> dict:
        return {
            "spotify_id": self.spotify_id,
            "name": self.name,
            "artists": self.artists,
            "track_count": self.track_count,
            "tracks": [t.to_dict() for t in self.tracks],
            "selected": self.selected,
            "matching_pref": self.matching_pref.value,
            "transfer_status": self.transfer_status.value,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Album:
        return cls(
            spotify_id=d["spotify_id"],
            name=d["name"],
            artists=d.get("artists", []),
            track_count=d.get("track_count", 0),
            tracks=[Track.from_dict(t) for t in d.get("tracks", [])],
            selected=d.get("selected", True),
            matching_pref=MatchingPreference(d.get("matching_pref", "fuzzy")),
            transfer_status=TransferStatus(d.get("transfer_status", "pending")),
        )


@dataclass
class Artist:
    spotify_id: str
    name: str
    genres: list[str] = field(default_factory=list)
    selected: bool = True
    transfer_status: TransferStatus = TransferStatus.PENDING

    def to_dict(self) -> dict:
        return {
            "spotify_id": self.spotify_id,
            "name": self.name,
            "genres": self.genres,
            "selected": self.selected,
            "transfer_status": self.transfer_status.value,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Artist:
        return cls(
            spotify_id=d["spotify_id"],
            name=d["name"],
            genres=d.get("genres", []),
            selected=d.get("selected", True),
            transfer_status=TransferStatus(d.get("transfer_status", "pending")),
        )


@dataclass
class SpotifyLibrary:
    playlists: list[Playlist] = field(default_factory=list)
    liked_tracks: list[Track] = field(default_factory=list)
    albums: list[Album] = field(default_factory=list)
    artists: list[Artist] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "playlists": [p.to_dict() for p in self.playlists],
            "liked_tracks": [t.to_dict() for t in self.liked_tracks],
            "albums": [a.to_dict() for a in self.albums],
            "artists": [a.to_dict() for a in self.artists],
        }

    @classmethod
    def from_dict(cls, d: dict) -> SpotifyLibrary:
        return cls(
            playlists=[Playlist.from_dict(p) for p in d.get("playlists", [])],
            liked_tracks=[Track.from_dict(t) for t in d.get("liked_tracks", [])],
            albums=[Album.from_dict(a) for a in d.get("albums", [])],
            artists=[Artist.from_dict(a) for a in d.get("artists", [])],
        )
