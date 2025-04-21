"""
File monitoring functionality for Scanly.

This module provides the FileMonitor class for scanning directories for new files.
"""

import os
import time
from pathlib import Path
from typing import List, Set, Optional

from src.utils.logger import get_logger

logger = get_logger(__name__)

class FileMonitor:
    """
    Monitors a directory for new media files.
    """
    
    def __init__(self, directory: str):
        """Initialize the file monitor."""
        self.directory = directory
        self.logger = get_logger(__name__)
        # Common media file extensions
        self.media_extensions = ['.mkv', '.mp4', '.avi', '.mov', '.wmv', '.flv', '.m4v', '.ts']
    
    def scan_directory(self) -> List[str]:
        """
        Scan the directory and return a list of media files.
        
        Returns:
            List of media file paths
        """
        media_files = []
        try:
            # Walk through directory and find media files
            for root, _, files in os.walk(self.directory):
                for file in files:
                    # Check if file has a media extension
                    if any(file.lower().endswith(ext) for ext in self.media_extensions):
                        file_path = os.path.join(root, file)
                        media_files.append(file_path)
            
            # Sort media files for consistent results
            media_files.sort()
            self.logger.info(f"Found {len(media_files)} media files in {self.directory}")
            return media_files
            
        except Exception as e:
            self.logger.error(f"Error scanning directory {self.directory}: {e}")
            return []