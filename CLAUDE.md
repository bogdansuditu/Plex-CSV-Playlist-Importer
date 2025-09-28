# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Running the Application
```bash
# Native development (recommended on macOS)
source .venv/bin/activate
python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port ${APP_PORT:-8080}

# Docker development
docker-compose up -d --build
```

### Testing & Quality Assurance
```bash
# Test Plex connectivity with detailed diagnostics
.venv/bin/python3 test_connection.py

# Comprehensive diagnostics (raw sockets, HTTP libraries, etc.)
.venv/bin/python3 app/test.py

# Note: No automated test suite currently exists
# Manual testing checklist available in README.md
```

### Environment Setup
```bash
# Initial setup
python3 -m venv .venv
source .venv/bin/activate
pip3 install --upgrade pip setuptools wheel
pip3 install -r requirements.txt
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
- `/import` - Playlist processing with progress tracking (POST)
- `/preview` - CSV validation and normalization (POST)
- `/progress/{job_id}` - Real-time import progress via SSE
- `/libraries` - Dynamic Plex library section discovery (GET)
- `/report/{token}` - CSV export of import results with matched/unmatched status

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
- `DEFAULT_REPLACE_PLAYLIST` - Default checkbox state for replacing playlists
- `APP_PORT` - Exposed FastAPI port (default: 8080)
- `MATCH_CONFIDENCE_THRESHOLD` - Fuzzy match acceptance score (0-100)
- `LOG_LEVEL` - Console verbosity (file logging always DEBUG)

## Design System

**Plex-Inspired Interface**: The application features a completely redesigned UI that matches Plex's visual design language:

### Color Palette
- **Primary Background**: Deep blacks (`#0f0f0f`, `#1a1a1a`) with subtle gradients
- **Surface Colors**: Dark grays (`#1e1e1e`, `#242424`) with gradient overlays
- **Accent Color**: Plex's signature Gamboge (`#e5a00d`) for highlights and actions
- **Text Hierarchy**: Pure white (`#ffffff`) for headings, muted grays (`#9ca3af`, `#6b7280`) for secondary text
- **State Colors**: Success (`#22c55e`), Error (`#ef4444`) with proper dark variants

### Visual Elements
- **Cards**: Gradient backgrounds with subtle borders and box shadows
- **Buttons**: Plex-style gradients with hover animations and proper shadows
- **Form Fields**: Dark surfaces with focus states using accent colors
- **Progress Elements**: Animated components with Plex branding
- **Icons**: SVG icons integrated throughout for better visual hierarchy

### Typography
- **Font Stack**: System fonts (`-apple-system`, `BlinkMacSystemFont`, `Segoe UI`)
- **Hierarchy**: Bold headings, medium body text, and subtle helper text
- **Spacing**: Generous white space following Plex's clean design principles

## File Structure Notes

- **Templates**: Jinja2 templates in `app/templates/` use Tailwind CSS via CDN with custom Plex color configuration
  - `base.html` - Plex-inspired layout with custom CSS design system and gradient backgrounds
  - `index.html` - Sectioned form interface with enhanced file upload and real-time feedback
  - `result.html` - Success celebration with statistics cards and collapsible unmatched tracks
- **Logs**: Directory created automatically on startup
- **Static files**: Served directly by FastAPI (no separate static directory)
- **No database**: Uses in-memory stores for temporary data (progress, reports)
- **Virtual environment**: `.venv/` - activate before development
- **Report exports**: CSV reports stored temporarily in `REPORT_STORE` dict, accessible via `/report/{token}`

## Known Issues

**macOS Python Networking**: Python applications may fail to connect to Plex servers that are accessible via browsers and system tools. This is a macOS security/networking restriction, not an application bug. The application includes automatic connection testing and fallback mechanisms with detailed troubleshooting guidance.