#!/usr/bin/env python3
"""
Lidarr-specific API functions
Handles all communication with the Lidarr API (v1)
"""

import requests
import json
import sys
import time
import datetime
import traceback
import logging
from typing import List, Dict, Any, Optional, Union
from src.primary.utils.logger import get_logger, debug_log
from src.primary import settings_manager

# Get logger for the Lidarr app
lidarr_logger = get_logger("lidarr")

# Use a session for better performance
session = requests.Session()

def get_ssl_verify_setting() -> bool:
    """Get SSL verification setting from general configuration."""
    try:
        general_settings = settings_manager.load_settings("general")
        return general_settings.get("ssl_verify", True)  # Default to True for security
    except Exception as e:
        lidarr_logger.warning(f"Error getting SSL verify setting: {e}. Using default (True).")
        return True

def arr_request(api_url: str, api_key: str, api_timeout: int, endpoint: str, method: str = "GET", data: Dict = None, params: Dict = None, count_api: bool = True) -> Any:
    """
    Generic function to make requests to Lidarr API (V1).
    
    Args:
        api_url: The base URL of the Lidarr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        endpoint: The API endpoint to call
        method: HTTP method (GET, POST, PUT, DELETE)
        data: Data to send in the request body (for POST/PUT)
        params: Query parameters
        
    Returns:
        JSON response data, True for successful non-JSON responses, or None on error
    """
    try:
        # Clean up the URL - ensure no double slashes
        base_url = api_url.rstrip('/')
        clean_endpoint = endpoint.lstrip('/')
        
        # Construct full URL with V1 API prefix for Lidarr
        full_url = f"{base_url}/api/v1/{clean_endpoint}"       

        # Set up headers with User-Agent to identify Huntarr
        headers = {
            "X-Api-Key": api_key,
            "Content-Type": "application/json",
            "User-Agent": "Huntarr/1.0 (https://github.com/plexguide/Huntarr.io)"
        }

        lidarr_logger.debug(f"Using User-Agent: {headers['User-Agent']}")

        # Get SSL verification setting
        verify_ssl = get_ssl_verify_setting()

        if not verify_ssl:
            lidarr_logger.debug("SSL verification disabled by user setting")

        lidarr_logger.debug(f"Lidarr API Request: {method} {full_url} Params: {params} Data: {data}")

        response = session.request(
            method=method.upper(),
            url=full_url,
            headers=headers,
            json=data if data else None,
            params=params if method.upper() == "GET" else None,
            timeout=api_timeout,
            verify=verify_ssl
        )
            
        lidarr_logger.debug(f"Lidarr API Response Status: {response.status_code}")
        # Use the improved debug_log function to safely log response data
        if response.content and len(response.content) < 2000:
            try:
                response_data = response.json()
                debug_log(f"Lidarr API Response from {endpoint}", response_data, "lidarr")
            except json.JSONDecodeError:
                # If it's not JSON, log safely as text but truncated
                debug_log(f"Lidarr API Response (non-JSON) from {endpoint}", response.text[:500], "lidarr")
        elif response.content:
            lidarr_logger.debug(f"Lidarr API Response: Large response ({len(response.content)} bytes) - not logging content")

        # Check for successful response
        response.raise_for_status()
        
        # Increment API counter only if count_api is True and request was successful
        if count_api:
            try:
                from src.primary.stats_manager import increment_hourly_cap
                increment_hourly_cap("lidarr")
            except Exception as e:
                lidarr_logger.warning(f"Failed to increment API counter for lidarr: {e}")
            
        # Parse response if there is content
        if response.content and response.headers.get('Content-Type', '').startswith('application/json'):
            return response.json()
        elif response.status_code in [200, 201, 202]: # Success codes that might not return JSON
            return True 
        else: # Should have been caught by raise_for_status, but as a fallback
            lidarr_logger.warning(f"Request successful (status {response.status_code}) but no JSON content returned from {endpoint}")
            return True # Indicate success even without content
                
    except requests.exceptions.RequestException as e:
        error_msg = f"Error during {method} request to Lidarr endpoint '{endpoint}': {str(e)}"
        if e.response is not None:
             error_msg += f" | Status: {e.response.status_code} | Response: {e.response.text[:500]}"
        lidarr_logger.error(error_msg)
        return None
    except json.JSONDecodeError:
        lidarr_logger.error(f"Error decoding JSON response from Lidarr endpoint '{endpoint}'. Response: {response.text[:500]}")
        return None
            
    except Exception as e:
        # Catch all exceptions and log them with traceback
        error_msg = f"CRITICAL ERROR in Lidarr arr_request: {str(e)}"
        lidarr_logger.error(error_msg)
        lidarr_logger.error(f"Full traceback: {traceback.format_exc()}")
        print(error_msg, file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        return None

# --- Specific API Functions ---

def get_system_status(api_url: str, api_key: str, api_timeout: int) -> Dict:
    """
    Get Lidarr system status.
    
    Args:
        api_url: The base URL of the Lidarr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        
    Returns:
        System status information or empty dict if request failed
    """

    try:
        # For Lidarr, use V1 API
        endpoint = f"{api_url.rstrip('/')}/api/v1/system/status"
        
        response = arr_request(api_url, api_key, api_timeout, "system/status", method="GET")
        
        # Parse and return the result
        return response
    except Exception as e:
        lidarr_logger.error(f"Error getting system status: {str(e)}")
        return {}

def check_connection(api_url: str, api_key: str, api_timeout: int) -> bool:
    """Checks connection by fetching system status."""
    if not api_url:
        lidarr_logger.error("API URL is empty or not set")
        return False
    if not api_key:
        lidarr_logger.error("API Key is empty or not set")
        return False

    try:
        # Use a shorter timeout for a quick connection check
        quick_timeout = min(api_timeout, 15) 

        status = get_system_status(api_url, api_key, quick_timeout)
        if status and isinstance(status, dict) and 'version' in status:
             # Log success only if debug is enabled to avoid clutter
             lidarr_logger.debug(f"Connection check successful for {api_url}. Version: {status.get('version')}")
             return True
        else:
             # Log details if the status response was unexpected
             lidarr_logger.warning(f"Connection check for {api_url} returned unexpected status: {str(status)[:200]}")
             return False
    except Exception as e:
        lidarr_logger.error(f"Connection check failed for {api_url}")
        return False

def get_artists(api_url: str, api_key: str, api_timeout: int, artist_id: Optional[int] = None) -> Union[List, Dict, None]:
    """Get artist information from Lidarr."""
    endpoint = f"artist/{artist_id}" if artist_id else "artist"
    return arr_request(api_url, api_key, api_timeout, endpoint, count_api=False)

def get_albums(api_url: str, api_key: str, api_timeout: int, album_id: Optional[int] = None, artist_id: Optional[int] = None) -> Union[List, Dict, None]:
    """Get album information from Lidarr."""
    params = {}
    if artist_id:
        params['artistId'] = artist_id
        
    if album_id:
        endpoint = f"album/{album_id}"
    else:
        endpoint = "album"
        
    return arr_request(api_url, api_key, api_timeout, endpoint, params=params if params else None, count_api=False)

def get_tracks(api_url: str, api_key: str, api_timeout: int, album_id: Optional[int] = None) -> Union[List, None]:
     """Get track information for a specific album."""
     if not album_id:
         lidarr_logger.warning("get_tracks requires an album_id.")
         return None
     params = {'albumId': album_id}
     return arr_request(api_url, api_key, api_timeout, "track", params=params, count_api=False)

def get_queue(api_url: str, api_key: str, api_timeout: int) -> List:
    """Get the current queue from Lidarr (handles pagination)."""
    # Lidarr v1 queue endpoint supports pagination, unlike Sonarr v3's simple list
    all_records = []
    page = 1
    page_size = 1000 # Request large page size

    while True:
        params = {
            "page": page,
            "pageSize": page_size,
            "sortKey": "timeleft", # Example sort key
            "sortDir": "asc"
        }
        response = arr_request(api_url, api_key, api_timeout, "queue", params=params, count_api=False)
        
        if response and isinstance(response, dict) and 'records' in response:
            records = response.get('records', [])
            if not records:
                break # No more records
            all_records.extend(records)
            
            # Check if this was the last page
            total_records = response.get('totalRecords', 0)
            if len(all_records) >= total_records:
                break
            
            page += 1
        else:
            lidarr_logger.error(f"Failed to get queue page {page} or invalid response format.")
            break # Return what we have so far
            
    return all_records

def get_download_queue_size(api_url: str, api_key: str, api_timeout: int) -> int:
    """Get the current size of the Lidarr download queue."""
    params = {"pageSize": 1} # Only need 1 record to get totalRecords
    response = arr_request(api_url, api_key, api_timeout, "queue", params=params, count_api=False)
    
    if response and isinstance(response, dict) and 'totalRecords' in response:
        queue_size = response.get('totalRecords', 0)
        lidarr_logger.debug(f"Lidarr download queue size: {queue_size}")
        return queue_size
    else:
        lidarr_logger.error("Error getting Lidarr download queue size.")
        return -1 # Indicate error

def get_missing_albums(api_url: str, api_key: str, api_timeout: int, monitored_only: bool) -> List[Dict[str, Any]]:
    """Get missing albums from Lidarr, handling pagination."""
    endpoint = "wanted/missing"
    page = 1
    page_size = 1000 
    all_missing_albums = []
    total_records_reported = -1

    lidarr_logger.debug(f"Starting fetch for missing albums (monitored_only={monitored_only}).")

    while True:
        params = {
            "page": page,
            "pageSize": page_size,
            "includeArtist": "true" # Include artist info for filtering
            # Removed sortKey and sortDir
        }
        
        lidarr_logger.debug(f"Requesting missing albums page {page} with params: {params}")
        response = arr_request(api_url, api_key, api_timeout, endpoint, params=params, count_api=False)

        if response and isinstance(response, dict) and 'records' in response:
            records = response.get('records', [])
            total_records_on_page = len(records)

            if page == 1:
                total_records_reported = response.get('totalRecords', 0)
                lidarr_logger.debug(f"Lidarr API reports {total_records_reported} total missing albums.")

            lidarr_logger.debug(f"Parsed {total_records_on_page} missing album records from Lidarr API JSON (page {page}).")

            if not records:
                lidarr_logger.debug(f"No more missing records found on page {page}. Stopping pagination.")
                break

            all_missing_albums.extend(records)

            if total_records_reported >= 0 and len(all_missing_albums) >= total_records_reported:
                lidarr_logger.debug(f"Fetched {len(all_missing_albums)} records, matching or exceeding total reported ({total_records_reported}). Assuming last page.")
                break

            if total_records_on_page < page_size:
                lidarr_logger.debug(f"Received {total_records_on_page} records (less than page size {page_size}). Assuming last page.")
                break
                
            page += 1
            # time.sleep(0.1) # Optional delay

        else:
            lidarr_logger.error(f"Failed to get missing albums page {page} or invalid response format.")
            break # Return what we have so far
            
    lidarr_logger.info(f"Total missing albums fetched across all pages: {len(all_missing_albums)}")

    # Apply monitored filter after fetching
    if monitored_only:
        original_count = len(all_missing_albums)
        # Check both album and artist monitored status
        filtered_missing = [
            album for album in all_missing_albums
            if album.get('monitored', False) and album.get('artist', {}).get('monitored', False)
        ]
        lidarr_logger.debug(f"Filtered for monitored_only=True: {len(filtered_missing)} monitored missing albums remain (out of {original_count} total).")
        return filtered_missing
    else:
        lidarr_logger.debug(f"Returning {len(all_missing_albums)} missing albums (monitored_only=False).")
        return all_missing_albums

def get_cutoff_unmet_albums(api_url: str, api_key: str, api_timeout: int, monitored_only: bool) -> List[Dict[str, Any]]:
    """Get cutoff unmet albums from Lidarr, handling pagination."""
    # Note: Lidarr API returns ALBUMS for cutoff unmet, not tracks.
    endpoint = "wanted/cutoff"
    page = 1
    page_size = 1000 # Adjust page size if needed, Lidarr default might be smaller
    all_cutoff_unmet = []
    total_records_reported = -1

    lidarr_logger.debug(f"Starting fetch for cutoff unmet albums (monitored_only={monitored_only}).")

    while True:
        params = {
            "page": page,
            "pageSize": page_size,
            "includeArtist": "true" # Include artist info for filtering
            # Removed sortKey and sortDir
        }
        
        lidarr_logger.debug(f"Requesting cutoff unmet albums page {page} with params: {params}")
        response = arr_request(api_url, api_key, api_timeout, endpoint, params=params, count_api=False)
        
        if response and isinstance(response, dict) and 'records' in response:
            records = response.get('records', [])
            total_records_on_page = len(records)

            if page == 1:
                total_records_reported = response.get('totalRecords', 0)
                lidarr_logger.debug(f"Lidarr API reports {total_records_reported} total cutoff unmet albums.")

            lidarr_logger.debug(f"Parsed {total_records_on_page} cutoff unmet album records from Lidarr API JSON (page {page}).")

            if not records:
                lidarr_logger.debug(f"No more cutoff unmet records found on page {page}. Stopping pagination.")
                break

            all_cutoff_unmet.extend(records)

            # Check if we have fetched all reported records
            if total_records_reported >= 0 and len(all_cutoff_unmet) >= total_records_reported:
                lidarr_logger.debug(f"Fetched {len(all_cutoff_unmet)} records, matching or exceeding total reported ({total_records_reported}). Assuming last page.")
                break

            # Check if the number of records received is less than the page size
            if total_records_on_page < page_size:
                lidarr_logger.debug(f"Received {total_records_on_page} records (less than page size {page_size}). Assuming last page.")
                break
                
            page += 1
            # time.sleep(0.1) # Optional small delay between pages

        else:
            # Log the error based on the response received (handled in arr_request)
            lidarr_logger.error(f"Error getting cutoff unmet albums from Lidarr (page {page}) or invalid response format. Stopping pagination.")
            # Return what we have so far, or indicate complete failure? Let's return what we have.
            break 

    lidarr_logger.info(f"Total cutoff unmet albums fetched across all pages: {len(all_cutoff_unmet)}")

    # Apply monitored filter after fetching all pages
    if monitored_only:
        original_count = len(all_cutoff_unmet)
        # Check both album and artist monitored status
        filtered_cutoff_unmet = [
            album for album in all_cutoff_unmet
            if album.get('monitored', False) and album.get('artist', {}).get('monitored', False)
        ]
        lidarr_logger.debug(f"Filtered for monitored_only=True: {len(filtered_cutoff_unmet)} monitored cutoff unmet albums remain (out of {original_count} total).")
        return filtered_cutoff_unmet
    else:
        lidarr_logger.debug(f"Returning {len(all_cutoff_unmet)} cutoff unmet albums (monitored_only=False).")
        return all_cutoff_unmet

def search_albums(api_url: str, api_key: str, api_timeout: int, album_ids: List[int]) -> Optional[Dict]:
    """Trigger a search for specific albums in Lidarr."""
    if not album_ids:
        lidarr_logger.warning("No album IDs provided for search.")
        return None
    
    # Check API limit before making request
    try:
        from src.primary.stats_manager import check_hourly_cap_exceeded
        if check_hourly_cap_exceeded("lidarr"):
            lidarr_logger.warning(f"🛑 Lidarr API hourly limit reached - skipping album search for {len(album_ids)} albums")
            return None
    except Exception as e:
        lidarr_logger.error(f"Error checking hourly API cap: {e}")
        # Continue with request if cap check fails - safer than skipping
        
    payload = {
        "name": "AlbumSearch",
        "albumIds": album_ids
    }
    response = arr_request(api_url, api_key, api_timeout, "command", method="POST", data=payload)
    
    if response and isinstance(response, dict) and 'id' in response:
        command_id = response.get('id')
        lidarr_logger.info(f"Triggered Lidarr AlbumSearch for album IDs: {album_ids}. Command ID: {command_id}")
        
        # Increment API counter after successful request
        try:
            from src.primary.stats_manager import increment_hourly_cap
            increment_hourly_cap("lidarr", 1)
            lidarr_logger.debug(f"Incremented Lidarr hourly API cap for album search ({len(album_ids)} albums)")
        except Exception as cap_error:
            lidarr_logger.error(f"Failed to increment hourly API cap for album search: {cap_error}")
        
        return response # Return the full command object including ID
    else:
        lidarr_logger.error(f"Failed to trigger Lidarr AlbumSearch for album IDs {album_ids}. Response: {response}")
        return None

def search_artist(api_url: str, api_key: str, api_timeout: int, artist_id: int) -> Optional[Dict]:
    """Trigger a search for a specific artist in Lidarr."""
    
    # Check API limit before making request
    try:
        from src.primary.stats_manager import check_hourly_cap_exceeded
        if check_hourly_cap_exceeded("lidarr"):
            lidarr_logger.warning(f"🛑 Lidarr API hourly limit reached - skipping artist search for artist {artist_id}")
            return None
    except Exception as e:
        lidarr_logger.error(f"Error checking hourly API cap: {e}")
        # Continue with request if cap check fails - safer than skipping
    
    payload = {
        "name": "ArtistSearch",
        "artistIds": [artist_id]
    }
    response = arr_request(api_url, api_key, api_timeout, "command", method="POST", data=payload)

    if response and isinstance(response, dict) and 'id' in response:
        command_id = response.get('id')
        lidarr_logger.info(f"Triggered Lidarr ArtistSearch for artist ID: {artist_id}. Command ID: {command_id}")
        
        # Increment API counter after successful request
        try:
            from src.primary.stats_manager import increment_hourly_cap
            increment_hourly_cap("lidarr", 1)
            lidarr_logger.debug(f"Incremented Lidarr hourly API cap for artist search (artist {artist_id})")
        except Exception as cap_error:
            lidarr_logger.error(f"Failed to increment hourly API cap for artist search: {cap_error}")
        
        return response # Return the full command object
    else:
        lidarr_logger.error(f"Failed to trigger Lidarr ArtistSearch for artist ID {artist_id}. Response: {response}")
        return None

def refresh_artist(api_url: str, api_key: str, api_timeout: int, artist_id: int) -> Optional[Dict]:
    """Refresh functionality has been removed as it was a performance bottleneck.
    This function now returns a placeholder success value without making any API calls."""
    lidarr_logger.debug(f"Refresh functionality disabled for artist ID: {artist_id}")
    # Return a placeholder command object to simulate success
    return {
        'id': 123,
        'name': 'RefreshArtist',
        'status': 'completed',
        'artistId': artist_id,
        'message': 'Refresh functionality disabled for performance reasons'
    }

def get_command_status(api_url: str, api_key: str, api_timeout: int, command_id: int) -> Optional[Dict[str, Any]]:
    """Get the status of a Lidarr command."""
    response = arr_request(api_url, api_key, api_timeout, f"command/{command_id}")
    if response and isinstance(response, dict):
        lidarr_logger.debug(f"Checked Lidarr command status for ID {command_id}: {response.get('status')}")
        return response
    else:
         lidarr_logger.error(f"Error getting Lidarr command status for ID {command_id}. Response: {response}")
         return None

def get_artist_by_id(api_url: str, api_key: str, api_timeout: int, artist_id: int) -> Optional[Dict[str, Any]]:
    """Get artist details by ID from Lidarr."""
    return arr_request(api_url, api_key, api_timeout, f"artist/{artist_id}")

def get_or_create_tag(api_url: str, api_key: str, api_timeout: int, tag_label: str) -> Optional[int]:
    """
    Get existing tag ID or create a new tag in Lidarr.
    
    Args:
        api_url: The base URL of the Lidarr API
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
                    lidarr_logger.debug(f"Found existing tag '{tag_label}' with ID: {tag_id}")
                    return tag_id
        
        # Tag doesn't exist, create it
        tag_data = {"label": tag_label}
        response = arr_request(api_url, api_key, api_timeout, "tag", method="POST", data=tag_data, count_api=False)
        if response and 'id' in response:
            tag_id = response['id']
            lidarr_logger.info(f"Created new tag '{tag_label}' with ID: {tag_id}")
            return tag_id
        else:
            lidarr_logger.error(f"Failed to create tag '{tag_label}'. Response: {response}")
            return None
            
    except Exception as e:
        lidarr_logger.error(f"Error managing tag '{tag_label}': {e}")
        return None

def add_tag_to_artist(api_url: str, api_key: str, api_timeout: int, artist_id: int, tag_id: int) -> bool:
    """
    Add a tag to an artist in Lidarr.
    
    Args:
        api_url: The base URL of the Lidarr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        artist_id: The ID of the artist to tag
        tag_id: The ID of the tag to add
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # First get the current artist data
        artist_data = arr_request(api_url, api_key, api_timeout, f"artist/{artist_id}", count_api=False)
        if not artist_data:
            lidarr_logger.error(f"Failed to get artist data for ID: {artist_id}")
            return False
        
        # Check if the tag is already present
        current_tags = artist_data.get('tags', [])
        if tag_id in current_tags:
            lidarr_logger.debug(f"Tag {tag_id} already exists on artist {artist_id}")
            return True
        
        # Add the new tag to the list
        current_tags.append(tag_id)
        artist_data['tags'] = current_tags
        
        # Update the artist with the new tags
        response = arr_request(api_url, api_key, api_timeout, f"artist/{artist_id}", method="PUT", data=artist_data, count_api=False)
        if response:
            lidarr_logger.debug(f"Successfully added tag {tag_id} to artist {artist_id}")
            return True
        else:
            lidarr_logger.error(f"Failed to update artist {artist_id} with tag {tag_id}")
            return False
            
    except Exception as e:
        lidarr_logger.error(f"Error adding tag {tag_id} to artist {artist_id}: {e}")
        return False

def tag_processed_artist(api_url: str, api_key: str, api_timeout: int, artist_id: int, tag_label: str = "huntarr-missing") -> bool:
    """
    Tag an artist in Lidarr with the specified tag.
    
    Args:
        api_url: The base URL of the Lidarr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        artist_id: The ID of the artist to tag
        tag_label: The tag to apply (huntarr-missing, huntarr-upgraded)
        
    Returns:
        True if the tagging was successful, False otherwise
    """
    try:
        # Get or create the tag
        tag_id = get_or_create_tag(api_url, api_key, api_timeout, tag_label)
        if tag_id is None:
            lidarr_logger.error(f"Failed to get or create tag '{tag_label}' in Lidarr")
            return False
            
        # Add the tag to the artist
        success = add_tag_to_artist(api_url, api_key, api_timeout, artist_id, tag_id)
        if success:
            lidarr_logger.debug(f"Successfully tagged Lidarr artist {artist_id} with '{tag_label}'")
            return True
        else:
            lidarr_logger.error(f"Failed to add tag '{tag_label}' to Lidarr artist {artist_id}")
            return False
            
    except Exception as e:
        lidarr_logger.error(f"Error tagging Lidarr artist {artist_id} with '{tag_label}': {e}")
        return False

def get_missing_albums_random_page(api_url: str, api_key: str, api_timeout: int, monitored_only: bool, count: int) -> List[Dict[str, Any]]:
    """
    Get a specified number of random missing albums by selecting a random page.
    This is much more efficient for very large libraries.
    
    Args:
        api_url: The base URL of the Lidarr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        monitored_only: Whether to include only monitored albums
        count: How many albums to return
        
    Returns:
        A list of randomly selected missing albums, up to the requested count
    """
    endpoint = "wanted/missing"
    page_size = 100  # Smaller page size for better performance
    retries = 2
    retry_delay = 3
    
    # First, make a request to get just the total record count (page 1 with size=1)
    params = {
        "page": 1,
        "pageSize": 1,
        "includeArtist": "true"  # Include artist info for filtering
    }
    
    for attempt in range(retries + 1):
        try:
            # Get total record count from a minimal query
            lidarr_logger.debug(f"Getting missing albums count (attempt {attempt+1}/{retries+1})")
            response = arr_request(api_url, api_key, api_timeout, endpoint, params=params, count_api=False)
            
            if not response or not isinstance(response, dict):
                lidarr_logger.warning(f"Invalid response when getting missing count (attempt {attempt+1})")
                if attempt < retries:
                    time.sleep(retry_delay)
                    continue
                return []
                
            total_records = response.get('totalRecords', 0)
            
            if total_records == 0:
                lidarr_logger.info("No missing albums found in Lidarr.")
                return []
                
            # Calculate total pages with our desired page size
            total_pages = (total_records + page_size - 1) // page_size
            lidarr_logger.info(f"Found {total_records} total missing albums across {total_pages} pages")
            
            if total_pages == 0:
                return []
                
            # Select a random page
            import random
            random_page = random.randint(1, total_pages)
            lidarr_logger.info(f"Selected random page {random_page} of {total_pages} for missing albums")
            
            # Get albums from the random page
            params = {
                "page": random_page,
                "pageSize": page_size,
                "includeArtist": "true"
            }
            
            response = arr_request(api_url, api_key, api_timeout, endpoint, params=params, count_api=False)
            
            if not response or not isinstance(response, dict):
                lidarr_logger.warning(f"Invalid response when getting missing albums page {random_page}")
                return []
                
            records = response.get('records', [])
            lidarr_logger.info(f"Retrieved {len(records)} missing albums from page {random_page}")
            
            # Apply monitored filter if requested
            if monitored_only:
                filtered_records = [
                    album for album in records
                    if album.get('monitored', False) and album.get('artist', {}).get('monitored', False)
                ]
                lidarr_logger.debug(f"Filtered to {len(filtered_records)} monitored missing albums")
                records = filtered_records
            
            # Select random albums from this page
            if len(records) > count:
                selected_records = random.sample(records, count)
                lidarr_logger.debug(f"Randomly selected {len(selected_records)} missing albums from page {random_page}")
                return selected_records
            else:
                # If we have fewer albums than requested, return all of them
                lidarr_logger.debug(f"Returning all {len(records)} missing albums from page {random_page} (fewer than requested {count})")
                return records
                
        except Exception as e:
            lidarr_logger.error(f"Error getting missing albums from Lidarr (attempt {attempt+1}): {str(e)}")
            if attempt < retries:
                time.sleep(retry_delay)
                continue
            return []
    
    # If we get here, all retries failed
    lidarr_logger.error("All attempts to get missing albums failed")
    return []

def get_cutoff_unmet_albums_random_page(api_url: str, api_key: str, api_timeout: int, monitored_only: bool, count: int) -> List[Dict[str, Any]]:
    """
    Get a specified number of random cutoff unmet albums by selecting a random page.
    This is much more efficient for very large libraries.
    
    Args:
        api_url: The base URL of the Lidarr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        monitored_only: Whether to include only monitored albums
        count: How many albums to return
        
    Returns:
        A list of randomly selected cutoff unmet albums
    """
    endpoint = "wanted/cutoff"
    page_size = 100  # Smaller page size for better performance
    retries = 2
    retry_delay = 3
    
    # First, make a request to get just the total record count (page 1 with size=1)
    params = {
        "page": 1,
        "pageSize": 1,
        "includeArtist": "true"  # Include artist info for filtering
    }
    
    for attempt in range(retries + 1):
        try:
            # Get total record count from a minimal query
            lidarr_logger.debug(f"Getting cutoff unmet albums count (attempt {attempt+1}/{retries+1})")
            response = arr_request(api_url, api_key, api_timeout, endpoint, params=params, count_api=False)
            
            if not response or not isinstance(response, dict):
                lidarr_logger.warning(f"Invalid response when getting cutoff unmet count (attempt {attempt+1})")
                if attempt < retries:
                    time.sleep(retry_delay)
                    continue
                return []
                
            total_records = response.get('totalRecords', 0)
            
            if total_records == 0:
                lidarr_logger.info("No cutoff unmet albums found in Lidarr.")
                return []
                
            # Calculate total pages with our desired page size
            total_pages = (total_records + page_size - 1) // page_size
            lidarr_logger.info(f"Found {total_records} total cutoff unmet albums across {total_pages} pages")
            
            if total_pages == 0:
                return []
                
            # Select a random page
            import random
            random_page = random.randint(1, total_pages)
            lidarr_logger.info(f"Selected random page {random_page} of {total_pages} for cutoff unmet albums")
            
            # Get albums from the random page
            params = {
                "page": random_page,
                "pageSize": page_size,
                "includeArtist": "true"
            }
            
            response = arr_request(api_url, api_key, api_timeout, endpoint, params=params, count_api=False)
            
            if not response or not isinstance(response, dict):
                lidarr_logger.warning(f"Invalid response when getting cutoff unmet albums page {random_page}")
                return []
                
            records = response.get('records', [])
            lidarr_logger.info(f"Retrieved {len(records)} cutoff unmet albums from page {random_page}")
            
            # Apply monitored filter if requested
            if monitored_only:
                filtered_records = [
                    album for album in records
                    if album.get('monitored', False) and album.get('artist', {}).get('monitored', False)
                ]
                lidarr_logger.debug(f"Filtered to {len(filtered_records)} monitored cutoff unmet albums")
                records = filtered_records
            
            # Select random albums from this page
            if len(records) > count:
                selected_records = random.sample(records, count)
                lidarr_logger.debug(f"Randomly selected {len(selected_records)} cutoff unmet albums from page {random_page}")
                return selected_records
            else:
                # If we have fewer albums than requested, return all of them
                lidarr_logger.debug(f"Returning all {len(records)} cutoff unmet albums from page {random_page} (fewer than requested {count})")
                return records
                
        except Exception as e:
            lidarr_logger.error(f"Error getting cutoff unmet albums from Lidarr (attempt {attempt+1}): {str(e)}")
            if attempt < retries:
                time.sleep(retry_delay)
                continue
            return []
    
    # If we get here, all retries failed
    lidarr_logger.error("All attempts to get cutoff unmet albums failed")
    return []

def get_quality_profiles(api_url: str, api_key: str, api_timeout: int) -> Optional[List[Dict]]:
    """
    Get all quality profiles configured in Lidarr.

    Args:
        api_url: The base URL of the Lidarr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request

    Returns:
        A list of quality profile objects, or None if the request failed.
        Each profile contains: id, name, upgradeAllowed, cutoff, items, etc.
    """
    try:
        lidarr_logger.debug("Fetching quality profiles from Lidarr...")
        
        # Use the qualityProfile endpoint - this doesn't count toward API limits since it's configuration data
        # Note: Lidarr uses API v1, not v3 like Sonarr/Radarr
        profiles = arr_request(api_url, api_key, api_timeout, "qualityProfile", count_api=False)
        
        if profiles is None:
            lidarr_logger.error("Failed to retrieve quality profiles from Lidarr API.")
            return None
        
        lidarr_logger.debug(f"Found {len(profiles)} quality profiles in Lidarr")
        
        # Log profile names for debugging
        profile_names = [profile.get('name', 'Unknown') for profile in profiles]
        lidarr_logger.debug(f"Quality profiles: {', '.join(profile_names)}")
        
        return profiles
        
    except Exception as e:
        lidarr_logger.error(f"Error retrieving quality profiles: {str(e)}")
        return None