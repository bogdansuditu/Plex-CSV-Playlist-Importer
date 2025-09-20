from __future__ import annotations

import csv
import io
import logging
from typing import Dict, List, Optional, Sequence

import pandas as pd

from app.models import PlaylistEntry, PlaylistPayload

logger = logging.getLogger(__name__)


class CSVParseError(Exception):
    pass


COLUMN_ALIASES: Dict[str, str] = {
    "track name": "track_name",
    "title": "track_name",
    "track": "track_name",
    "artist name": "artist_name",
    "artist": "artist_name",
    "album": "album_name",
    "album name": "album_name",
}


REQUIRED_COLUMNS = {"track_name", "artist_name"}
def parse_playlist_csv(csv_text: str = "", csv_bytes: Optional[bytes] = None) -> PlaylistPayload:
    raw_csv = _resolve_csv_payload(csv_text, csv_bytes)

    try:
        dataframe = pd.read_csv(
            io.StringIO(raw_csv),
            sep=None,
            engine="python",
            dtype=str,
            keep_default_na=False,
        )
    except Exception as exc:  # pragma: no cover - pandas parses many edge cases
        raise CSVParseError(f"Unable to parse CSV: {exc}") from exc

    if dataframe.empty:
        raise CSVParseError("The CSV file is empty.")

    normalized = {_normalize(col): col for col in dataframe.columns}
    column_map: Dict[str, str] = {}
    for friendly, internal in COLUMN_ALIASES.items():
        if friendly in normalized:
            column_map[internal] = normalized[friendly]

    missing = REQUIRED_COLUMNS - column_map.keys()
    if missing:
        pretty = ", ".join(sorted(missing))
        raise CSVParseError(f"Missing required columns: {pretty}.")

    rows = dataframe.to_dict(orient="records")
    parsed_entries: List[PlaylistEntry] = []

    for display_index, row in enumerate(rows, start=2):
        track_name = _clean_cell(row.get(column_map["track_name"]))
        artist_name = _clean_cell(row.get(column_map["artist_name"]))
        if not track_name or not artist_name:
            logger.debug(
                "Skipping row %s due to missing track/artist: track='%s' artist='%s'",
                display_index,
                track_name,
                artist_name,
            )
            continue

        album_name = _clean_cell(row.get(column_map.get("album_name", ""))) if "album_name" in column_map else None

        parsed_entries.append(
            PlaylistEntry(
                row=display_index,
                track_name=track_name,
                artist_name=artist_name,
                album_name=album_name or None,
            )
        )

    if not parsed_entries:
        raise CSVParseError("No valid tracks found in the CSV.")

    entries = parsed_entries
    normalized_csv = _serialize_entries(entries)

    logger.info("Parsed %s rows into %s playlist entries", len(rows), len(entries))
    return PlaylistPayload(entries=entries, normalized_csv=normalized_csv)


def _resolve_csv_payload(csv_text: str, csv_bytes: Optional[bytes]) -> str:
    candidate = csv_text.strip()
    if candidate:
        return candidate

    if csv_bytes is None:
        raise CSVParseError("No CSV content provided.")

    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return csv_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise CSVParseError("Unable to decode CSV. Please use UTF-8 or Latin-1 encoding.")


def _normalize(column_name: str) -> str:
    return column_name.strip().lower().replace("_", " ")


def _clean_cell(value: Optional[str]) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return text


def _serialize_entries(entries: Sequence[PlaylistEntry]) -> str:
    header = ["Artist name", "Album", "Track name"]
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(header)
    for entry in entries:
        writer.writerow(
            [
                entry.artist_name,
                entry.album_name or "",
                entry.track_name,
            ]
        )
    return output.getvalue().strip()
