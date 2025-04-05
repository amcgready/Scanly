"""
Symlink repair functionality for Scanly.

This module provides functionality for detecting and repairing broken symlinks.
"""

import os
import time
from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple
import threading

from src.config import (
    DESTINATION_DIRECTORY, 
    RELATIVE_SYMLINK,
    AUTO_REPAIR_SYMLINKS  # Changed from AUTO_SYMLINK_REPAIR
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


class SymlinkRepair:
    """
    Handles detection and repair of broken symlinks.
    
    Attributes:
        destination_dir: Directory containing symlinks to check
        last_check_time: Timestamp of the last check
        symlink_map: Maps symlinks to their targets
        search_paths: List of directories to search for targets
        monitor_active: Whether the background monitor is active
        monitor_interval: How often to check for broken symlinks (in seconds)
    """
    
    def __init__(self, destination_dir: Optional[str] = None, search_paths: Optional[List[str]] = None, 
                 auto_repair: bool = True, monitor_interval: int = 3600):
        """
        Initialize the symlink repair.
        
        Args:
            destination_dir: Root directory containing symlinks to check
            search_paths: List of directories to search for missing targets
            auto_repair: Whether to automatically repair broken symlinks
            monitor_interval: How often to check for broken symlinks (in seconds)
        """
        self.destination_dir = destination_dir or DESTINATION_DIRECTORY
        self.last_check_time = time.time()
        self.symlink_map: Dict[str, str] = {}
        self.auto_repair = auto_repair and AUTO_REPAIR_SYMLINKS and LINK_TYPE == 'symlink'
        self.monitor_interval = monitor_interval
        self.monitor_active = False
        self.monitor_thread = None
        self.search_paths = search_paths or self._get_default_search_paths()
        
        # Statistics
        self.broken_links_found = 0
        self.links_repaired = 0
        self.links_failed = 0
        
        # Load initial symlink map
        if self.auto_repair:
            self._build_symlink_map()
    
    def _get_default_search_paths(self) -> List[str]:
        """Get default search paths for finding missing files."""
        paths = []
        
        # Add the origin directory if available
        if ORIGIN_DIRECTORY and os.path.isdir(ORIGIN_DIRECTORY):
            paths.append(ORIGIN_DIRECTORY)
        
        # Add common Linux paths that might contain media
        for path in ['/media', '/mnt', '/home']:
            if os.path.isdir(path):
                paths.append(path)
                
        # Add current user's home directory
        home_dir = os.path.expanduser("~")
        if home_dir and os.path.isdir(home_dir):
            paths.append(home_dir)
            
        # Add the parent directory of the destination
        if self.destination_dir:
            parent = os.path.dirname(self.destination_dir)
            if parent and os.path.isdir(parent):
                paths.append(parent)
                
        return paths
    
    def _build_symlink_map(self):
        """Build a map of all symlinks and their targets in the destination directory."""
        logger.info(f"Building symlink map for {self.destination_dir}")
        self.symlink_map = {}
        
        try:
            if not os.path.exists(self.destination_dir):
                logger.warning(f"Destination directory does not exist: {self.destination_dir}")
                return
                
            for root, _, files in os.walk(self.destination_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    if os.path.islink(file_path):
                        target = os.readlink(file_path)
                        self.symlink_map[file_path] = target
        except Exception as e:
            logger.error(f"Error building symlink map: {e}")
        
        logger.debug(f"Found {len(self.symlink_map)} symlinks")
    
    def _find_broken_symlinks(self) -> List[str]:
        """
        Find broken symlinks in the destination directory.
        
        Returns:
            List of paths to broken symlinks
        """
        broken_symlinks = []
        
        for symlink, target in self.symlink_map.items():
            # Handle relative symlinks
            if not os.path.isabs(target):
                target = os.path.join(os.path.dirname(symlink), target)
                
            if not os.path.exists(target):
                broken_symlinks.append(symlink)
        
        return broken_symlinks
    
    def _find_replacement(self, filename: str) -> Optional[str]:
        """
        Search for a replacement file matching the given filename.
        
        Args:
            filename: Name of the file to find
            
        Returns:
            Path to the replacement file if found, None otherwise
        """
        for search_dir in self.search_paths:
            if not os.path.isdir(search_dir):
                continue
                
            logger.debug(f"Searching for '{filename}' in {search_dir}")
            
            # First try a simple recursive search
            for root, _, files in os.walk(search_dir):
                if filename in files:
                    return os.path.join(root, filename)
        
        return None
    
    def _repair_symlink(self, broken_symlink: str) -> bool:
        """
        Attempt to repair a broken symlink.
        
        Args:
            broken_symlink: Path to the broken symlink
            
        Returns:
            True if successfully repaired, False otherwise
        """
        original_target = self.symlink_map.get(broken_symlink)
        if not original_target:
            return False
        
        # Try to find the file in the original directory
        filename = os.path.basename(original_target)
        
        # Check if original target exists but with a different path
        if os.path.isabs(original_target) and os.path.exists(original_target):
            try:
                os.unlink(broken_symlink)
                os.symlink(original_target, broken_symlink)
                logger.info(f"Repaired symlink by updating path: {broken_symlink} -> {original_target}")
                return True
            except Exception as e:
                logger.error(f"Failed to update symlink {broken_symlink}: {e}")
                return False
        
        # Search for a replacement file
        new_target = self._find_replacement(filename)
        
        if new_target:
            # Remove the broken symlink
            try:
                os.unlink(broken_symlink)
            except Exception as e:
                logger.error(f"Failed to remove broken symlink {broken_symlink}: {e}")
                return False
            
            # Create a new symlink to the found file
            try:
                # Check if we should use relative paths
                if os.environ.get('RELATIVE_SYMLINK', 'false').lower() == 'true':
                    # Calculate relative path
                    link_dir = os.path.dirname(broken_symlink)
                    rel_path = os.path.relpath(new_target, link_dir)
                    os.symlink(rel_path, broken_symlink)
                    logger.info(f"Repaired symlink with relative path: {broken_symlink} -> {rel_path}")
                else:
                    # Use absolute path
                    os.symlink(new_target, broken_symlink)
                    logger.info(f"Repaired symlink: {broken_symlink} -> {new_target}")
                return True
            except Exception as e:
                logger.error(f"Failed to create new symlink {broken_symlink}: {e}")
                return False
        
        logger.warning(f"Could not find target for {broken_symlink}")
        return False
    
    def scan_for_broken_links(self) -> List[str]:
        """
        Perform a scan for broken symlinks in the destination directory.
        
        Returns:
            List of broken symlink paths found
        """
        # Refresh the symlink map first
        self._build_symlink_map()
        
        # Find broken symlinks
        broken_symlinks = self._find_broken_symlinks()
        
        # Update statistics
        self.broken_links_found = len(broken_symlinks)
        logger.info(f"Found {len(broken_symlinks)} broken symlinks")
        
        return broken_symlinks
    
    def check_and_repair(self) -> int:
        """
        Check for and repair broken symlinks.
        
        Returns:
            Number of repaired symlinks
        """
        if not self.auto_repair:
            return 0
        
        try:
            # Find broken symlinks
            broken_symlinks = self.scan_for_broken_links()
            
            if not broken_symlinks:
                return 0
                
            # Reset repair counters
            self.links_repaired = 0
            self.links_failed = 0
            
            # Repair broken symlinks
            for symlink in broken_symlinks:
                if self._repair_symlink(symlink):
                    self.links_repaired += 1
                else:
                    self.links_failed += 1
            
            if self.links_repaired > 0:
                logger.info(f"Repaired {self.links_repaired} symlinks, {self.links_failed} failed")
            
            return self.links_repaired
        except Exception as e:
            logger.error(f"Error checking and repairing symlinks: {e}", exc_info=True)
            return 0
    
    def _monitor_symlinks(self):
        """Background thread function that periodically checks for broken symlinks."""
        while self.monitor_active:
            try:
                repaired = self.check_and_repair()
                if repaired > 0:
                    logger.info(f"Background monitor repaired {repaired} symlinks")
            except Exception as e:
                logger.error(f"Error in symlink monitor: {e}")
            
            # Sleep for the specified interval
            time.sleep(self.monitor_interval)
    
    def start_monitor(self):
        """Start the background symlink monitoring thread."""
        if self.monitor_active:
            logger.warning("Symlink monitor is already running")
            return
            
        if not self.auto_repair:
            logger.warning("Auto-repair is disabled, not starting monitor")
            return
        
        self.monitor_active = True
        self.monitor_thread = threading.Thread(target=self._monitor_symlinks, daemon=True)
        self.monitor_thread.start()
        logger.info(f"Started symlink monitor thread (interval: {self.monitor_interval}s)")
    
    def stop_monitor(self):
        """Stop the background symlink monitoring thread."""
        if not self.monitor_active:
            return
            
        self.monitor_active = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=1.0)
            logger.info("Stopped symlink monitor thread")
    
    def repair_all(self) -> Tuple[int, int]:
        """
        Manually repair all broken symlinks.
        
        Returns:
            Tuple of (repaired count, failed count)
        """
        self.check_and_repair()
        return (self.links_repaired, self.links_failed)
    
    def add_search_path(self, path: str):
        """
        Add a directory to the search paths.
        
        Args:
            path: Directory path to add
        """
        if os.path.isdir(path) and path not in self.search_paths:
            self.search_paths.append(path)
            logger.debug(f"Added search path: {path}")