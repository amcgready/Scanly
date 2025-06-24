# Scanly

![Scanly Banner](https://i.imgur.com/nUa5M6m.png)

[![wakatime](https://wakatime.com/badge/github/amcgready/Scanly.svg)](https://wakatime.com/badge/github/amcgready/Scanly)

**Version:** 1.5.0  
**Last Updated:** 2025-06-24

---

## What is Scanly?

**Scanly** is a powerful media file organization tool that scans, categorizes, and organizes your media library. It supports movies, TV shows, anime, and more, using symlinks or hardlinks and integrates with The Movie Database (TMDB) for accurate metadata.

---

## Features

- **Media Organization:** Scans directories for media files and organizes them using symlinks or hardlinks.
- **Metadata Integration:** Fetches accurate metadata for TV shows and movies using the TMDB API.
- **Content Type Detection:** Automatically detects and separates movies, TV, anime, and more.
- **Customizable Structure:** Supports custom folder structures and resolution-based organization.
- **Anime Separation:** Detects and organizes anime content separately.
- **Resume & Skipped Items:** Tracks scan progress and skipped items for reliable, resumable operations.
- **Plex Integration:** Supports Plex library refreshes after organizing media.
- **Discord Notifications:** Sends notifications to Discord via webhooks for key events.
- **Monitoring:** Watches directories for new files and auto-processes them.
- **Scanner Lists:** Maintains and manages lists of known media for fast matching.
- **Docker Support:** Easily run Scanly in a containerized environment.

---

## Installation

### Prerequisites

- Python 3.6 or higher
- Git

### Standard Installation

```bash
git clone https://github.com/amcgready/Scanly.git
cd Scanly
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Docker Installation

1. Copy `.env.template` to `.env` and edit your settings.
2. Build and run with Docker Compose:

```bash
docker compose up --build
```

Or use the provided `simple-compose.yml` for a minimal setup.

---

## Configuration

Edit the `.env` file to set your API keys and preferences:

```ini
TMDB_API_KEY=your_tmdb_api_key_here
DESTINATION_DIRECTORY=/mnt/Scanly
LINK_TYPE=symlink  # or hardlink
RELATIVE_SYMLINK=false
# ...other options...
```

See `.env.template` for all available options.

---

## Usage

### Command Line

```bash
python src/main.py --scan /path/to/media
python src/main.py --monitor /path/to/watch
```

**Common CLI options:**
- `--scan` / `-s`: Scan a directory
- `--monitor` / `-w`: Monitor a directory for changes
- `--movie` / `-m`: Process as movie
- `--tv` / `-t`: Process as TV show
- `--debug` / `-d`: Enable debug mode

### Docker

Mount your media and library directories as volumes:

```yaml
services:
  scanly:
    build: .
    environment:
      - TMDB_API_KEY=your_tmdb_api_key_here
      - DESTINATION_DIRECTORY=/media/library
    volumes:
      - ./logs:/app/logs
      - ./data:/app/data
      - /path/to/your/media:/media/source:ro
      - /path/to/your/library:/media/library
```

---

## Scanner Lists

Scanly uses scanner lists to match and organize known media. These are stored as JSON files in `data/` (e.g., `movie_scanner.json`, `tv_scanner.json`). You can edit these lists to add or remove entries.

---

## Advanced Features

- **Plex Integration:** Set `PLEX_URL` and `PLEX_TOKEN` in your `.env` to enable automatic Plex library refreshes.
- **Discord Webhooks:** Set `DISCORD_WEBHOOK_URL` to receive notifications for new links, deletions, and repairs.
- **Monitoring:** Enable directory monitoring for automatic processing of new files.
- **Custom Folder Structure:** Adjust folder names and resolution-based organization in your `.env`.

---

## Troubleshooting

- Check logs in the `logs/` directory for errors.
- Ensure your API keys are valid and set in `.env`.
- For Docker, ensure volumes are mounted with correct permissions.

---

## Contributing

Pull requests and issues are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## License

This project is licensed under the MIT License.

---

**Scanly** — Effortless media organization for your entire library.
