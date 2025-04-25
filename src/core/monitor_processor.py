"""
Monitor processor for handling newly detected files in monitored directories.

This module processes files detected by the monitor_manager.
"""

import os
import sys
import logging
import time
import re
from pathlib import Path

# Fix import path issues - add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from src.main import DirectoryProcessor, get_logger
except ImportError:
    # Define fallback if imports fail
    import logging
    def get_logger(name):
        return logging.getLogger(name)
    
    # Create a stub DirectoryProcessor class
    class DirectoryProcessor:
        def __init__(self, directory_path, resume=False, auto_mode=False):
            self.directory_path = directory_path
            self.resume = resume
            self.auto_mode = auto_mode
            self.media_files = []
            self.total_files = 0
            self.processed_files = 0
            self.errors = 0
            self.skipped = 0
            self.subfolder_files = {}
            
        def _process_media_files(self):
            pass

class MonitorProcessor:
    """Process files detected by the directory monitor."""
    
    def __init__(self, auto_mode=False):
        """
        Initialize the monitor processor.
        
        Args:
            auto_mode: Whether to process files automatically without user interaction
        """
        self.logger = get_logger(__name__)
        self.auto_mode = auto_mode
        
    def process_new_files(self, directory_path, file_paths):
        """
        Process newly detected files in a monitored directory.
        
        Args:
            directory_path: Path to the directory to monitor
            file_paths: List of new file paths detected
        
        Returns:
            Tuple of (processed_count, error_count, skipped_count)
        """
        if not file_paths:
            self.logger.info(f"No new files to process in {directory_path}")
            return 0, 0, 0
            
        self.logger.info(f"Processing {len(file_paths)} new files in {directory_path}")
        
        # Filter for only media files
        media_extensions = ['.mkv', '.mp4', '.avi', '.mov', '.wmv', '.flv', '.m4v', '.ts']
        media_files = [f for f in file_paths if any(f.lower().endswith(ext) for ext in media_extensions)]
        
        if not media_files:
            self.logger.info("No media files found among new files")
            return 0, 0, 0
            
        # Group files by subfolder for better processing
        subfolder_files = {}
        for file_path in media_files:
            subfolder = os.path.dirname(file_path)
            if subfolder not in subfolder_files:
                subfolder_files[subfolder] = []
            subfolder_files[subfolder].append(file_path)
        
        total_processed = 0
        total_errors = 0
        total_skipped = 0
        
        try:
            # Import the load_skipped_items and save_skipped_items functions from main
            from src.main import load_skipped_items, save_skipped_items
            skipped_items_registry = load_skipped_items()
        except ImportError:
            skipped_items_registry = []
            self.logger.warning("Could not import skipped items functions, skipped items may not be saved properly")
        
        # Process each subfolder with the DirectoryProcessor
        for subfolder, files in subfolder_files.items():
            self.logger.info(f"Processing subfolder: {subfolder}")
            
            # Check if the folder name contains a TMDB ID
            subfolder_name = os.path.basename(subfolder)
            tmdb_id = None
            
            # Look for TMDB ID in folder name - format: "Title (Year) [TMDB_ID]"
            tmdb_id_match = re.search(r'\[(\d+)\]', subfolder_name)
            if tmdb_id_match:
                tmdb_id = tmdb_id_match.group(1)
                self.logger.info(f"Found TMDB ID in folder name: {tmdb_id}")
            
            try:
                # Create a temporary DirectoryProcessor for this subfolder
                processor = DirectoryProcessor(subfolder, resume=False, auto_mode=self.auto_mode)
                
                # Override the processor's media_files with just the new files
                processor.media_files = files
                processor.total_files = len(files)
                processor.processed_files = 0
                processor.subfolder_files = {subfolder: files}
                
                # If the folder has a TMDB ID, we'll need to set it in the processor somehow
                # This will depend on how the DirectoryProcessor handles existing IDs
                
                # Process the media files in this subfolder - use existing DirectoryProcessor logic
                # The process will handle skipping files properly since we're using the main DirectoryProcessor
                processor._process_media_files()
                
                # Update counts
                total_processed += processor.processed_files
                total_errors += processor.errors
                total_skipped += processor.skipped
                
                # Log the results
                self.logger.info(f"Processed {processor.processed_files} files in {subfolder}")
                if processor.errors > 0:
                    self.logger.warning(f"Encountered {processor.errors} errors in {subfolder}")
                if processor.skipped > 0:
                    self.logger.info(f"Skipped {processor.skipped} files in {subfolder}")
                
            except Exception as e:
                self.logger.error(f"Error processing subfolder {subfolder}: {e}", exc_info=True)
                # Add files to skipped items registry when there's an error
                for file_path in files:
                    try:
                        # Create a skipped item entry similar to what DirectoryProcessor would create
                        skipped_item = {
                            'path': file_path,
                            'subfolder': subfolder,
                            'suggested_name': os.path.basename(file_path),
                            'is_tv': False,  # Default to movie if we can't determine
                            'is_anime': False
                        }
                        skipped_items_registry.append(skipped_item)
                    except Exception as inner_e:
                        self.logger.error(f"Error adding file to skipped items: {inner_e}")
                
                total_errors += len(files)
        
        # Save updated skipped items
        try:
            save_skipped_items(skipped_items_registry)
        except Exception as e:
            self.logger.error(f"Error saving skipped items: {e}")
        
        return total_processed, total_errors, total_skipped

# For direct testing
if __name__ == "__main__":
    # Setup basic logging
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Test the processor
    processor = MonitorProcessor(auto_mode=False)
    print("Monitor processor initialized")