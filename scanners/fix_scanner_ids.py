#!/usr/bin/env python3
"""
Fix movie IDs in scanner files.

This script converts ID formats in scanner files to the standard [tmdb-ID] format.
"""

import os
import re
import sys
from pathlib import Path

def fix_scanner_ids(scanner_file):
    """
    Fix IDs in a scanner file to use [tmdb-ID] format.
    
    Args:
        scanner_file: Path to the scanner file
    
    Returns:
        Tuple of (number of entries processed, number of entries modified)
    """
    if not os.path.exists(scanner_file):
        print(f"Scanner file not found: {scanner_file}")
        return 0, 0
    
    try:
        with open(scanner_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        total_entries = len(lines)
        modified_count = 0
        corrected_lines = []
        
        for line in lines:
            # Skip empty lines
            if not line.strip():
                corrected_lines.append(line)
                continue
            
            # Replace different ID formats with [tmdb-ID]
            # Case 1: [movie:ID]
            modified_line = re.sub(r'\[movie:(\d+)\]', r'[tmdb-\1]', line)
            
            # Case 2: [ID] (plain ID without prefix)
            modified_line = re.sub(r'\[(\d+)\](?!\])', r'[tmdb-\1]', modified_line)
            
            if modified_line != line:
                modified_count += 1
                
            corrected_lines.append(modified_line)
        
        # Write the modified content back to file
        with open(scanner_file, 'w', encoding='utf-8') as f:
            f.writelines(corrected_lines)
        
        return total_entries, modified_count
    
    except Exception as e:
        print(f"Error fixing scanner IDs: {e}")
        return 0, 0

def main():
    """Main entry point."""
    # Use the current working directory to locate the scanners folder
    cwd = Path.cwd()
    scanner_dir = cwd / 'scanners'
    
    # Fix scanner files
    scanner_files = [
        'movies.txt',
        'anime_movies.txt',
        'tv_series.txt',
        'anime_series.txt'
    ]
    
    print(f"Looking for scanner files in: {scanner_dir}")
    
    for scanner_file in scanner_files:
        file_path = scanner_dir / scanner_file
        if file_path.exists():
            print(f"Processing {scanner_file}...")
            total, fixed = fix_scanner_ids(str(file_path))
            print(f"  - Total entries: {total}")
            print(f"  - Fixed entries: {fixed}")
        else:
            print(f"Scanner file not found: {file_path}")

if __name__ == "__main__":
    main()