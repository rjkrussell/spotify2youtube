"""Track matching engine: exact -> fuzzy -> manual fallback."""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass

from rapidfuzz import fuzz

from src.models.library import Track, MatchingPreference, TransferStatus

log = logging.getLogger(__name__)


# Patterns to clean from search queries
CLEAN_PATTERNS = [
    r"\s*\(feat\..*?\)",
    r"\s*\(ft\..*?\)",
    r"\s*feat\..*$",
    r"\s*ft\..*$",
    r"\s*-\s*Remastered.*$",
    r"\s*-\s*Remaster.*$",
    r"\s*\(Remastered.*?\)",
    r"\s*\(Deluxe.*?\)",
    r"\s*\(Bonus.*?\)",
    r"\s*\(Live.*?\)",
    r"\s*\[.*?\]",
]


def clean_query(text: str) -> str:
    """Remove noise from track/artist names for better matching."""
    for pattern in CLEAN_PATTERNS:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    return text.strip()


@dataclass
class MatchResult:
    track: Track
    status: TransferStatus
    best_match: dict | None = None
    score: float = 0.0
    candidates: list[dict] | None = None
    error: str | None = None
    context: str = ""
    yt_playlist_id: str = ""


class TrackMatcher:
    """Three-step track matching: exact -> fuzzy -> manual fallback."""

    EXACT_THRESHOLD = 90
    FUZZY_THRESHOLD = 70
    REQUEST_DELAY = 0.5
    MAX_RETRIES = 3

    def __init__(self, youtube_service):
        self.yt = youtube_service
        self._last_request = 0.0

    def match_track(self, track: Track, album_name: str = "") -> MatchResult:
        """Match a single track. Returns a MatchResult.

        If *album_name* is provided the search query is augmented with the
        album name so YouTube results are biased toward the correct release.
        """
        first_artist = track.artists[0] if track.artists else ""
        base_query = f"{track.name} {first_artist}"

        # Manual preference => skip to ambiguous
        if track.matching_pref == MatchingPreference.MANUAL:
            candidates = self._search_with_rate_limit(base_query)
            return MatchResult(
                track=track,
                status=TransferStatus.AMBIGUOUS,
                candidates=candidates,
            )

        threshold = self.EXACT_THRESHOLD if track.matching_pref == MatchingPreference.STRICT else self.FUZZY_THRESHOLD

        # Step 1: Exact search (include album name when available)
        query = f"{base_query} {album_name}".strip() if album_name else base_query
        results = self._search_with_rate_limit(query)
        best, score = self._score_results(track, results)

        log.info(
            "match %r q=%r results=%d best_score=%.0f threshold=%d",
            track.name, query, len(results), score, threshold,
        )

        if best and score >= self.EXACT_THRESHOLD:
            return MatchResult(
                track=track,
                status=TransferStatus.SUCCESS,
                best_match=best,
                score=score,
            )

        # Step 2: Fuzzy search (clean query)
        if track.matching_pref != MatchingPreference.STRICT:
            cleaned_name = clean_query(track.name)
            cleaned_artist = clean_query(first_artist) if first_artist else ""
            cleaned_album = clean_query(album_name) if album_name else ""
            fuzzy_query = f"{cleaned_name} {cleaned_artist} {cleaned_album}".strip()

            if fuzzy_query != query:
                results2 = self._search_with_rate_limit(fuzzy_query)
                best2, score2 = self._score_results(track, results2)

                if best2 and score2 > score:
                    best, score = best2, score2
                    results = results2
                    log.info("  fuzzy improved: q=%r score=%.0f", fuzzy_query, score)

        if best and score >= threshold:
            return MatchResult(
                track=track,
                status=TransferStatus.SUCCESS,
                best_match=best,
                score=score,
            )

        # Step 3: Queue as ambiguous
        log.warning(
            "  AMBIGUOUS %r best_score=%.0f < threshold=%d (%d candidates)",
            track.name, score, threshold, len(results),
        )
        return MatchResult(
            track=track,
            status=TransferStatus.AMBIGUOUS,
            best_match=best,
            score=score,
            candidates=results[:5] if results else [],
        )

    def _score_results(self, track: Track, results: list[dict]) -> tuple[dict | None, float]:
        """Score search results against the source track. Returns (best_match, score)."""
        if not results:
            return None, 0.0

        best = None
        best_score = 0.0

        for result in results:
            score = self._compute_score(track, result)
            if score > best_score:
                best_score = score
                best = result

        return best, best_score

    def _compute_score(self, track: Track, result: dict) -> float:
        """Weighted score: title (0.5), artist (0.3), duration (0.2)."""
        result_title = result.get("title", "")
        result_artists = [a.get("name", "") for a in result.get("artists", [])]
        result_artist = ", ".join(result_artists)

        title_score = fuzz.token_sort_ratio(track.name.lower(), result_title.lower())
        artist_score = fuzz.token_sort_ratio(
            ", ".join(track.artists).lower(),
            result_artist.lower(),
        )

        # Duration similarity (0-100 scale)
        result_duration = (result.get("duration_seconds") or 0) * 1000
        if result_duration and track.duration_ms:
            diff_ms = abs(track.duration_ms - result_duration)
            # Within 5 seconds = 100, within 30s = ~50, beyond = low
            duration_score = max(0, 100 - (diff_ms / 300))
        else:
            duration_score = 50  # neutral if no duration info

        return title_score * 0.5 + artist_score * 0.3 + duration_score * 0.2

    def _search_with_rate_limit(self, query: str) -> list[dict]:
        """Search with rate limiting and exponential backoff."""
        # Rate limit
        elapsed = time.time() - self._last_request
        if elapsed < self.REQUEST_DELAY:
            time.sleep(self.REQUEST_DELAY - elapsed)

        for attempt in range(self.MAX_RETRIES):
            try:
                self._last_request = time.time()
                return self.yt.search_tracks(query, limit=5)
            except Exception as e:
                if "429" in str(e) and attempt < self.MAX_RETRIES - 1:
                    backoff = self.REQUEST_DELAY * (2 ** (attempt + 1))
                    time.sleep(backoff)
                else:
                    raise
        return []
