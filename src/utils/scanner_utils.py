import os
import re
import logging
import sys

def check_scanner_lists(file_path_or_name):
    """
    Check if a file path or name is in any of the scanner lists.
    Prioritizes exact matches for proper content type detection.
    
    Args:
        file_path_or_name: The file path or name to check
    
    Returns:
        Tuple of (content_type, is_anime, tmdb_id) if found, None otherwise
    """
    logger = logging.getLogger(__name__)
    
    # Normalize the input
    file_path_or_name = file_path_or_name.strip()
    basename = os.path.basename(file_path_or_name)
    
    # Log the input for debugging
    logger.debug(f"Checking scanner lists for: '{file_path_or_name}'")
    logger.debug(f"Basename: '{basename}'")
    
    # Extract clean title from filename
    # First strip common file extensions and remove any tags in brackets/parentheses
    clean_title = re.sub(r'\.(mkv|mp4|avi|mov|wmv|flv)$', '', basename, flags=re.IGNORECASE)
    clean_title = re.sub(r'[._-]', ' ', clean_title)  # Replace separators with spaces
    clean_title = re.sub(r'\[[^\]]*\]|\([^\)]*\)', '', clean_title)  # Remove [...] and (...)
    
    # Remove common suffixes/markers for video files
    clean_title = re.sub(r'(?i)\b(1080p|720p|2160p|4K|HEVC|x264|x265|WEB-?DL|BluRay|S\d+|Season\s*\d+|Complete).*$', '', clean_title)
    
    # Normalize spaces and trim
    clean_title = re.sub(r'\s+', ' ', clean_title).strip()
    
    # Potential variations of the title to check
    title_variations = [clean_title]
    
    # Add variations without season markers if present
    season_removed = re.sub(r'\s+S\d+.*$|\s+Season\s*\d+.*$', '', clean_title, flags=re.IGNORECASE)
    if season_removed != clean_title:
        title_variations.append(season_removed)
    
    # Add the basename as a variation as well
    if basename not in title_variations:
        title_variations.append(basename)
    
    logger.debug(f"Title variations to check: {title_variations}")
    
    # Load scanner lists
    scanner_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'scanners')
    
    # Define scanner files with their content types
    scanner_configs = [
        ('tv_series.txt', 'tv', False),
        ('movies.txt', 'movie', False),
        ('anime_series.txt', 'tv', True),
        ('anime_movies.txt', 'movie', True)
    ]
    
    # For better debugging, check all possible matches first
    all_matches = []
    
    for file_name, content_type, is_anime in scanner_configs:
        scanner_file = os.path.join(scanner_dir, file_name)
        if not os.path.exists(scanner_file):
            logger.debug(f"Scanner file not found: {scanner_file}")
            continue
            
        try:
            with open(scanner_file, 'r', encoding='utf-8') as f:
                entries = [line.strip() for line in f if line.strip()]
                
                # Debug output to see what's in the scanner file
                logger.debug(f"Scanner file {file_name} has {len(entries)} entries")
                
                for entry in entries:
                    # Extract the base entry name without TMDB ID or year
                    entry_base = entry.strip()
                    tmdb_id = None
                    
                    # Extract TMDB ID if present
                    if '[' in entry and ']' in entry:
                        match = re.search(r'\[(\d+)\]', entry)
                        if match:
                            tmdb_id = match.group(1)
                            entry_base = entry[:entry.rfind('[')].strip()
                    
                    # Extract year if present
                    if '(' in entry_base and ')' in entry_base:
                        year_match = re.search(r'\((\d{4})\)', entry_base)
                        if year_match:
                            entry_base = entry_base[:entry_base.rfind('(')].strip()
                    
                    # Compare all variations of the title with the scanner entry
                    for title_var in title_variations:
                        # Case-insensitive comparison
                        if title_var.lower() == entry_base.lower():
                            logger.info(f"MATCH FOUND! '{title_var}' matches '{entry_base}' in {file_name}")
                            return (content_type, is_anime, tmdb_id)
                    
                    # Also check if the title is a substring of the entry (for more lenient matching)
                    for title_var in title_variations:
                        if title_var.lower() in entry_base.lower() or entry_base.lower() in title_var.lower():
                            all_matches.append((file_name, content_type, is_anime, tmdb_id, entry_base))
                    
        except Exception as e:
            logger.error(f"Error reading scanner file {file_name}: {e}")
    
    # If we found any matches, use the first one
    if all_matches:
        # Sort by match "quality" - prefer exact anime matches first
        anime_matches = [m for m in all_matches if m[2]]  # Is anime
        if anime_matches:
            match = anime_matches[0]
            logger.info(f"Using anime match: '{match[4]}' from {match[0]}")
            return (match[1], match[2], match[3])
        else:
            match = all_matches[0]
            logger.info(f"Using regular match: '{match[4]}' from {match[0]}")
            return (match[1], match[2], match[3])
    
    # If no matches were found, return None
    logger.debug(f"No match found in any scanner list for: '{clean_title}'")
    return None

if __name__ == "__main__":
    # Configure logging for direct script execution
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )
    
    # Test with some examples
    test_items = [
        "Star Trek: The Next Generation",
        "Star.Trek.The.Next.Generation.S01E01",
        "Pokemon Origins",
        "Pokemon.Origins.S01.1080p.WEB-DL.AAC2.0.H.264-Pikanet128[rartv]",
        "Pokemon Destiny Deoxys"
    ]
    
    for item in test_items:
        print(f"\nTesting: {item}")
        result = check_scanner_lists(item)
        if result:
            print(f"Match found: {result}")
        else:
            print("No match found")