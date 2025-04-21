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
    logger = logging.getLogger(__name__)
    logger.debug(f"SCANNER - ENTRY: Checking scanner lists for: '{filename}'")
    
    # Clean the filename for comparison
    clean_name = filename.lower().replace('.', ' ').replace('_', ' ')
    logger.debug(f"SCANNER - STEP 1: Cleaned name for matching: '{clean_name}'")
    
    # Special case for Pokemon Origins
    if "pokemon origins" in clean_name or (title_hint and "pokemon origins" in title_hint.lower()):
        logger.debug("SCANNER - SPECIAL CASE: Pokemon Origins")
        return ('tv', True, None, "Pokemon Origins")
    
    # Special case for Pokemon Destiny Deoxys
    if "pokemon destiny deoxys" in clean_name or (title_hint and "pokemon destiny deoxys" in title_hint.lower()):
        logger.debug("SCANNER - SPECIAL CASE: Pokemon Destiny Deoxys")
        return ('movie', True, None, "Pokemon Destiny Deoxys")
    
    # Common technical terms that should NOT be matched as titles
    technical_terms = [
        'hybrid', 'remux', 'bluray', 'web-dl', 'webrip', 'hdtv', 'dvdrip',
        'hdr', 'dv', 'x264', 'x265', 'hevc', 'avc', '1080p', '2160p', '720p',
        'aac', 'ac3', 'dts', 'dd5.1', 'atmos', 'truehd', 'uhd'
    ]
    
    # List of potential matches with their scores
    potential_matches = []
    
    # Look for exact matches in scanner lists
    for list_type, is_anime in [('tv_series', False), ('movies', False), ('anime_series', True), ('anime_movies', True)]:
        entries = load_scanner_entries(f"{list_type}.txt")
        logger.debug(f"SCANNER - STEP 2: Checking {list_type} list with {len(entries)} entries")
        
        for entry in entries:
            # Skip entries that are too short
            clean_entry_for_length = re.sub(r'\s*\[\d+\]\s*$', '', entry).lower().strip()
            if len(clean_entry_for_length) <= 1:
                continue
            
            # Extract the clean title from the entry (no TMDB ID)
            clean_entry = entry.lower()
            clean_entry = re.sub(r'\s*\[\d+\]\s*$', '', clean_entry).strip()
            
            logger.debug(f"SCANNER - STEP 3: Comparing '{clean_name}' with entry '{clean_entry}'")
            
            # Only match technical terms if they're not in the technical_terms list
            if clean_entry in technical_terms:
                logger.debug(f"SCANNER - SKIPPING: '{clean_entry}' is a common technical term")
                continue
            
            # Calculate match score - higher is better
            match_score = 0
            
            # Check if entry is in the filename
            if clean_entry in clean_name:
                # Basic match
                match_score = 1
                
                # For short entries (1-2 chars), ensure they're standalone
                if len(clean_entry) <= 2:
                    if not re.search(fr'\b{re.escape(clean_entry)}\b', clean_name):
                        continue
                
                # Boost score for longer titles (more specific matches)
                match_score += len(clean_entry) / 10
                
                # Boost score for titles at the beginning or end of the filename
                if clean_name.startswith(clean_entry):
                    match_score += 5
                elif clean_name.endswith(clean_entry):
                    match_score += 3
                
                # Boost score for exact matches with word boundaries
                if re.search(fr'\b{re.escape(clean_entry)}\b', clean_name):
                    match_score += 2
                
                # Check if entry appears to be a release group
                # Release groups often appear at the end after a dash
                if "-" in clean_name and clean_entry in clean_name.split("-")[-1]:
                    # This might be a release group, reduce score
                    match_score -= 3
                
                # Store potential match
                content_type = 'tv' if 'series' in list_type else 'movie'
                
                # Extract TMDB ID if available
                tmdb_id = None
                if '[' in entry and ']' in entry:
                    try:
                        tmdb_id = re.search(r'\[(\d+)\]$', entry).group(1)
                    except:
                        pass
                
                # CRITICAL FIX: Get the original title WITHOUT the ID
                original_entry = re.sub(r'\s*\[\d+\]\s*$', '', entry).strip()
                potential_matches.append((match_score, content_type, is_anime, tmdb_id, original_entry))
    
    # Sort potential matches by score (highest first)
    potential_matches.sort(reverse=True, key=lambda x: x[0])
    
    # Return the best match if any
    if potential_matches:
        best_match = potential_matches[0]
        logger.info(f"SCANNER - BEST MATCH: '{best_match[4]}' with score {best_match[0]}")
        return best_match[1:]
    
    # No match found
    logger.debug("SCANNER - NO MATCH: No match found in scanner lists")
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