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

def check_scanner_lists(title, check_full_path=False):
    """
    Check if a title matches any entry in the scanner lists.
    
    Args:
        title: The title to check
        check_full_path: If True, match against full paths instead of just titles
        
    Returns:
        A tuple of (content_type, is_anime, tmdb_id, title_override) or None if no match
    """
    logger = logging.getLogger(__name__)
    
    # Lists to check (in order of priority)
    scanner_files = [
        ('anime_series.txt', 'tv', True),
        ('anime_movies.txt', 'movie', True),
        ('tv_series.txt', 'tv', False),
        ('movies.txt', 'movie', False)
    ]
    
    # Get the base scanner directory
    scanner_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'scanners')
    
    # Function to normalize titles for comparison
    def normalize_title(text):
        if not text:
            return ""
        # Convert to lowercase
        text = text.lower()
        # Replace dots, underscores with spaces
        text = text.replace('.', ' ').replace('_', ' ')
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    normalized_title = normalize_title(title)
    
    # Check each scanner list
    for filename, content_type, is_anime in scanner_files:
        file_path = os.path.join(scanner_dir, filename)
        
        if not os.path.exists(file_path):
            continue
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    # Extract TMDB ID if present
                    tmdb_id = None
                    tmdb_match = re.search(r'\[(\d+)\]$', line)
                    if tmdb_match:
                        tmdb_id = tmdb_match.group(1)
                        # Remove the TMDB ID from the line for title matching
                        scanner_entry = line[:tmdb_match.start()].strip()
                    else:
                        scanner_entry = line
                    
                    # For full path matching, compare the normalized path
                    if check_full_path:
                        normalized_entry = normalize_title(scanner_entry)
                        if normalized_entry in normalized_title or normalized_title.endswith(normalized_entry):
                            logger.debug(f"Full path match found: '{scanner_entry}' in '{title}'")
                            return (content_type, is_anime, tmdb_id, scanner_entry)
                    else:
                        # For title matching, normalize both and compare
                        normalized_entry = normalize_title(scanner_entry)
                        if normalized_entry == normalized_title:
                            return (content_type, is_anime, tmdb_id, scanner_entry)
                        
                        # Also check if the scanner entry is a substring of the title
                        # This helps with titles that might have extra information
                        words_in_entry = normalized_entry.split()
                        if len(words_in_entry) > 2:  # Only do substring matching for longer entries
                            if normalized_entry in normalized_title:
                                return (content_type, is_anime, tmdb_id, scanner_entry)
        
        except Exception as e:
            logger.error(f"Error reading scanner file {filename}: {e}")
    
    return None

def update_scanner_entry(scanner_file, entry, tmdb_id):
    """
    Update a scanner entry with a new TMDB ID.
    
    Args:
        scanner_file: The scanner file to update (tv_series.txt, movies.txt, etc.)
        entry: The entry to update
        tmdb_id: The new TMDB ID
        
    Returns:
        Boolean indicating success
    """
    import os
    import re
    
    scanner_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'scanners', scanner_file)
    
    if not os.path.exists(scanner_path):
        return False
    
    # Read the file
    with open(scanner_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Entry might have trailing whitespace in the file
    entry = entry.strip()
    
    # Find and update the entry
    updated = False
    for i, line in enumerate(lines):
        if line.strip() == entry:
            # Clean entry (remove the existing ERROR part)
            clean_entry = re.sub(r'\s*\[.*?\]\s*$', '', entry).strip()
            # Add the new TMDB ID
            lines[i] = f"{clean_entry} [{tmdb_id}]\n"
            updated = True
            break
    
    # Write the file back if updated
    if updated:
        with open(scanner_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        return True
    
    return False

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