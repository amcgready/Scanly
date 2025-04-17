import os
import re
import logging
import sys

def load_scanner_entries(filename):
    """
    Load entries from a scanner list file.
    
    Args:
        filename: Name of the scanner list file
        
    Returns:
        List of entries from the file
    """
    try:
        # Define path to scanner file
        scanner_file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'scanners', filename)
        
        # Check if file exists
        if not os.path.exists(scanner_file_path):
            logger.warning(f"Scanner file not found: {scanner_file_path}")
            return []
        
        # Read entries from file
        with open(scanner_file_path, 'r', encoding='utf-8') as f:
            entries = [line.strip() for line in f.readlines() if line.strip()]
        
        return entries
    except Exception as e:
        logger.error(f"Error loading scanner entries from {filename}: {e}")
        return []

def check_scanner_lists(filename, title_hint=None):
    """
    Check if the filename matches any entries in scanner lists.
    
    Args:
        filename: The filename to check
        title_hint: Optional title hint to improve matching accuracy
        
    Returns:
        Tuple of (content_type, is_anime, tmdb_id, title) or None if no match
    """
    # Clean the filename for comparison
    clean_name = filename.lower().replace('.', ' ').replace('_', ' ')
    
    # Special case for Pokemon Origins
    if "pokemon origins" in clean_name or (title_hint and "pokemon origins" in title_hint.lower()):
        return ('tv', True, None, "Pokemon Origins")
    
    # Special case for Pokemon Destiny Deoxys
    if "pokemon destiny deoxys" in clean_name or (title_hint and "pokemon destiny deoxys" in title_hint.lower()):
        return ('movie', True, None, "Pokemon Destiny Deoxys")
    
    # If we have a title hint, use it for more accurate matching
    if title_hint:
        # Try exact match first with title hint
        for list_type, is_anime in [('tv_series', False), ('movies', False), ('anime_series', True), ('anime_movies', True)]:
            entries = load_scanner_entries(f"{list_type}.txt")
            for entry in entries:
                # Check for exact match with title_hint
                if title_hint.lower() == entry.lower() or title_hint.lower() in entry.lower():
                    content_type = 'tv' if 'series' in list_type else 'movie'
                    # Extract TMDB ID if available
                    tmdb_id = None
                    if '[' in entry and ']' in entry:
                        try:
                            tmdb_id = re.search(r'\[(\d+)\]$', entry).group(1)
                        except:
                            pass
                    return (content_type, is_anime, tmdb_id, entry)
    
    # If no match with title_hint or no hint provided, check against scanner lists
    for list_type, is_anime in [('tv_series', False), ('movies', False), ('anime_series', True), ('anime_movies', True)]:
        entries = load_scanner_entries(f"{list_type}.txt")
        for entry in entries:
            # Skip entries that are too short (like single letters that might match accidentally)
            clean_entry = entry.lower().replace('[', ' ').replace(']', ' ')
            if len(clean_entry.strip()) <= 1:
                continue
                
            # Check if entry is in the filename
            if clean_entry in clean_name:
                # Make sure this is not a partial word match
                # e.g., prevent "K" from matching "Pokemon"
                if len(clean_entry) <= 2:
                    # For single/double character entries, ensure they're standalone
                    if not re.search(fr'\b{re.escape(clean_entry)}\b', clean_name):
                        continue
                
                content_type = 'tv' if 'series' in list_type else 'movie'
                # Extract TMDB ID if available
                tmdb_id = None
                if '[' in entry and ']' in entry:
                    try:
                        tmdb_id = re.search(r'\[(\d+)\]$', entry).group(1)
                    except:
                        pass
                return (content_type, is_anime, tmdb_id, entry)
    
    # No match found
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