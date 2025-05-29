#!/usr/bin/env python3
"""
Threaded processing module for Scanly.

This module provides multi-threaded media file scanning and processing capabilities,
allowing Scanly to process multiple directories simultaneously for improved performance.
It also optimizes scanner list matching, which is typically the slowest operation.
"""
import os
import sys
import logging
import threading
import queue
import time
import re
import difflib
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable, Tuple, Set

# Ensure parent directory is in path for imports
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

# Import necessary modules from parent package
from src.main import DirectoryProcessor, get_logger, _clean_directory_path
from src.main import load_skipped_items, save_skipped_items

# Global scanner list cache - thread-safe via lock
_scanner_cache = {}
_scanner_cache_lock = threading.Lock()

class ScannerCache:
    """Thread-safe cache for scanner lists to avoid repeated file reads."""
    
    @staticmethod
    def get_scanner_list(scanner_file: str) -> List[Dict[str, Any]]:
        """Get a scanner list from cache or read from file.
        
        Args:
            scanner_file: Name of the scanner file (e.g., "movies.txt")
            
        Returns:
            List of entries from the scanner file
        """
        global _scanner_cache, _scanner_cache_lock
        
        with _scanner_cache_lock:
            if scanner_file in _scanner_cache:
                return _scanner_cache[scanner_file]
        
        # Scanner not in cache, load it
        logger = get_logger(__name__)
        scanners_dir = os.path.join(os.path.dirname(os.path.dirname(parent_dir)), 'scanners')
        scanner_path = os.path.join(scanners_dir, scanner_file)
        
        if not os.path.exists(scanner_path):
            logger.warning(f"Scanner file not found: {scanner_path}")
            with _scanner_cache_lock:
                _scanner_cache[scanner_file] = []
            return []
        
        entries = []
        try:
            with open(scanner_path, 'r', encoding='utf-8') as file:
                for line in file:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue  # Skip empty lines and comments
                    
                    # Parse the line (format: "Title (Year)" or just "Title")
                    match = re.match(r'(.+?)(?:\s+\((\d{4})\))?(?:\s+\[tmdb-(\d+)\])?$', line)
                    if not match:
                        continue
                    
                    scan_title = match.group(1).strip()
                    scan_year = match.group(2) if match and len(match.groups()) > 1 else None
                    tmdb_id = match.group(3) if match and len(match.groups()) > 2 else None
                    
                    entries.append({
                        'title': scan_title,
                        'year': scan_year,
                        'tmdb_id': tmdb_id,
                        'source': scanner_file
                    })
            
            # Store in cache
            with _scanner_cache_lock:
                _scanner_cache[scanner_file] = entries
            
            logger.info(f"Loaded {len(entries)} entries from scanner file: {scanner_file}")
            return entries
            
        except Exception as e:
            logger.error(f"Error reading scanner file {scanner_path}: {e}")
            with _scanner_cache_lock:
                _scanner_cache[scanner_file] = []
            return []
    
    @staticmethod
    def clear_cache():
        """Clear the scanner cache."""
        global _scanner_cache, _scanner_cache_lock
        with _scanner_cache_lock:
            _scanner_cache.clear()


class ScannerMatcherThread(threading.Thread):
    """Thread to match titles against scanner lists in parallel.
    
    This accelerates the slowest part of the processing pipeline.
    """
    
    def __init__(self, task_queue, result_queue):
        """Initialize the scanner matcher thread.
        
        Args:
            task_queue: Queue containing titles to match
            result_queue: Queue to store matching results
        """
        super().__init__()
        self.task_queue = task_queue
        self.result_queue = result_queue
        self.daemon = True  # Thread will exit when main program exits
        self.logger = get_logger(__name__ + '.scanner_matcher')
        self._stop_event = threading.Event()
    
    def stop(self):
        """Signal the thread to stop."""
        self._stop_event.set()
    
    def stopped(self):
        """Check if the thread has been signaled to stop."""
        return self._stop_event.is_set()
    
    def _is_title_match(self, title1, title2):
        """Compare two titles to determine if they match.
        
        Uses several normalization techniques to improve matching:
        - Convert to lowercase
        - Remove punctuation
        - Normalize whitespace
        
        Args:
            title1: First title
            title2: Second title
            
        Returns:
            True if titles match, False otherwise
        """
        # Normalize both titles
        def normalize(title):
            # Convert to lowercase
            title = title.lower()
            # Remove punctuation
            title = re.sub(r'[^\w\s]', '', title)
            # Normalize whitespace
            title = re.sub(r'\s+', ' ', title).strip()
            return title
        
        norm1 = normalize(title1)
        norm2 = normalize(title2)
        
        # Check for exact match after normalization
        if norm1 == norm2:
            return True
        
        # Check for substring match (one title contained in another)
        if norm1 in norm2 or norm2 in norm1:
            return True
        
        # Calculate similarity score
        similarity = difflib.SequenceMatcher(None, norm1, norm2).ratio()
        # Return True if similarity is above threshold
        return similarity > 0.8
    
    def run(self):
        """Main thread execution loop."""
        while not self.stopped():
            try:
                # Get title from queue with timeout to allow checking stop flag
                try:
                    task = self.task_queue.get(timeout=0.5)
                except queue.Empty:
                    continue
                
                # Process the task
                try:
                    title = task['title']
                    year = task.get('year')
                    is_tv = task.get('is_tv', False)
                    is_anime = task.get('is_anime', False)
                    task_id = task.get('id')
                    
                    # Determine which scanner list to use
                    if is_anime and is_tv:
                        scanner_file = "anime_series.txt"
                    elif is_anime and not is_tv:
                        scanner_file = "anime_movies.txt"
                    elif is_tv and not is_anime:
                        scanner_file = "tv_series.txt"
                    else:
                        scanner_file = "movies.txt"
                    
                    # Get scanner list from cache
                    scanner_entries = ScannerCache.get_scanner_list(scanner_file)
                    
                    matches = []
                    for entry in scanner_entries:
                        scan_title = entry['title']
                        scan_year = entry['year']
                        
                        # Skip entries where year doesn't match (if specified)
                        if year and scan_year and year != scan_year:
                            continue
                            
                        # Check title match
                        if self._is_title_match(title, scan_title):
                            matches.append(entry)
                    
                    # Put results in result queue
                    self.result_queue.put({
                        'id': task_id,
                        'title': title,
                        'year': year,
                        'matches': matches,
                        'scanner_file': scanner_file
                    })
                    
                except Exception as e:
                    self.logger.error(f"Error matching title '{task.get('title', 'Unknown')}': {e}")
                    self.result_queue.put({
                        'id': task.get('id'),
                        'title': task.get('title', 'Unknown'),
                        'error': str(e),
                        'matches': []
                    })
                
                # Mark task as done
                self.task_queue.task_done()
                
            except Exception as e:
                self.logger.error(f"Scanner matcher thread error: {e}")


class EnhancedDirectoryProcessor(DirectoryProcessor):
    """Enhanced directory processor with multi-threaded scanner matching."""
    
    def __init__(self, directory_path, scanner_matcher_pool, resume=False, auto_mode=False):
        """Initialize the enhanced directory processor.
        
        Args:
            directory_path: Path to the directory to process
            scanner_matcher_pool: Pool of scanner matcher threads
            resume: Whether this is resuming a previous scan
            auto_mode: Whether to run in automatic mode
        """
        super().__init__(directory_path, resume, auto_mode)
        self.scanner_matcher_pool = scanner_matcher_pool
    
    def _check_scanner_lists(self, title, year=None, is_tv=False, is_anime=False):
        """Check scanner lists using the thread pool.
        
        Args:
            title: Title to check
            year: Year to check (optional)
            is_tv: Whether the content is a TV series
            is_anime: Whether the content is anime
            
        Returns:
            List of matching entries
        """
        # This enhanced version uses the scanner matcher pool
        # to perform the matching in parallel
        task_id = f"{title}_{year}_{is_tv}_{is_anime}_{time.time()}"
        
        # Create task
        task = {
            'id': task_id,
            'title': title,
            'year': year,
            'is_tv': is_tv,
            'is_anime': is_anime
        }
        
        # Submit task to pool
        self.scanner_matcher_pool.add_task(task)
        
        # Wait for result
        result = self.scanner_matcher_pool.get_result(task_id)
        
        if result:
            matches = result.get('matches', [])
            self.logger.info(f"Found {len(matches)} matches for '{title}' in {result.get('scanner_file', 'unknown')}")
            return matches
            
        return []


class ScannerMatcherPool:
    """Pool of scanner matcher threads for parallel matching."""
    
    def __init__(self, num_threads=4):
        """Initialize the scanner matcher pool.
        
        Args:
            num_threads: Number of matcher threads to create
        """
        self.task_queue = queue.Queue()
        self.result_queue = queue.Queue()
        self.result_map = {}  # Map task IDs to results
        self.result_map_lock = threading.Lock()
        self.logger = get_logger(__name__ + '.scanner_matcher_pool')
        
        # Create and start threads
        self.threads = []
        for _ in range(num_threads):
            thread = ScannerMatcherThread(self.task_queue, self.result_queue)
            thread.start()
            self.threads.append(thread)
            
        # Start result collector thread
        self.collector_thread = threading.Thread(target=self._collect_results, daemon=True)
        self.collector_thread.start()
    
    def _collect_results(self):
        """Collect results from matcher threads."""
        while True:
            try:
                result = self.result_queue.get(timeout=0.5)
                task_id = result.get('id')
                
                with self.result_map_lock:
                    self.result_map[task_id] = result
                
                self.result_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"Error collecting results: {e}")
    
    def add_task(self, task):
        """Add a task to the pool.
        
        Args:
            task: Dictionary containing task information
        """
        self.task_queue.put(task)
    
    def get_result(self, task_id, timeout=30):
        """Get the result for a specific task.
        
        Args:
            task_id: ID of the task
            timeout: Maximum time to wait for result (seconds)
            
        Returns:
            Result dictionary or None if timeout
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            with self.result_map_lock:
                if task_id in self.result_map:
                    return self.result_map.pop(task_id)
            time.sleep(0.1)
        
        self.logger.warning(f"Timeout waiting for result of task {task_id}")
        return None
    
    def shutdown(self):
        """Shut down the pool."""
        # Stop all matcher threads
        for thread in self.threads:
            thread.stop()
        
        # Clear resources
        with self.result_map_lock:
            self.result_map.clear()


class DirectoryWorkerThread(threading.Thread):
    """Worker thread that processes directories."""
    
    def __init__(self, task_queue, result_queue, scanner_matcher_pool, skipped_items_registry, auto_mode=False):
        """Initialize the directory worker thread.
        
        Args:
            task_queue: Queue containing directories to process
            result_queue: Queue to store processing results
            scanner_matcher_pool: Pool of scanner matcher threads
            skipped_items_registry: Global registry of skipped items
            auto_mode: Whether to run in automatic mode
        """
        super().__init__()
        self.task_queue = task_queue
        self.result_queue = result_queue
        self.scanner_matcher_pool = scanner_matcher_pool
        self.skipped_items_registry = skipped_items_registry
        self.auto_mode = auto_mode
        self.daemon = True
        self.logger = get_logger(__name__ + '.directory_worker')
        self._stop_event = threading.Event()
    
    def stop(self):
        """Signal the thread to stop."""
        self._stop_event.set()
    
    def stopped(self):
        """Check if the thread has been signaled to stop."""
        return self._stop_event.is_set()
    
    def run(self):
        """Main thread execution loop."""
        while not self.stopped():
            try:
                # Get directory from queue with timeout
                try:
                    directory_info = self.task_queue.get(timeout=0.5)
                except queue.Empty:
                    continue
                
                # Process the directory
                try:
                    directory_path = directory_info.get('path')
                    self.logger.info(f"Thread {self.name} processing: {directory_path}")
                    
                    # Create enhanced processor instance with scanner matcher pool
                    processor = EnhancedDirectoryProcessor(
                        directory_path, 
                        self.scanner_matcher_pool,
                        resume=directory_info.get('resume', False),
                        auto_mode=self.auto_mode
                    )
                    
                    # Process files
                    result = processor._process_media_files()
                    
                    # Store the result
                    self.result_queue.put({
                        'path': directory_path,
                        'result': result,
                        'success': result >= 0,  # -1 indicates error
                        'type': 'directory_result'
                    })
                    
                except Exception as e:
                    self.logger.error(f"Error processing directory {directory_info.get('path')}: {e}")
                    self.result_queue.put({
                        'path': directory_info.get('path'),
                        'result': -1,
                        'error': str(e),
                        'success': False,
                        'type': 'directory_result'
                    })
                
                # Mark task as done
                self.task_queue.task_done()
                
            except Exception as e:
                self.logger.error(f"Directory worker thread error: {e}")


class ThreadedDirectoryProcessor:
    """Process multiple directories using thread pool with optimized scanner matching."""
    
    def __init__(self, num_directory_workers=4, num_scanner_workers=4, auto_mode=False):
        """Initialize the threaded directory processor.
        
        Args:
            num_directory_workers: Number of directory worker threads
            num_scanner_workers: Number of scanner matcher threads  
            auto_mode: Whether to run in automatic mode
        """
        self.logger = get_logger(__name__ + '.manager')
        self.auto_mode = auto_mode
        
        # Determine number of workers if not specified
        if num_directory_workers is None or num_scanner_workers is None:
            import multiprocessing
            cpu_count = multiprocessing.cpu_count()
            if num_directory_workers is None:
                num_directory_workers = max(2, cpu_count // 2)
            if num_scanner_workers is None:
                num_scanner_workers = max(2, cpu_count // 2)
        
        self.num_directory_workers = num_directory_workers
        self.num_scanner_workers = num_scanner_workers
        
        # Create queues
        self.directory_task_queue = queue.Queue()
        self.result_queue = queue.Queue()
        
        # Initialize scanner matcher pool
        self.scanner_matcher_pool = ScannerMatcherPool(num_scanner_workers)
        
        # Load skipped items
        self.skipped_items_registry = load_skipped_items() or []
        
        # Create directory worker threads
        self.directory_workers = []
        
        self.logger.info(f"Initialized processor with {num_directory_workers} directory workers "
                         f"and {num_scanner_workers} scanner matcher workers")
    
    def _start_workers(self):
        """Start directory worker threads."""
        for _ in range(self.num_directory_workers):
            worker = DirectoryWorkerThread(
                self.directory_task_queue,
                self.result_queue,
                self.scanner_matcher_pool,
                self.skipped_items_registry,
                self.auto_mode
            )
            worker.start()
            self.directory_workers.append(worker)
        
        self.logger.info(f"Started {len(self.directory_workers)} directory worker threads")
    
    def _stop_workers(self):
        """Stop all worker threads."""
        for worker in self.directory_workers:
            worker.stop()
            
        # Shutdown scanner matcher pool
        self.scanner_matcher_pool.shutdown()
        
        self.logger.info("Stopped all worker threads")
    
    def add_directory(self, directory_path, resume=False):
        """Add a directory to the processing queue.
        
        Args:
            directory_path: Path to the directory to process
            resume: Whether this is resuming a previous scan
        """
        self.directory_task_queue.put({
            'path': directory_path,
            'resume': resume
        })
        self.logger.info(f"Added directory to processing queue: {directory_path}")
    
    def add_directories(self, directory_paths, resume=False):
        """Add multiple directories to the processing queue.
        
        Args:
            directory_paths: List of directory paths to process
            resume: Whether this is resuming previous scans
        """
        for path in directory_paths:
            self.add_directory(path, resume)
        self.logger.info(f"Added {len(directory_paths)} directories to processing queue")
    
    def process_directories(self, 
                           progress_callback=None,
                           completion_callback=None):
        """Process all directories in the queue.
        
        Args:
            progress_callback: Callback function for progress updates
            completion_callback: Callback function called when all processing is complete
            
        Returns:
            List of result dictionaries with processing outcomes
        """
        results = []
        total_tasks = self.directory_task_queue.qsize()
        
        if total_tasks == 0:
            self.logger.warning("No directories to process")
            return []
        
        try:
            # Start worker threads
            self._start_workers()
            
            # Monitor progress
            processed_count = 0
            
            while True:
                # Check if we're done
                if processed_count >= total_tasks and self.result_queue.empty():
                    break
                
                # Check for results
                try:
                    result = self.result_queue.get(timeout=0.5)
                    
                    # Only count directory results toward completion
                    if result.get('type') == 'directory_result':
                        results.append(result)
                        processed_count += 1
                        
                        # Call progress callback if provided
                        if progress_callback:
                            progress_data = {
                                'processed': processed_count,
                                'total': total_tasks,
                                'percentage': int((processed_count / total_tasks) * 100),
                                'current_result': result
                            }
                            progress_callback(progress_data)
                    
                    self.result_queue.task_done()
                except queue.Empty:
                    # No results available yet
                    pass
                    
                # Sleep briefly to avoid CPU hogging
                time.sleep(0.1)
            
            # Wait for all tasks to complete
            self.directory_task_queue.join()
            
            # Call completion callback if provided
            if completion_callback:
                completion_callback(results)
            
            return results
            
        finally:
            # Stop worker threads
            self._stop_workers()
            
            # Clear scanner cache to free memory
            ScannerCache.clear_cache()
    
    def get_progress(self):
        """Get current progress information.
        
        Returns:
            Dictionary with progress information
        """
        total = self.directory_task_queue.qsize() + sum(1 for r in self.directory_workers if r.is_alive())
        processed = len(self.directory_workers) - sum(1 for r in self.directory_workers if r.is_alive())
        
        return {
            'processed': processed,
            'total': total,
            'percentage': int((processed / total) * 100) if total > 0 else 100
        }


# Helper function for console progress reporting
def console_progress_reporter(progress_data):
    """Print progress information to console.
    
    Args:
        progress_data: Dictionary with progress information
    """
    path = progress_data.get('current_result', {}).get('path', 'Unknown')
    success = progress_data.get('current_result', {}).get('success', False)
    status = "✓" if success else "✗"
    
    print(f"[{progress_data['processed']}/{progress_data['total']}] "
          f"({progress_data['percentage']}%) {status} {os.path.basename(path)}")


# Main function to process directories with threading
def process_directories_with_threading(directories, 
                                     directory_workers=None, 
                                     scanner_workers=None, 
                                     auto_mode=False):
    """Process multiple directories with multi-threading.
    
    Args:
        directories: List of directory paths to process
        directory_workers: Number of directory worker threads
        scanner_workers: Number of scanner matcher threads
        auto_mode: Whether to run in automatic mode
        
    Returns:
        List of result dictionaries
    """
    # Use system CPU count to determine thread counts if not specified
    if directory_workers is None or scanner_workers is None:
        import multiprocessing
        cpu_count = multiprocessing.cpu_count()
        
        if directory_workers is None:
            directory_workers = max(2, cpu_count // 2)
        if scanner_workers is None: 
            scanner_workers = max(2, cpu_count // 2)
    
    processor = ThreadedDirectoryProcessor(
        num_directory_workers=directory_workers,
        num_scanner_workers=scanner_workers,
        auto_mode=auto_mode
    )
    
    # Add directories to process
    processor.add_directories([d for d in directories if os.path.isdir(d)])
    
    print(f"Starting parallel processing with {directory_workers} directory workers "
          f"and {scanner_workers} scanner workers")
    print("=" * 60)
    
    # Process directories with progress reporting
    results = processor.process_directories(progress_callback=console_progress_reporter)
    
    print("=" * 60)
    print(f"Processing complete. Processed {len(results)} directories.")
    
    # Print summary
    successful = sum(1 for r in results if r.get('success', False))
    print(f"Successful: {successful}")
    print(f"Failed: {len(results) - successful}")
    
    return results


# Function to perform multi-scan from command line
def perform_multi_scan():
    """Perform a multi-scan operation using the threaded processor."""
    clear_screen()
    display_ascii_art()
    print("=" * 60)
    print("MULTI SCAN")
    print("=" * 60)
    
    # Get directories to scan
    print("\nEnter directories to scan, one per line.")
    print("Press Enter on a blank line when done.")
    
    directories = []
    while True:
        directory = input(f"\nEnter directory path #{len(directories) + 1} (or Enter to finish): ").strip()
        if not directory:
            break
        
        directory = _clean_directory_path(directory)
        if os.path.isdir(directory):
            directories.append(directory)
        else:
            print(f"Invalid directory path: {directory}")
    
    if not directories:
        print("\nNo valid directories provided.")
        input("\nPress Enter to continue...")
        return
    
    # Ask for number of threads
    directory_workers = input("\nEnter number of directory worker threads (or Enter for auto): ").strip()
    if directory_workers and directory_workers.isdigit():
        directory_workers = int(directory_workers)
    else:
        directory_workers = None  # Auto-determine
    
    scanner_workers = input("Enter number of scanner worker threads (or Enter for auto): ").strip()
    if scanner_workers and scanner_workers.isdigit():
        scanner_workers = int(scanner_workers) 
    else:
        scanner_workers = None  # Auto-determine
    
    # Ask for auto mode
    auto_mode = input("\nEnable auto mode? Skip user input for each file. (y/n): ").strip().lower() == 'y'
    
    try:
        # Process directories with threading
        print(f"\nStarting multi-scan with {len(directories)} directories...")
        results = process_directories_with_threading(
            directories, 
            directory_workers=directory_workers,
            scanner_workers=scanner_workers,
            auto_mode=auto_mode
        )
        
    except Exception as e:
        print(f"\nError during multi-scan: {e}")
    
    input("\nPress Enter to continue...")


# Import necessary functions for the module when called from main.py
def clear_screen():
    """Clear the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')


def display_ascii_art():
    """Display the program's ASCII art."""
    try:
        art_path = os.path.join(os.path.dirname(os.path.dirname(parent_dir)), 'art.txt')
        if os.path.exists(art_path):
            with open(art_path, 'r') as f:
                print(f.read())
        else:
            print("\nSCANLY")
    except Exception:
        print("SCANLY")  # Fallback if art file can't be loaded


# Modify the main() function in main.py to handle the Multi Scan option
def update_main_function():
    """Add this function to main.py to integrate the multi-scan functionality."""
    # Add to main.py in the main() function where it handles choice == "2":
    # Can be a code example to follow
    """
    elif choice == "2":
        # Multi Scan
        try:
            from src.core.threaded_processor import perform_multi_scan
            perform_multi_scan()
        except ImportError as e:
            print(f"\nError importing threaded processor: {e}")
            input("\nPress Enter to continue...")
    """