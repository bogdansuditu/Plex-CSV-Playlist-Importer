# Plex CSV Playlist Importer

A beautifully designed, self-hosted FastAPI web app that transforms CSV/TXT playlist exports into Plex playlists with a **stunning Plex-inspired interface**. The app features intelligent track metadata parsing, advanced fuzzy-matching against your Plex music library, and seamless playlist integration. Built with a premium design system that matches Plex's visual language, offering both Docker and native workflows with extensive logging for troubleshooting.

---

## Features

### 🎨 **Premium Plex-Inspired Design**
- **Authentic Plex interface** with signature Gamboge accent colors and gradient cards
- **Professional typography** using system font stacks for optimal readability
- **Smooth animations** and hover effects throughout the interface
- **Responsive design** that works beautifully on desktop and mobile
- **Dark theme** with proper contrast and visual hierarchy

### 🚀 **Powerful Import Engine**
- **Smart CSV ingestion** via upload or paste, with UTF-8 / Latin-1 auto-detection and pandas-backed parsing
- **Live preview + progress**: uploaded files are rendered into a canonical `Artist name,Album,Track name` table with real-time track counting
- **Advanced fuzzy matching**: RapidFuzz + Unidecode scoring against Plex search results, with album-based tie-breaking
- **Detailed post-import reports**: download comprehensive CSV reports with match status and troubleshooting info

### 🔧 **Seamless Plex Integration**
- **Auto-discovery**: the UI dynamically pulls music libraries from your Plex server
- **Flexible playlist management**: replace or append existing Plex playlists while avoiding duplicates
- **Connection diagnostics**: robust connectivity testing with macOS-specific troubleshooting
- **Real-time progress tracking**: watch your import progress with animated status updates

### 📊 **Developer Experience**
- **Rich logging**: all activity streams to `logs/importer.log` for detailed analysis
- **Docker + Compose** packaging, plus documented native macOS/Linux workflow
- **FastAPI backend** with comprehensive error handling and API documentation

---

## Stack

| Layer      | Technology |
|------------|------------|
| Runtime    | Python 3.12+ |
| Web        | FastAPI, Uvicorn, Jinja2 |
| Parsing    | pandas |
| Matching   | RapidFuzz, Unidecode, PlexAPI |
| Design     | Tailwind CSS (CDN) + Custom Plex Design System |
| UI/UX      | Plex-inspired interface with Gamboge accents |

---

## Project Structure

```
app/
├── main.py               # FastAPI endpoints, logging configuration
├── config.py             # Environment-driven settings (pydantic-settings)
├── models.py             # Pydantic models for playlist payloads & results
├── services/
│   ├── csv_loader.py     # CSV parsing, normalisation, preview serialisation
│   ├── matching.py       # RapidFuzz-based track matcher against Plex
│   └── playlist_importer.py  # Plex API orchestration & playlist updates
└── templates/            # Jinja2 templates (Plex-inspired UI)
Dockerfile                # Python slim image with pinned dependencies
docker-compose.yml        # Single-service stack + .env wiring
requirements.txt          # Pinned Python dependencies
README.md                 # This document
```

---

## Configuration

Copy `.env.example` to `.env` and edit the values:

```env
PLEX_URL=http://plex:32400
PLEX_TOKEN=changeme
DEFAULT_MUSIC_SECTION=Music
DEFAULT_REPLACE_PLAYLIST=true
APP_PORT=8080
MATCH_CONFIDENCE_THRESHOLD=70
LOG_LEVEL=INFO
```

Key variables:

- `PLEX_URL` / `PLEX_TOKEN`: Plex server endpoint and auth token.
- `DEFAULT_MUSIC_SECTION`: Library section name as shown in Plex.
- `DEFAULT_REPLACE_PLAYLIST`: Default checkbox state for replacing playlists.
- `MATCH_CONFIDENCE_THRESHOLD`: RapidFuzz acceptance score (0–100).
- `LOG_LEVEL`: Console verbosity (file logging always runs at DEBUG).
- `APP_PORT`: Exposed FastAPI port.

All logs stream to `logs/importer.log` on the host.

---

## Running Locally (Recommended on macOS)

```bash
# Clone / unpack repo, then
python3 -m venv .venv
source .venv/bin/activate
pip3 install --upgrade pip setuptools wheel
pip3 install -r requirements.txt
cp .env.example .env  # edit values afterwards
python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port ${APP_PORT:-8080}
```

Visit `http://localhost:8080` to experience the beautiful Plex-inspired interface. Upload or paste your CSV, review the live preview, then create your playlist with real-time progress tracking.

To stop: `Ctrl+C` followed by `deactivate`.

---

## Running via Docker

> Note: Docker Desktop on macOS may not reach host-only / VPN networks (e.g. Tailscale). Prefer native execution if your Plex server lives on that network.

```bash
cp .env.example .env  # set real Plex values
docker-compose up -d --build
```

Once the container is healthy, the app is available on `http://localhost:${APP_PORT}`.

Container logs:

```bash
docker-compose logs -f web
```

To tear down:

```bash
docker-compose down
```

---

## Usage Workflow

1. **Upload / paste CSV** – Accepts `.csv`/`.txt`. Required headers: `Artist name`, `Track name`. Optional `Album` is used to improve match scores.
2. **Preview + edit** – The textarea shows the canonical form (`Artist name,Album,Track name`). Edit, add, or remove rows as needed.
3. **Configure playlist** – Override Plex URL/token, select the target music library from the dropdown, set playlist name, and optionally replace an existing playlist.
4. **Import** – Submit to trigger fuzzy matching and playlist creation/update. Results page summarises matches, additions, and unmatched items; unmatched rows list original metadata and reasons.
5. **Debug if needed** – Check `logs/importer.log` for row-level parsing decisions, RapidFuzz scores, and Plex API activity.

---

## Design Philosophy

The interface has been completely redesigned to **match Plex's visual identity**:

### **Authentic Plex Experience**
- **Color Palette**: Deep blacks and grays with Plex's signature Gamboge (`#e5a00d`) accent
- **Typography**: Clean system fonts with proper hierarchy and spacing
- **Visual Elements**: Gradient cards, subtle shadows, and smooth animations
- **Responsive Design**: Beautiful on desktop and mobile devices

### **Enhanced User Experience**
- **Sectioned Interface**: Clear organization of server connection, library selection, and import data
- **Real-time Feedback**: Live track counting, animated progress bars, and status indicators
- **Visual Hierarchy**: Icons, colors, and spacing guide users through the workflow
- **Success Celebrations**: Beautiful results page with statistics and detailed reporting

## Implementation Notes

- **CSV parsing**: `app/services/csv_loader.py` uses pandas with automatic delimiter detection, trims whitespace, and filters down to the required columns. The same module serialises the canonical preview table.
- **Fuzzy search**: `TrackMatcher` normalises text using Unidecode, strips common noise (`feat.`, remaster tags), and scores candidates with `fuzz.WRatio`. Album similarity contributes to tie-breaking when available.
- **Plex coordination**: `PlaylistImporter` deduplicates by `ratingKey`, skips items lacking playable media, and allows replace-or-append semantics.
- **Design System**: Custom Tailwind CSS configuration with Plex color tokens, gradient utilities, and animation classes defined in `base.html`.
- **Logging**: `app/main.py` attaches console + file handlers up front; DEBUG traces (including individual match scores and parsing skips) are written to `logs/importer.log`.
- **Preview endpoint**: `/preview` shares the same parsing pipeline as imports to guarantee consistency between what you edit and what gets submitted.

---

## Testing Checklist

- Upload a CSV with the expected headers and verify the textarea preview matches `Artist name,Album,Track name`.
- Toggle "Replace existing playlist" to confirm append vs replace behaviour.
- Inspect `logs/importer.log` after imports for unmatched rows and RapidFuzz scores.
- Validate Docker deployment only if your Plex server is routable from the container runtime; otherwise prefer native execution.

---

## Future Enhancements

- CSV export of unmatched rows for downstream editing.
- Batch playlist imports per file.
- Auth layer for the UI (Plex SSO, OAuth, etc.).
- API endpoints returning JSON reports for automated workflows.

---

## License

MIT or private license as you prefer – update this section to match your distribution model.
