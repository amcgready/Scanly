"""
Symlink repair functionality for Scanly.

This module provides tools to detect and repair broken symlinks
in the organized media library.
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set

from src.config import DESTINATION_DIRECTORY
from src.utils.logger import get_logger
from src.core.symlink_creator import SymlinkCreator

logger = get_logger(__name__)

class SymlinkRepair:
    """
    Tool for repairing broken symlinks in the Scanly library.
    """
    
    def __init__(self, destination_directory: Optional[str] = None):
        """
        Initialize the SymlinkRepair tool.
        
        Args:
            destination_directory: Directory to scan for broken links.
                                  If None, uses the value from settings.
        """
        self.destination_dir = destination_directory or DESTINATION_DIRECTORY
        self.symlink_creator = SymlinkCreator(destination_directory)
        
        # Statistics
        self.broken_links_found = 0
        self.links_repaired = 0
        self.links_failed = 0
        
        # Keep track of broken links we find
        self.broken_links = []
        
    def scan_for_broken_links(self, directory: Optional[str] = None) -> List[str]:
        """
        Scan for broken symlinks in the given directory and its subdirectories.
        
        Args:
            directory: Directory to scan. If None, uses the destination directory.
            
        Returns:
            List of paths to broken symlinks
        """
        scan_dir = directory or self.destination_dir
        logger.info(f"Scanning for broken symlinks in: {scan_dir}")
        
        if not os.path.exists(scan_dir):
            logger.error(f"Directory does not exist: {scan_dir}")
            return []
        
        broken_links = []
        
        for root, _, files in os.walk(scan_dir):
            for file in files:
                file_path = os.path.join(root, file)
                
                if os.path.islink(file_path) and not os.path.exists(os.path.realpath(file_path)):
                    logger.debug(f"Found broken symlink: {file_path}")
                    broken_links.append(file_path)
        
        self.broken_links = broken_links
        self.broken_links_found = len(broken_links)
        logger.info(f"Found {len(broken_links)} broken symlinks")
        
        return broken_links
    
    def attempt_repair(self, broken_link: str, search_directories: List[str]) -> bool:
        """
        Attempt to repair a single broken symlink by searching for the target file.
        
        Args:
            broken_link: Path to the broken symlink
            search_directories: List of directories to search for the target file
            
        Returns:
            True if the repair was successful, False otherwise
        """
        if not os.path.islink(broken_link):
            logger.error(f"Not a symlink: {broken_link}")
            return False
        
        # Get the original target and filename
        target = os.readlink(broken_link)
        filename = os.path.basename(target)
        
        logger.debug(f"Attempting to repair link: {broken_link} -> {target}")
        logger.debug(f"Looking for file: {filename}")
        
        # First try to see if the target exists but the path has changed
        if os.path.exists(target):
            logger.info(f"Original target exists but symlink is broken: {target}")
            # Remove and recreate the symlink
            os.unlink(broken_link)
            os.symlink(target, broken_link)
            logger.info(f"Repaired symlink: {broken_link} -> {target}")
            self.links_repaired += 1
            return True
        
        # Search for the file in the provided directories
        for directory in search_directories:
            if not os.path.exists(directory):
                logger.warning(f"Search directory does not exist: {directory}")
                continue
                
            for root, _, files in os.walk(directory):
                for file in files:
                    if file == filename:
                        new_target = os.path.join(root, file)
                        
                        # Verify it's the same file (size check)
                        if os.path.exists(new_target):
                            logger.info(f"Found potential replacement: {new_target}")
                            
                            # Remove the broken link and create a new one
                            os.unlink(broken_link)
                            
                            # Create either relative or absolute symlink based on config
                            if os.environ.get('RELATIVE_SYMLINK', 'false').lower() == 'true':
                                # Calculate relative path
                                link_dir = os.path.dirname(broken_link)
                                rel_path = os.path.relpath(new_target, link_dir)
                                os.symlink(rel_path, broken_link)
                                logger.info(f"Created relative symlink: {broken_link} -> {rel_path}")
                            else:
                                # Create absolute symlink
                                os.symlink(new_target, broken_link)
                                logger.info(f"Created absolute symlink: {broken_link} -> {new_target}")
                            
                            self.links_repaired += 1
                            return True
        
        logger.warning(f"Could not find replacement for: {broken_link}")
        self.links_failed += 1
        return False
    
    def repair_all(self, search_directories: List[str]) -> Dict[str, int]:
        """
        Attempt to repair all broken symlinks found by the scanner.
        
        Args:
            search_directories: List of directories to search for the target files
            
        Returns:
            Dictionary with repair statistics
        """
        if not self.broken_links:
            self.scan_for_broken_links()
        
        total_links = len(self.broken_links)
        if total_links == 0:
            logger.info("No broken symlinks found to repair")
            return {
                "total": 0,
                "repaired": 0,
                "failed": 0
            }
        
        logger.info(f"Attempting to repair {total_links} broken symlinks")
        
        # Reset counters
        self.links_repaired = 0
        self.links_failed = 0
        
        # Try to repair each link
        for link in self.broken_links:
            self.attempt_repair(link, search_directories)
        
        # Log summary
        logger.info(f"Symlink repair summary: {self.links_repaired} repaired, {self.links_failed} failed")
        
        return {
            "total": total_links,
            "repaired": self.links_repaired,
            "failed": self.links_failed
        }