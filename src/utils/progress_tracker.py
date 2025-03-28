"""
Progress tracking functionality for Scanly.

This module provides functions for tracking scan progress and
allowing users to resume interrupted scans.
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Set, Any

from src.config import PROGRESS_FILE
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ProgressTracker:
    """
    Tracks progress of file processing.
    
    Allows users to resume interrupted scans by tracking processed
    and skipped files.
    """
    
    def __init__(self, progress_file: str = None):
        """
        Initialize the progress tracker.
        
        Args:
            progress_file: Path to the progress file. If not provided, uses the one from settings.
        """
        self.progress_file = progress_file or Path(__file__).parents[3] / PROGRESS_FILE
        self.data = self._load_progress()
    
    def _load_progress(self) -> Dict[str, Any]:
        """
        Load progress data from the progress file.
        
        Returns:
            Progress data
        """
        if not os.path.exists(self.progress_file):
            return {
                'processed': [],
                'skipped': [],
                'unfinished': []
            }
        
        try:
            with open(self.progress_file, 'r') as f:
                data = json.load(f)
            
            # Ensure all required keys exist
            for key in ['processed', 'skipped', 'unfinished']:
                if key not in data:
                    data[key] = []
            
            return data
        except Exception as e:
            logger.error(f"Failed to load progress data: {e}")
            return {
                'processed': [],
                'skipped': [],
                'unfinished': []
            }
    
    def _save_progress(self):
        """Save progress data to the progress file."""
        try:
            with open(self.progress_file, 'w') as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save progress data: {e}")
    
    def mark_processed(self, path: str):
        """
        Mark a file or directory as processed.
        
        Args:
            path: Path to the file or directory
        """
        path = os.path.abspath(path)
        
        if path not in self.data['processed']:
            self.data['processed'].append(path)
        
        # Remove from other lists if present
        if path in self.data['skipped']:
            self.data['skipped'].remove(path)
        
        if path in self.data['unfinished']:
            self.data['unfinished'].remove(path)
        
        self._save_progress()
    
    def mark_skipped(self, path: str):
        """
        Mark a file or directory as skipped.
        
        Args:
            path: Path to the file or directory
        """
        path = os.path.abspath(path)
        
        if path not in self.data['skipped']:
            self.data['skipped'].append(path)
        
        # Remove from unfinished if present
        if path in self.data['unfinished']:
            self.data['unfinished'].remove(path)
        
        self._save_progress()
    
    def mark_unfinished(self, path: str):
        """
        Mark a file or directory as unfinished.
        
        Args:
            path: Path to the file or directory
        """
        path = os.path.abspath(path)
        
        if path not in self.data['unfinished']:
            self.data['unfinished'].append(path)
        
        self._save_progress()
    
    def is_processed(self, path: str) -> bool:
        """
        Check if a file or directory has been processed.
        
        Args:
            path: Path to check
            
        Returns:
            True if processed, False otherwise
        """
        path = os.path.abspath(path)
        return path in self.data['processed']
    
    def is_skipped(self, path: str) -> bool:
        """
        Check if a file or directory has been skipped.
        
        Args:
            path: Path to check
            
        Returns:
            True if skipped, False otherwise
        """
        path = os.path.abspath(path)
        return path in self.data['skipped']
    
    def is_unfinished(self, path: str) -> bool:
        """
        Check if a file or directory is unfinished.
        
        Args:
            path: Path to check
            
        Returns:
            True if unfinished, False otherwise
        """
        path = os.path.abspath(path)
        return path in self.data['unfinished']
    
    def get_processed_items(self) -> List[str]:
        """
        Get all processed items.
        
        Returns:
            List of processed item paths
        """
        return self.data['processed']
    
    def get_skipped_items(self) -> List[str]:
        """
        Get all skipped items.
        
        Returns:
            List of skipped item paths
        """
        return self.data['skipped']
    
    def get_unfinished_items(self) -> List[str]:
        """
        Get all unfinished items.
        
        Returns:
            List of unfinished item paths
        """
        return self.data['unfinished']
    
    def reset_progress(self):
        """Reset all progress data."""
        self.data = {
            'processed': [],
            'skipped': [],
            'unfinished': []
        }
        self._save_progress()
        logger.info("Progress data reset")
    
    def get_statistics(self) -> Dict[str, int]:
        """
        Get statistics about processed, skipped, and unfinished items.
        
        Returns:
            Dictionary with count statistics
        """
        return {
            'processed_count': len(self.data['processed']),
            'skipped_count': len(self.data['skipped']),
            'unfinished_count': len(self.data['unfinished'])
        }