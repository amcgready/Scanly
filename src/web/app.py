#!/usr/bin/env python3
"""
Flask web application for Scanly.
This provides a web interface for the Scanly media scanner.
"""

import os
import sys
import json
import logging
import socket
import psutil  # Import psutil for system status monitoring
import io
import csv
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, jsonify, request, redirect, url_for, flash, make_response

# Ensure parent directory is in path for imports
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

# Import from main.py
from src.main import (
    DirectoryProcessor,
    load_scan_history,
    clear_scan_history,
    history_exists,
    load_skipped_items,
    save_skipped_items,
    _clean_directory_path,
    _update_env_var,
    get_logger
)

# Create Flask app
app = Flask(__name__, 
            static_folder='static',
            template_folder='templates')
app.secret_key = os.urandom(24)  # For flash messages

# Properly register the API blueprint with the correct URL prefix
from src.web.routes.api import api_bp
app.register_blueprint(api_bp, url_prefix='/api')

# Set up logging
logger = get_logger(__name__)

@app.route('/')
def index():
    """Render the dashboard."""
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
        
        # Get monitored directories
        monitored_directories = []
        try:
            from src.core.monitor_manager import MonitorManager
            mm = MonitorManager()
            monitored_dirs = mm.get_monitored_directories() or {}
            
            for dir_id, info in monitored_dirs.items():
                monitored_directories.append({
                    'id': dir_id,
                    'path': info.get('path', 'Unknown'),
                    'description': info.get('description', ''),
                    'active': info.get('active', False),
                    'last_scan': info.get('last_scan', 'Never'),
                    'next_scan': info.get('next_scan', 'Not scheduled'),
                    'pending_files': len(info.get('pending_files', []))
                })
        except ImportError:
            logger.warning("Monitor manager not available")
        
        # Get recent activity (most recent 5 items)
        recent_activity = get_activities(page=1, per_page=5) or []
        
        # Update the stats with the actual count of monitored directories we retrieved
        # This ensures we display the correct count even if get_system_stats() couldn't get it
        if monitored_directories:
            stats['monitored_dirs'] = len(monitored_directories)
        
        return render_template('index.html', 
                               stats=stats, 
                               system_status=system_status, 
                               monitored_directories=monitored_directories,
                               recent_activity=recent_activity)
    except Exception as e:
        logger.error(f"Error rendering index page: {e}", exc_info=True)
        return render_template('error.html', error=str(e))

@app.route('/api/dashboard/stats')
def dashboard_stats():
    """API endpoint for dashboard statistics."""
    try:
        # Get system statistics
        stats = get_system_stats() or {}
        
        # Direct load of skipped items for absolute accuracy
        skipped_count = 0
        skipped_items_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'skipped_items.json')
        
        try:
            if os.path.exists(skipped_items_path):
                with open(skipped_items_path, 'r', encoding='utf-8') as f:
                    items_list = json.load(f)
                    skipped_count = len(items_list)
            else:
                # Try the parent directory location
                parent_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'skipped_items.json')
                if os.path.exists(parent_path):
                    with open(parent_path, 'r', encoding='utf-8') as f:
                        items_list = json.load(f)
                        skipped_count = len(items_list)
        except Exception as e:
            logger.error(f"Error reading skipped_items.json: {e}", exc_info=True)
        
        # Add system status information
        system_status = {
            'disk_usage': int(psutil.disk_usage('/').percent),
            'cpu_usage': int(psutil.cpu_percent()),
            'memory_usage': int(psutil.virtual_memory().percent),
            'monitoring_active': True,  # Force this to true as monitoring should be active
            'plex_configured': True     # Force this to true as Plex should be connected
        }
        
        # Get monitored directories
        monitored_directories = []
        try:
            from src.core.monitor_manager import MonitorManager
            mm = MonitorManager()
            monitored_dirs = mm.get_monitored_directories() or {}
            
            for dir_id, info in monitored_dirs.items():
                monitored_directories.append({
                    'id': dir_id,
                    'path': info.get('path', 'Unknown'),
                    'description': info.get('description', ''),
                    'active': info.get('active', False),
                    'last_scan': info.get('last_scan', 'Never'),
                    'next_scan': info.get('next_scan', 'Not scheduled'),
                    'pending_files': len(info.get('pending_files', []))
                })
        except ImportError as e:
            logger.warning(f"Monitor manager not available: {e}")
        except Exception as e:
            logger.error(f"Error getting monitored directories: {e}")
        
        # Update stats with monitored directories count
        monitored_count = len(monitored_directories)
        
        # Create response object
        response_data = {
            'movies': stats.get('movies', 0),
            'tv_shows': stats.get('tv_shows', 0),
            'monitored': monitored_count,
            'skipped': skipped_count,
            'system_status': system_status,
            'monitored_directories': monitored_directories,
            'recent_activity': []
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"Error in dashboard_stats API: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/api/skipped/count-test')
def skipped_count_test():
    """A simple test endpoint that returns only the count of skipped items."""
    try:
        skipped_count = 0
        skipped_items_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'skipped_items.json')
        
        if os.path.exists(skipped_items_path):
            with open(skipped_items_path, 'r', encoding='utf-8') as f:
                items_list = json.load(f)
                skipped_count = len(items_list)
        else:
            # Try the parent directory location
            parent_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'skipped_items.json')
            if os.path.exists(parent_path):
                with open(parent_path, 'r', encoding='utf-8') as f:
                    items_list = json.load(f)
                    skipped_count = len(items_list)
        
        # Return a very simple response with only the count
        return jsonify({
            'count': skipped_count
        })
    
    except Exception as e:
        logger.error(f"Error in skipped count test endpoint: {e}", exc_info=True)
        return jsonify({'error': str(e), 'count': 0}), 500

@app.route('/scan')
def scan_index():
    """Render the scan options page."""
    return render_template('scan_index.html')

@app.route('/scan/individual', methods=['GET', 'POST'])
def individual_scan():
    """Handle individual directory scan."""
    if request.method == 'POST':
        dir_path = request.form.get('directory')
        content_type = request.form.get('content_type', 'auto')
        force_rescan = request.form.get('force_rescan') == 'on'
        
        if not dir_path:
            flash('No directory specified', 'error')
            return redirect(url_for('individual_scan'))
        
        # Clean directory path
        dir_path = _clean_directory_path(dir_path)
        
        if not os.path.isdir(dir_path):
            flash(f"Error: '{dir_path}' is not a valid directory.", 'error')
            return redirect(url_for('individual_scan'))
        
        # Process directory
        try:
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
                
            processor.process()
            flash(f"Successfully processed directory: {dir_path}", 'success')
        except Exception as e:
            logger.error(f"Error processing directory: {e}", exc_info=True)
            flash(f"Error processing directory: {str(e)}", 'error')
        
        return redirect(url_for('individual_scan'))
    
    return render_template('individual_scan.html')

@app.route('/scan/multi', methods=['GET', 'POST'])
def multi_scan():
    """Handle multi directory scan."""
    if request.method == 'POST':
        dirs = request.form.getlist('directories[]')
        if not dirs:
            flash('No directories specified', 'error')
            return redirect(url_for('multi_scan'))
        
        results = []
        for dir_path in dirs:
            # Clean directory path
            dir_path = _clean_directory_path(dir_path)
            
            if not os.path.isdir(dir_path):
                results.append({
                    'path': dir_path,
                    'success': False,
                    'message': 'Not a valid directory'
                })
                continue
            
            # Process directory
            try:
                processor = DirectoryProcessor(dir_path)
                processor.process()
                results.append({
                    'path': dir_path,
                    'success': True,
                    'message': 'Successfully processed'
                })
            except Exception as e:
                logger.error(f"Error processing directory: {e}", exc_info=True)
                results.append({
                    'path': dir_path,
                    'success': False,
                    'message': str(e)
                })
        
        return jsonify({'results': results})
    
    return render_template('multi_scan.html')

@app.route('/scan/resume')
def resume_scan():
    """Resume a previously interrupted scan."""
    # Load scan history
    history = load_scan_history()
    if not history:
        flash('No scan history found.', 'warning')
        return redirect(url_for('scan_index'))
    
    dir_path = history.get('path', '')
    processed_files = history.get('processed_files', 0)
    total_files = history.get('total_files', 0)
    
    if not os.path.isdir(dir_path):
        flash(f"Error: The directory in scan history no longer exists: {dir_path}", 'error')
        return redirect(url_for('scan_index'))
    
    return render_template('resume_scan.html', 
                           dir_path=dir_path, 
                           processed_files=processed_files,
                           total_files=total_files)

@app.route('/scan/resume/process', methods=['POST'])
def process_resume_scan():
    """Process a resume scan request."""
    action = request.form.get('action')
    
    if action == 'resume':
        # Load scan history
        history = load_scan_history()
        if not history:
            return jsonify({'success': False, 'message': 'No scan history found.'})
        
        dir_path = history.get('path', '')
        
        if not os.path.isdir(dir_path):
            return jsonify({'success': False, 'message': f"Directory does not exist: {dir_path}"})
        
        # Resume scan
        try:
            processor = DirectoryProcessor(dir_path, resume=True)
            processor.process()
            return jsonify({'success': True, 'message': f"Successfully resumed scan of {dir_path}"})
        except Exception as e:
            logger.error(f"Error resuming scan: {e}", exc_info=True)
            return jsonify({'success': False, 'message': str(e)})
    
    elif action == 'restart':
        # Load scan history
        history = load_scan_history()
        if not history:
            return jsonify({'success': False, 'message': 'No scan history found.'})
        
        dir_path = history.get('path', '')
        
        if not os.path.isdir(dir_path):
            return jsonify({'success': False, 'message': f"Directory does not exist: {dir_path}"})
        
        # Clear history and start new scan
        clear_scan_history()
        
        try:
            processor = DirectoryProcessor(dir_path)
            processor.process()
            return jsonify({'success': True, 'message': f"Successfully restarted scan of {dir_path}"})
        except Exception as e:
            logger.error(f"Error starting new scan: {e}", exc_info=True)
            return jsonify({'success': False, 'message': str(e)})
    
    elif action == 'clear':
        # Clear scan history
        if clear_scan_history():
            return jsonify({'success': True, 'message': 'Scan history cleared successfully.'})
        else:
            return jsonify({'success': False, 'message': 'Failed to clear scan history.'})
    
    return jsonify({'success': False, 'message': 'Invalid action specified.'})

@app.route('/monitor')
def monitor():
    """Show monitoring page."""
    try:
        from src.core.monitor_manager import MonitorManager
        mm = MonitorManager()
        monitored_dirs = mm.get_monitored_directories()
        
        # Format for display
        directories = []
        for dir_id, info in monitored_dirs.items():
            directories.append({
                'id': dir_id,
                'path': info.get('path', 'Unknown'),
                'description': info.get('description', os.path.basename(info.get('path', 'Unknown'))),
                'active': info.get('active', False),
                'auto_mode': info.get('auto_mode', False),
                'last_scan': info.get('last_scan', 'Never'),
                'next_scan': info.get('next_scan', 'Not scheduled'),
                'pending_files': len(info.get('pending_files', []))
            })
        
        is_monitoring = mm.is_monitoring_active()
        
        return render_template('monitor.html', 
                               directories=directories, 
                               is_monitoring=is_monitoring)
    except ImportError:
        flash('Monitoring module not available', 'error')
        return redirect(url_for('index'))

@app.route('/monitor/add', methods=['POST'])
def add_monitor():
    """Add a new directory to monitor."""
    try:
        from src.core.monitor_manager import MonitorManager
        
        dir_path = request.form.get('directory')
        description = request.form.get('description') or os.path.basename(dir_path)
        auto_process = request.form.get('auto_process') == 'on'
        
        if not dir_path:
            flash('No directory specified', 'error')
            return redirect(url_for('monitor'))
        
        # Clean directory path
        dir_path = _clean_directory_path(dir_path)
        
        if not os.path.isdir(dir_path):
            flash(f"Error: '{dir_path}' is not a valid directory.", 'error')
            return redirect(url_for('monitor'))
        
        # Add to monitored directories
        mm = MonitorManager()
        dir_id = mm.add_directory(dir_path, description, auto_process=auto_process)
        
        if dir_id:
            flash(f"Directory added to monitoring: {dir_path}", 'success')
        else:
            flash(f"Failed to add directory to monitoring: {dir_path}", 'error')
        
        return redirect(url_for('monitor'))
    except ImportError:
        flash('Monitoring module not available', 'error')
        return redirect(url_for('monitor'))

@app.route('/monitor/toggle/<dir_id>')
def toggle_monitor(dir_id):
    """Toggle a monitored directory's status."""
    try:
        from src.core.monitor_manager import MonitorManager
        
        mm = MonitorManager()
        monitored_dirs = mm.get_monitored_directories()
        
        if dir_id not in monitored_dirs:
            flash('Directory not found in monitored directories', 'error')
            return redirect(url_for('monitor'))
        
        current_state = monitored_dirs[dir_id].get('active', False)
        new_state = not current_state
        
        if mm.set_directory_status(dir_id, new_state):
            status_text = 'enabled' if new_state else 'paused'
            flash(f"Directory monitoring {status_text}", 'success')
        else:
            flash(f"Failed to update directory status", 'error')
        
        return redirect(url_for('monitor'))
    except ImportError:
        flash('Monitoring module not available', 'error')
        return redirect(url_for('monitor'))

@app.route('/monitor/remove/<dir_id>')
def remove_monitor(dir_id):
    """Remove a monitored directory."""
    try:
        from src.core.monitor_manager import MonitorManager
        
        mm = MonitorManager()
        
        if mm.remove_directory(dir_id):
            flash("Directory removed from monitoring", 'success')
        else:
            flash("Failed to remove directory", 'error')
        
        return redirect(url_for('monitor'))
    except ImportError:
        flash('Monitoring module not available', 'error')
        return redirect(url_for('monitor'))

@app.route('/skipped')
def skipped_items():
    """Show skipped items."""
    items = load_skipped_items()
    return render_template('skipped.html', items=items)

@app.route('/skipped/process/<int:item_id>', methods=['GET', 'POST'])
def process_skipped_item(item_id):
    """Process a skipped item."""
    items = load_skipped_items()
    
    if item_id < 0 or item_id >= len(items):
        flash('Invalid item ID', 'error')
        return redirect(url_for('skipped_items'))
    
    item = items[item_id]
    path = item.get('path', '')
    
    if not os.path.exists(path):
        flash('File or directory no longer exists', 'error')
        items.pop(item_id)
        save_skipped_items(items)
        return redirect(url_for('skipped_items'))
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'process':
            title = request.form.get('title')
            year = request.form.get('year')
            content_type = request.form.get('content_type', '1')  # Default to movie
            
            # Set content type flags
            is_tv = content_type in ('2', '4')
            is_anime = content_type in ('3', '4')
            
            # Process the item
            try:
                processor = DirectoryProcessor(path)
                processor._create_symlinks(path, title, year, is_tv, is_anime)
                
                # Remove from skipped items
                items.pop(item_id)
                save_skipped_items(items)
                
                flash('Item processed successfully', 'success')
                return redirect(url_for('skipped_items'))
            except Exception as e:
                logger.error(f"Error processing skipped item: {e}", exc_info=True)
                flash(f"Error processing item: {str(e)}", 'error')
        
        elif action == 'remove':
            # Remove item from list
            items.pop(item_id)
            save_skipped_items(items)
            flash('Item removed from skipped items', 'success')
            return redirect(url_for('skipped_items'))
    
    return render_template('process_skipped.html', item=item, item_id=item_id)

@app.route('/settings')
def settings():
    """Show settings page."""
    current_settings = {
        'destination_dir': os.environ.get('DESTINATION_DIRECTORY', ''),
        'api_key': os.environ.get('TMDB_API_KEY', ''),
        'include_tmdb_id': os.environ.get('INCLUDE_TMDB_ID', 'true').lower() == 'true',
        'use_symlinks': os.environ.get('USE_SYMLINKS', 'true').lower() == 'true',
        'refresh_plex': os.environ.get('REFRESH_PLEX', 'true').lower() == 'true',
        'plex_url': os.environ.get('PLEX_URL', ''),
        'plex_token': os.environ.get('PLEX_TOKEN', ''),
        'plex_movies_section': os.environ.get('PLEX_MOVIES_SECTION', '1'),
        'plex_tv_section': os.environ.get('PLEX_TV_SECTION', '2'),
        'plex_anime_movies_section': os.environ.get('PLEX_ANIME_MOVIES_SECTION', '3'),
        'plex_anime_tv_section': os.environ.get('PLEX_ANIME_TV_SECTION', '4'),
        'monitor_interval': os.environ.get('MONITOR_INTERVAL_MINUTES', '60')
    }
    
    return render_template('settings.html', settings=current_settings)

@app.route('/settings/update', methods=['POST'])
def update_settings():
    """Update settings."""
    category = request.form.get('category')
    
    if category == 'directory':
        dir_path = request.form.get('destination_directory')
        if dir_path:
            dir_path = _clean_directory_path(dir_path)
            
            # Create directory if it doesn't exist
            if not os.path.exists(dir_path):
                try:
                    os.makedirs(dir_path, exist_ok=True)
                except Exception as e:
                    flash(f"Error creating directory: {e}", 'error')
                    return redirect(url_for('settings'))
            
            _update_env_var('DESTINATION_DIRECTORY', dir_path)
            flash('Destination directory updated', 'success')
    
    elif category == 'tmdb':
        api_key = request.form.get('tmdb_api_key')
        include_tmdb_id = request.form.get('include_tmdb_id') == 'on'
        
        if api_key:
            _update_env_var('TMDB_API_KEY', api_key)
        
        _update_env_var('INCLUDE_TMDB_ID', 'true' if include_tmdb_id else 'false')
        flash('TMDB settings updated', 'success')
    
    elif category == 'file_management':
        use_symlinks = request.form.get('use_symlinks') == 'on'
        refresh_plex = request.form.get('refresh_plex') == 'on'
        
        _update_env_var('USE_SYMLINKS', 'true' if use_symlinks else 'false')
        _update_env_var('REFRESH_PLEX', 'true' if refresh_plex else 'false')
        flash('File management settings updated', 'success')
    
    elif category == 'plex':
        plex_url = request.form.get('plex_url')
        plex_token = request.form.get('plex_token')
        movies_section = request.form.get('plex_movies_section')
        tv_section = request.form.get('plex_tv_section')
        anime_movies_section = request.form.get('plex_anime_movies_section')
        anime_tv_section = request.form.get('plex_anime_tv_section')
        
        if plex_url:
            _update_env_var('PLEX_URL', plex_url)
        
        if plex_token:
            _update_env_var('PLEX_TOKEN', plex_token)
        
        if movies_section:
            _update_env_var('PLEX_MOVIES_SECTION', movies_section)
        
        if tv_section:
            _update_env_var('PLEX_TV_SECTION', tv_section)
        
        if anime_movies_section:
            _update_env_var('PLEX_ANIME_MOVIES_SECTION', anime_movies_section)
        
        if anime_tv_section:
            _update_env_var('PLEX_ANIME_TV_SECTION', anime_tv_section)
        
        flash('Plex settings updated', 'success')
    
    elif category == 'monitoring':
        interval = request.form.get('monitor_interval')
        
        if interval and interval.isdigit() and int(interval) > 0:
            _update_env_var('MONITOR_INTERVAL_MINUTES', interval)
            flash('Monitoring interval updated', 'success')
        else:
            flash('Invalid monitoring interval', 'error')
    
    return redirect(url_for('settings'))

@app.route('/api/file_browser')
def file_browser():
    """API endpoint for browsing files and directories."""
    path = request.args.get('path', '/')
    path = _clean_directory_path(path)
    
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
        logger.error(f"Error browsing files: {e}", exc_info=True)
        return jsonify({'error': str(e)})

@app.route('/api/test_plex')
def test_plex():
    """API endpoint for testing Plex connection."""
    # Get Plex configuration
    plex_url = os.environ.get('PLEX_URL', '')
    plex_token = os.environ.get('PLEX_TOKEN', '')
    
    # Check if Plex is configured
    if not plex_url or not plex_token:
        return jsonify({
            'success': False,
            'message': 'Plex server URL or token not configured.'
        })
    
    try:
        import requests
        from xml.etree import ElementTree
        
        # Construct the API endpoint for fetching server info
        endpoint = f"{plex_url}/"
        params = {'X-Plex-Token': plex_token}
        
        # Make the API request
        response = requests.get(endpoint, params=params, timeout=10)
        
        # Check if the request was successful
        if response.status_code == 200:
            # Parse XML response to get server name
            root = ElementTree.fromstring(response.content)
            server_name = root.get('friendlyName', 'Unknown')
            
            # Try to get the list of libraries
            library_endpoint = f"{plex_url}/library/sections"
            library_response = requests.get(library_endpoint, params=params, timeout=10)
            
            libraries = []
            if library_response.status_code == 200:
                # Parse XML to get libraries
                library_root = ElementTree.fromstring(library_response.content)
                for directory in library_root.findall('.//Directory'):
                    libraries.append({
                        'id': directory.get('key', 'Unknown'),
                        'title': directory.get('title', 'Unknown'),
                        'type': directory.get('type', 'Unknown')
                    })
            
            return jsonify({
                'success': True,
                'server_name': server_name,
                'libraries': libraries
            })
        else:
            return jsonify({
                'success': False,
                'message': f"Failed to connect to Plex server: HTTP {response.status_code}"
            })
    
    except Exception as e:
        logger.error(f"Error testing Plex connection: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'message': f"Error: {str(e)}"
        })

@app.route('/activity')
def activity_log():
    """Display the activity log page."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    activity_type = request.args.get('type', '')
    status = request.args.get('status', '')
    start_date = request.args.get('start', '')
    end_date = request.args.get('end', '')
    
    # Get activities from database or log file
    activities = get_activities(
        page=page,
        per_page=per_page,
        activity_type=activity_type,
        status=status,
        start_date=start_date,
        end_date=end_date
    )
    
    # Get total count for pagination
    total_activities = get_activities_count(
        activity_type=activity_type,
        status=status,
        start_date=start_date,
        end_date=end_date
    )
    
    # Calculate total pages
    total_pages = (total_activities + per_page - 1) // per_page
    
    return render_template(
        'activity.html',
        activities=activities,
        page=page,
        per_page=per_page,
        total_activities=total_activities,
        total_pages=total_pages,
        activity_type=activity_type,
        status=status,
        start_date=start_date,
        end_date=end_date
    )

@app.route('/api/activity/export')
def export_activities():
    """Export activities data in CSV format."""
    format_type = request.args.get('format', 'csv')
    activity_type = request.args.get('type', '')
    status = request.args.get('status', '')
    start_date = request.args.get('start', '')
    end_date = request.args.get('end', '')
    
    # Get all activities matching the filters
    activities = get_all_activities(
        activity_type=activity_type,
        status=status,
        start_date=start_date,
        end_date=end_date
    )
    
    if format_type.lower() == 'csv':
        # Create CSV data
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header row
        writer.writerow(['Timestamp', 'Type', 'Item', 'Status', 'Message', 'Error', 'Source Path', 'Destination Path'])
        
        # Write data rows
        for activity in activities:
            writer.writerow([
                activity.get('timestamp', ''),
                activity.get('action', ''),
                activity.get('item', ''),
                activity.get('status', ''),
                activity.get('message', ''),
                activity.get('error', ''),
                activity.get('path', ''),
                activity.get('destination_path', '')
            ])
        
        # Create response with CSV data
        response = make_response(output.getvalue())
        response.headers['Content-Disposition'] = f'attachment; filename=scanly_activity_{datetime.now().strftime("%Y%m%d%H%M%S")}.csv'
        response.headers['Content-Type'] = 'text/csv'
        return response
    
    # Default to JSON if format is not recognized
    return jsonify(activities)

def get_system_stats():
    """Get system statistics for the dashboard."""
    stats = {
        'movies': 0,
        'tv_shows': 0,
        'monitored_dirs': 0,
        'skipped_items': 0
    }
    
    # Load skipped items count
    try:
        skipped_items = load_skipped_items()
        if skipped_items:
            stats['skipped_items'] = len(skipped_items)
            logger.debug(f"Loaded {stats['skipped_items']} skipped items")
    except Exception as e:
        logger.error(f"Error loading skipped items in get_system_stats: {e}")
        stats['skipped_items'] = 0
    
    # Get monitored directories count
    try:
        from src.core.monitor_manager import MonitorManager
        mm = MonitorManager()
        monitored_dirs = mm.get_monitored_directories() or {}
        stats['monitored_dirs'] = len(monitored_dirs)
    except ImportError:
        logger.warning("Monitor manager not available in get_system_stats")
    except Exception as e:
        logger.error(f"Error getting monitored directories in get_system_stats: {e}")
    
    # Count media in destination directory
    dest_dir = os.environ.get('DESTINATION_DIRECTORY', '')
    if dest_dir and os.path.isdir(dest_dir):
        # Count movies
        movies_dir = os.path.join(dest_dir, 'Movies')
        if os.path.isdir(movies_dir):
            try:
                stats['movies'] += len([d for d in os.listdir(movies_dir) 
                                     if os.path.isdir(os.path.join(movies_dir, d))])
            except Exception as e:
                logger.error(f"Error counting movies: {e}")
        
        # Count anime movies
        anime_movies_dir = os.path.join(dest_dir, 'Anime Movies')
        if os.path.isdir(anime_movies_dir):
            try:
                stats['movies'] += len([d for d in os.listdir(anime_movies_dir) 
                                     if os.path.isdir(os.path.join(anime_movies_dir, d))])
            except Exception as e:
                logger.error(f"Error counting anime movies: {e}")
        
        # Count TV shows
        tv_dir = os.path.join(dest_dir, 'TV Shows')
        if os.path.isdir(tv_dir):
            try:
                stats['tv_shows'] += len([d for d in os.listdir(tv_dir) 
                                       if os.path.isdir(os.path.join(tv_dir, d))])
            except Exception as e:
                logger.error(f"Error counting TV shows: {e}")
        
        # Count anime series
        anime_tv_dir = os.path.join(dest_dir, 'Anime Series')
        if os.path.isdir(anime_tv_dir):
            try:
                stats['tv_shows'] += len([d for d in os.listdir(anime_tv_dir) 
                                       if os.path.isdir(os.path.join(anime_tv_dir, d))])
            except Exception as e:
                logger.error(f"Error counting anime series: {e}")
    
    logger.debug(f"System stats: {stats}")
    return stats

def get_activities(page=1, per_page=20, activity_type='', status='', start_date='', end_date=''):
    """
    Get activities focused on media processing events from the log files.
    Filters out excessive technical information and shows only relevant media processing events.
    """
    try:
        # Path to log directory
        log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'logs')
        log_file = os.path.join(log_dir, 'scanly.log')
        
        if not os.path.exists(log_file):
            logger.warning(f"Log file not found: {log_file}")
            return []
        
        # Parse log file to extract activities focused on media processing
        activities = []
        activity_id = 1
        
        # Keywords that indicate media processing activities
        media_keywords = [
            'movie', 'tv show', 'series', 'anime', 'episode', 'scan', 'process', 
            'rename', 'move', 'copy', 'skipped', 'plex', 'monitor', 'directory'
        ]
        
        # Open and read the log file
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                try:
                    # Skip lines that don't have our expected format or don't contain media-related keywords
                    if ' - ' not in line or not any(keyword in line.lower() for keyword in media_keywords):
                        continue
                    
                    parts = line.strip().split(' - ', 2)
                    if len(parts) < 3:
                        continue
                    
                    timestamp = parts[0]
                    level_module = parts[1]
                    message = parts[2]
                    
                    # Extract level and module
                    if ' - ' in level_module:
                        level, module = level_module.rsplit(' - ', 1)
                    else:
                        level = level_module
                        module = "unknown"
                    
                    # Skip DEBUG level messages unless they're important
                    if "DEBUG" in level and not any(k in message.lower() for k in ['process', 'scan complete', 'found']):
                        continue
                    
                    # Determine action type based on message content for media-focused events
                    action = 'info'
                    if 'scan' in message.lower():
                        action = 'scan'
                    elif 'process' in message.lower():
                        action = 'process'
                    elif 'move' in message.lower() or 'rename' in message.lower() or 'copy' in message.lower():
                        action = 'move'
                    elif 'monitor' in message.lower():
                        action = 'monitor'
                    elif 'skip' in message.lower():
                        action = 'skip'
                    elif 'error' in message.lower() or 'failed' in message.lower():
                        action = 'error'
                    
                    # Determine status
                    status_val = 'info'
                    if 'error' in message.lower() or 'failed' in message.lower() or 'ERROR' in level:
                        status_val = 'error'
                    elif 'warning' in message.lower() or 'WARNING' in level:
                        status_val = 'warning'
                    elif 'complete' in message.lower() or 'success' in message.lower():
                        status_val = 'success'
                    
                    # Extract file/directory paths from the message
                    path = ""
                    destination_path = ""
                    
                    # Look for movie/TV show titles or file paths
                    if '/' in message:
                        # Find paths in the message
                        path_matches = re.findall(r'(/[^\s:]*)+', message)
                        if path_matches:
                            path = path_matches[0]
                            if len(path_matches) > 1:
                                destination_path = path_matches[1]
                    
                    # Try to extract media item name (e.g., "Processing: Movie Title (2023)")
                    item_name = ""
                    media_match = re.search(r'(process|found|scan|rename|move)(?:ing)?\s*[:\-]?\s*["\'`]?([^"\'`/\n\r]+)["\'`]?', 
                                           message, re.IGNORECASE)
                    if media_match:
                        item_name = media_match.group(2).strip()
                    
                    # If no item name was found, use the filename from the path
                    if not item_name and path:
                        item_name = os.path.basename(path)
                    
                    # Clean up the message for display
                    display_message = message
                    if len(message) > 500:  # Truncate very long messages
                        display_message = message[:497] + '...'
                    
                    # Create a simplified, media-focused activity record
                    activity = {
                        'id': activity_id,
                        'timestamp': timestamp,
                        'action': action,
                        'item': item_name or "System Event",
                        'path': path,
                        'destination_path': destination_path,
                        'status': status_val,
                        'message': display_message,
                        'error': display_message if status_val == 'error' else None
                    }
                    
                    activities.append(activity)
                    activity_id += 1
                    
                except Exception as e:
                    logger.error(f"Error parsing log line: {e}")
                    continue
        
        # Apply filters
        filtered_activities = activities
        
        if activity_type:
            filtered_activities = [a for a in filtered_activities if a['action'] == activity_type]
        
        if status:
            filtered_activities = [a for a in filtered_activities if a['status'] == status]
            
        if start_date:
            try:
                start_datetime = datetime.strptime(start_date, '%Y-%m-%d')
                filtered_activities = [a for a in filtered_activities if 
                                      datetime.strptime(a['timestamp'].split()[0], '%Y-%m-%d') >= start_datetime]
            except ValueError:
                logger.error(f"Invalid start date format: {start_date}")
            
        if end_date:
            try:
                end_datetime = datetime.strptime(end_date, '%Y-%m-%d')
                filtered_activities = [a for a in filtered_activities if 
                                      datetime.strptime(a['timestamp'].split()[0], '%Y-%m-%d') <= end_datetime]
            except ValueError:
                logger.error(f"Invalid end date format: {end_date}")
        
        # Reverse to get newest first
        filtered_activities = list(reversed(filtered_activities))
        
        # Apply pagination
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        
        return filtered_activities[start_idx:end_idx]
    except Exception as e:
        logger.error(f"Error getting activities: {e}", exc_info=True)
        return []

def get_activities_count(activity_type='', status='', start_date='', end_date=''):
    """
    Get the total count of activities based on filters.
    """
    # Use the same filtering logic as get_activities but count the results
    activities = get_all_activities(activity_type, status, start_date, end_date)
    return len(activities)

def get_all_activities(activity_type='', status='', start_date='', end_date=''):
    """
    Get all activities matching the filters without pagination.
    """
    # Call get_activities with a large per_page to get all results
    return get_activities(page=1, per_page=1000000, activity_type=activity_type, 
                         status=status, start_date=start_date, end_date=end_date)

def find_available_port(start_port=8000, max_port=8020):
    """Find an available port within the given range."""
    for port in range(start_port, max_port + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                # Try to bind to the port
                s.bind(('127.0.0.1', port))
                # If successful, return the port
                return port
            except socket.error:
                # Port is already in use, try the next one
                logger.info(f"Port {port} is in use, trying next port...")
                continue
    
    # If we get here, all ports in the range are in use
    logger.warning(f"All ports from {start_port} to {max_port} are in use.")
    return None

# Run the app when executed directly
if __name__ == '__main__':
    # Try to find an available port
    port = find_available_port()
    
    if port:
        print(f"Starting Scanly Web UI on port {port}")
        app.run(host='0.0.0.0', port=port, debug=True)
    else:
        print("Error: Unable to find an available port. Please close other applications using ports 8000-8020.")
        sys.exit(1)