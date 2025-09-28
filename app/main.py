import asyncio
import csv
import logging
from io import StringIO
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import Body, FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.services.csv_loader import CSVParseError, parse_playlist_csv
from app.services.playlist_importer import PlaylistImportError, PlaylistImporter
from app.services.progress import progress_tracker
from app.services.connection_tester import test_plex_connection, PlexConnectionError
from plexapi.server import PlexServer
from app.models import ImportResult, PlaylistEntry

LOG_DIR = Path("logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "importer.log"

root_logger = logging.getLogger()
root_logger.handlers.clear()
root_logger.setLevel(logging.DEBUG)

console_handler = logging.StreamHandler()
console_handler.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
console_handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))

file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(
    logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
)

root_logger.addHandler(console_handler)
root_logger.addHandler(file_handler)

logger = logging.getLogger(__name__)

app = FastAPI(title="Plex CSV Playlist Importer")
templates = Jinja2Templates(directory="app/templates")

REPORT_STORE: Dict[str, str] = {}


def _form_bool(value: Optional[str]) -> bool:
    return value is not None and value.lower() in {"on", "true", "1", "yes"}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    context = {
        "request": request,
        "defaults": settings,
        "error": None,
        "form_values": {
            "plex_url": settings.plex_url,
            "plex_token": settings.plex_token,
            "music_section": settings.default_music_section,
            "playlist_name": "",
            "replace_existing": settings.default_replace_playlist,
            "csv_text": "",
        },
    }
    return templates.TemplateResponse("index.html", context)


@app.post("/import", response_class=HTMLResponse)
async def import_playlist(
    request: Request,
    plex_url: str = Form(""),
    plex_token: str = Form(""),
    music_section: str = Form("Music"),
    playlist_name: str = Form(""),
    replace_existing: Optional[str] = Form(None),
    csv_text: str = Form(""),
    csv_file: Optional[UploadFile] = File(None),
    job_id: str = Form(""),
) -> HTMLResponse:
    replace_flag = _form_bool(replace_existing)
    active_playlist_name = playlist_name.strip()
    csv_text_value = csv_text

    logger.info(
        "Received import request for playlist '%s' targeting section '%s'",
        active_playlist_name or "<auto>",
        music_section,
    )

    if not csv_text.strip() and (not csv_file or not csv_file.filename):
        logger.warning("Import aborted: no CSV text or file provided")
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "defaults": settings,
                "error": "Please provide CSV text or upload a CSV file.",
                "form_values": {
                    "plex_url": plex_url or settings.plex_url,
                    "plex_token": plex_token,
                    "music_section": music_section,
                    "playlist_name": playlist_name,
                    "replace_existing": replace_flag,
                    "csv_text": csv_text_value,
                },
            },
            status_code=400,
        )

    csv_bytes: Optional[bytes] = None
    if csv_file and csv_file.filename:
        csv_bytes = await csv_file.read()

    job_id = job_id.strip()
    if job_id:
        progress_tracker.start(job_id, 0)

    try:
        playlist_payload = parse_playlist_csv(
            csv_text=csv_text_value,
            csv_bytes=csv_bytes,
        )
        csv_text_value = playlist_payload.normalized_csv
    except CSVParseError as exc:
        logger.exception("CSV parsing failed: %s", exc)
        if job_id:
            progress_tracker.error(job_id)
            progress_tracker.pop(job_id)
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "defaults": settings,
                "error": str(exc),
                "form_values": {
                    "plex_url": plex_url or settings.plex_url,
                    "plex_token": plex_token,
                    "music_section": music_section,
                    "playlist_name": playlist_name,
                    "replace_existing": replace_flag,
                    "csv_text": csv_text_value,
                },
            },
            status_code=400,
        )

    if not active_playlist_name:
        active_playlist_name = "Imported Playlist"

    total_entries = len(playlist_payload.entries)

    if job_id:
        progress_tracker.set_total(job_id, total_entries)

    logger.info("Importing against Plex library section '%s'", music_section)

    def progress_callback(processed: int) -> None:
        if job_id:
            progress_tracker.update(job_id, processed)

    # Test connection with fallbacks before creating the importer
    target_plex_url = plex_url or settings.plex_url
    target_plex_token = plex_token or settings.plex_token

    logger.info(f"Testing connection to Plex server before import: {target_plex_url}")
    success, working_url, connection_error = test_plex_connection(target_plex_url, target_plex_token)

    if not success:
        logger.error(f"Plex connection failed: {connection_error}")
        if job_id:
            progress_tracker.error(job_id)
            progress_tracker.pop(job_id)

        # Return detailed error with troubleshooting steps
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "defaults": settings,
                "error": f"{connection_error}\n\nTroubleshooting steps:\n" +
                        "\n".join(f"• {step}" for step in connection_error.troubleshooting_steps),
                "form_values": {
                    "plex_url": plex_url or settings.plex_url,
                    "plex_token": plex_token,
                    "music_section": music_section,
                    "playlist_name": playlist_name,
                    "replace_existing": replace_flag,
                    "csv_text": csv_text_value,
                },
            },
            status_code=502,
        )

    # Use the working URL (might be different from original if fallback was used)
    if working_url != target_plex_url:
        logger.info(f"Using fallback URL for import: {working_url}")

    importer = PlaylistImporter(
        plex_url=working_url,
        plex_token=target_plex_token,
        music_section=music_section,
        match_threshold=settings.match_confidence_threshold,
    )

    try:
        result = await asyncio.to_thread(
            importer.import_playlist,
            playlist_payload.entries,
            active_playlist_name,
            replace_flag if replace_existing is not None else settings.default_replace_playlist,
            progress_callback,
        )
    except PlaylistImportError as exc:
        if job_id:
            progress_tracker.error(job_id)
        logger.exception("Playlist import failed: %s", exc)
        response = templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "defaults": settings,
                "error": str(exc),
                "form_values": {
                    "plex_url": plex_url or settings.plex_url,
                    "plex_token": plex_token,
                    "music_section": music_section,
                    "playlist_name": active_playlist_name,
                    "replace_existing": replace_flag,
                    "csv_text": csv_text_value,
                },
            },
            status_code=502,
        )
        if job_id:
            progress_tracker.pop(job_id)
        return response

    if job_id:
        progress_tracker.finish(job_id)

    logger.info(
        "Playlist '%s' processed: %s matched, %s added, %s unmatched",
        active_playlist_name,
        result.matched_count,
        result.added_count,
        len(result.unmatched),
    )

    context: Dict[str, Any] = {
        "request": request,
        "result": result,
        "playlist_name": active_playlist_name,
        "plex_url": importer.plex_url,
    }
    report_token = _store_report(result, playlist_payload.entries)
    context["report_token"] = report_token
    response = templates.TemplateResponse("result.html", context)
    if job_id:
        progress_tracker.pop(job_id)
    return response


@app.post("/preview")
async def preview_playlist(
    csv_text: str = Form(""),
    csv_file: Optional[UploadFile] = File(None),
) -> JSONResponse:
    csv_bytes: Optional[bytes] = None
    if csv_file and csv_file.filename:
        csv_bytes = await csv_file.read()

    try:
        playlist_payload = parse_playlist_csv(
            csv_text=csv_text,
            csv_bytes=csv_bytes,
        )
    except CSVParseError as exc:
        logger.exception("CSV preview failed: %s", exc)
        return JSONResponse({"error": str(exc)}, status_code=400)

    response_body: Dict[str, Any] = {
        "csv": playlist_payload.normalized_csv,
        "entryCount": len(playlist_payload.entries),
    }
    return JSONResponse(response_body)


@app.get("/progress/{job_id}")
async def get_progress(job_id: str) -> JSONResponse:
    snapshot = progress_tracker.snapshot(job_id)
    if snapshot is None:
        return JSONResponse({"status": "unknown"}, status_code=404)
    status = snapshot.get("status")
    if status in {"completed", "error"}:
        progress_tracker.pop(job_id)
    return JSONResponse(snapshot)


@app.post("/libraries")
async def fetch_music_libraries(payload: Dict[str, str] = Body(default={})):  # type: ignore[assignment]
    plex_url = payload.get("plex_url") or settings.plex_url
    plex_token = payload.get("plex_token") or settings.plex_token

    if not plex_token:
        return JSONResponse({"error": "Plex token is required to list libraries."}, status_code=400)

    # Test connection with fallbacks before attempting to use PlexAPI
    logger.info(f"Testing connection to Plex server: {plex_url}")
    success, working_url, connection_error = test_plex_connection(plex_url, plex_token)

    if not success:
        logger.error(f"Plex connection failed: {connection_error}")

        # Return detailed error with troubleshooting steps
        error_response = {
            "error": str(connection_error),
            "troubleshooting": connection_error.troubleshooting_steps,
            "details": "Connection test failed - see troubleshooting steps"
        }
        return JSONResponse(error_response, status_code=502)

    # Use the working URL (might be different from original if fallback was used)
    if working_url != plex_url:
        logger.info(f"Using fallback URL: {working_url}")

    try:
        plex = PlexServer(working_url, plex_token)
        sections = []
        for section in plex.library.sections():
            section_type = getattr(section, "type", "")
            if section_type == "artist":
                sections.append({
                    "key": section.key,
                    "title": section.title,
                })
        if not sections:
            return JSONResponse({"sections": [], "message": "No music libraries found."})

        response = {"sections": sections}

        # Include the working URL if it was different
        if working_url != plex_url:
            response["suggested_url"] = working_url
            response["message"] = f"Connected using fallback URL: {working_url}"

        return JSONResponse(response)

    except Exception as exc:
        logger.exception("Failed to fetch Plex libraries: %s", exc)
        return JSONResponse({
            "error": "Unable to retrieve music libraries after successful connection test.",
            "details": str(exc)
        }, status_code=502)


@app.get("/report/{token}")
async def download_report(token: str) -> Response:
    csv_data = REPORT_STORE.pop(token, None)
    if not csv_data:
        return JSONResponse({"error": "Report expired or not found."}, status_code=404)
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=import-report-{token}.csv"
        },
    )


def _store_report(result: ImportResult, entries: List[PlaylistEntry]) -> str:
    unmatched_map = {
        item.row: item.reason or "No confident match found."
        for item in result.unmatched
    }

    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Artist", "Album", "Track", "Status"])

    for entry in entries:
        status = unmatched_map.get(entry.row, "Imported ok")
        writer.writerow([
            entry.artist_name,
            entry.album_name or "",
            entry.track_name,
            status,
        ])

    token = uuid4().hex
    REPORT_STORE[token] = buffer.getvalue()
    return token
