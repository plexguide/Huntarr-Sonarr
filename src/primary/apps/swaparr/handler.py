"""
Enhanced implementation of the swaparr functionality to detect and remove stalled downloads in Starr apps.
Based on the functionality provided by https://github.com/ThijmenGThN/swaparr/releases/tag/0.10.0

Improvements in this version:
- Better statistics tracking and reporting
- Enhanced error handling and logging
- Improved state management
- More granular status tracking
- Better API timeout handling
"""

import os
import json
import time
import hashlib
from datetime import datetime, timedelta
import requests
from typing import Dict, List, Any, Optional

from src.primary.utils.logger import get_logger
from src.primary.settings_manager import load_settings
from src.primary.state import get_state_file_path
from src.primary.settings_manager import get_ssl_verify_setting
from src.primary.utils.database import get_database
from src.primary.apps.swaparr.stats_manager import increment_swaparr_stat

# Create logger
swaparr_logger = get_logger("swaparr")

# Enhanced statistics tracking
SWAPARR_STATS = {
    'total_processed': 0,
    'strikes_added': 0,
    'downloads_removed': 0,
    'malicious_removed': 0,
    'items_ignored': 0,
    'api_calls_made': 0,
    'errors_encountered': 0,
    'last_run_time': None,
    'apps_processed': set(),
    'session_start_time': datetime.utcnow().isoformat()
}

def reset_session_stats():
    """Reset session statistics"""
    global SWAPARR_STATS
    SWAPARR_STATS.update({
        'total_processed': 0,
        'strikes_added': 0,
        'downloads_removed': 0,
        'malicious_removed': 0,
        'items_ignored': 0,
        'api_calls_made': 0,
        'errors_encountered': 0,
        'apps_processed': set(),
        'session_start_time': datetime.utcnow().isoformat()
    })
    swaparr_logger.info("Reset Swaparr session statistics")

def get_session_stats():
    """Get current session statistics"""
    stats_copy = SWAPARR_STATS.copy()
    stats_copy['apps_processed'] = list(stats_copy['apps_processed'])  # Convert set to list for JSON
    return stats_copy

def load_strike_data(app_name):
    """Load strike data for a specific app from database"""
    try:
        db = get_database()
        return db.get_swaparr_strike_data(app_name)
    except Exception as e:
        swaparr_logger.error(f"Error loading strike data for {app_name}: {str(e)}")
        SWAPARR_STATS['errors_encountered'] += 1
        return {}

def save_strike_data(app_name, strike_data):
    """Save strike data for a specific app to database"""
    try:
        db = get_database()
        db.set_swaparr_strike_data(app_name, strike_data)
    except Exception as e:
        swaparr_logger.error(f"Error saving strike data for {app_name}: {str(e)}")
        SWAPARR_STATS['errors_encountered'] += 1

def load_removed_items(app_name):
    """Load list of permanently removed items from database"""
    try:
        db = get_database()
        return db.get_swaparr_removed_items(app_name)
    except Exception as e:
        swaparr_logger.error(f"Error loading removed items for {app_name}: {str(e)}")
        SWAPARR_STATS['errors_encountered'] += 1
        return {}

def save_removed_items(app_name, removed_items):
    """Save list of permanently removed items to database"""
    try:
        db = get_database()
        db.set_swaparr_removed_items(app_name, removed_items)
    except Exception as e:
        swaparr_logger.error(f"Error saving removed items for {app_name}: {str(e)}")
        SWAPARR_STATS['errors_encountered'] += 1

def generate_item_hash(item):
    """Generate a unique hash for an item based on its name and size.
    This helps track items across restarts even if their queue ID changes."""
    hash_input = f"{item['name']}_{item['size']}"
    return hashlib.md5(hash_input.encode('utf-8')).hexdigest()

def check_for_malicious_files(item, settings):
    """Check if download contains malicious file types"""
    if not settings.get('malicious_file_detection', False):
        return False, None
    
    # Use user-defined malicious extensions from settings
    malicious_extensions = settings.get('malicious_extensions', [
        '.lnk', '.exe', '.bat', '.cmd', '.scr', '.pif', '.com', 
        '.zipx', '.jar', '.vbs', '.js', '.jse', '.wsf', '.wsh'
    ])
    
    # Use user-defined suspicious patterns from settings
    suspicious_patterns = settings.get('suspicious_patterns', [
        'password.txt', 'readme.txt', 'install.exe', 'setup.exe',
        'keygen', 'crack', 'patch.exe', 'activator'
    ])
    
    item_name = item.get('name', '').lower()
    
    # Check for malicious extensions in the title/name
    for ext in malicious_extensions:
        if ext.lower() in item_name:
            swaparr_logger.warning(f"Malicious file detected in '{item_name}': contains {ext}")
            return True, f"Contains malicious file type: {ext}"
    
    # Check for suspicious patterns
    for pattern in suspicious_patterns:
        if pattern.lower() in item_name:
            swaparr_logger.warning(f"Suspicious content detected in '{item_name}': contains {pattern}")
            return True, f"Contains suspicious content: {pattern}"
    
    return False, None

def check_age_based_removal(item, strike_data, settings):
    """Check if download should be removed based on age"""
    if not settings.get('age_based_removal', False):
        return False, None
    
    max_age_days = settings.get('max_age_days', 7)
    item_id = str(item.get('id', ''))
    
    # Check if we have strike data for this item
    if item_id not in strike_data or not strike_data[item_id].get('first_strike_time'):
        return False, None
    
    try:
        first_strike = datetime.fromisoformat(strike_data[item_id]['first_strike_time'].replace('Z', '+00:00'))
        age_days = (datetime.utcnow() - first_strike).days
        
        if age_days >= max_age_days:
            swaparr_logger.warning(f"Age-based removal triggered for '{item['name']}': {age_days} days old (max: {max_age_days})")
            return True, f"Too old: {age_days} days (max: {max_age_days})"
    except (ValueError, KeyError) as e:
        swaparr_logger.error(f"Error parsing first strike time for item {item_id}: {e}")
    
    return False, None

def check_quality_based_removal(item, settings):
    """Check if download should be removed based on quality"""
    if not settings.get('quality_based_removal', False):
        return False, None
    
    # Use user-defined blocked quality patterns from settings
    blocked_qualities = settings.get('blocked_quality_patterns', [
        'cam', 'camrip', 'hdcam', 'ts', 'telesync', 'tc', 'telecine',
        'r6', 'dvdscr', 'dvdscreener', 'workprint', 'wp'
    ])
    
    item_name = item.get('name', '').lower()
    
    # Check for blocked quality patterns
    for quality in blocked_qualities:
        if quality.lower() in item_name:
            swaparr_logger.warning(f"Quality-based removal triggered for '{item['name']}': contains blocked quality '{quality}'")
            return True, f"Blocked quality: {quality}"
    
    return False, None

def check_for_failed_imports(item, settings):
    """Check if download has failed import based on error patterns"""
    if not settings.get("failed_import_detection", False):
        return False, ""
    
    error_message = item.get("error_message", "").lower()
    status = item.get("status", "").lower()
    
    # Common import failure indicators
    import_failure_indicators = [
        "import failed", "unable to import", "import error",
        "no files found", "path not found", "access denied",
        "disk full", "permission denied", "invalid path",
        "file not found", "directory not found", "cannot import",
        "import unsuccessful", "failed to import", "import aborted",
        "insufficient space", "read-only", "network error",
        "timeout", "connection lost", "corrupted", "invalid format",
        "no space left", "operation not permitted", "input/output error"
    ]
    
    # Check error message and status for failure patterns
    for pattern in import_failure_indicators:
        if pattern in error_message or pattern in status:
            return True, f"Import failure detected: {pattern}"
    
    # Also check for specific status values that indicate import failures
    failed_statuses = ["failed", "error", "warning"]
    if status in failed_statuses and ("import" in error_message or "file" in error_message or "path" in error_message):
        return True, f"Import failure status: {status}"
    
    return False, ""

def parse_time_string_to_seconds(time_string):
    """Parse a time string like '2h', '30m', '1d' to seconds"""
    if not time_string:
        return 7200  # Default 2 hours
    
    unit = time_string[-1].lower()
    try:
        value = int(time_string[:-1])
    except ValueError:
        swaparr_logger.error(f"Invalid time string: {time_string}, using default 2 hours")
        return 7200
    
    if unit == 'd':
        return value * 86400  # Days to seconds
    elif unit == 'h':
        return value * 3600   # Hours to seconds
    elif unit == 'm':
        return value * 60     # Minutes to seconds
    else:
        swaparr_logger.error(f"Unknown time unit in: {time_string}, using default 2 hours")
        return 7200

def parse_size_string_to_bytes(size_string):
    """Parse a size string like '25GB', '1TB' to bytes"""
    if not size_string:
        return 25 * 1024 * 1024 * 1024  # Default 25GB
    
    # Extract the numeric part and unit
    unit = ""
    for i in range(len(size_string) - 1, -1, -1):
        if not size_string[i].isalpha():
            value = float(size_string[:i+1])
            unit = size_string[i+1:].upper()
            break
    else:
        swaparr_logger.error(f"Invalid size string: {size_string}, using default 25GB")
        return 25 * 1024 * 1024 * 1024
    
    # Convert to bytes based on unit
    if unit == 'B':
        return int(value)
    elif unit == 'KB':
        return int(value * 1024)
    elif unit == 'MB':
        return int(value * 1024 * 1024)
    elif unit == 'GB':
        return int(value * 1024 * 1024 * 1024)
    elif unit == 'TB':
        return int(value * 1024 * 1024 * 1024 * 1024)
    else:
        swaparr_logger.error(f"Unknown size unit in: {size_string}, using default 25GB")
        return 25 * 1024 * 1024 * 1024

def get_queue_items(app_name, api_url, api_key, api_timeout=120):
    """Get download queue items from a Starr app API with pagination support"""
    api_version_map = {
        "radarr": "v3",
        "sonarr": "v3",
        "lidarr": "v1",
        "readarr": "v1",
        "whisparr": "v3",
        "eros": "v3"  # Eros is Whisparr V3
    }
    
    api_version = api_version_map.get(app_name, "v3")
    all_records = []
    page = 1
    page_size = 100  # Request a large page size to reduce API calls
    
    while True:
        # Add pagination parameters
        queue_url = f"{api_url.rstrip('/')}/api/{api_version}/queue?page={page}&pageSize={page_size}"
        headers = {'X-Api-Key': api_key}
        verify_ssl = get_ssl_verify_setting()
        if not verify_ssl:
            swaparr_logger.debug("SSL verification disabled by user setting for get_queue_items")
        try:
            SWAPARR_STATS['api_calls_made'] += 1
            response = requests.get(queue_url, headers=headers, timeout=api_timeout, verify=verify_ssl)
            response.raise_for_status()
            queue_data = response.json()
            
            if api_version in ["v3"]:  # Radarr, Sonarr, Whisparr, Eros use v3
                records = queue_data.get("records", [])
                total_records = queue_data.get("totalRecords", 0)
            else:  # Lidarr, Readarr use v1 - but they also use the records structure
                records = queue_data.get("records", [])
                total_records = queue_data.get("totalRecords", len(records))
            
            # Add this page's records to our collection
            all_records.extend(records)
            
            # If we've fetched all records or there are no more, break the loop
            if len(all_records) >= total_records or len(records) == 0:
                break
            
            # Otherwise, move to the next page
            page += 1
            
        except requests.exceptions.RequestException as e:
            swaparr_logger.error(f"Error fetching queue for {app_name} (page {page}): {str(e)}")
            SWAPARR_STATS['errors_encountered'] += 1
            break
    
    swaparr_logger.info(f"Fetched {len(all_records)} queue items for {app_name} using {page} API calls")
    
    # Normalize the response based on app type
    if app_name in ["radarr", "whisparr", "eros"]:
        return parse_queue_items(all_records, "movie", app_name)
    elif app_name == "sonarr":
        return parse_queue_items(all_records, "series", app_name)
    elif app_name == "lidarr":
        return parse_queue_items(all_records, "album", app_name)
    elif app_name == "readarr":
        return parse_queue_items(all_records, "book", app_name)
    else:
        swaparr_logger.error(f"Unknown app type: {app_name}")
        return []

def parse_queue_items(records, item_type, app_name):
    """Parse queue items from API response into a standardized format"""
    queue_items = []
    
    for record in records:
        # Skip non-dictionary records
        if not isinstance(record, dict):
            swaparr_logger.warning(f"Skipping non-dictionary record in {app_name} queue: {record}")
            continue
            
        # Extract the name based on the item type
        name = None
        if item_type == "movie" and record.get("movie"):
            name = record["movie"].get("title", "Unknown Movie")
        elif item_type == "series" and record.get("series"):
            name = record["series"].get("title", "Unknown Series")
        elif item_type == "album" and record.get("album"):
            name = record["album"].get("title", "Unknown Album")
        elif item_type == "book" and record.get("book"):
            name = record["book"].get("title", "Unknown Book")
        
        # If no name was found, try to use the download title
        if not name and record.get("title"):
            name = record.get("title", "Unknown Download")
        
        # Parse ETA if available
        eta_seconds = 0
        if record.get("timeleft"):
            eta = record.get("timeleft", "")
            # Basic parsing of timeleft format like "00:30:00" (30 minutes)
            try:
                eta_parts = eta.split(':')
                if len(eta_parts) == 3:
                    eta_seconds = int(eta_parts[0]) * 3600 + int(eta_parts[1]) * 60 + int(eta_parts[2])
            except (ValueError, IndexError):
                eta_seconds = 0
        
        queue_items.append({
            "id": record.get("id"),
            "name": name,
            "size": record.get("size", 0),
            "status": record.get("status", "unknown").lower(),
            "eta": eta_seconds,
            "error_message": record.get("errorMessage", "")
        })
    
    return queue_items

def trigger_search_for_item(app_name, api_url, api_key, item, api_timeout=120):
    """Trigger a search for the item that was removed"""
    api_version_map = {
        "radarr": "v3",
        "sonarr": "v3", 
        "lidarr": "v1",
        "readarr": "v1",
        "whisparr": "v3",
        "eros": "v3"
    }
    
    api_version = api_version_map.get(app_name, "v3")
    headers = {'X-Api-Key': api_key, 'Content-Type': 'application/json'}
    
    try:
        # Different apps have different search endpoints and payload structures
        if app_name == "sonarr":
            # For Sonarr, we need the series ID and episode IDs
            series_id = item.get("seriesId")
            episode_ids = item.get("episodeIds", [])
            if series_id and episode_ids:
                search_url = f"{api_url.rstrip('/')}/api/{api_version}/command"
                payload = {
                    "name": "EpisodeSearch",
                    "seriesId": series_id,
                    "episodeIds": episode_ids
                }
            else:
                swaparr_logger.warning(f"Cannot trigger search for {item.get('name', 'unknown')} - missing series/episode IDs")
                return False
                
        elif app_name == "radarr":
            # For Radarr, we need the movie ID
            movie_id = item.get("movieId")
            if movie_id:
                search_url = f"{api_url.rstrip('/')}/api/{api_version}/command"
                payload = {
                    "name": "MoviesSearch",
                    "movieIds": [movie_id]
                }
            else:
                swaparr_logger.warning(f"Cannot trigger search for {item.get('name', 'unknown')} - missing movie ID")
                return False
                
        elif app_name == "lidarr":
            # For Lidarr, we need the album ID
            album_id = item.get("albumId")
            if album_id:
                search_url = f"{api_url.rstrip('/')}/api/{api_version}/command"
                payload = {
                    "name": "AlbumSearch",
                    "albumIds": [album_id]
                }
            else:
                swaparr_logger.warning(f"Cannot trigger search for {item.get('name', 'unknown')} - missing album ID")
                return False
                
        elif app_name == "readarr":
            # For Readarr, we need the book ID
            book_id = item.get("bookId")
            if book_id:
                search_url = f"{api_url.rstrip('/')}/api/{api_version}/command"
                payload = {
                    "name": "BookSearch",
                    "bookIds": [book_id]
                }
            else:
                swaparr_logger.warning(f"Cannot trigger search for {item.get('name', 'unknown')} - missing book ID")
                return False
                
        elif app_name in ["whisparr", "eros"]:
            # For Whisparr/Eros, we need the movie ID (same structure as Radarr)
            movie_id = item.get("movieId")
            if movie_id:
                search_url = f"{api_url.rstrip('/')}/api/{api_version}/command"
                payload = {
                    "name": "MoviesSearch", 
                    "movieIds": [movie_id]
                }
            else:
                swaparr_logger.warning(f"Cannot trigger search for {item.get('name', 'unknown')} - missing movie ID")
                return False
        else:
            swaparr_logger.warning(f"Search not supported for app: {app_name}")
            return False
        
        verify_ssl = get_ssl_verify_setting()

        if not verify_ssl:
            swaparr_logger.debug("SSL verification disabled by user setting for trigger_search_for_item")

        # Execute the search command
        SWAPARR_STATS['api_calls_made'] += 1
        response = requests.post(search_url, headers=headers, json=payload, timeout=api_timeout, verify=verify_ssl)
        response.raise_for_status()
        
        swaparr_logger.info(f"Successfully triggered search for {item.get('name', 'unknown')} in {app_name}")
        return True
        
    except requests.exceptions.RequestException as e:
        swaparr_logger.error(f"Error triggering search for {item.get('name', 'unknown')} in {app_name}: {str(e)}")
        SWAPARR_STATS['errors_encountered'] += 1
        return False

def delete_download(app_name, api_url, api_key, download_id, remove_from_client=True, item=None, trigger_search=False, api_timeout=120):
    """Delete a download from a Starr app and optionally trigger a new search"""
    api_version_map = {
        "radarr": "v3",
        "sonarr": "v3",
        "lidarr": "v1",
        "readarr": "v1",
        "whisparr": "v3",
        "eros": "v3"
    }
    
    api_version = api_version_map.get(app_name, "v3")
    delete_url = f"{api_url.rstrip('/')}/api/{api_version}/queue/{download_id}?removeFromClient={str(remove_from_client).lower()}&blocklist=true"
    headers = {'X-Api-Key': api_key}
    verify_ssl = get_ssl_verify_setting()
    if not verify_ssl:
        swaparr_logger.debug("SSL verification disabled by user setting for delete_download")
    try:
        SWAPARR_STATS['api_calls_made'] += 1
        response = requests.delete(delete_url, headers=headers, timeout=api_timeout, verify=verify_ssl)
        response.raise_for_status()
        swaparr_logger.info(f"Successfully removed download {download_id} from {app_name}")
        SWAPARR_STATS['downloads_removed'] += 1
        increment_swaparr_stat("removals", 1)  # Track removals in persistent system
        
        # Trigger search if requested and item data is available
        if trigger_search and item:
            swaparr_logger.info(f"Triggering new search for removed download: {item.get('name', 'unknown')}")
            search_success = trigger_search_for_item(app_name, api_url, api_key, item, api_timeout)
            if search_success:
                swaparr_logger.info(f"Successfully triggered search after removal for: {item.get('name', 'unknown')}")
            else:
                swaparr_logger.warning(f"Failed to trigger search after removal for: {item.get('name', 'unknown')}")
        
        return True
    except requests.exceptions.RequestException as e:
        swaparr_logger.error(f"Error removing download {download_id} from {app_name}: {str(e)}")
        SWAPARR_STATS['errors_encountered'] += 1
        return False

def process_stalled_downloads(app_name, instance_name, instance_data, settings):
    """Process stalled downloads for a specific app instance."""
    swaparr_logger.info(f"Checking download queue for {app_name} instance: {instance_name}")
    
    try:
        # Check if instance has Swaparr enabled
        if not instance_data.get("swaparr_enabled", False):
            swaparr_logger.info(f"Swaparr not enabled for {app_name} instance: {instance_name}, skipping")
            return 0  # Return 0 processed
        
        # Check for disabled setting during processing (every 10 items to avoid excessive I/O)
        current_swaparr_settings = load_settings("swaparr")
        if not current_swaparr_settings or not current_swaparr_settings.get("enabled", False):
            swaparr_logger.warning(f"Swaparr was disabled during download processing for {app_name} instance: {instance_name}. Stopping processing.")
            return 0
        
        # Get the download queue
        queue_response = get_queue_items(app_name, instance_data["api_url"], instance_data["api_key"])
        queue_items = queue_response
        
        swaparr_logger.info(f"Found {len(queue_items)} downloads in queue for {app_name} instance: {instance_name}")
        
        if len(queue_items) == 0:
            swaparr_logger.info(f"No downloads to process for {app_name} instance: {instance_name}")
            return 0
        
        # Load strike data and removed items for this app
        strike_data = load_strike_data(app_name)
        removed_items = load_removed_items(app_name)
        
        # Process each queue item
        items_processed_this_run = 0
        for item in queue_items:
            # Check if Swaparr has been disabled during processing (every 10 items to avoid excessive I/O)
            if items_processed_this_run % 10 == 0:
                current_swaparr_settings = load_settings("swaparr")
                if not current_swaparr_settings or not current_swaparr_settings.get("enabled", False):
                    swaparr_logger.warning(f"Swaparr was disabled during download processing for {app_name} instance: {instance_name}. Stopping after processing {items_processed_this_run} items.")
                    break
            
            item_id = str(item["id"])
            item_state = "Normal"
            item_hash = generate_item_hash(item)
            
            SWAPARR_STATS['total_processed'] += 1
            if not settings.get("dry_run", False):
                increment_swaparr_stat("processed", 1)  # Track processed items in persistent system
            items_processed_this_run += 1
            
            # Check if this item has been previously removed
            if item_hash in removed_items:
                last_removed_date = datetime.fromisoformat(removed_items[item_hash]["removed_time"].replace('Z', '+00:00'))
                days_since_removal = (datetime.utcnow() - last_removed_date).days
                
                # Re-remove it automatically if it's been less than 7 days since last removal
                if days_since_removal < 7:
                    swaparr_logger.warning(f"Found previously removed download that reappeared: {item['name']} (removed {days_since_removal} days ago)")
                    
                    if not settings.get("dry_run", False):
                        # Don't trigger search for re-removed items (they were already searched before)
                        if delete_download(app_name, instance_data["api_url"], instance_data["api_key"], item["id"], True, item, False):
                            swaparr_logger.info(f"Re-removed previously removed download: {item['name']}")
                            # Update the removal time
                            removed_items[item_hash]["removed_time"] = datetime.utcnow().isoformat()
                            # Note: Swaparr uses its own statistics system (SWAPARR_STATS), not the hunting stats manager
                    else:
                        swaparr_logger.info(f"DRY RUN: Would have re-removed previously removed download: {item['name']}")
                    
                    item_state = "Re-removed" if not settings.get("dry_run", False) else "Would Re-remove (Dry Run)"
                    continue
            
            # Skip large files if configured
            max_size = parse_size_string_to_bytes(settings.get("ignore_above_size", "25GB"))
            if item["size"] >= max_size:
                swaparr_logger.debug(f"Ignoring large download: {item['name']} ({item['size']} bytes > {max_size} bytes)")
                item_state = "Ignored (Size)"
                SWAPARR_STATS['items_ignored'] += 1
                if not settings.get("dry_run", False):
                    increment_swaparr_stat("ignored", 1)  # Track ignored items in persistent system
                continue
            
            # Handle delayed items - we'll skip these (respects delay profiles)
            if item["status"] == "delay":
                swaparr_logger.debug(f"Ignoring delayed download: {item['name']}")
                item_state = "Ignored (Delayed)"
                SWAPARR_STATS['items_ignored'] += 1
                if not settings.get("dry_run", False):
                    increment_swaparr_stat("ignored", 1)  # Track ignored items in persistent system
                continue
            
            # Special handling for "queued" status
            # We only skip truly queued items, not those with metadata issues
            metadata_issue = "metadata" in item["status"].lower() or "metadata" in item["error_message"].lower()
            
            if item["status"] == "queued" and not metadata_issue:
                # For regular queued items, check how long they've been in strike data
                if item_id in strike_data and "first_strike_time" in strike_data[item_id]:
                    first_strike = datetime.fromisoformat(strike_data[item_id]["first_strike_time"].replace('Z', '+00:00'))
                    if (datetime.utcnow() - first_strike) < timedelta(hours=1):
                        # Skip if it's been less than 1 hour since first seeing it
                        swaparr_logger.debug(f"Ignoring recently queued download: {item['name']}")
                        item_state = "Ignored (Recently Queued)"
                        SWAPARR_STATS['items_ignored'] += 1
                        if not settings.get("dry_run", False):
                            increment_swaparr_stat("ignored", 1)  # Track ignored items in persistent system
                        continue
                else:
                    # Initialize with first strike time for queued items
                    if item_id not in strike_data:
                        strike_data[item_id] = {
                            "strikes": 0,
                            "name": item["name"],
                            "first_strike_time": datetime.utcnow().isoformat(),
                            "last_strike_time": None
                        }
                    swaparr_logger.debug(f"Monitoring new queued download: {item['name']}")
                    item_state = "Monitoring (Queued)"
                    continue
            
            # Check for malicious files FIRST - immediate removal without strikes
            is_malicious, malicious_reason = check_for_malicious_files(item, settings)
            if is_malicious:
                swaparr_logger.error(f"MALICIOUS CONTENT DETECTED: {item['name']} - {malicious_reason}")
                
                if not settings.get("dry_run", False):
                    # Check if re-search is enabled for malicious removals
                    trigger_search = settings.get("research_removed", False)
                    if delete_download(app_name, instance_data["api_url"], instance_data["api_key"], item["id"], True, item, trigger_search):
                        swaparr_logger.info(f"Successfully removed malicious download: {item['name']}")
                        
                        # Mark as removed to prevent reappearance
                        removed_items[item_hash] = {
                            "name": item["name"],
                            "removed_time": datetime.utcnow().isoformat(),
                            "reason": f"Malicious: {malicious_reason}",
                            "size": item["size"]
                        }
                        save_removed_items(app_name, removed_items)
                        
                        item_state = f"REMOVED (Malicious: {malicious_reason})"
                        
                        # Track malicious removal statistics
                        SWAPARR_STATS['malicious_removed'] = SWAPARR_STATS.get('malicious_removed', 0) + 1
                        increment_swaparr_stat("malicious_removals", 1)
                else:
                    swaparr_logger.info(f"DRY RUN: Would remove malicious download: {item['name']} - {malicious_reason}")
                    item_state = f"Would Remove (Malicious: {malicious_reason})"
                
                continue  # Skip to next item - don't process further
            
            # Check for quality-based removal SECOND - immediate removal without strikes  
            is_quality_blocked, quality_reason = check_quality_based_removal(item, settings)
            if is_quality_blocked:
                swaparr_logger.warning(f"QUALITY-BASED REMOVAL: {item['name']} - {quality_reason}")
                
                if not settings.get("dry_run", False):
                    # Check if re-search is enabled for quality-based removals
                    trigger_search = settings.get("research_removed", False)
                    if delete_download(app_name, instance_data["api_url"], instance_data["api_key"], item["id"], True, item, trigger_search):
                        swaparr_logger.info(f"Successfully removed quality-blocked download: {item['name']}")
                        
                        # Mark as removed to prevent reappearance
                        removed_items[item_hash] = {
                            "name": item["name"],
                            "removed_time": datetime.utcnow().isoformat(),
                            "reason": f"Quality: {quality_reason}",
                            "size": item["size"]
                        }
                        save_removed_items(app_name, removed_items)
                        
                        item_state = f"REMOVED (Quality: {quality_reason})"
                        
                        # Track quality removal statistics
                        SWAPARR_STATS['quality_removed'] = SWAPARR_STATS.get('quality_removed', 0) + 1
                        increment_swaparr_stat("quality_removals", 1)
                else:
                    swaparr_logger.info(f"DRY RUN: Would remove quality-blocked download: {item['name']} - {quality_reason}")
                    item_state = f"Would Remove (Quality: {quality_reason})"
                
                continue  # Skip to next item - don't process further
            
            # Initialize strike count if not already in strike data
            if item_id not in strike_data:
                strike_data[item_id] = {
                    "strikes": 0,
                    "name": item["name"],
                    "first_strike_time": datetime.utcnow().isoformat(),
                    "last_strike_time": None
                }
            
            # Check for age-based removal THIRD - immediate removal without strikes
            is_age_expired, age_reason = check_age_based_removal(item, strike_data, settings)
            if is_age_expired:
                swaparr_logger.warning(f"AGE-BASED REMOVAL: {item['name']} - {age_reason}")
                
                if not settings.get("dry_run", False):
                    # Check if re-search is enabled for age-based removals
                    trigger_search = settings.get("research_removed", False)
                    if delete_download(app_name, instance_data["api_url"], instance_data["api_key"], item["id"], True, item, trigger_search):
                        swaparr_logger.info(f"Successfully removed age-expired download: {item['name']}")
                        
                        # Mark as removed to prevent reappearance
                        removed_items[item_hash] = {
                            "name": item["name"],
                            "removed_time": datetime.utcnow().isoformat(),
                            "reason": f"Age: {age_reason}",
                            "size": item["size"]
                        }
                        save_removed_items(app_name, removed_items)
                        
                        # Keep the item in strike data for reference but mark as removed
                        strike_data[item_id]["removed"] = True
                        strike_data[item_id]["removed_time"] = datetime.utcnow().isoformat()
                        
                        item_state = f"REMOVED (Age: {age_reason})"
                        
                        # Track age removal statistics
                        SWAPARR_STATS['age_removed'] = SWAPARR_STATS.get('age_removed', 0) + 1
                        increment_swaparr_stat("age_removals", 1)
                else:
                    swaparr_logger.info(f"DRY RUN: Would remove age-expired download: {item['name']} - {age_reason}")
                    item_state = f"Would Remove (Age: {age_reason})"
                
                continue  # Skip to next item - don't process further
            
            # Check for failed imports FOURTH - immediate removal and re-search
            is_import_failed, import_reason = check_for_failed_imports(item, settings)
            if is_import_failed:
                swaparr_logger.warning(f"FAILED IMPORT DETECTED: {item['name']} - {import_reason}")
                
                if not settings.get("dry_run", False):
                    # Always trigger search for failed imports (this is the main purpose)
                    trigger_search = True
                    if delete_download(app_name, instance_data["api_url"], instance_data["api_key"], item["id"], True, item, trigger_search):
                        swaparr_logger.info(f"Successfully removed failed import: {item['name']}")
                        
                        # Mark as removed to prevent reappearance
                        removed_items[item_hash] = {
                            "name": item["name"],
                            "removed_time": datetime.utcnow().isoformat(),
                            "reason": f"Failed Import: {import_reason}",
                            "size": item["size"]
                        }
                        save_removed_items(app_name, removed_items)
                        
                        item_state = f"REMOVED (Failed Import: {import_reason})"
                        
                        # Track failed import removal statistics
                        SWAPARR_STATS['import_failed_removed'] = SWAPARR_STATS.get('import_failed_removed', 0) + 1
                        increment_swaparr_stat("import_failed_removals", 1)
                else:
                    swaparr_logger.info(f"DRY RUN: Would remove failed import: {item['name']} - {import_reason}")
                    item_state = f"Would Remove (Failed Import: {import_reason})"
                
                continue  # Skip to next item - don't process further
            
            # Check if download should be striked
            should_strike = False
            strike_reason = ""
            
            # Strike if metadata issue, eta too long, or no progress (eta = 0 and not queued)
            if metadata_issue:
                should_strike = True
                strike_reason = "Metadata"
            elif item["eta"] >= parse_time_string_to_seconds(settings.get("max_download_time", "2h")):
                should_strike = True
                strike_reason = "ETA too long"
            elif item["eta"] == 0 and item["status"] not in ["queued", "delay"]:
                should_strike = True
                strike_reason = "No progress"
            
            # If we should strike this item, add a strike
            if should_strike:
                strike_data[item_id]["strikes"] += 1
                strike_data[item_id]["last_strike_time"] = datetime.utcnow().isoformat()
                
                if strike_data[item_id]["first_strike_time"] is None:
                    strike_data[item_id]["first_strike_time"] = datetime.utcnow().isoformat()
                
                current_strikes = strike_data[item_id]["strikes"]
                swaparr_logger.info(f"Added strike ({current_strikes}/{settings.get('max_strikes', 3)}) to {item['name']} - Reason: {strike_reason}")
                SWAPARR_STATS['strikes_added'] += 1
                if not settings.get("dry_run", False):
                    increment_swaparr_stat("strikes", 1)  # Track strikes in persistent system
                
                # If max strikes reached, remove the download
                if current_strikes >= settings.get('max_strikes', 3):
                    swaparr_logger.warning(f"Max strikes reached for {item['name']}, removing download")
                    
                    if not settings.get("dry_run", False):
                        # Check if re-search is enabled for strike-based removals
                        trigger_search = settings.get("research_removed", False)
                        if delete_download(app_name, instance_data["api_url"], instance_data["api_key"], item["id"], True, item, trigger_search):
                            swaparr_logger.info(f"Successfully removed {item['name']} after {settings.get('max_strikes', 3)} strikes")
                            
                            # Keep the item in strike data for reference but mark as removed
                            strike_data[item_id]["removed"] = True
                            strike_data[item_id]["removed_time"] = datetime.utcnow().isoformat()
                            
                            # Add to removed items list for persistent tracking
                            removed_items[item_hash] = {
                                "name": item["name"],
                                "size": item["size"],
                                "removed_time": datetime.utcnow().isoformat(),
                                "reason": strike_reason
                            }
                            
                            # Note: Swaparr uses its own statistics system (SWAPARR_STATS), not the hunting stats manager
                    else:
                        swaparr_logger.info(f"DRY RUN: Would have removed {item['name']} after {settings.get('max_strikes', 3)} strikes")
                    
                    item_state = "Removed" if not settings.get("dry_run", False) else "Would Remove (Dry Run)"
                else:
                    item_state = f"Striked ({current_strikes}/{settings.get('max_strikes', 3)})"
            
            swaparr_logger.debug(f"Processed download: {item['name']} - State: {item_state}")
        
        # Save updated strike data
        save_strike_data(app_name, strike_data)
        
        # Save updated removed items list
        save_removed_items(app_name, removed_items)
        
        # Update last run time
        SWAPARR_STATS['last_run_time'] = datetime.utcnow().isoformat()
        
        swaparr_logger.info(f"Finished processing {items_processed_this_run} downloads for {app_name} instance: {instance_name}")
        swaparr_logger.info(f"Session stats - Strikes: {SWAPARR_STATS['strikes_added']}, Removed: {SWAPARR_STATS['downloads_removed']}, Ignored: {SWAPARR_STATS['items_ignored']}, API calls: {SWAPARR_STATS['api_calls_made']}")
        
        return items_processed_this_run
    except Exception as e:
        swaparr_logger.error(f"Error processing {app_name} instance {instance_name}: {str(e)}")
        SWAPARR_STATS['errors_encountered'] += 1
        return 0

def run_swaparr():
    """Run Swaparr cycle to check for stalled downloads in all configured Starr app instances"""
    from src.primary.apps.swaparr import get_configured_instances
    
    settings = load_settings("swaparr")
    
    if not settings or not settings.get("enabled", False):
        # Swaparr is disabled - no need to log this repeatedly
        return
    
    swaparr_logger.info("Starting Swaparr stalled download detection cycle")
    
    instances = get_configured_instances()
    total_instances = sum(len(app_instances) for app_instances in instances.values())
    
    # Count only Swaparr-enabled instances
    swaparr_enabled_count = 0
    for app_name, app_instances in instances.items():
        for app_settings in app_instances:
            if app_settings.get("swaparr_enabled", False):
                swaparr_enabled_count += 1
    
    if swaparr_enabled_count == 0:
        swaparr_logger.info(f"Found {total_instances} configured Starr app instances, but none have Swaparr enabled. Cycle complete.")
        return
    
    swaparr_logger.info(f"Found {swaparr_enabled_count} Swaparr-enabled instances out of {total_instances} total configured Starr app instances")
    
    # Process stalled downloads for each app type and instance
    processed_instances = 0
    swaparr_enabled_instances = 0
    
    for app_name, app_instances in instances.items():
        for app_settings in app_instances:
            # Debug log the swaparr_enabled status
            swaparr_enabled = app_settings.get("swaparr_enabled", False)
            instance_name = app_settings.get('instance_name', 'Unknown')
            swaparr_logger.debug(f"Checking {app_name} instance '{instance_name}' - swaparr_enabled: {swaparr_enabled}")
            
            # Skip instances that don't have Swaparr enabled
            if not swaparr_enabled:
                swaparr_logger.debug(f"Skipping {app_name} instance '{instance_name}' - Swaparr not enabled for this instance")
                continue
            
            swaparr_enabled_instances += 1
            swaparr_logger.info(f"Processing {app_name} instance '{instance_name}' - Swaparr enabled")
            
            # Check if Swaparr has been disabled during processing
            current_settings = load_settings("swaparr")
            if not current_settings or not current_settings.get("enabled", False):
                swaparr_logger.warning(f"Swaparr was disabled during processing. Ending cycle early after processing {processed_instances}/{swaparr_enabled_instances} Swaparr-enabled instances.")
                return
            
            try:
                items_processed = process_stalled_downloads(app_name, app_settings.get('instance_name', 'Unknown'), app_settings, current_settings)
                processed_instances += 1
                swaparr_logger.debug(f"Processed {items_processed} items from {app_name} instance '{app_settings.get('instance_name', 'Unknown')}'")
            except Exception as e:
                swaparr_logger.error(f"Error processing {app_name} instance {app_settings.get('instance_name', 'Unknown')}: {str(e)}")
                SWAPARR_STATS['errors_encountered'] += 1
                processed_instances += 1
    
    stats = get_session_stats()
    swaparr_logger.info(f"=== SWAPARR cycle completed. Processed {processed_instances} Swaparr-enabled app instances. ===")
    
    # Log summary stats if there was activity
    if stats['total_processed'] > 0:
        swaparr_logger.info(f"Swaparr activity summary: {stats['strikes_added']} strikes added, {stats['downloads_removed']} downloads removed, {stats['items_ignored']} items ignored") 