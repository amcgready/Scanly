"""
Scanner list processing functionality for Scanly.

This module searches scanner list files for matches before falling back to TMDB API.
"""

import os
import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from src.config import TMDB_API_KEY
from src.utils.logger import get_logger
from src.api.tmdb import TMDB

logger = get_logger(__name__)


class ScannerProcessor:
    """
    Process files using scanner lists.
    
    Attributes:
        scanner_dir: Directory containing scanner list files
        tmdb: TMDB API instance
        movie_entries: Entries from movies scanner list
        tv_entries: Entries from TV series scanner list
        anime_movie_entries: Entries from anime movies scanner list
        anime_tv_entries: Entries from anime series scanner list
    """
    
    def __init__(self, scanner_dir: Optional[str] = None):
        """
        Initialize the scanner processor.
        
        Args:
            scanner_dir: Directory containing scanner list files
        """
        self.scanner_dir = scanner_dir or os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'scanners')
        self.tmdb = TMDB(api_key=TMDB_API_KEY)
        
        # Load scanner lists
        self.movie_entries = self._load_scanner_list('movies.txt')
        self.tv_entries = self._load_scanner_list('tv_series.txt')
        self.anime_movie_entries = self._load_scanner_list('anime_movies.txt')
        self.anime_tv_entries = self._load_scanner_list('anime_series.txt')
        
        logger.info(f"Loaded scanner lists: {len(self.movie_entries)} movies, {len(self.tv_entries)} TV series, "
                   f"{len(self.anime_movie_entries)} anime movies, {len(self.anime_tv_entries)} anime series")
    
    def _load_scanner_list(self, filename: str) -> Dict[str, Union[str, int]]:
        """
        Load a scanner list file and extract entries with TMDB IDs.
        
        Args:
            filename: Scanner list filename
            
        Returns:
            Dictionary mapping clean titles to TMDB IDs where available
        """
        entries = {}
        file_path = os.path.join(self.scanner_dir, filename)
        
        if not os.path.exists(file_path):
            logger.warning(f"Scanner list file not found: {file_path}")
            return entries
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    # Check if entry has TMDB ID in format: "Title (Year) [12345]"
                    tmdb_id_match = re.search(r'\[(\d+)\]$', line)
                    if tmdb_id_match:
                        tmdb_id = int(tmdb_id_match.group(1))
                        # Remove the TMDB ID part for matching
                        title = re.sub(r'\s*\[\d+\]\s*$', '', line).lower()
                        entries[title] = tmdb_id
                    else:
                        entries[line.lower()] = None
        except Exception as e:
            logger.error(f"Error loading scanner list {filename}: {e}")
        
        return entries
    
    def _clean_filename(self, filename: str) -> str:
        """
        Clean filename for matching against scanner lists.
        
        Args:
            filename: Original filename
            
        Returns:
            Cleaned filename for matching
        """
        # Remove extension
        name = os.path.splitext(os.path.basename(filename))[0]
        
        # Replace dots, underscores with spaces
        name = name.replace('.', ' ').replace('_', ' ')
        
        # Remove common keywords
        patterns = [
            r'(?i)1080p', r'(?i)720p', r'(?i)2160p', r'(?i)480p',
            r'(?i)bluray', r'(?i)webrip', r'(?i)brrip', r'(?i)dvdrip',
            r'(?i)x264', r'(?i)x265', r'(?i)hdtv', r'(?i)hevc',
            r'(?i)aac', r'(?i)ac3', r'(?i)mp3', r'(?i)xvid'
        ]
        for pattern in patterns:
            name = re.sub(pattern, '', name)
        
        # Clean up multiple spaces
        name = re.sub(r'\s+', ' ', name).strip().lower()
        
        return name
    
    def _extract_year(self, filename: str) -> Tuple[str, Optional[str]]:
        """
        Extract year from filename.
        
        Args:
            filename: Filename to process
            
        Returns:
            Tuple of (clean_name, year or None)
        """
        year_match = re.search(r'(?:^|\D)((19|20)\d{2})(?:\D|$)', filename)
        if year_match:
            year = year_match.group(1)
            clean_name = re.sub(r'(?:^|\D)((19|20)\d{2})(?:\D|$)', ' ', filename).strip()
            return clean_name, year
        return filename, None
    
    def _find_match(self, clean_name: str, year: Optional[str], entries: Dict[str, Union[str, int]]) -> Optional[int]:
        """
        Find a match in the scanner entries.
        
        Args:
            clean_name: Clean filename
            year: Year if available
            entries: Scanner list entries
            
        Returns:
            TMDB ID if found, None otherwise
        """
        # Try exact match with year
        if year:
            key = f"{clean_name} ({year})".lower()
            if key in entries:
                return entries[key]
        
        # Try exact match without year
        if clean_name.lower() in entries:
            return entries[clean_name.lower()]
        
        # Try partial matches
        for entry, tmdb_id in entries.items():
            if clean_name.lower() in entry or entry in clean_name.lower():
                return tmdb_id
        
        return None
    
    def process_file(self, file_path: str) -> Dict:
        """
        Process a file using scanner lists.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Dictionary with match info or empty dict if no match
        """
        filename = os.path.basename(file_path)
        clean_name = self._clean_filename(filename)
        clean_name, year = self._extract_year(clean_name)
        
        logger.debug(f"Processing file using scanner lists: {filename} -> {clean_name} ({year or 'no year'})")
        
        # Try all scanner lists
        for media_type, entries in [
            ("movie", self.movie_entries),
            ("tv", self.tv_entries),
            ("anime_movie", self.anime_movie_entries),
            ("anime_tv", self.anime_tv_entries)
        ]:
            tmdb_id = self._find_match(clean_name, year, entries)
            if tmdb_id:
                # If we found a match but don't have a TMDB ID, continue to next list
                if tmdb_id is None:
                    continue
                    
                # Get full details from TMDB API
                try:
                    if media_type == "movie" or media_type == "anime_movie":
                        details = self.tmdb.get_movie_details(tmdb_id)
                        is_anime = media_type == "anime_movie"
                        return {
                            "tmdb_id": tmdb_id,
                            "title": details.get("title", clean_name),
                            "year": details.get("release_date", "")[:4] if details.get("release_date") else year,
                            "type": "movie",
                            "is_anime": is_anime,
                            "details": details
                        }
                    else:  # TV series
                        details = self.tmdb.get_tv_details(tmdb_id)
                        is_anime = media_type == "anime_tv"
                        return {
                            "tmdb_id": tmdb_id,
                            "title": details.get("name", clean_name),
                            "year": details.get("first_air_date", "")[:4] if details.get("first_air_date") else year,
                            "type": "tv",
                            "is_anime": is_anime,
                            "details": details
                        }
                except Exception as e:
                    logger.error(f"Error getting details for TMDB ID {tmdb_id}: {e}")
        
        return {}