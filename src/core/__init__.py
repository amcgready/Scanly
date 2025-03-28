"""
Core module for Scanly.

This module contains the main functionality for monitoring,
processing files, and creating symlinks.
"""

from .file_monitor import FileMonitor
from .file_processor import FileProcessor, MovieProcessor, TVProcessor
from .symlink_creator import SymlinkCreator