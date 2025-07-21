# CSV Import Feature - Implementation Summary

## Overview
The CSV Import feature has been successfully implemented in Scanly to process media file paths from CSV files, treating each file as an individual scan with proper content type detection and season/episode prompting.

## Key Features Implemented

### 1. CSV Processing
- **Multiple delimiter support**: Automatically detects comma, semicolon, tab, and pipe delimiters
- **Header detection**: Handles CSV files with or without headers
- **Path validation**: Validates that each path in the CSV points to an actual file
- **Progress tracking**: Shows detailed progress and results for each file processed

### 2. Content Type Detection
- **Movie Detection**: Standard movie files without season/episode patterns
- **TV Series Detection**: Files with S##E## patterns or TV-related keywords
- **Anime Detection**: Files with anime-related keywords and patterns
- **Wrestling Detection**: Framework in place for future wrestling content

### 3. Metadata Extraction
- **Title Extraction**: Cleans filenames to extract readable titles
- **Year Detection**: Extracts 4-digit years (1900-2099) from filenames
- **Pattern Cleaning**: Removes quality indicators, codecs, release groups
- **Unicode Normalization**: Handles special characters properly

### 4. Season/Episode Prompting
For TV Series and Anime Series content:
- **Auto-detection**: Attempts to extract season/episode from filename
- **User prompts**: Interactive prompts for season and episode numbers
- **Smart defaults**: Uses detected values as defaults, falls back to sensible defaults

### 5. File Processing
- **Individual file processing**: Each CSV entry is processed as a separate media item
- **DirectoryProcessor integration**: Uses existing file processing infrastructure
- **Content-aware processing**: Creates TV or Movie processors based on content type
- **Error handling**: Graceful handling of processing failures with detailed reporting

## Implementation Details

### Menu Integration
- Added "CSV Import" option to main menu (option 3)
- Added CSV Import option to ui/menu.py for alternative menu system
- Comprehensive help text explaining the feature

### File Structure
```
src/
├── main.py                    # Main CSV import logic in perform_csv_import()
├── ui/menu.py                 # Alternative menu with CSV import option
└── config/__init__.py         # Updated with required constants
```

### Key Functions Added
- `perform_csv_import()` - Main CSV import logic
- `extract_folder_metadata()` - Title and year extraction
- `detect_if_tv_show()` - TV series content detection
- `detect_if_anime()` - Anime content detection

### Configuration Updates
Added missing constants to `src/config/__init__.py`:
- `DESTINATION_DIRECTORY`
- `ALLOWED_EXTENSIONS`
- `RELATIVE_SYMLINK`
- `LINK_TYPE`
- `CUSTOM_MOVIE_FOLDER`
- `MOVIE_COLLECTION_ENABLED`
- `CUSTOM_SHOW_FOLDER`
- `TMDB_FOLDER_ID`
- `TVDB_FOLDER_ID`

## Usage
1. Prepare a CSV file with one file path per line (or per column)
2. Run Scanly and select "3. CSV Import" from the main menu
3. Enter the path to your CSV file
4. For each file, review the detected content type
5. For TV/Anime series, provide season and episode information when prompted
6. Watch as each file is processed individually

## Testing
- ✅ CSV parsing with various delimiters
- ✅ Content type detection accuracy  
- ✅ Metadata extraction from filenames
- ✅ Season/episode pattern recognition
- ✅ Individual file processing workflow

## Example CSV Format
```
/path/to/Movie.Title.2023.1080p.BluRay.x264.mkv
/path/to/TV.Show.S01E01.Episode.Title.2023.1080p.WEB-DL.x264.mkv
/path/to/Anime.Series.S01E01.1080p.BluRay.x264.mkv
```

The feature is now ready for use and provides the requested functionality of treating CSV file entries as individual scans with proper content type detection and season/episode prompting.
