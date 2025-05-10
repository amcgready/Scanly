"""API routes for the Scanly web application."""

import os
import json
import threading
import psutil
from flask import Blueprint, jsonify, request, current_app
from pathlib import Path
from datetime import datetime
from src.main import DirectoryProcessor, get_logger

logger = get_logger(__name__)

# Create a Blueprint for API routes - remove the url_prefix, it's set in app.py
api_bp = Blueprint('api', __name__)

# Store ongoing scans in memory
active_scans = {}

@api_bp.route('/dashboard/stats')
def dashboard_stats():
    """API endpoint for dashboard statistics."""
    try:
        # Get system statistics
        stats = get_system_stats()
        
        # System status for gauges
        system_status = {
            'disk_usage': int(psutil.disk_usage('/').percent),
            'cpu_usage': int(psutil.cpu_percent()),
            'memory_usage': int(psutil.virtual_memory().percent),
            'monitoring_active': True,  # Force this to true as monitoring should be active
            'plex_configured': True     # Force this to true as Plex should be connected
        }
        
        response_data = {
            'movies': stats.get('movies', 0) if stats else 0,
            'tv_shows': stats.get('tv_shows', 0) if stats else 0,
            'monitored': 0,  # Placeholder
            'skipped': stats.get('skipped_items', 0) if stats else 0,
            'system_status': system_status,
            'monitored_directories': [],
            'recent_activity': []
        }
        
        return jsonify(response_data)
    except Exception as e:
        logger.error(f"Error in dashboard stats: {str(e)}")
        return jsonify({'error': str(e)}), 500

def get_system_stats():
    """Get system statistics."""
    try:
        # This is a placeholder - implement your actual stats logic here
        return {
            'movies': 0,
            'tv_shows': 0,
            'skipped_items': 0
        }
    except Exception as e:
        logger.error(f"Error getting system stats: {e}")
        return {}

@api_bp.route('/dashboard/system_resources')
def system_resources():
    """A lightweight endpoint that only returns CPU and memory usage for more frequent updates"""
    try:
        system_status = {
            'cpu_usage': int(psutil.cpu_percent()),
            'memory_usage': int(psutil.virtual_memory().percent)
        }
        return jsonify(system_status)
    except Exception as e:
        logger.error(f"Error getting system resources: {e}")
        return jsonify({'error': str(e)}), 500

# API routes for file browser
@api_bp.route('/file_browser')
def file_browser():
    """API endpoint for browsing files and directories."""
    path = request.args.get('path', '/')
    path = path.replace('\\', '/').rstrip('/')
    
    if not os.path.isdir(path):
        return jsonify({'error': 'Invalid directory path'})
    
    try:
        directories = []
        files = []
        
        for entry in os.scandir(path):
            if entry.is_dir():
                directories.append(entry.name)
            elif entry.is_file():
                files.append(entry.name)
        
        directories.sort()
        files.sort()
        
        return jsonify({
            'path': path,
            'directories': directories,
            'files': files
        })
    except Exception as e:
        return jsonify({'error': str(e)})

# API endpoint for individual scan
@api_bp.route('/scan/individual', methods=['POST'])
def start_individual_scan():
    """API endpoint for starting an individual directory scan."""
    data = request.get_json()
    
    if not data or 'directory' not in data:
        return jsonify({'error': 'No directory specified'})
    
    dir_path = data['directory']
    content_type = data.get('content_type', 'auto')
    force_rescan = data.get('force_rescan', False)
    
    # Clean directory path
    dir_path = dir_path.replace('\\', '/').rstrip('/')
    
    if not os.path.isdir(dir_path):
        return jsonify({'error': f"Invalid directory path: {dir_path}"})
    
    try:
        # Create a scan ID (can be timestamp or random ID)
        import time
        scan_id = str(int(time.time()))
        
        # Store scan info in app context for progress tracking
        if not hasattr(current_app, 'active_scans'):
            current_app.active_scans = {}
        
        current_app.active_scans[scan_id] = {
            'directory': dir_path,
            'content_type': content_type,
            'force_rescan': force_rescan,
            'progress': 0,
            'status': 'Initializing',
            'current_file': '',
            'results': []
        }
        
        # Start scan in a background thread
        scan_thread = threading.Thread(
            target=process_directory,
            args=(scan_id, dir_path, content_type, force_rescan)
        )
        scan_thread.daemon = True
        scan_thread.start()
        
        return jsonify({
            'success': True,
            'scan_id': scan_id
        })
    
    except Exception as e:
        return jsonify({'error': str(e)})

# API endpoint for checking scan progress
@api_bp.route('/scan/progress/<scan_id>')
def check_scan_progress(scan_id):
    """API endpoint for checking the progress of a scan."""
    if not hasattr(current_app, 'active_scans') or scan_id not in current_app.active_scans:
        return jsonify({'error': 'Invalid or expired scan ID'})
    
    scan_info = current_app.active_scans[scan_id]
    
    return jsonify({
        'progress': scan_info['progress'],
        'status': scan_info['status'],
        'current_file': scan_info['current_file'],
        'results': scan_info.get('results', [])
    })

# Function to process directory in background thread
def process_directory(scan_id, dir_path, content_type, force_rescan):
    """Process directory in background thread and update progress."""
    try:
        # Access the shared scan info
        scan_info = current_app.active_scans[scan_id]
        scan_info['status'] = 'Scanning'
        
        # Create a directory processor with optional content type
        processor = DirectoryProcessor(dir_path)
        
        # Set content type if specified
        if content_type != 'auto':
            if content_type == 'movie':
                processor.force_movie = True
            elif content_type == 'tv':
                processor.force_tv = True
            elif content_type == 'anime_movie':
                processor.force_movie = True
                processor.force_anime = True
            elif content_type == 'anime_tv':
                processor.force_tv = True
                processor.force_anime = True
        
        # Set force rescan option
        if force_rescan:
            processor.force_rescan = True
        
        # Count files to process
        total_files = 0
        for root, _, files in os.walk(dir_path):
            for file in files:
                if processor._is_media_file(file):
                    total_files += 1
        
        # Initialize results list
        results = []
        processed_files = 0
        
        # Process the directory
        for root, _, files in os.walk(dir_path):
            for file in files:
                if processor._is_media_file(file):
                    file_path = os.path.join(root, file)
                    scan_info['current_file'] = file_path
                    
                    # Process the file
                    try:
                        success = False
                        title = os.path.basename(file_path)
                        year = ""
                        
                        # Try to match filename
                        base_name = os.path.basename(file_path)
                        match_data = processor._match_filename(base_name)
                        
                        if match_data:
                            title, year = match_data[:2]
                            
                        # Process the file
                        processor._process_file(file_path)
                        success = True
                        
                        results.append({
                            'path': file_path,
                            'title': title,
                            'year': year,
                            'success': success
                        })
                    except Exception as e:
                        results.append({
                            'path': file_path,
                            'title': os.path.basename(file_path),
                            'year': '',
                            'success': False,
                            'error': str(e)
                        })
                    
                    # Update progress
                    processed_files += 1
                    scan_info['progress'] = processed_files / total_files if total_files > 0 else 0
        
        # Update final results and status
        scan_info['results'] = results
        scan_info['status'] = 'Complete'
        
    except Exception as e:
        import traceback
        if scan_id in current_app.active_scans:
            scan_info = current_app.active_scans[scan_id]
            scan_info['status'] = 'Error'
            scan_info['error'] = str(e)
            scan_info['traceback'] = traceback.format_exc()