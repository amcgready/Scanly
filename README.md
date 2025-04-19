<p align="center">
  <img src="https://i.imgur.com/nUa5M6m.png" alt="Project Banner">
</p>

<p align="center">
  <a href="https://discord.gg/hdDj4aZTVf">
    <img src="https://img.shields.io/badge/Chat-Join%20us%20on%20Discord-7289da?logo=discord&logoColor=white" alt="Join us on Discord">
  </a>
  <img src="https://img.shields.io/github/downloads/amcgready/Scanly/total" alt="GitHub all releases">
</p>

# Scanly

Version: 1.3.0
Last Updated: 2025-04-19

Scanly is a media file organizer that monitors directories for new files and creates an organized library using symbolic or hard links.

## Features

- Monitor directories for new media files
- Extract show or movie information from filenames
- Extract season and episode numbers for TV shows
- Integration with TMDB for accurate metadata
- Create organized library using symbolic links or hard links
- Resume interrupted scans
- Track skipped items

## Installation

### Standard Installation

1. Clone the repository:
```bash
git clone https://github.com/amcgready/scanly.git
cd scanly
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file based on the example:
```bash
cp .env.template .env
```

4. Edit the `.env` file and set your TMDB API key and other settings.

### Docker Installation

1. Clone the repository:
```bash
git clone https://github.com/amcgready/scanly.git
cd scanly
```

2. Create a `.env` file for Docker:
```bash
cp .env.example .env
```

3. Edit the `.env` file to set your TMDB API key and (optionally) other settings.

4. Set environment variables for your media directories:
```bash
export MEDIA_SOURCE_DIR=/path/to/your/media
export MEDIA_LIBRARY_DIR=/path/to/your/library
```

5. Build and run the Docker container:
```bash
docker-compose up -d
```

## Usage

### Standard Usage

Run Scanly from the project directory:
```bash
python src/main.py
```

### Docker Usage

#### Interactive Mode

To use Scanly in interactive mode with Docker:
```bash
docker-compose exec -it scanly python src/main.py
```

#### Process a Specific Path

To process a specific path inside the container:
```bash
docker-compose exec scanly python src/main.py --movie /media/source/movies
# or
docker-compose exec scanly python src/main.py --tv /media/source/tv_shows
```

#### View Logs

To view the logs:
```bash
docker-compose logs -f scanly
```

## Configuration

Scanly can be configured using the `.env` file. Here's a complete list of all available configuration options:

### API Settings
- `TMDB_API_KEY`: Your TMDB API key (required)
- `TMDB_BASE_URL`: Base URL for TMDB API (default: https://api.themoviedb.org/3)
- `MDBLIST_API_KEY`: API key for MDBList integration

### File System Settings
- `DESTINATION_DIRECTORY`: Destination directory for the organized library

### Link Settings
- `LINK_TYPE`: Type of links to create - 'symlink' or 'hardlink' (default: symlink)
- `RELATIVE_SYMLINK`: Use relative paths for symlinks (true/false)

### Custom Folder Structure
- `CUSTOM_SHOW_FOLDER`: Custom name for TV shows folder (default: "TV Shows")
- `CUSTOM_4KSHOW_FOLDER`: Custom name for 4K TV shows folder
- `CUSTOM_ANIME_SHOW_FOLDER`: Custom name for anime shows folder (default: "Anime Shows")
- `CUSTOM_MOVIE_FOLDER`: Custom name for movies folder (default: "Movies")
- `CUSTOM_4KMOVIE_FOLDER`: Custom name for 4K movies folder
- `CUSTOM_ANIME_MOVIE_FOLDER`: Custom name for anime movies folder (default: "Anime Movies")

### Resolution-based Organization
- `SHOW_RESOLUTION_STRUCTURE`: Enable organization by resolution for TV shows (true/false)
- `MOVIE_RESOLUTION_STRUCTURE`: Enable organization by resolution for movies (true/false)

### Show Resolution Folder Mappings
- `SHOW_RESOLUTION_FOLDER_REMUX_4K`: Folder name for 4K remux shows
- `SHOW_RESOLUTION_FOLDER_REMUX_1080P`: Folder name for 1080p remux shows
- `SHOW_RESOLUTION_FOLDER_REMUX_DEFAULT`: Folder name for other remux shows
- `SHOW_RESOLUTION_FOLDER_2160P`: Folder name for 2160p shows
- `SHOW_RESOLUTION_FOLDER_1080P`: Folder name for 1080p shows
- `SHOW_RESOLUTION_FOLDER_720P`: Folder name for 720p shows
- `SHOW_RESOLUTION_FOLDER_480P`: Folder name for 480p shows
- `SHOW_RESOLUTION_FOLDER_DVD`: Folder name for DVD shows
- `SHOW_RESOLUTION_FOLDER_DEFAULT`: Default folder for shows with unrecognized resolution

### Movie Resolution Folder Mappings
- `MOVIE_RESOLUTION_FOLDER_REMUX_4K`: Folder name for 4K remux movies
- `MOVIE_RESOLUTION_FOLDER_REMUX_1080P`: Folder name for 1080p remux movies
- `MOVIE_RESOLUTION_FOLDER_REMUX_DEFAULT`: Folder name for other remux movies
- `MOVIE_RESOLUTION_FOLDER_2160P`: Folder name for 2160p movies
- `MOVIE_RESOLUTION_FOLDER_1080P`: Folder name for 1080p movies
- `MOVIE_RESOLUTION_FOLDER_720P`: Folder name for 720p movies
- `MOVIE_RESOLUTION_FOLDER_480P`: Folder name for 480p movies
- `MOVIE_RESOLUTION_FOLDER_DVD`: Folder name for DVD movies
- `MOVIE_RESOLUTION_FOLDER_DEFAULT`: Default folder for movies with unrecognized resolution

### Anime Settings
- `ANIME_SCAN`: Enable scanning for anime content (true/false)
- `ANIME_SEPARATION`: Separate anime into its own folder structure (true/false)

### Scanner Settings
- `SCANNER_ENABLED`: Enable scanner functionality (true/false)
- `SCANNER_PRIORITY`: Prioritize scanner results over other metadata sources (true/false)

### Folder ID Settings
- `TMDB_FOLDER_ID`: Include TMDB ID in folder names (true/false)
- `IMDB_FOLDER_ID`: Include IMDB ID in folder names (true/false)
- `TVDB_FOLDER_ID`: Include TVDB ID in folder names (true/false)

### Renaming Settings
- `RENAME_ENABLED`: Enable file renaming (true/false)
- `RENAME_TAGS`: Custom tags to include in renamed files

### System Settings
- `MAX_PROCESSES`: Maximum number of concurrent processes
- `ALLOWED_EXTENSIONS`: Comma-separated list of file extensions to process (e.g., .mp4,.mkv,.srt)
- `SKIP_ADULT_PATTERNS`: Skip files that match adult content patterns (true/false)
- `SKIP_EXTRAS_FOLDER`: Skip processing "extras" folders (true/false)
- `EXTRAS_MAX_SIZE_MB`: Maximum size in MB for files in extras folders

### Rclone Settings
- `RCLONE_MOUNT`: Enable Rclone mount integration (true/false)
- `MOUNT_CHECK_INTERVAL`: Interval in seconds to check mount status

### Monitoring Settings
- `SLEEP_TIME`: Time to sleep between monitoring iterations in seconds
- `SYMLINK_CLEANUP_INTERVAL`: Interval in seconds for cleaning up broken symlinks

### Plex Integration
- `ENABLE_PLEX_UPDATE`: Enable Plex library updates (true/false)
- `PLEX_URL`: URL for your Plex server (e.g., http://localhost:32400)
- `PLEX_TOKEN`: Authentication token for your Plex server

### Database Settings
- `DB_THROTTLE_RATE`: Database operation throttling rate
- `DB_MAX_RETRIES`: Maximum number of retries for database operations
- `DB_RETRY_DELAY`: Delay in seconds between database operation retries
- `DB_BATCH_SIZE`: Size of batches for database operations
- `DB_MAX_WORKERS`: Maximum number of database worker threads

### Logging Settings
- `LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `LOG_FILE`: Path to log file

### Application Settings
- `AUTO_EXTRACT_EPISODES`: Automatically extract episode numbers without prompting (true/false)
- `PROGRESS_FILE`: Path to the progress tracking file (default: scanly_progress.json)

### Docker Environment Variables

When using Docker, you can set these additional environment variables either in the `.env` file or in `docker-compose.yml`:

- `MEDIA_SOURCE_DIR`: Host path to your media files (read-only mount)
- `MEDIA_LIBRARY_DIR`: Host path where the organized library will be created

## Command Line Arguments

Scanly supports several command line arguments:

```bash
# Process a specific movie directory
python src/main.py --movie /path/to/movies

# Process a specific TV show directory
python src/main.py --tv /path/to/tv_shows

# Force rescan of already processed files
python src/main.py --force

# Use a specific configuration file
python src/main.py --config /path/to/custom.env

# Enable debug logging
python src/main.py --debug

# Run in quiet mode (less output)
python src/main.py --quiet

# Show help
python src/main.py --help
```

[![Donate](https://img.shields.io/badge/Donate-PayPal-blue.svg)](https://paypal.me/PhtmRaven?country.x=US&locale.x=en_US)
[![GitHub Sponsors](https://img.shields.io/badge/Sponsor-💖%20GitHub%20Sponsors-orange?logo=github)](https://github.com/sponsors/amcgready)
