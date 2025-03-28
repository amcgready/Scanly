"""
File monitoring functionality for Scanly.

This module monitors directories for new files and
initiates the processing of those files.
"""

import os
import time
from pathlib import Path
from typing import Callable, List, Set, Optional

from src.config import ORIGIN_DIRECTORY
from src.utils.logger import get_logger

logger = get_logger(__name__)


class FileMonitor:
    """
    Monitors a directory for new files to process.
    """
    
    def __init__(self, directory: Optional[str] = None, callback: Optional[Callable] = None):
        """
        Initialize the file monitor.
        
        Args:
            directory: Directory to monitor. If not provided, uses the one from settings.
            callback: Function to call when new files are found.
        """
        self.directory = directory or ORIGIN_DIRECTORY
        self.callback = callback
        self.processed_files: Set[str] = set()
        
        if not os.path.isdir(self.directory):
            raise ValueError(f"Directory does not exist: {self.directory}")
        
        logger.info(f"Monitoring directory: {self.directory}")
    
    def scan_directory(self) -> List[str]:
        """
        Scan the monitored directory for files.
        
        Returns:
            List of file paths that haven't been processed yet.
        """
        new_files = []
        
        for root, _, files in os.walk(self.directory):
            for file in files:
                # Only consider media files
                if self._is_media_file(file):
                    full_path = os.path.join(root, file)
                    if full_path not in self.processed_files:
                        new_files.append(full_path)
        
        return new_files
    
    def _is_media_file(self, filename: str) -> bool:
        """
        Check if a file is a media file based on its extension.
        
        Args:
            filename: Name of the file to check
            
        Returns:
            True if the file has a media extension, False otherwise
        """
        media_extensions = {
            '.mp4', '.mkv', '.avi', '.mov', '.wmv', '.m4v', 
            '.mpg', '.mpeg', '.flv', '.webm'
        }
        
        _, ext = os.path.splitext(filename.lower())
        return ext in media_extensions
    
    def start_monitoring(self, interval: int = 60):
        """
        Start monitoring the directory for new files.
        
        Args:
            interval: Seconds between each scan
        """
        logger.info(f"Starting monitoring with {interval}s interval")
        
        try:
            while True:
                new_files = self.scan_directory()
                
                if new_files and self.callback:
                    logger.info(f"Found {len(new_files)} new files")
                    self.callback(new_files)
                    self.processed_files.update(new_files)
                
                time.sleep(interval)
        except KeyboardInterrupt:
            logger.info("Monitoring stopped by user")
    
    def process_single_file(self, file_path: str) -> bool:
        """
        Process a single file that was manually specified.
        
        Args:
            file_path: Path to the file to process
            
        Returns:
            True if processing was successful, False otherwise
        """
        if not os.path.isfile(file_path):
            logger.error(f"File does not exist: {file_path}")
            return False
        
        if not self._is_media_file(file_path):
            logger.warning(f"Not a media file: {file_path}")
            return False
        
        if self.callback:
            self.callback([file_path])
            self.processed_files.add(file_path)
            return True
        
        return False