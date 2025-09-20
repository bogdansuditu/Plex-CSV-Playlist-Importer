from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Set

from rapidfuzz import fuzz
from unidecode import unidecode

from app.models import PlaylistEntry

logger = logging.getLogger(__name__)

REMOVALS = (
    r"\((feat\.|featuring).*?\)",
    r"-\s*remaster(ed)?\s*\d*",
    r"-\s*deluxe edition",
    r"-\s*live",
    r"\[.*?\]",
)
STOP_WORDS = {
    "feat.",
    "featuring",
    "remastered",
    "remaster",
    "deluxe",
    "edition",
    "explicit",
}


@dataclass
class MatchResult:
    track: Any
    score: float


@dataclass
class MatchAttempt:
    result: Optional[MatchResult]
    best_score: float
    had_candidates: bool


class TrackMatcher:
    def __init__(self, section: Any, threshold: float = 70.0) -> None:
        self.section = section
        self.threshold = threshold

    def find_best_match(self, entry: PlaylistEntry) -> MatchAttempt:
        logger.debug(
            "Searching for track='%s' artist='%s' (row %s)",
            entry.track_name,
            entry.artist_name,
            entry.row,
        )
        queries = self._build_queries(entry)
        best: Optional[MatchResult] = None
        seen_keys: Set[str] = set()
        had_candidates = False
        best_score_seen = 0.0

        for query in queries:
            candidates = list(self._search_candidates(query))
            if candidates:
                had_candidates = True
            logger.debug("Query %s returned %s candidates", query, len(candidates))
            for candidate in candidates:
                rating_key = getattr(candidate, "ratingKey", None)
                if rating_key in seen_keys:
                    continue
                seen_keys.add(rating_key)

                score = self._score_candidate(entry, candidate)
                best_score_seen = max(best_score_seen, score)
                logger.debug(
                    "Candidate title='%s' artist='%s' score=%.2f",
                    getattr(candidate, "title", "<unknown>"),
                    getattr(candidate, "grandparentTitle", "") or getattr(candidate, "artist", ""),
                    score,
                )
                if score >= self.threshold and (best is None or score > best.score):
                    best = MatchResult(track=candidate, score=score)
                    if score == 100:
                        return MatchAttempt(result=best, best_score=best_score_seen, had_candidates=had_candidates)
        if best is None:
            if had_candidates:
                logger.debug("Best score %.2f below threshold %.2f", best_score_seen, self.threshold)
            else:
                logger.debug("No candidates met threshold %.2f", self.threshold)
        return MatchAttempt(result=best, best_score=best_score_seen, had_candidates=had_candidates)

    def _build_queries(self, entry: PlaylistEntry) -> List[Dict[str, Any]]:
        title_variants = self._title_variants(entry.track_name)
        artist = entry.artist_name.strip()
        album = entry.album_name.strip() if entry.album_name else None

        queries: List[Dict[str, Any]] = []
        for title in title_variants:
            if title and artist and album:
                queries.append({"title": title, "artist": artist, "album": album})
            if title and artist:
                queries.append({"title": title, "artist": artist})
            if title and album:
                queries.append({"title": title, "album": album})
            if title:
                queries.append({"title": title})
        return queries

    def _search_candidates(self, query: Dict[str, Any]) -> Iterable[Any]:
        search_kwargs = {k: v for k, v in query.items() if v}
        title = search_kwargs.get("title")
        if not title:
            return []

        try:
            results = self.section.searchTracks(**search_kwargs)
        except Exception as exc:
            logger.debug("searchTracks error for %s: %s", search_kwargs, exc)
            results = []

        filtered = [
            item
            for item in results
            if getattr(item, "title", "")
            and getattr(item, "ratingKey", None) is not None
            and getattr(item, "TYPE", getattr(item, "type", "")) == "track"
        ]

        if filtered:
            return filtered

        fallback_query = " ".join(filter(None, [query.get("artist"), query.get("title"), query.get("album")]))
        if not fallback_query:
            fallback_query = title

        try:
            fallback_results = self.section.search(fallback_query, libtype="track")
        except Exception as exc:
            logger.debug("Fallback search error for '%s': %s", fallback_query, exc)
            return []

        fallback_filtered = [
            item
            for item in fallback_results
            if getattr(item, "title", "")
            and getattr(item, "ratingKey", None) is not None
            and getattr(item, "TYPE", getattr(item, "type", "")) == "track"
        ]
        if fallback_filtered:
            logger.debug(
                "Fallback search for '%s' returned %s candidates",
                fallback_query,
                len(fallback_filtered),
            )
        return fallback_filtered

    def _score_candidate(self, entry: PlaylistEntry, candidate: Any) -> float:
        entry_key = normalize_key(entry.combined_key)
        candidate_title = getattr(candidate, "title", "")
        candidate_artist = getattr(candidate, "grandparentTitle", "") or getattr(candidate, "artist", "")
        candidate_album = getattr(candidate, "parentTitle", "")

        candidate_key = normalize_key(f"{candidate_artist} - {candidate_title}")
        base_score = fuzz.WRatio(entry_key, candidate_key)

        if entry.album_name and candidate_album:
            album_score = fuzz.partial_ratio(normalize_key(entry.album_name), normalize_key(candidate_album))
            base_score = (base_score * 0.7) + (album_score * 0.3)

        return float(round(base_score, 2))

    def _title_variants(self, title: str) -> List[str]:
        variants: List[str] = []
        seen: Set[str] = set()

        def _add(value: str) -> None:
            candidate = value.strip()
            if candidate and candidate.lower() not in seen:
                seen.add(candidate.lower())
                variants.append(candidate)

        _add(title)
        stripped_parentheses = re.sub(r"\s*\(.*?\)", "", title)
        _add(stripped_parentheses)
        dashed_split = re.split(r"\s+-\s+", stripped_parentheses, maxsplit=1)[0]
        _add(dashed_split)
        feat_removed = re.sub(r"\s*(feat\.|featuring)\b.*", "", dashed_split, flags=re.IGNORECASE)
        _add(feat_removed)

        return variants


def normalize_key(text: str) -> str:
    lowered = unidecode(text or "").lower()
    cleaned = lowered
    for pattern in REMOVALS:
        cleaned = re.sub(pattern, " ", cleaned)
    for word in STOP_WORDS:
        cleaned = cleaned.replace(word, " ")
    cleaned = re.sub(r"[^a-z0-9]+", " ", cleaned)
    return cleaned.strip()
