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
    Check if a title matches any entry in the scanner lists with weighted matching.
    
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
    
    # Clean the input title to remove technical info
    def clean_title(text):
        """Clean title for comparison by removing technical info"""
        if not text:
            return ""
            
        # Remove resolution indicators
        clean = re.sub(r'\b(?:720p|1080p|2160p|4K|UHD)\b', '', text, flags=re.IGNORECASE)
        
        # Remove media quality and encoding info
        clean = re.sub(r'\b(?:BluRay|BRRip|HDTV|WEB-DL|WEBRip|DVDRip|x264|x265|HEVC|10bit|HDR|DV)\b', '', clean, flags=re.IGNORECASE)
        
        # Remove release group tags and technical terms
        clean = re.sub(r'\b(?:REMUX|HYBRID|PROPER|REPACK|Atmos|ExKinoRay|YIFY|YTS(?:\.MX)?|RARBG|AMZN)\b', '', clean, flags=re.IGNORECASE)
        
        # Remove content in brackets and parentheses
        clean = re.sub(r'\[[^\]]*\]|\([^)]*\)', '', clean)
        
        # Normalize spaces and trim
        clean = re.sub(r'\s+', ' ', clean).strip()
        
        return clean
    
    # Function to normalize titles for comparison
    def normalize_title(text):
        if not text:
            return ""
        # Convert to lowercase
        text = text.lower()
        # Replace dots, underscores with spaces
        text = text.replace('.', ' ').replace('_', ' ')
        # Replace dashes with spaces
        text = text.replace('-', ' ')
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    # Calculate match score between two strings
    def calculate_match_score(input_title, scanner_entry):
        # First clean both titles to remove technical info
        clean_input = clean_title(input_title)
        clean_scanner = scanner_entry  # Scanner entries should already be clean
        
        # Then normalize for comparison
        input_words = set(normalize_title(clean_input).split())
        entry_words = set(normalize_title(clean_scanner).split())
        
        # Calculate word overlap
        common_words = input_words.intersection(entry_words)
        
        # If no common words, no match
        if not common_words:
            return 0
            
        # Calculate coverage ratio
        input_coverage = len(common_words) / len(input_words) if input_words else 0
        entry_coverage = len(common_words) / len(entry_words) if entry_words else 0
        
        # Base score calculation - weighted toward input coverage
        base_score = (input_coverage * 0.7) + (entry_coverage * 0.3)
        
        # Boost for exact match
        if normalize_title(clean_input) == normalize_title(clean_scanner):
            base_score *= 2.0
            
        # Boost for titles with similar length (prevents matching "3 Idiots" with "JourneyQuest 3.5")
        length_ratio = min(len(input_words), len(entry_words)) / max(len(input_words), len(entry_words))
        if length_ratio > 0.7:  # At least 70% similar in length
            base_score *= 1.2
            
        # Special handling for short titles with numbers (like "3 Idiots")
        input_has_number_prefix = bool(re.match(r'^\d+\b', normalize_title(clean_input)))
        entry_has_number_prefix = bool(re.match(r'^\d+\b', normalize_title(clean_scanner)))
        
        # If input starts with number but entry doesn't (or vice versa), penalize
        if input_has_number_prefix != entry_has_number_prefix:
            base_score *= 0.5
            
        # If both start with different numbers, heavy penalty
        if input_has_number_prefix and entry_has_number_prefix:
            input_number = re.match(r'^(\d+)\b', normalize_title(clean_input)).group(1)
            entry_number = re.match(r'^(\d+)\b', normalize_title(clean_scanner)).group(1)
            if input_number != entry_number:
                base_score *= 0.2  # Major penalty for mismatched numbers
                
        return base_score
    
    # Function to clean up scanner entry title
    def clean_scanner_entry(scanner_entry):
        # Remove the TMDB ID or [Error] part
        cleaned = re.sub(r'\s*\[[^\]]*\]$', '', scanner_entry.strip())
        return cleaned
        
    # Clean and normalize the input title
    clean_input_title = clean_title(title)
    normalized_title = normalize_title(clean_input_title)
    
    logger.debug(f"Checking scanner lists for: '{title}'")
    logger.debug(f"Cleaned title for matching: '{clean_input_title}'")
    
    best_match = None
    best_score = 0
    
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
                    if tmdb_match and tmdb_match.group(1) != "Error":
                        tmdb_id = tmdb_match.group(1)
                    
                    # Clean the scanner entry (remove [Error] or [TMDB_ID])
                    scanner_entry = clean_scanner_entry(line)
                    
                    # Calculate match score
                    match_score = calculate_match_score(title, scanner_entry)
                    
                    # For exact matches (highly confident)
                    if normalize_title(clean_input_title) == normalize_title(scanner_entry):
                        logger.debug(f"EXACT MATCH: '{clean_input_title}' == '{scanner_entry}'")
                        return (content_type, is_anime, tmdb_id, scanner_entry)
                    
                    # Track best match
                    if match_score > best_score:
                        best_score = match_score
                        best_match = (content_type, is_anime, tmdb_id, scanner_entry)
                        logger.debug(f"New best match: '{scanner_entry}' with score {best_score:.2f}")
        
        except Exception as e:
            logger.error(f"Error reading scanner file {filename}: {e}")
    
    # Use a high threshold to prevent false positives
    threshold = 0.6
    
    if best_match and best_score > threshold:
        logger.debug(f"Final best match: '{best_match[3]}' with score {best_score:.2f}")
        return best_match
    else:
        logger.debug(f"No good match found with score above {threshold:.2f} (best: {best_score:.2f})")
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