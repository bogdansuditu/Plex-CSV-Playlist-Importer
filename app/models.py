from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class PlaylistEntry(BaseModel):
    row: int
    track_name: str
    artist_name: str
    album_name: Optional[str] = None

    @property
    def combined_key(self) -> str:
        return f"{self.artist_name} - {self.track_name}".strip()


class PlaylistPayload(BaseModel):
    entries: List[PlaylistEntry]
    normalized_csv: str


class UnmatchedTrack(BaseModel):
    row: int
    track_name: str
    artist_name: str
    reason: Optional[str] = None


class ImportResult(BaseModel):
    matched_count: int
    added_count: int
    unmatched: List[UnmatchedTrack]


__all__ = [
    "ImportResult",
    "PlaylistEntry",
    "PlaylistPayload",
    "UnmatchedTrack",
]
