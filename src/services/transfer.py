"""Transfer controller: threading + queue orchestration."""

from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass, field

from src.models.library import (
    Track, Playlist, Album, Artist, SpotifyLibrary,
    MatchingPreference, TransferStatus,
)
from src.services.matcher import TrackMatcher, MatchResult


@dataclass
class ArtistResult:
    artist: Artist
    status: TransferStatus
    channel_title: str = ""
    error: str | None = None


@dataclass
class TransferProgress:
    total: int = 0
    completed: int = 0
    current_item: str = ""
    results: list[MatchResult] = field(default_factory=list)
    failed_tracks: list[Track] = field(default_factory=list)
    ambiguous_tracks: list[MatchResult] = field(default_factory=list)
    artist_results: list[ArtistResult] = field(default_factory=list)
    done: bool = False
    error: str | None = None
    cancelled: bool = False
    # Per-category totals (set at start)
    total_playlists: int = 0
    total_playlist_tracks: int = 0
    total_liked: int = 0
    total_album_tracks: int = 0
    total_artists: int = 0


class TransferController:
    """Runs the transfer in a background thread, communicating via a queue."""

    def __init__(self, youtube_service, state_manager, dry_run: bool = False,
                 max_consecutive_failures: int = 5):
        self.yt = youtube_service
        self.state_manager = state_manager
        self.dry_run = dry_run
        self.max_consecutive_failures = max_consecutive_failures
        self.matcher = TrackMatcher(youtube_service)
        self.progress = TransferProgress()
        self._queue: queue.Queue = queue.Queue()
        self._thread: threading.Thread | None = None
        self._cancel = threading.Event()

    def start(self, selected: dict):
        """Start the transfer in a background thread."""
        self._cancel.clear()
        self.progress = TransferProgress()

        # Count total items (per-category and overall)
        pl_count = len(selected.get("playlists", []))
        pl_tracks = sum(len([t for t in pl.tracks if t.selected]) for pl in selected.get("playlists", []))
        liked_count = len(selected.get("liked_tracks", []))
        album_tracks = sum(len([t for t in alb.tracks if t.selected]) for alb in selected.get("albums", []))
        artist_count = len(selected.get("artists", []))

        self.progress.total_playlists = pl_count
        self.progress.total_playlist_tracks = pl_tracks
        self.progress.total_liked = liked_count
        self.progress.total_album_tracks = album_tracks
        self.progress.total_artists = artist_count
        self.progress.total = pl_count + pl_tracks + liked_count + album_tracks + artist_count

        self._thread = threading.Thread(target=self._run, args=(selected,), daemon=True)
        self._thread.start()

    def cancel(self):
        """Signal the transfer to stop."""
        self._cancel.set()

    def poll(self) -> TransferProgress:
        """Read latest progress (called from main thread via after())."""
        while not self._queue.empty():
            try:
                msg = self._queue.get_nowait()
                if msg["type"] == "progress":
                    self.progress.completed = msg["completed"]
                    self.progress.current_item = msg["item"]
                elif msg["type"] == "result":
                    self.progress.results.append(msg["result"])
                elif msg["type"] == "artist_result":
                    self.progress.artist_results.append(msg["result"])
                elif msg["type"] == "done":
                    self.progress.done = True
                elif msg["type"] == "error":
                    self.progress.error = msg["error"]
                    self.progress.done = True
            except queue.Empty:
                break
        return self.progress

    def _run(self, selected: dict):
        """Main transfer loop (runs in background thread)."""
        try:
            completed = 0
            consecutive_failures = 0

            # Transfer playlists
            for pl in selected.get("playlists", []):
                if self._cancel.is_set():
                    break

                self._queue.put({"type": "progress", "completed": completed, "item": f"Playlist: {pl.display_name()}"})

                # Match tracks
                matched_ids = []
                for track in pl.tracks:
                    if not track.selected:
                        continue
                    if self._cancel.is_set():
                        break
                    if track.transfer_status == TransferStatus.SUCCESS and track.yt_video_id:
                        matched_ids.append(track.yt_video_id)
                        completed += 1
                        self._queue.put({"type": "progress", "completed": completed, "item": f"Already matched: {track.name}"})
                        continue

                    try:
                        result = self.matcher.match_track(track)
                    except Exception as e:
                        result = MatchResult(track=track, status=TransferStatus.FAILED, error=str(e))
                    result.context = f"Playlist: {pl.display_name()}"
                    self._queue.put({"type": "result", "result": result})

                    if result.status == TransferStatus.SUCCESS and result.best_match:
                        video_id = result.best_match.get("videoId", "")
                        track.yt_video_id = video_id
                        track.transfer_status = TransferStatus.SUCCESS
                        matched_ids.append(video_id)
                        consecutive_failures = 0
                    elif result.status == TransferStatus.AMBIGUOUS:
                        track.transfer_status = TransferStatus.AMBIGUOUS
                        track.yt_candidates = result.candidates or []
                        self.progress.ambiguous_tracks.append(result)
                        consecutive_failures = 0
                    else:
                        track.transfer_status = TransferStatus.FAILED
                        self.progress.failed_tracks.append(track)
                        consecutive_failures += 1

                    completed += 1
                    self._queue.put({"type": "progress", "completed": completed, "item": f"Track: {track.name}"})
                    self.state_manager.save()

                    if consecutive_failures >= self.max_consecutive_failures:
                        err = result.error or "Unknown error"
                        self._queue.put({"type": "error", "error": f"Stopped: {consecutive_failures} consecutive failures ({err})"})
                        return

                # Create/merge playlist on YT
                if not self.dry_run and matched_ids:
                    if pl.merge_into_yt_id:
                        self.yt.add_playlist_items(pl.merge_into_yt_id, matched_ids)
                        pl.yt_playlist_id = pl.merge_into_yt_id
                    else:
                        yt_id = self.yt.create_playlist(
                            pl.display_name(),
                            pl.description,
                            video_ids=matched_ids,
                        )
                        pl.yt_playlist_id = yt_id

                # Backfill yt_playlist_id on ambiguous results so review screen can add them later
                if pl.yt_playlist_id:
                    for ar in self.progress.ambiguous_tracks:
                        if ar.context == f"Playlist: {pl.display_name()}" and not ar.yt_playlist_id:
                            ar.yt_playlist_id = pl.yt_playlist_id

                selected_tracks = [t for t in pl.tracks if t.selected]
                if any(t.transfer_status == TransferStatus.FAILED for t in selected_tracks):
                    pl.transfer_status = TransferStatus.FAILED
                elif any(t.transfer_status == TransferStatus.AMBIGUOUS for t in selected_tracks):
                    pl.transfer_status = TransferStatus.AMBIGUOUS
                else:
                    pl.transfer_status = TransferStatus.SUCCESS
                completed += 1
                self._queue.put({"type": "progress", "completed": completed, "item": f"Playlist done: {pl.display_name()}"})
                self.state_manager.save()

            # Transfer liked tracks
            consecutive_failures = 0
            for track in selected.get("liked_tracks", []):
                if self._cancel.is_set():
                    break
                if track.transfer_status == TransferStatus.SUCCESS and track.yt_video_id:
                    completed += 1
                    self._queue.put({"type": "progress", "completed": completed, "item": f"Already liked: {track.name}"})
                    continue

                try:
                    result = self.matcher.match_track(track)
                except Exception as e:
                    result = MatchResult(track=track, status=TransferStatus.FAILED, error=str(e))
                result.context = "Liked Songs"
                self._queue.put({"type": "result", "result": result})

                if result.status == TransferStatus.SUCCESS and result.best_match:
                    video_id = result.best_match.get("videoId", "")
                    track.yt_video_id = video_id
                    track.transfer_status = TransferStatus.SUCCESS
                    consecutive_failures = 0
                    if not self.dry_run:
                        try:
                            self.yt.rate_song(video_id, "LIKE")
                        except Exception:
                            pass  # Like failed but match succeeded
                elif result.status == TransferStatus.AMBIGUOUS:
                    track.transfer_status = TransferStatus.AMBIGUOUS
                    track.yt_candidates = result.candidates or []
                    self.progress.ambiguous_tracks.append(result)
                    consecutive_failures = 0
                else:
                    track.transfer_status = TransferStatus.FAILED
                    self.progress.failed_tracks.append(track)
                    consecutive_failures += 1

                completed += 1
                self._queue.put({"type": "progress", "completed": completed, "item": f"Liked: {track.name}"})
                self.state_manager.save()

                if consecutive_failures >= self.max_consecutive_failures:
                    err = result.error or "Unknown error"
                    self._queue.put({"type": "error", "error": f"Stopped: {consecutive_failures} consecutive failures ({err})"})
                    return

            # Transfer album tracks (like each track)
            consecutive_failures = 0
            for album in selected.get("albums", []):
                if self._cancel.is_set():
                    break
                for track in album.tracks:
                    if not track.selected or self._cancel.is_set():
                        continue
                    if track.transfer_status == TransferStatus.SUCCESS and track.yt_video_id:
                        completed += 1
                        self._queue.put({"type": "progress", "completed": completed, "item": f"Already matched: {track.name}"})
                        continue

                    try:
                        result = self.matcher.match_track(track)
                    except Exception as e:
                        result = MatchResult(track=track, status=TransferStatus.FAILED, error=str(e))
                    result.context = f"Album: {album.name}"
                    self._queue.put({"type": "result", "result": result})

                    if result.status == TransferStatus.SUCCESS and result.best_match:
                        video_id = result.best_match.get("videoId", "")
                        track.yt_video_id = video_id
                        track.transfer_status = TransferStatus.SUCCESS
                        consecutive_failures = 0
                        if not self.dry_run:
                            try:
                                self.yt.rate_song(video_id, "LIKE")
                            except Exception:
                                pass
                    elif result.status == TransferStatus.AMBIGUOUS:
                        track.transfer_status = TransferStatus.AMBIGUOUS
                        track.yt_candidates = result.candidates or []
                        self.progress.ambiguous_tracks.append(result)
                        consecutive_failures = 0
                    else:
                        track.transfer_status = TransferStatus.FAILED
                        self.progress.failed_tracks.append(track)
                        consecutive_failures += 1

                    completed += 1
                    self._queue.put({"type": "progress", "completed": completed, "item": f"Album track: {track.name}"})
                    self.state_manager.save()

                    if consecutive_failures >= self.max_consecutive_failures:
                        err = result.error or "Unknown error"
                        self._queue.put({"type": "error", "error": f"Stopped: {consecutive_failures} consecutive failures ({err})"})
                        return

                selected_tracks = [t for t in album.tracks if t.selected]
                if any(t.transfer_status == TransferStatus.FAILED for t in selected_tracks):
                    album.transfer_status = TransferStatus.FAILED
                elif any(t.transfer_status == TransferStatus.AMBIGUOUS for t in selected_tracks):
                    album.transfer_status = TransferStatus.AMBIGUOUS
                else:
                    album.transfer_status = TransferStatus.SUCCESS

            # Subscribe to artists
            for artist in selected.get("artists", []):
                if self._cancel.is_set():
                    break
                if artist.transfer_status == TransferStatus.SUCCESS:
                    completed += 1
                    continue

                ar_result = ArtistResult(artist=artist, status=TransferStatus.FAILED)

                if not self.dry_run:
                    try:
                        channels = self.yt.search_channels(artist.name, limit=1)
                        if channels:
                            channel_id = channels[0].get("channelId", "")
                            channel_title = channels[0].get("title", "")
                            if channel_id:
                                self.yt.subscribe_artist(channel_id)
                                artist.transfer_status = TransferStatus.SUCCESS
                                ar_result.status = TransferStatus.SUCCESS
                                ar_result.channel_title = channel_title
                            else:
                                artist.transfer_status = TransferStatus.FAILED
                                ar_result.error = "No channel ID in search result"
                        else:
                            artist.transfer_status = TransferStatus.FAILED
                            ar_result.error = "No channels found"
                    except Exception as e:
                        artist.transfer_status = TransferStatus.FAILED
                        ar_result.error = str(e)
                else:
                    artist.transfer_status = TransferStatus.SUCCESS
                    ar_result.status = TransferStatus.SUCCESS

                self._queue.put({"type": "artist_result", "result": ar_result})
                completed += 1
                self._queue.put({"type": "progress", "completed": completed, "item": f"Artist: {artist.name}"})
                self.state_manager.save()

            if self._cancel.is_set():
                self.progress.cancelled = True

            self._queue.put({"type": "done"})

        except Exception as e:
            self._queue.put({"type": "error", "error": str(e)})
