#!/usr/bin/env python3
"""
Utilities for managing scanner lists.

This module provides functions for working with scanner lists in Scanly.
"""

import os
import re
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

class ScannerUtils:
    """Utilities for scanner list operations."""
    
    @staticmethod
    def format_entry(title: str, year: Optional[str], tmdb_id: str) -> str:
        """
        Format an entry for a scanner list.
        
        Args:
            title: Title of the show or movie
            year: Release year or None if unknown
            tmdb_id: TMDB ID
            
        Returns:
            Formatted entry for the scanner list
        """
        # Format with year if available and use the standard [tmdb-ID] format
        if year:
            return f"{title} ({year}) [tmdb-{tmdb_id}]"
        else:
            return f"{title} [tmdb-{tmdb_id}]"
    
    @staticmethod
    def parse_entry(entry: str) -> Dict[str, Any]:
        """
        Parse a scanner list entry.
        
        Args:
            entry: A line from a scanner list file
            
        Returns:
            Dictionary containing title, year (if any), and ID
        """
        result = {
            "title": "",
            "year": None,
            "tmdb_id": None,
            "error": False
        }
        
        # Check for error entries
        if "[Error]" in entry:
            title_part = entry.split("[Error]")[0].strip()
            result["title"] = title_part
            result["error"] = True
            return result
            
        # Extract ID - look for [tmdb-ID] pattern
        id_match = re.search(r'\[tmdb-(\d+)\]', entry)
        
        # Fall back to other patterns if needed
        if not id_match:
            id_match = re.search(r'\[movie:(\d+)\]', entry)
        if not id_match:
            id_match = re.search(r'\[(\d+)\]', entry)
            
        if id_match:
            result["tmdb_id"] = id_match.group(1)
            
            # Extract title and year
            title_part = re.split(r'\[', entry)[0].strip()
            year_match = re.search(r'\((\d{4})\)$', title_part)
            
            if year_match:
                result["year"] = year_match.group(1)
                result["title"] = title_part[:-7].strip()
            else:
                result["title"] = title_part
        
        return result
    
    @staticmethod
    def add_to_scanner(scanner_file: str, title: str, year: Optional[str], tmdb_id: str) -> bool:
        """
        Add an entry to a scanner file.
        
        Args:
            scanner_file: Path to the scanner file
            title: Title of the show or movie
            year: Release year or None
            tmdb_id: TMDB ID
            
        Returns:
            True if added successfully, False otherwise
        """
        entry = ScannerUtils.format_entry(title, year, tmdb_id)
        
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(scanner_file), exist_ok=True)
            
            # Append entry to file
            with open(scanner_file, 'a', encoding='utf-8') as f:
                f.write(f"{entry}\n")
            return True
        except Exception as e:
            logger.error(f"Failed to add entry to scanner file: {e}")
            return False
    
    @staticmethod
    def get_all_entries(scanner_file: str) -> List[Dict[str, Any]]:
        """
        Get all entries from a scanner file.
        
        Args:
            scanner_file: Path to the scanner file
            
        Returns:
            List of parsed entries
        """
        entries = []
        try:
            if not os.path.exists(scanner_file):
                return entries
                
            with open(scanner_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
            for line in lines:
                if line.strip():
                    entry = ScannerUtils.parse_entry(line.strip())
                    entries.append(entry)
                    
            return entries
        except Exception as e:
            logger.error(f"Failed to read scanner file: {e}")
            return entries