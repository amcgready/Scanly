"""
Utility functions for working with rclone mounts.

This module provides functions for verifying that rclone mounts
are properly mounted and available before proceeding with operations.
"""

import os
import time
from pathlib import Path

from src.config import RCLONE_MOUNT, MOUNT_CHECK_INTERVAL, ORIGIN_DIRECTORY, DESTINATION_DIRECTORY
from src.utils.logger import get_logger

logger = get_logger(__name__)


def is_mount_available(path: str) -> bool:
    """
    Check if a mount point is available.
    
    Args:
        path: Path to check
        
    Returns:
        True if the path is available, False otherwise
    """
    if not os.path.exists(path):
        return False
    
    # Try to list directory contents as a basic check
    try:
        next(os.scandir(path), None)
        return True
    except PermissionError:
        logger.error(f"Permission denied when checking mount: {path}")
        return False
    except OSError as e:
        logger.error(f"Error checking mount {path}: {e}")
        return False


def wait_for_mounts() -> bool:
    """
    Wait for all required mount points to be available.
    
    Returns:
        True if all mount points are available, False otherwise
    """
    if not RCLONE_MOUNT:
        return True
    
    paths_to_check = [
        Path(ORIGIN_DIRECTORY),
        Path(DESTINATION_DIRECTORY)
    ]
    
    # Remove any invalid paths
    paths_to_check = [p for p in paths_to_check if p.as_posix() != '/']
    
    if not paths_to_check:
        return True
    
    logger.info("Checking rclone mount points...")
    attempts = 0
    max_attempts = 10  # Limit the number of attempts
    
    while attempts < max_attempts:
        all_available = True
        
        for path in paths_to_check:
            if not is_mount_available(str(path)):
                all_available = False
                logger.warning(f"Mount point not available: {path}")
            else:
                logger.debug(f"Mount point available: {path}")
        
        if all_available:
            logger.info("All mount points are available")
            return True
        
        attempts += 1
        logger.info(f"Waiting for mount points... (attempt {attempts}/{max_attempts})")
        time.sleep(MOUNT_CHECK_INTERVAL)
    
    logger.error("Timed out waiting for mount points")
    return False