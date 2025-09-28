# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Running the Application
```bash
# Native development (recommended on macOS)
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port ${APP_PORT:-8080}

# Docker development
docker-compose up -d --build
```

### Connection Testing & Troubleshooting
```bash
# Test Plex connectivity with detailed diagnostics
.venv/bin/python test_connection.py

# Comprehensive diagnostics (raw sockets, HTTP libraries, etc.)
.venv/bin/python app/test.py
```

### Environment Setup
```bash
# Initial setup
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
cp .env.example .env  # Edit with real Plex credentials
```

### Logs and Debugging
- Application logs: `logs/importer.log` (DEBUG level, created automatically)
- Console logs: Controlled by `LOG_LEVEL` env var
- Docker logs: `docker-compose logs -f web`

## Architecture Overview

This is a FastAPI web application that imports CSV playlists into Plex Media Server. The core workflow involves CSV parsing, fuzzy track matching against Plex libraries, and playlist creation/updates.

### Core Components

**`app/main.py`**: FastAPI application with endpoints for:
- `/` - Main upload form with live library discovery
- `/import` - Playlist processing with progress tracking
- `/preview` - CSV validation and normalization
- `/progress/{job_id}` - Real-time import progress
- `/libraries` - Dynamic Plex library section discovery
- `/report/{token}` - CSV export of import results

**`app/services/`**:
- `csv_loader.py` - pandas-based CSV parsing with encoding detection and column normalization
- `matching.py` - RapidFuzz + Unidecode fuzzy matching against Plex search results
- `playlist_importer.py` - Plex API orchestration, playlist creation/replacement
- `progress.py` - Thread-safe progress tracking for async imports

**`app/config.py`**: Pydantic settings with `.env` file support for Plex connection and matching thresholds

**`app/models.py`**: Pydantic models for request/response schemas and internal data structures

### Key Technical Details

**CSV Processing**: Supports UTF-8/Latin-1 auto-detection, flexible column mapping (aliases for common variations), and pandas delimiter auto-detection. Required columns: `Artist name`, `Track name`. Optional: `Album`.

**Fuzzy Matching**: Uses Unidecode for text normalization, strips common noise patterns (feat., remaster tags, brackets), and scores with `fuzz.WRatio`. Album similarity provides tie-breaking when available. Configurable confidence threshold via `MATCH_CONFIDENCE_THRESHOLD`.

**Plex Integration**: PlexAPI-based library discovery, search, and playlist management. Supports replace/append modes with duplicate `ratingKey` prevention.

**Progress Tracking**: Thread-safe progress updates for real-time UI feedback during imports. Jobs are identified by UUID and automatically cleaned up.

**Connection Testing**: `app/services/connection_tester.py` provides robust Plex connectivity testing with fallback URL discovery and macOS-specific troubleshooting guidance. Integrated into main endpoints to handle networking issues gracefully.

## Configuration

Key environment variables in `.env`:
- `PLEX_URL` / `PLEX_TOKEN` - Plex server connection
- `DEFAULT_MUSIC_SECTION` - Target library section name
- `MATCH_CONFIDENCE_THRESHOLD` - Fuzzy match acceptance score (0-100)
- `LOG_LEVEL` - Console verbosity (file logging always DEBUG)

## File Structure Notes

- Templates use Tailwind CSS via CDN
- Logs directory created automatically on startup
- Static files served directly by FastAPI
- No database - uses in-memory stores for temporary data (progress, reports)
- Virtual environment in `.venv/` - activate before development

## Known Issues

**macOS Python Networking**: Python applications may fail to connect to Plex servers that are accessible via browsers and system tools. This is a macOS security/networking restriction, not an application bug. The application includes automatic connection testing and fallback mechanisms with detailed troubleshooting guidance.