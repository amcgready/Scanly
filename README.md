<p align="center">
  <img src="https://i.imgur.com/nUa5M6m.png" alt="Project Banner">
</p>

<p align="center">
  <a href="https://wakatime.com/badge/github/amcgready/Scanly"><img src="https://wakatime.com/badge/github/amcgready/Scanly.svg" alt="wakatime"></a>
</p>

# Scanly

Version: 1.4.0
Last Updated: 2025-05-29

# What is Scanly?

Scanly is a media file organization tool that helps scan, categorize, and organize your media library.

## Main Features

Scanly offers these key features:

1. **Media Organization**: Scans directories for media files and organizes them using symlinks or hardlinks
2. **Metadata Integration**: Uses TMDB API to fetch accurate metadata for TV shows and movies
3. **Content Type Detection**: Uses scanner lists (like tv_series.txt, anime_movies.txt, etc.) to identify content types
4. **Library Structure**: Creates an organized library structure with customizable folder naming
5. **Anime Separation**: Optionally separates anime content into dedicated folders
6. **Resume Functionality**: Tracks progress to resume interrupted scans
7. **Skipped Items Tracking**: Keeps track of items that couldn't be processed

## Configuration System

Scanly uses a comprehensive configuration system:

1. **Environment Variables**: Loaded from .env file using `python-dotenv`
2. **Command Line Arguments**: For one-time overrides and specific operations
3. **Settings Management UI**: An interactive menu to modify settings

## Core Components

1. **Scanner Lists**: Text files in the scanners directory containing known TV series and movies with their IDs
2. **Directory Processor**: Processes directories recursively to find media files
3. **File Processor**: Extracts information from filenames (show name, season/episode)
4. **API Integration**: Connects to TMDB for metadata
5. **Symlink/Hardlink Creator**: Creates the organized library structure

## Settings Menu

The settings menu allows users to modify configuration through a text-based interface. It reads from and writes to the .env file, making changes persistent.

## Docker Support

Scanly has Docker support with:
- Volume mounts for media directories
- Environment variable overrides
- An entrypoint script that manages configuration

## Scanner Lists

The scanner lists (like tv_series.txt) contain entries in formats like:
- `Show Name [TMDB_ID]` 
- `Show Name [Error]` (when ID couldn't be determined)

These lists help identify TV shows and movies by name.

## Command-Line Interface

Scanly supports various command-line arguments:
- `--movie`: Process a specific movie directory
- `--tv`: Process a specific TV show directory
- `--force`: Force rescan of already processed files
- `--config`: Use a specific configuration file
- `--debug`: Enable debug logging
- `--quiet`: Run in quiet mode

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
export DESTINATION_DIRECTORY=/path/to/your/library
```

5. Build and run the Docker container:
```bash
docker-compose up -d
```

## Quick Installation

1. Clone the repository:
```bash
git clone https://github.com/amcgready/Scanly.git
cd Scanly
```

2. Create a virtual environment and install dependencies:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. Configure your environment:
```bash
cp .env.template .env
# Edit .env with your preferred text editor and add your TMDB API key
```

4. Launch Scanly:
```bash
python src/main.py
```

For detailed installation instructions, see [INSTALL.md](INSTALL.md).

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

## Special Instructions for Synology Users

When running Scanly on Synology NAS, you may encounter permission issues. Follow these steps for a successful setup:

1. Use the Synology Docker UI to create the container
2. Set the correct PUID and PGID values:
   - Run `id` in the Synology terminal to get your user's UID and GID
   - Set these values as environment variables in the Docker UI
3. Mount volumes properly:
   - For media source: `/volume1/path/to/your/media:/media/source:ro`
   - For destination library: `/volume1/path/to/your/library:/media/library`
4. Set the DESTINATION_DIRECTORY environment variable to `/media/library`

Alternatively, create a `.env` file in your Scanly directory with:
```
PUID=1026  # Replace with your actual user ID
PGID=100   # Replace with your actual group ID
MEDIA_SOURCE_DIR=/volume1/path/to/your/media
MEDIA_LIBRARY_DIR=/volume1/path/to/your/library
```

Then run with:
```bash
docker-compose -f simple-compose.yml up -d
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

## Running Scanly

### Command Line Interface (CLI)

Scanly can be run entirely via the command line:

1. Activate your virtual environment (if you created one):
```bash
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Run the main script directly:
```bash
python src/main.py
```

3. Follow the interactive prompts to scan and organize your media.

You can also use command line arguments for specific operations:

```bash
# Scan a specific movie directory
python src/main.py --movie /path/to/movies

# Scan a specific TV show directory
python src/main.py --tv /path/to/tv_shows

# Start in interactive menu mode
python src/main.py --interactive

# Force rescan of previously processed files
python src/main.py --force

# See all available options
python src/main.py --help
```

The CLI mode is particularly useful for:
- Server environments without a GUI
- Automation via cron jobs or scripts
- Quick scans of specific directories
- Users who prefer terminal-based workflows

[![Donate](https://img.shields.io/badge/Donate-PayPal-blue.svg)](https://paypal.me/PhtmRaven?country.x=US&locale.x=en_US)
[![GitHub Sponsors](https://img.shields.io/badge/Sponsor-💖%20GitHub%20Sponsors-orange?logo=github)](https://github.com/sponsors/amcgready)
