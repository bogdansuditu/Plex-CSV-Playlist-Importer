from __future__ import annotations

import logging
from typing import Callable, Iterable, List, Optional

from plexapi.exceptions import NotFound
from plexapi.server import PlexServer

from app.models import ImportResult, PlaylistEntry, UnmatchedTrack
from app.services.matching import TrackMatcher

logger = logging.getLogger(__name__)


class PlaylistImportError(Exception):
    pass


class PlaylistImporter:
    def __init__(self, plex_url: str, plex_token: str, music_section: str, match_threshold: float) -> None:
        if not plex_token:
            raise PlaylistImportError("Plex token is required.")
        self.plex_url = plex_url
        self.plex_token = plex_token
        self.music_section = music_section
        self.match_threshold = match_threshold

    def import_playlist(
        self,
        entries: Iterable[PlaylistEntry],
        playlist_name: str,
        replace_existing: bool,
        progress_callback: Optional[Callable[[int], None]] = None,
    ) -> ImportResult:
        try:
            plex = PlexServer(self.plex_url, self.plex_token)
        except Exception as exc:
            logger.exception("Failed to connect to Plex server at %s", self.plex_url)
            raise PlaylistImportError(
                f"Unable to connect to Plex server. Check URL and token. ({exc})"
            ) from exc

        try:
            section = plex.library.section(self.music_section)
        except Exception as exc:
            logger.exception("Music section '%s' not found", self.music_section)
            raise PlaylistImportError(f"Music section '{self.music_section}' not found. ({exc})") from exc

        matcher = TrackMatcher(section=section, threshold=self.match_threshold)
        matched_tracks: List = []
        unmatched: List[UnmatchedTrack] = []
        seen_rating_keys = set()
        matched_count = 0

        for index, entry in enumerate(entries, start=1):
            attempt = matcher.find_best_match(entry)
            match = attempt.result
            if match and getattr(match.track, "ratingKey", None) is not None:
                if not _has_playable_media(match.track):
                    logger.warning(
                        "Skipping track %s — Plex reports no playable media.",
                        getattr(match.track, "title", "<unknown>"),
                    )
                    unmatched.append(
                        UnmatchedTrack(
                            row=entry.row,
                            track_name=entry.track_name,
                            artist_name=entry.artist_name,
                            reason="Matched Plex track has no playable media (check library paths).",
                        )
                    )
                    continue
                matched_count += 1
                rating_key = getattr(match.track, "ratingKey")
                if rating_key in seen_rating_keys:
                    continue
                seen_rating_keys.add(rating_key)
                matched_tracks.append(match.track)
            else:
                if attempt.had_candidates and attempt.best_score > 0:
                    reason = (
                        f"Best match score {attempt.best_score:.1f} < threshold {self.match_threshold:.0f}."
                    )
                else:
                    reason = "Track not found in the selected library."
                unmatched.append(
                    UnmatchedTrack(
                        row=entry.row,
                        track_name=entry.track_name,
                        artist_name=entry.artist_name,
                        reason=reason,
                    )
                )

            if progress_callback:
                try:
                    progress_callback(index)
                except Exception:  # pragma: no cover - progress is best-effort
                    logger.debug("Progress callback failed", exc_info=True)

        try:
            added_count = self._apply_playlist_changes(
                plex,
                section=section,
                playlist_name=playlist_name,
                tracks=matched_tracks,
                replace_existing=replace_existing,
            )
        except Exception as exc:
            logger.exception("Failed to apply playlist changes for '%s'", playlist_name)
            raise PlaylistImportError(f"Failed to update playlist '{playlist_name}'. ({exc})") from exc

        result = ImportResult(
            matched_count=matched_count,
            added_count=added_count,
            unmatched=unmatched,
        )
        return result

    def _apply_playlist_changes(
        self,
        plex: PlexServer,
        section,
        playlist_name: str,
        tracks: List,
        replace_existing: bool,
    ) -> int:
        if not tracks:
            logger.info("No tracks matched for playlist '%s'; skipping Plex updates", playlist_name)
            return 0

        try:
            playlist = plex.playlist(playlist_name)
        except NotFound:
            playlist = None

        if playlist is None:
            logger.info(
                "Creating new Plex playlist '%s' with %s tracks in section '%s'",
                playlist_name,
                len(tracks),
                getattr(section, "title", section),
            )
            plex.createPlaylist(playlist_name, items=tracks, section=section)
            return len(tracks)

        if replace_existing:
            logger.info("Replacing contents of existing playlist '%s' with %s tracks", playlist_name, len(tracks))
            items = list(playlist.items())
            if items:
                try:
                    playlist.removeItems(items)
                except Exception:
                    logger.warning("Failed to remove items via removeItems; retrying individually", exc_info=True)
                    for item in items:
                        try:
                            playlist.removeItems([item])
                        except Exception:
                            logger.exception("Unable to remove track %s", getattr(item, "title", "<unknown>"))
            playlist.addItems(tracks)
            return len(tracks)

        existing_rating_keys = {item.ratingKey for item in playlist.items()}
        new_tracks = [track for track in tracks if getattr(track, "ratingKey", None) not in existing_rating_keys]
        if not new_tracks:
            logger.info("No new tracks to add to playlist '%s'", playlist_name)
            return 0
        logger.info("Appending %s new tracks to playlist '%s'", len(new_tracks), playlist_name)
        playlist.addItems(new_tracks)
        return len(new_tracks)


def _has_playable_media(track) -> bool:
    locations = []
    try:
        locations = list(getattr(track, "locations", []) or [])
    except Exception:
        locations = []

    if locations:
        return True

    try:
        for media in getattr(track, "media", []) or []:
            for part in getattr(media, "parts", []) or []:
                if getattr(part, "file", None):
                    return True
    except Exception:
        pass
    return False
