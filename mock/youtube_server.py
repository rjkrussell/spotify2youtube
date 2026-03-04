"""Mock YouTube Data API v3 server.

Run:  python -m mock.youtube_server          (port 8444)
Use:  YOUTUBE_MOCK=1 python -m src            (app hits this instead of Google)

All write operations are tracked in memory and logged to stdout.
State persists only for the server's lifetime.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from rapidfuzz import fuzz

from mock.seed_data import TRACK_INDEX, CHANNEL_INDEX

PORT = 8444
MIN_SCORE = 60

# ── In-memory state ──────────────────────────────────────────────────────

playlists: dict[str, dict] = {}        # id -> {title, description, videoIds}
liked_videos: list[str] = []           # videoIds
subscriptions: list[str] = []          # channelIds


def _reset_state():
    playlists.clear()
    liked_videos.clear()
    subscriptions.clear()


# ── Helpers ──────────────────────────────────────────────────────────────

def _stable_id(prefix: str, query: str) -> str:
    """Generate a deterministic mock ID from a query so repeated searches return the same videoId."""
    h = hashlib.md5(query.encode()).hexdigest()[:10]
    return f"{prefix}_{h}"


def _synthetic_tracks(query: str, max_results: int) -> list[dict]:
    """Generate plausible fake tracks from the query string.

    The query is always "{track_name} {artist}" but we don't know where one
    ends and the other begins.  Generate one candidate per split point and
    let the matcher's scoring pick the best one — just like the real API
    returns multiple results.
    """
    # Explicit separator
    if " - " in query:
        parts = query.split(" - ", 1)
        return [{
            "videoId": _stable_id("mock_gen", query.lower()),
            "title": parts[0].strip(),
            "artist": parts[1].strip(),
            "duration_seconds": None,
        }]

    words = query.strip().split()
    if len(words) <= 1:
        return [{
            "videoId": _stable_id("mock_gen", query.lower()),
            "title": query.strip(),
            "artist": query.strip(),
            "duration_seconds": None,
        }]

    results = []
    for i in range(1, len(words)):
        title = " ".join(words[:i])
        artist = " ".join(words[i:])
        results.append({
            "videoId": _stable_id("mock_gen", f"{title}|{artist}"),
            "title": title,
            "artist": artist,
            "duration_seconds": None,
        })
    return results[:max_results]


def _synthetic_channel(query: str) -> dict:
    return {
        "channelId": _stable_id("mock_gch", query.lower()),
        "title": query.strip(),
    }


def _search_tracks(query: str, max_results: int) -> list[dict]:
    q = query.lower()
    scored = []
    for entry in TRACK_INDEX:
        score = fuzz.token_sort_ratio(q, entry["key"])
        if score >= MIN_SCORE:
            scored.append((score, entry["track"]))
    scored.sort(key=lambda x: x[0], reverse=True)
    results = [t for _, t in scored[:max_results]]
    # If no seed data matched well, generate synthetic candidates
    if not results:
        results = _synthetic_tracks(query, max_results)
    return results[:max_results]


def _search_channels(query: str, max_results: int) -> list[dict]:
    q = query.lower()
    scored = []
    for entry in CHANNEL_INDEX:
        score = fuzz.token_sort_ratio(q, entry["key"])
        if score >= MIN_SCORE:
            scored.append((score, entry["channel"]))
    scored.sort(key=lambda x: x[0], reverse=True)
    results = [c for _, c in scored[:max_results]]
    if not results:
        results = [_synthetic_channel(query)]
    return results[:max_results]


def _track_to_search_item(track: dict) -> dict:
    """Format a seed track as a YouTube search result item."""
    return {
        "kind": "youtube#searchResult",
        "id": {"kind": "youtube#video", "videoId": track["videoId"]},
        "snippet": {
            "title": track["title"],
            "channelTitle": track["artist"],
            "description": f"Mock video for {track['title']}",
        },
    }


def _channel_to_search_item(channel: dict) -> dict:
    return {
        "kind": "youtube#searchResult",
        "id": {"kind": "youtube#channel", "channelId": channel["channelId"]},
        "snippet": {
            "title": channel["title"],
            "channelId": channel["channelId"],
            "description": f"Mock channel for {channel['title']}",
        },
    }


def _read_body(handler: BaseHTTPRequestHandler) -> dict:
    """Read and parse the request body (JSON or form-encoded)."""
    length = int(handler.headers.get("Content-Length", 0))
    if length == 0:
        return {}
    raw = handler.rfile.read(length)
    content_type = handler.headers.get("Content-Type", "")
    if "json" in content_type:
        return json.loads(raw)
    # form-encoded
    return dict(parse_qs(raw.decode(), keep_blank_values=True))


# ── Request handler ──────────────────────────────────────────────────────

class MockHandler(BaseHTTPRequestHandler):

    def _send_json(self, data: dict | list, status: int = 200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_no_content(self):
        self.send_response(204)
        self.end_headers()

    # ── GET ───────────────────────────────────────────────────────────

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        def p(key: str) -> str:
            return params.get(key, [""])[0]

        # /youtube/v3/search
        if path == "/youtube/v3/search":
            query = p("q")
            search_type = p("type")
            max_results = int(p("maxResults") or "5")

            if search_type == "channel":
                channels = _search_channels(query, max_results)
                items = [_channel_to_search_item(c) for c in channels]
                print(f"  SEARCH channels q={query!r} -> {len(items)} results")
            else:
                tracks = _search_tracks(query, max_results)
                items = [_track_to_search_item(t) for t in tracks]
                print(f"  SEARCH tracks q={query!r} -> {len(items)} results")

            self._send_json({
                "kind": "youtube#searchListResponse",
                "items": items,
            })
            return

        # /youtube/v3/channels?mine=true
        if path == "/youtube/v3/channels":
            if p("mine") == "true":
                self._send_json({
                    "kind": "youtube#channelListResponse",
                    "items": [{
                        "kind": "youtube#channel",
                        "id": "mock_channel_mine",
                        "snippet": {"title": "Mock User Channel"},
                    }],
                })
                print("  CHANNELS mine=true -> Mock User Channel")
                return

        # /youtube/v3/playlists (list)
        if path == "/youtube/v3/playlists":
            items = []
            for pid, pl in playlists.items():
                items.append({
                    "kind": "youtube#playlist",
                    "id": pid,
                    "snippet": {
                        "title": pl["title"],
                        "description": pl.get("description", ""),
                    },
                    "contentDetails": {"itemCount": len(pl.get("videoIds", []))},
                })
            self._send_json({
                "kind": "youtube#playlistListResponse",
                "items": items,
            })
            print(f"  PLAYLISTS list -> {len(items)} playlists")
            return

        # /mock/stats
        if path == "/mock/stats":
            self._send_json({
                "playlists": {pid: {
                    "title": pl["title"],
                    "videoCount": len(pl.get("videoIds", [])),
                    "videoIds": pl.get("videoIds", []),
                } for pid, pl in playlists.items()},
                "liked_videos": liked_videos,
                "subscriptions": subscriptions,
            })
            return

        # /mock/reset
        if path == "/mock/reset":
            _reset_state()
            self._send_json({"status": "reset"})
            print("  RESET all state")
            return

        self.send_error(404, f"Not found: {path}")

    # ── POST ──────────────────────────────────────────────────────────

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)
        body = _read_body(self)

        def p(key: str) -> str:
            return params.get(key, [""])[0]

        # /oauth2/token
        if path == "/oauth2/token":
            self._send_json({
                "access_token": f"mock_access_{uuid.uuid4().hex[:8]}",
                "expires_in": 3600,
                "token_type": "Bearer",
                "refresh_token": "mock_refresh_token",
            })
            print("  TOKEN refresh -> issued mock token")
            return

        # /youtube/v3/playlists (create)
        if path == "/youtube/v3/playlists":
            title = body.get("snippet", {}).get("title", "Untitled")
            description = body.get("snippet", {}).get("description", "")
            pid = f"mock_pl_{uuid.uuid4().hex[:8]}"
            playlists[pid] = {
                "title": title,
                "description": description,
                "videoIds": [],
            }
            self._send_json({
                "kind": "youtube#playlist",
                "id": pid,
                "snippet": {"title": title, "description": description},
                "status": {"privacyStatus": "private"},
            })
            print(f"  CREATE playlist {pid!r} title={title!r}")
            return

        # /youtube/v3/playlistItems (add video)
        if path == "/youtube/v3/playlistItems":
            snippet = body.get("snippet", {})
            playlist_id = snippet.get("playlistId", "")
            video_id = snippet.get("resourceId", {}).get("videoId", "")
            if playlist_id in playlists:
                playlists[playlist_id]["videoIds"].append(video_id)
            item_id = f"mock_pli_{uuid.uuid4().hex[:8]}"
            self._send_json({
                "kind": "youtube#playlistItem",
                "id": item_id,
                "snippet": {
                    "playlistId": playlist_id,
                    "resourceId": {"kind": "youtube#video", "videoId": video_id},
                },
            })
            print(f"  ADD video {video_id!r} to playlist {playlist_id!r}")
            return

        # /youtube/v3/videos/rate (like)
        if path == "/youtube/v3/videos/rate":
            video_id = p("id")
            rating = p("rating")
            liked_videos.append(video_id)
            print(f"  RATE video {video_id!r} rating={rating!r}")
            self._send_no_content()
            return

        # /youtube/v3/subscriptions (subscribe)
        if path == "/youtube/v3/subscriptions":
            channel_id = body.get("snippet", {}).get("resourceId", {}).get("channelId", "")
            subscriptions.append(channel_id)
            sub_id = f"mock_sub_{uuid.uuid4().hex[:8]}"
            self._send_json({
                "kind": "youtube#subscription",
                "id": sub_id,
                "snippet": {
                    "resourceId": {"kind": "youtube#channel", "channelId": channel_id},
                },
            })
            print(f"  SUBSCRIBE channel {channel_id!r}")
            return

        self.send_error(404, f"Not found: {path}")

    def log_message(self, format, *args):
        # Suppress default access logs; we print our own
        pass


# ── Main ─────────────────────────────────────────────────────────────────

def main():
    server = HTTPServer(("127.0.0.1", PORT), MockHandler)
    print(f"Mock YouTube API server running on http://127.0.0.1:{PORT}")
    print(f"  API base:  http://127.0.0.1:{PORT}/youtube/v3")
    print(f"  Token URL: http://127.0.0.1:{PORT}/oauth2/token")
    print(f"  Stats:     http://127.0.0.1:{PORT}/mock/stats")
    print(f"  Reset:     http://127.0.0.1:{PORT}/mock/reset")
    print()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()


if __name__ == "__main__":
    main()
