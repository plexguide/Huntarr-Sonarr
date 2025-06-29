#!/usr/bin/env python3
"""
Eros-specific API functions
Handles all communication with the Eros API

Exclusively uses the Eros API v3
"""

import requests
import json
import time
import datetime
import traceback
import sys
from typing import List, Dict, Any, Optional, Union
from src.primary.utils.logger import get_logger
from src.primary.settings_manager import get_ssl_verify_setting

# Get logger for the Eros app
eros_logger = get_logger("eros")

# Use a session for better performance
session = requests.Session()

def arr_request(api_url: str, api_key: str, api_timeout: int, endpoint: str, method: str = "GET", count_api: bool = True, data: Optional[Dict] = None, params: Optional[Dict] = None) -> Any:
    """
    Make a request to the Eros API.
    
    Args:
        api_url: The base URL of the Eros API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        endpoint: The API endpoint to call
        method: HTTP method (GET, POST, PUT, DELETE)
        data: Optional data payload for POST/PUT requests
    
    Returns:
        The parsed JSON response or None if the request failed
    """
    try:
        if not api_url or not api_key:
            eros_logger.error("No URL or API key provided")
            return None
        
        # Ensure api_url has a scheme
        if not (api_url.startswith('http://') or api_url.startswith('https://')):
            eros_logger.error(f"Invalid URL format: {api_url} - URL must start with http:// or https://")
            return None
            
        # Construct the full URL properly
        full_url = f"{api_url.rstrip('/')}/api/v3/{endpoint.lstrip('/')}"
        
    
        
        # Set up headers with User-Agent to identify Huntarr
        headers = {
            "X-Api-Key": api_key,
            "Content-Type": "application/json",
            "User-Agent": "Huntarr/1.0 (https://github.com/plexguide/Huntarr.io)"
        }
        
        # Get SSL verification setting
        verify_ssl = get_ssl_verify_setting()
        
        if not verify_ssl:
            eros_logger.debug("SSL verification disabled by user setting")
        
        try:
            if method.upper() == "GET":
                response = session.get(full_url, headers=headers, timeout=api_timeout, verify=verify_ssl)
            elif method.upper() == "POST":
                response = session.post(full_url, headers=headers, json=data, timeout=api_timeout, verify=verify_ssl)
            elif method.upper() == "PUT":
                response = session.put(full_url, headers=headers, json=data, timeout=api_timeout, verify=verify_ssl)
            elif method.upper() == "DELETE":
                response = session.delete(full_url, headers=headers, timeout=api_timeout, verify=verify_ssl)
            else:
                eros_logger.error(f"Unsupported HTTP method: {method}")
                return None
            
            # Check if the request was successful
            try:
                response.raise_for_status()
                
                # Increment API counter only if count_api is True and request was successful
                if count_api:
                    try:
                        from src.primary.stats_manager import increment_hourly_cap
                        increment_hourly_cap("eros")
                    except Exception as e:
                        eros_logger.warning(f"Failed to increment API counter for eros: {e}")
                        
            except requests.exceptions.HTTPError as e:
                eros_logger.error(f"Error during {method} request to {endpoint}: {e}, Status Code: {response.status_code}")
                eros_logger.debug(f"Response content: {response.text[:200]}")
                return None
            
            # Try to parse JSON response
            try:
                if response.text:
                    result = response.json()
                    eros_logger.debug(f"Response from {response.url}: Status {response.status_code}, JSON parsed successfully")
                    return result
                else:
                    eros_logger.debug(f"Response from {response.url}: Status {response.status_code}, Empty response")
                    return {}
            except json.JSONDecodeError:
                eros_logger.error(f"Invalid JSON response from API: {response.text[:200]}")
                return None
            
        except requests.exceptions.RequestException as e:
            eros_logger.error(f"Request failed: {e}")
            return None
    except Exception as e:
        eros_logger.error(f"Unexpected error during API request: {e}")
        return None

def get_download_queue_size(api_url: str, api_key: str, api_timeout: int) -> int:
    """
    Get the current size of the download queue.

    Args:
        api_url: The base URL of the Eros API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request

    Returns:
        The number of items in the download queue, or -1 if the request failed
    """
    response = arr_request(api_url, api_key, api_timeout, "queue", count_api=False)
    
    if response is None:
        return -1
    
    # V3 API returns a list directly
    if isinstance(response, list):
        return len(response)
    # Fallback to records format if needed
    elif isinstance(response, dict) and "records" in response:
        return len(response["records"])
    else:
        return -1

def get_items_with_missing(api_url: str, api_key: str, api_timeout: int, monitored_only: bool, search_mode: str = "movie") -> List[Dict[str, Any]]:
    """
    Get a list of items with missing files (not downloaded/available).

    Args:
        api_url: The base URL of the Eros API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        monitored_only: If True, only return monitored items.
        search_mode: The search mode to use - 'movie' for movie-based or 'scene' for scene-based

    Returns:
        A list of item objects with missing files, or None if the request failed.
    """
    try:
        eros_logger.debug(f"Retrieving missing items using search mode: {search_mode}...")
        
        if search_mode == "movie":
            # In movie mode, we get all movies and filter for ones without files
            endpoint = "movie"
            
            response = arr_request(api_url, api_key, api_timeout, endpoint, count_api=False)
            
            if response is None:
                return None
            
            # Extract the movies with missing files
            items = []
            if isinstance(response, list):
                # Filter for movies that don't have files (hasFile = false)
                items = [item for item in response if not item.get("hasFile", True)]
            elif isinstance(response, dict) and "records" in response:
                # Fallback to old format if somehow it returns in this format
                items = [item for item in response["records"] if not item.get("hasFile", True)]
        
        elif search_mode == "scene":
            # In scene mode, we try to use scene-specific endpoints
            # First check if the movie-scene endpoint exists
            endpoint = "scene/missing?pageSize=1000"
            
            response = arr_request(api_url, api_key, api_timeout, endpoint, count_api=False)
            
            if response is None:
                # Fallback to regular movie filtering if scene endpoint doesn't exist
                eros_logger.warning("Scene endpoint not available, falling back to movie mode")
                return get_items_with_missing(api_url, api_key, api_timeout, monitored_only, "movie")
            
            # Extract the scenes
            items = []
            if isinstance(response, dict) and "records" in response:
                items = response["records"]
            elif isinstance(response, list):
                items = response
        
        else:
            # Invalid search mode
            eros_logger.error(f"Invalid search mode: {search_mode}. Must be 'movie' or 'scene'")
            return None
        
        # Filter monitored if needed
        if monitored_only:
            items = [item for item in items if item.get("monitored", False)]
        
        eros_logger.debug(f"Found {len(items)} missing items using {search_mode} mode")
        
        return items
        
    except Exception as e:
        eros_logger.error(f"Error retrieving missing items: {str(e)}")
        return None

def get_cutoff_unmet_items(api_url: str, api_key: str, api_timeout: int, monitored_only: bool) -> List[Dict[str, Any]]:
    """
    Get a list of items that don't meet their quality profile cutoff.

    Args:
        api_url: The base URL of the Eros API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        monitored_only: If True, only return monitored items.

    Returns:
        A list of item objects that need quality upgrades, or None if the request failed.
    """
    try:
        eros_logger.debug(f"Retrieving cutoff unmet items...")
        
        # Endpoint
        endpoint = "wanted/cutoff?pageSize=1000&sortKey=airDateUtc&sortDirection=descending"
        
        response = arr_request(api_url, api_key, api_timeout, endpoint, count_api=False)
        
        if response is None:
            return None
        
        # Extract the episodes/items
        items = []
        if isinstance(response, dict) and "records" in response:
            items = response["records"]
        elif isinstance(response, list):
            items = response
        
        eros_logger.debug(f"Found {len(items)} cutoff unmet items")
        
        # Just filter monitored if needed
        if monitored_only:
            items = [item for item in items if item.get("monitored", False)]
            eros_logger.debug(f"Found {len(items)} cutoff unmet items after filtering monitored")
        
        return items
        
    except Exception as e:
        eros_logger.error(f"Error retrieving cutoff unmet items: {str(e)}")
        return None

def get_quality_upgrades(api_url: str, api_key: str, api_timeout: int, monitored_only: bool, search_mode: str = "movie") -> List[Dict[str, Any]]:
    """
    Get a list of items that can be upgraded to better quality.

    Args:
        api_url: The base URL of the Eros API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        monitored_only: If True, only return monitored items.
        search_mode: The search mode to use - 'movie' for movie-based or 'scene' for scene-based

    Returns:
        A list of item objects that need quality upgrades, or None if the request failed.
    """
    try:
        eros_logger.debug(f"Retrieving quality upgrade items using search mode: {search_mode}...")
        
        if search_mode == "movie":
            # In movie mode, we get all movies and filter for ones that have files but need quality upgrades
            endpoint = "movie"
            
            response = arr_request(api_url, api_key, api_timeout, endpoint, count_api=False)
            
            if response is None:
                return None
            
            # Extract movies that have files but need quality upgrades
            items = []
            if isinstance(response, list):
                # Filter for movies that have files but haven't met quality cutoff
                items = [item for item in response if item.get("hasFile", False) and item.get("qualityCutoffNotMet", False)]
            elif isinstance(response, dict) and "records" in response:
                # Fallback to old format if somehow it returns in this format
                items = [item for item in response["records"] if item.get("hasFile", False) and item.get("qualityCutoffNotMet", False)]
        
        elif search_mode == "scene":
            # In scene mode, try to use scene-specific endpoints
            endpoint = "scene/cutoff?pageSize=1000"
            
            response = arr_request(api_url, api_key, api_timeout, endpoint, count_api=False)
            
            if response is None:
                # Fallback to regular movie filtering if scene endpoint doesn't exist
                eros_logger.warning("Scene cutoff endpoint not available, falling back to movie mode")
                return get_quality_upgrades(api_url, api_key, api_timeout, monitored_only, "movie")
            
            # Extract the scenes
            items = []
            if isinstance(response, dict) and "records" in response:
                items = response["records"]
            elif isinstance(response, list):
                items = response
                
        else:
            # Invalid search mode
            eros_logger.error(f"Invalid search mode: {search_mode}. Must be 'movie' or 'scene'")
            return None
        
        # Filter monitored if needed
        if monitored_only:
            items = [item for item in items if item.get("monitored", False)]
            
        eros_logger.debug(f"Found {len(items)} quality upgrade items using {search_mode} mode")
        
        return items
        
    except Exception as e:
        eros_logger.error(f"Error retrieving quality upgrade items: {str(e)}")
        return None

def refresh_item(api_url: str, api_key: str, api_timeout: int, item_id: int) -> int:
    """
    Refresh functionality has been removed as it was a performance bottleneck.
    This function now returns a placeholder command ID without making any API calls.
    
    Args:
        api_url: The base URL of the Whisparr V3 API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        item_id: The ID of the movie to refresh
        
    Returns:
        A placeholder command ID (123) to simulate success
    """
    eros_logger.debug(f"Refresh functionality disabled for movie ID: {item_id}")
    # Return a placeholder command ID to simulate success without actually refreshing
    return 123

def item_search(api_url: str, api_key: str, api_timeout: int, item_ids: List[int], verify_ssl: Optional[bool] = None) -> int:
    """
    Trigger a search for one or more movies in Whisparr V3.
    
    Args:
        api_url: The base URL of the Whisparr V3 API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        item_ids: A list of movie IDs to search for
        
    Returns:
        The command ID if the search command was triggered successfully, None otherwise
    """
    
    # Check API limit before making request
    try:
        from src.primary.stats_manager import check_hourly_cap_exceeded
        if check_hourly_cap_exceeded("eros"):
            eros_logger.warning(f"🛑 Eros API hourly limit reached - skipping item search for {len(item_ids)} items")
            return None
    except Exception as e:
        eros_logger.error(f"Error checking hourly API cap: {e}")
        # Continue with request if cap check fails - safer than skipping
    
    try:
        if not item_ids:
            eros_logger.warning("No movie IDs provided for search.")
            return None
            
        eros_logger.debug(f"Searching for movies with IDs: {item_ids}")

        # Try several possible command formats, as the API might be in flux
        possible_commands = [
            {"name": "MoviesSearch", "movieIds": item_ids},  # Standard movie search
            {"name": "MovieSearch", "movieIds": item_ids},   # Alternative format
            {"name": "EpisodeSearch", "episodeIds": item_ids}  # Fallback to episode format
        ]
        
        command_endpoint = "command"
        
        # Try each command format until one works
        for i, payload in enumerate(possible_commands):
            eros_logger.debug(f"Trying search command format {i+1}: {payload}")
            
            # Make the API request
            response = arr_request(api_url, api_key, api_timeout, command_endpoint, "POST", payload, verify_ssl=verify_ssl)
            
            if response and "id" in response:
                command_id = response["id"]
                eros_logger.debug(f"Search command format {i+1} succeeded with ID {command_id}")
                
                # Increment API counter after successful request
                try:
                    from src.primary.stats_manager import increment_hourly_cap
                    increment_hourly_cap("eros", 1)
                    eros_logger.debug(f"Incremented Eros hourly API cap for item search ({len(item_ids)} items)")
                except Exception as cap_error:
                    eros_logger.error(f"Failed to increment hourly API cap for item search: {cap_error}")
                
                return command_id
                
        # If we've tried all formats and none worked:
        eros_logger.error("All search command formats failed - no command ID returned")
        return None
            
    except Exception as e:
        eros_logger.error(f"Error searching for movies: {str(e)}")
        return None

def get_command_status(api_url: str, api_key: str, api_timeout: int, command_id: int) -> Optional[Dict]:
    """
    Get the status of a specific command.

    Args:
        api_url: The base URL of the Eros API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        command_id: The ID of the command to check

    Returns:
        A dictionary containing the command status, or None if the request failed.
    """
    if not command_id:
        eros_logger.error("No command ID provided for status check.")
        return None
        
    try:
        command_endpoint = f"command/{command_id}"
        
        # Make the API request
        result = arr_request(api_url, api_key, api_timeout, command_endpoint, count_api=False)
        
        if result:
            eros_logger.debug(f"Command {command_id} status: {result.get('status', 'unknown')}")
            return result
        else:
            eros_logger.error(f"Failed to get command status for ID {command_id}")
            return None
            
    except Exception as e:
        eros_logger.error(f"Error getting command status for ID {command_id}: {e}")
        return None

def check_connection(api_url: str, api_key: str, api_timeout: int) -> bool:
    """
    Check the connection to Whisparr V3 API.
    
    Args:
        api_url: The base URL of the Whisparr V3 API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        verify_ssl: Whether to verify SSL certificates (overrides global setting if provided)
        
    Returns:
        True if the connection is successful, False otherwise
    """
    try:
        eros_logger.debug(f"Checking connection to Whisparr V3 instance at {api_url}")
        
        endpoint = "system/status"
        response = arr_request(api_url, api_key, api_timeout, endpoint, count_api=False)
        
        if response is not None:
            # Get the version information if available
            version = response.get("version", "unknown")
            
            # Simply check if we received a valid response - Whisparr V3 is in development
            # so the version number might be in various formats
            if version and isinstance(version, str):
                eros_logger.debug(f"Successfully connected to Whisparr V3 API, reported version: {version}")
                return True
            else:
                eros_logger.warning(f"Connected to server but found unexpected version format: {version}")
                return False
        else:
            eros_logger.error("Failed to connect to Whisparr V3 API")
            return False
            
    except Exception as e:
        eros_logger.error(f"Error checking connection to Whisparr V3 API: {str(e)}")
        return False

def get_or_create_tag(api_url: str, api_key: str, api_timeout: int, tag_label: str) -> Optional[int]:
    """
    Get existing tag ID or create a new tag in Eros.
    
    Args:
        api_url: The base URL of the Eros API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        tag_label: The label/name of the tag to create or find
        
    Returns:
        The tag ID if successful, None otherwise
    """
    try:
        # First, check if the tag already exists
        response = arr_request(api_url, api_key, api_timeout, "tag", count_api=False)
        if response:
            for tag in response:
                if tag.get('label') == tag_label:
                    tag_id = tag.get('id')
                    eros_logger.debug(f"Found existing tag '{tag_label}' with ID: {tag_id}")
                    return tag_id
        
        # Tag doesn't exist, create it
        tag_data = {"label": tag_label}
        response = arr_request(api_url, api_key, api_timeout, "tag", method="POST", data=tag_data, count_api=False)
        if response and 'id' in response:
            tag_id = response['id']
            eros_logger.info(f"Created new tag '{tag_label}' with ID: {tag_id}")
            return tag_id
        else:
            eros_logger.error(f"Failed to create tag '{tag_label}'. Response: {response}")
            return None
            
    except Exception as e:
        eros_logger.error(f"Error managing tag '{tag_label}': {e}")
        return None

def add_tag_to_movie(api_url: str, api_key: str, api_timeout: int, movie_id: int, tag_id: int) -> bool:
    """
    Add a tag to a movie in Eros.
    
    Args:
        api_url: The base URL of the Eros API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        movie_id: The ID of the movie to tag
        tag_id: The ID of the tag to add
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # First get the current movie data
        movie_data = arr_request(api_url, api_key, api_timeout, f"movie/{movie_id}", count_api=False)
        if not movie_data:
            eros_logger.error(f"Failed to get movie data for ID: {movie_id}")
            return False
        
        # Check if the tag is already present
        current_tags = movie_data.get('tags', [])
        if tag_id in current_tags:
            eros_logger.debug(f"Tag {tag_id} already exists on movie {movie_id}")
            return True
        
        # Add the new tag to the list
        current_tags.append(tag_id)
        movie_data['tags'] = current_tags
        
        # Update the movie with the new tags
        response = arr_request(api_url, api_key, api_timeout, f"movie/{movie_id}", method="PUT", data=movie_data, count_api=False)
        if response:
            eros_logger.debug(f"Successfully added tag {tag_id} to movie {movie_id}")
            return True
        else:
            eros_logger.error(f"Failed to update movie {movie_id} with tag {tag_id}")
            return False
            
    except Exception as e:
        eros_logger.error(f"Error adding tag {tag_id} to movie {movie_id}: {e}")
        return False

def tag_processed_movie(api_url: str, api_key: str, api_timeout: int, movie_id: int, tag_label: str = "huntarr-missing") -> bool:
    """
    Tag a movie in Eros with the specified tag.
    
    Args:
        api_url: The base URL of the Eros API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        movie_id: The ID of the movie to tag
        tag_label: The tag to apply (huntarr-missing, huntarr-upgraded)
        
    Returns:
        True if the tagging was successful, False otherwise
    """
    try:
        # Get or create the tag
        tag_id = get_or_create_tag(api_url, api_key, api_timeout, tag_label)
        if tag_id is None:
            eros_logger.error(f"Failed to get or create tag '{tag_label}' in Eros")
            return False
            
        # Add the tag to the movie
        success = add_tag_to_movie(api_url, api_key, api_timeout, movie_id, tag_id)
        if success:
            eros_logger.debug(f"Successfully tagged Eros movie {movie_id} with '{tag_label}'")
            return True
        else:
            eros_logger.error(f"Failed to add tag '{tag_label}' to Eros movie {movie_id}")
            return False
            
    except Exception as e:
        eros_logger.error(f"Error tagging Eros movie {movie_id} with '{tag_label}': {e}")
        return False

def get_quality_profiles(api_url: str, api_key: str, api_timeout: int) -> Optional[List[Dict]]:
    """
    Get all quality profiles configured in Eros.

    Args:
        api_url: The base URL of the Eros API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request

    Returns:
        A list of quality profile objects, or None if the request failed.
        Each profile contains: id, name, upgradeAllowed, cutoff, items, etc.
    """
    try:
        eros_logger.debug("Fetching quality profiles from Eros...")
        
        # Use the qualityProfile endpoint - this doesn't count toward API limits since it's configuration data
        profiles = arr_request(api_url, api_key, api_timeout, "qualityProfile", count_api=False)
        
        if profiles is None:
            eros_logger.error("Failed to retrieve quality profiles from Eros API.")
            return None
        
        eros_logger.debug(f"Found {len(profiles)} quality profiles in Eros")
        
        # Log profile names for debugging
        profile_names = [profile.get('name', 'Unknown') for profile in profiles]
        eros_logger.debug(f"Quality profiles: {', '.join(profile_names)}")
        
        return profiles
        
    except Exception as e:
        eros_logger.error(f"Error retrieving quality profiles: {str(e)}")
        return None
