#!/usr/bin/env python3
"""
Arr API Helper Functions
Handles all communication with the Arr API
"""

import requests
import time
from typing import List, Dict, Any, Optional, Union
from primary.settings_manager import get_ssl_verify_setting
from primary.utils.logger import logger, debug_log
from primary.config import API_KEY, API_URL, API_TIMEOUT, COMMAND_WAIT_DELAY, COMMAND_WAIT_ATTEMPTS, APP_TYPE
from src.primary.stats_manager import get_stats, reset_stats

# Create a session for reuse
session = requests.Session()

def arr_request(endpoint: str, method: str = "GET", data: Dict = None) -> Optional[Union[Dict, List]]:
    """
    Make a request to the Arr API.
    `endpoint` should be something like 'series', 'command', 'wanted/cutoff', etc.
    """
    # Determine the API version based on app type
    if APP_TYPE == "sonarr":
        api_base = "api/v3"
    elif APP_TYPE == "radarr":
        api_base = "api/v3"
    elif APP_TYPE == "lidarr":
        api_base = "api/v1"
    elif APP_TYPE == "readarr":
        api_base = "api/v1"
    else:
        # Default to v3 for unknown app types
        api_base = "api/v3"
    
    url = f"{API_URL}/{api_base}/{endpoint}"
    headers = {
        "X-Api-Key": API_KEY,
        "Content-Type": "application/json"
    }

    # Get SSL verification setting
    verify_ssl = get_ssl_verify_setting()
    
    if not verify_ssl:
        logger.debug("SSL verification disabled by global user setting")
    
    try:
        if method.upper() == "GET":
            response = session.get(url, headers=headers, timeout=API_TIMEOUT, verify=verify_ssl)
        elif method.upper() == "POST":
            response = session.post(url, headers=headers, json=data, timeout=API_TIMEOUT, verify=verify_ssl)
        else:
            logger.error(f"Unsupported HTTP method: {method}")
            return None
        
        # Check for 401 Unauthorized or other error status codes
        if response.status_code == 401:
            logger.error(f"API request error: 401 Client Error: Unauthorized for url: {url}")
            return None
        
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"API request error: {e}")
        return None

def check_connection(app_type: str = None) -> bool:
    """
    Check if we can connect to the Arr API.
    Returns True if connection is successful, False otherwise.
    
    Args:
        app_type: Optional app type to check connection for (sonarr, radarr, etc.).
                 If None, uses the global APP_TYPE.
    """
    # Determine which app type to use
    current_app_type = app_type or APP_TYPE
    
    # Get API credentials for the specified app type
    from src.primary.settings_manager import load_settings
    settings = load_settings(current_app_type)
    if settings:
        api_url = settings.get('url', '')
        api_key = settings.get('api_key', '')
    else:
        api_url, api_key = '', ''
    
    # First explicitly check if API URL and Key are configured
    if not api_url:
        logger.error(f"API URL is not configured for {current_app_type} in settings. Please set it up in the Settings page.")
        return False
    
    if not api_key:
        logger.error(f"API Key is not configured for {current_app_type} in settings. Please set it up in the Settings page.")
        return False
    
    # Log what we're attempting to connect to
    logger.debug(f"Attempting to connect to {current_app_type.title()} at {api_url}")
    
    # Try to access the system/status endpoint which should be available on all Arr applications
    try:
        endpoint = "system/status"
            
        # Determine the API version based on app type
        if current_app_type == "sonarr":
            api_base = "api/v3"
        elif current_app_type == "radarr":
            api_base = "api/v3"
        elif current_app_type == "lidarr":
            api_base = "api/v1"
        elif current_app_type == "readarr":
            api_base = "api/v1"
        else:
            # Default to v3 for unknown app types
            api_base = "api/v3"
        
        url = f"{api_url}/{api_base}/{endpoint}"
        headers = {
            "X-Api-Key": api_key,
            "Content-Type": "application/json"
        }
        
        logger.debug(f"Testing connection with URL: {url}")

        # Get SSL verification setting
        verify_ssl = get_ssl_verify_setting()
        
        if not verify_ssl:
            logger.debug("SSL verification disabled by global user setting")

        response = session.get(url, headers=headers, timeout=API_TIMEOUT, verify=verify_ssl)
        
        if response.status_code == 401:
            logger.error(f"Connection test failed: 401 Client Error: Unauthorized - Invalid API key for {current_app_type.title()}")
            return False
            
        response.raise_for_status()
        logger.info(f"Connection to {current_app_type.title()} at {api_url} successful")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Connection test failed for {current_app_type}: {e}")
        return False

def wait_for_command(command_id: int):
    logger.debug(f"Waiting for command {command_id} to complete...")
    attempts = 0
    while True:
        try:
            time.sleep(COMMAND_WAIT_DELAY)
            response = arr_request(f"command/{command_id}")
            logger.debug(f"Command {command_id} Status: {response['status']}")
        except Exception as error:
            logger.error(f"Error fetching command status on attempt {attempts + 1}: {error}")
            return False

        attempts += 1

        if response['status'].lower() in ['complete', 'completed'] or attempts >= COMMAND_WAIT_ATTEMPTS:
            break

    if response['status'].lower() not in ['complete', 'completed']:
        logger.warning(f"Command {command_id} did not complete within the allowed attempts.")
        return False

    time.sleep(0.5)

    return response['status'].lower() in ['complete', 'completed']

# Sonarr-specific functions
def get_series() -> List[Dict]:
    """Get all series from Sonarr."""
    if APP_TYPE != "sonarr":
        logger.error("get_series() called but APP_TYPE is not sonarr")
        return []
    
    series_list = arr_request("series")
    if series_list:
        debug_log("Raw series API response sample:", series_list[:2] if len(series_list) > 2 else series_list)
    return series_list or []

def refresh_series(series_id: int) -> bool:
    """
    POST /api/v5/command
    {
      "name": "RefreshSeries",
      "seriesId": <series_id>
    }
    """
    if APP_TYPE != "sonarr":
        logger.error("refresh_series() called but APP_TYPE is not sonarr")
        return False
    
    data = {
        "name": "RefreshSeries",
        "seriesId": series_id
    }
    response = arr_request("command", method="POST", data=data)
    if not response or 'id' not in response:
        return False
    return wait_for_command(response['id'])

def episode_search_episodes(episode_ids: List[int]) -> bool:
    """
    POST /api/v5/command
    {
      "name": "EpisodeSearch",
      "episodeIds": [...]
    }
    """
    if APP_TYPE != "sonarr":
        logger.error("episode_search_episodes() called but APP_TYPE is not sonarr")
        return False
    
    data = {
        "name": "EpisodeSearch",
        "episodeIds": episode_ids
    }
    response = arr_request("command", method="POST", data=data)
    if not response or 'id' not in response:
        return False
    return wait_for_command(response['id'])

def get_download_queue_size() -> int:
    """
    GET /api/v5/queue
    Returns total number of items in the queue with the status 'downloading'.
    """
    # Endpoint is the same for all apps
    response = arr_request("queue?status=downloading")
    if not response:
        return 0
        
    total_records = response.get("totalRecords", 0)
    if not isinstance(total_records, int):
        total_records = 0
    logger.debug(f"Download Queue Size: {total_records}")

    return total_records

def get_cutoff_unmet(page: int = 1) -> Optional[Dict]:
    """
    GET /api/v5/wanted/cutoff?sortKey=airDateUtc&sortDirection=descending&includeSeriesInformation=true
        &page=<page>&pageSize=200
    Returns JSON with a "records" array and "totalRecords".
    """
    if APP_TYPE != "sonarr":
        logger.error("get_cutoff_unmet() called but APP_TYPE is not sonarr")
        return None
    
    endpoint = (
        "wanted/cutoff?"
        "sortKey=airDateUtc&sortDirection=descending&includeSeriesInformation=true"
        f"&page={page}&pageSize=200"
    )
    return arr_request(endpoint, method="GET")

def get_cutoff_unmet_total_pages() -> int:
    """
    To find total pages, call the endpoint with page=1&pageSize=1, read totalRecords,
    then compute how many pages if each pageSize=200.
    """
    if APP_TYPE != "sonarr":
        logger.error("get_cutoff_unmet_total_pages() called but APP_TYPE is not sonarr")
        return 0
    
    response = arr_request("wanted/cutoff?page=1&pageSize=1")
    if not response or "totalRecords" not in response:
        return 0
    
    total_records = response.get("totalRecords", 0)
    if not isinstance(total_records, int) or total_records < 1:
        return 0
    
    # Each page has up to 200 episodes
    total_pages = (total_records + 200 - 1) // 200
    return max(total_pages, 1)

def get_episodes_for_series(series_id: int) -> Optional[List[Dict]]:
    """Get all episodes for a specific series"""
    if APP_TYPE != "sonarr":
        logger.error("get_episodes_for_series() called but APP_TYPE is not sonarr")
        return None
    
    return arr_request(f"episode?seriesId={series_id}", method="GET")

def get_missing_episodes(pageSize: int = 1000) -> Optional[Dict]:
    """
    GET /api/v5/wanted/missing?pageSize=<pageSize>&includeSeriesInformation=true
    Returns JSON with a "records" array of missing episodes and "totalRecords".
    """
    if APP_TYPE != "sonarr":
        logger.error("get_missing_episodes() called but APP_TYPE is not sonarr")
        return None
    
    endpoint = f"wanted/missing?pageSize={pageSize}&includeSeriesInformation=true"
    result = arr_request(endpoint, method="GET")
    
    # Better debugging for missing episodes query
    if result:
        logger.debug(f"Found {result.get('totalRecords', 0)} total missing episodes")
        if result.get('records'):
            logger.debug(f"First few missing episodes: {result['records'][:2] if len(result['records']) > 2 else result['records']}")
    else:
        logger.warning("Missing episodes query returned no data")
    
    return result

def get_series_with_missing_episodes() -> List[Dict]:
    """
    Fetch all shows that have missing episodes using the wanted/missing endpoint.
    Returns a list of series objects with an additional 'missingEpisodes' field 
    containing the list of missing episodes for that series.
    """
    if APP_TYPE != "sonarr":
        logger.error("get_series_with_missing_episodes() called but APP_TYPE is not sonarr")
        return []
    
    # Log request attempt
    logger.debug("Requesting missing episodes from Sonarr API")
    
    missing_data = get_missing_episodes()
    if not missing_data or "records" not in missing_data:
        logger.error("Failed to get missing episodes data or no 'records' field in response")
        return []
    
    # Group missing episodes by series ID
    series_with_missing = {}
    for episode in missing_data.get("records", []):
        series_id = episode.get("seriesId")
        if not series_id:
            logger.warning(f"Found episode without seriesId: {episode}")
            continue
            
        series_title = None
        
        # Try to get series info from the episode record
        if "series" in episode and isinstance(episode["series"], dict):
            series_info = episode["series"]
            series_title = series_info.get("title")
            
            # Initialize the series entry if it doesn't exist
            if series_id not in series_with_missing:
                series_with_missing[series_id] = {
                    "id": series_id,
                    "title": series_title or "Unknown Show",
                    "monitored": series_info.get("monitored", False),
                    "missingEpisodes": []
                }
        else:
            # If we don't have series info, need to fetch it
            if series_id not in series_with_missing:
                # Get series info directly
                series_info = arr_request(f"series/{series_id}", method="GET")
                if series_info:
                    series_with_missing[series_id] = {
                        "id": series_id,
                        "title": series_info.get("title", "Unknown Show"),
                        "monitored": series_info.get("monitored", False),
                        "missingEpisodes": []
                    }
                else:
                    logger.warning(f"Could not get series info for ID {series_id}, skipping episode")
                    continue
        
        # Add the episode to the series record
        if series_id in series_with_missing:
            series_with_missing[series_id]["missingEpisodes"].append(episode)
    
    # Convert to list and add count for convenience
    result = []
    for series_id, series_data in series_with_missing.items():
        series_data["missingEpisodeCount"] = len(series_data["missingEpisodes"])
        result.append(series_data)
    
    logger.debug(f"Processed missing episodes data into {len(result)} series with missing episodes")
    return result

def get_media_stats():
    """Get statistics for hunted and upgraded media"""
    try:
        stats = get_stats()
        return jsonify({
            "success": True,
            "stats": stats
        })
    except Exception as e:
        logger.error(f"Error retrieving media statistics: {e}")
        return jsonify({
            "success": False,
            "message": "Error retrieving media statistics."
        }), 500
        
def reset_media_stats():
    """Reset statistics for hunted and upgraded media"""
    try:
        app_type = request.json.get('app_type') if request.json else None
        reset_stats(app_type)
        return jsonify({
            "success": True,
            "message": f"Successfully reset statistics for {'all apps' if app_type is None else app_type}."
        })
    except Exception as e:
        logger.error(f"Error resetting media statistics: {e}")
        return jsonify({
            "success": False,
            "message": "Error resetting media statistics."
        }), 500