# CSV Import Feature for Scanly

## Overview
The CSV Import feature allows you to process multiple media paths from a CSV file in batch. This is perfect for importing existing media databases or processing large lists of media files/directories.

## How to Use

### 1. Running Scanly
```bash
cd /home/adam/Scanly
python src/main.py
```

### 2. Select CSV Import
From the main menu, select option **3. CSV Import**

### 3. Prepare Your CSV File
Your CSV file should contain paths to media files or directories. The CSV can have the following formats:

#### Format 1: Paths only
```csv
path
/path/to/media/folder1
/path/to/media/folder2
/path/to/media/file.mkv
```

#### Format 2: Paths with metadata (recommended)
```csv
path,title,year
/path/to/media/folder1,Movie Title,2023
/path/to/media/folder2,TV Show Name,2024
/path/to/media/file.mkv,Another Movie,2022
```

### 4. Processing
The system will:
- Validate each path in the CSV
- Process valid paths through Scanly's normal scanning logic
- Show progress for each item
- Provide a summary at the end
- Trigger Plex refresh if any items were processed

## Features

### ✅ What the CSV Import Does:
- **Automatic Path Validation**: Checks if each path exists before processing
- **Progress Tracking**: Shows current progress (e.g., "Processing 5 of 20")
- **Error Handling**: Gracefully handles invalid paths or processing errors
- **File/Directory Support**: Handles both individual files and directories
- **Batch Processing**: Processes multiple paths without manual intervention
- **Summary Report**: Shows total processed items and any failed paths
- **Plex Integration**: Automatically triggers Plex refresh after processing

### ✅ CSV Format Support:
- **Header Detection**: Automatically detects if the first row contains headers
- **Multiple Columns**: Supports CSV files with additional metadata columns
- **Path Priority**: Always uses the first column as the media path
- **Flexible Format**: Works with various CSV formats and encodings

## Example Usage

### Your Database Export CSV:
Based on your `database_export_2025-07-19.csv`, the system will:
1. Read each path from the first column
2. Validate that the path exists on your system
3. Process each valid path through Scanly's scanning logic
4. Create symlinks/hardlinks as configured
5. Update scan history to avoid reprocessing

### Sample Test:
```bash
# Test with the included sample
cd /home/adam/Scanly
python src/main.py
# Select: 3. CSV Import  
# Enter: /home/adam/Scanly/sample_media_paths.csv
```

## Error Handling
- **Invalid paths**: Skipped with warning message
- **Processing errors**: Logged and reported in final summary
- **Malformed CSV**: Clear error messages with troubleshooting info
- **Permission issues**: Graceful handling with error reporting

## Integration
The CSV Import feature integrates seamlessly with existing Scanly functionality:
- Uses the same `DirectoryProcessor` as individual scans
- Respects all existing configuration settings
- Works with scanner lists and TMDB integration
- Maintains scan history consistency
- Supports all content types (movies, TV shows, anime, etc.)

## Tips for Best Results
1. **Clean Paths**: Ensure all paths in your CSV are absolute and accessible
2. **Test First**: Try with a small CSV file to verify functionality
3. **Backup**: Consider backing up your scan history before large imports
4. **Monitor Progress**: The feature shows real-time progress and status updates

The CSV Import feature is now ready to process your database export!
