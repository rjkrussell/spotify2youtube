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
class TransferProgress:
    total: int = 0
    completed: int = 0
    current_item: str = ""
    results: list[MatchResult] = field(default_factory=list)
    failed_tracks: list[Track] = field(default_factory=list)
    ambiguous_tracks: list[MatchResult] = field(default_factory=list)
    done: bool = False
    error: str | None = None
    cancelled: bool = False


class TransferController:
    """Runs the transfer in a background thread, communicating via a queue."""

    def __init__(self, youtube_service, state_manager, dry_run: bool = False):
        self.yt = youtube_service
        self.state_manager = state_manager
        self.dry_run = dry_run
        self.matcher = TrackMatcher(youtube_service)
        self.progress = TransferProgress()
        self._queue: queue.Queue = queue.Queue()
        self._thread: threading.Thread | None = None
        self._cancel = threading.Event()

    def start(self, selected: dict):
        """Start the transfer in a background thread."""
        self._cancel.clear()
        self.progress = TransferProgress()

        # Count total items
        total = 0
        for pl in selected.get("playlists", []):
            total += 1 + len([t for t in pl.tracks if t.selected])
        total += len(selected.get("liked_tracks", []))
        for alb in selected.get("albums", []):
            total += len([t for t in alb.tracks if t.selected])
        total += len(selected.get("artists", []))
        self.progress.total = total

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
                    except Exception:
                        result = MatchResult(track=track, status=TransferStatus.FAILED)
                    self._queue.put({"type": "result", "result": result})

                    if result.status == TransferStatus.SUCCESS and result.best_match:
                        video_id = result.best_match.get("videoId", "")
                        track.yt_video_id = video_id
                        track.transfer_status = TransferStatus.SUCCESS
                        matched_ids.append(video_id)
                    elif result.status == TransferStatus.AMBIGUOUS:
                        track.transfer_status = TransferStatus.AMBIGUOUS
                        track.yt_candidates = result.candidates or []
                        self.progress.ambiguous_tracks.append(result)
                    else:
                        track.transfer_status = TransferStatus.FAILED
                        self.progress.failed_tracks.append(track)

                    completed += 1
                    self._queue.put({"type": "progress", "completed": completed, "item": f"Track: {track.name}"})
                    self.state_manager.save()

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

                pl.transfer_status = TransferStatus.SUCCESS
                completed += 1
                self._queue.put({"type": "progress", "completed": completed, "item": f"Playlist done: {pl.display_name()}"})
                self.state_manager.save()

            # Transfer liked tracks
            for track in selected.get("liked_tracks", []):
                if self._cancel.is_set():
                    break
                if track.transfer_status == TransferStatus.SUCCESS and track.yt_video_id:
                    completed += 1
                    self._queue.put({"type": "progress", "completed": completed, "item": f"Already liked: {track.name}"})
                    continue

                try:
                    result = self.matcher.match_track(track)
                except Exception:
                    result = MatchResult(track=track, status=TransferStatus.FAILED)
                self._queue.put({"type": "result", "result": result})

                if result.status == TransferStatus.SUCCESS and result.best_match:
                    video_id = result.best_match.get("videoId", "")
                    track.yt_video_id = video_id
                    track.transfer_status = TransferStatus.SUCCESS
                    if not self.dry_run:
                        try:
                            self.yt.rate_song(video_id, "LIKE")
                        except Exception:
                            pass  # Like failed but match succeeded
                elif result.status == TransferStatus.AMBIGUOUS:
                    track.transfer_status = TransferStatus.AMBIGUOUS
                    track.yt_candidates = result.candidates or []
                    self.progress.ambiguous_tracks.append(result)
                else:
                    track.transfer_status = TransferStatus.FAILED
                    self.progress.failed_tracks.append(track)

                completed += 1
                self._queue.put({"type": "progress", "completed": completed, "item": f"Liked: {track.name}"})
                self.state_manager.save()

            # Transfer album tracks (like each track)
            for album in selected.get("albums", []):
                if self._cancel.is_set():
                    break
                for track in album.tracks:
                    if not track.selected or self._cancel.is_set():
                        continue
                    if track.transfer_status == TransferStatus.SUCCESS and track.yt_video_id:
                        completed += 1
                        continue

                    try:
                        result = self.matcher.match_track(track)
                    except Exception:
                        result = MatchResult(track=track, status=TransferStatus.FAILED)
                    self._queue.put({"type": "result", "result": result})

                    if result.status == TransferStatus.SUCCESS and result.best_match:
                        video_id = result.best_match.get("videoId", "")
                        track.yt_video_id = video_id
                        track.transfer_status = TransferStatus.SUCCESS
                        if not self.dry_run:
                            try:
                                self.yt.rate_song(video_id, "LIKE")
                            except Exception:
                                pass
                    elif result.status == TransferStatus.AMBIGUOUS:
                        track.transfer_status = TransferStatus.AMBIGUOUS
                        track.yt_candidates = result.candidates or []
                        self.progress.ambiguous_tracks.append(result)
                    else:
                        track.transfer_status = TransferStatus.FAILED
                        self.progress.failed_tracks.append(track)

                    completed += 1
                    self._queue.put({"type": "progress", "completed": completed, "item": f"Album track: {track.name}"})
                    self.state_manager.save()

                album.transfer_status = TransferStatus.SUCCESS

            # Subscribe to artists
            for artist in selected.get("artists", []):
                if self._cancel.is_set():
                    break
                if artist.transfer_status == TransferStatus.SUCCESS:
                    completed += 1
                    continue

                if not self.dry_run:
                    try:
                        # Search for artist to get channel ID
                        results = self.yt.ytm.search(artist.name, filter="artists", limit=1)
                        if results:
                            channel_id = results[0].get("browseId", "")
                            if channel_id:
                                self.yt.subscribe_artist(channel_id)
                                artist.transfer_status = TransferStatus.SUCCESS
                            else:
                                artist.transfer_status = TransferStatus.FAILED
                        else:
                            artist.transfer_status = TransferStatus.FAILED
                    except Exception:
                        artist.transfer_status = TransferStatus.FAILED
                else:
                    artist.transfer_status = TransferStatus.SUCCESS

                completed += 1
                self._queue.put({"type": "progress", "completed": completed, "item": f"Artist: {artist.name}"})
                self.state_manager.save()

            if self._cancel.is_set():
                self.progress.cancelled = True

            self._queue.put({"type": "done"})

        except Exception as e:
            self._queue.put({"type": "error", "error": str(e)})
