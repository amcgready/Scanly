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

Scanly is a media file organizer that monitors directories for new files and creates an organized library using symbolic links.

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

Scanly can be configured using the `.env` file or through the Settings menu. Key configuration options include:

- `TMDB_API_KEY`: Your TMDB API key (required)
- `ORIGIN_DIRECTORY`: Default directory to monitor for media files
- `DESTINATION_DIRECTORY`: Destination directory for the organized library
- `LINK_TYPE`: Type of links to create - 'symlink' (default) or 'hardlink'
- `RELATIVE_SYMLINK`: Use relative paths for symlinks ('true' or 'false')
- `LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `AUTO_EXTRACT_EPISODES`: Automatically extract episode numbers without prompting

### Docker Environment Variables

When using Docker, you can set these environment variables either in the `.env` file or in `docker-compose.yml`:

- `TMDB_API_KEY`: Your TMDB API key
- `MEDIA_SOURCE_DIR`: Host path to your media files (read-only mount)
- `MEDIA_LIBRARY_DIR`: Host path where the organized library will be created
- `LOG_LEVEL`: Logging level
- `AUTO_EXTRACT_EPISODES`: Whether to extract episode numbers automatically

[![Donate](https://img.shields.io/badge/Donate-PayPal-blue.svg)](https://paypal.me/PhtmRaven?country.x=US&locale.x=en_US)
[![GitHub Sponsors](https://img.shields.io/badge/Sponsor-💖%20GitHub%20Sponsors-orange?logo=github)](https://github.com/sponsors/amcgready)
