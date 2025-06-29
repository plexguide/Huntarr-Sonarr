#!/usr/bin/env python3
"""
Whisparr-specific API functions
Handles all communication with the Whisparr API

Exclusively uses the Whisparr V2 API
"""

import requests
import json
import time
import datetime
import traceback
import sys
from typing import List, Dict, Any, Optional, Union, Callable
from src.primary.utils.logger import get_logger
from src.primary.settings_manager import get_ssl_verify_setting

# Get logger for the Whisparr app
whisparr_logger = get_logger("whisparr")

# Use a session for better performance
session = requests.Session()

def arr_request(api_url: str, api_key: str, api_timeout: int, endpoint: str, method: str = "GET", data: Dict = None, count_api: bool = True) -> Any:
    """
    Make a request to the Whisparr API.
    
    Args:
        api_url: The base URL of the Whisparr API
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
            whisparr_logger.error("No URL or API key provided")
            return None
        
        # Ensure api_url has a scheme
        if not (api_url.startswith('http://') or api_url.startswith('https://')):
            whisparr_logger.error(f"Invalid URL format: {api_url} - URL must start with http:// or https://")
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
            whisparr_logger.debug("SSL verification disabled by user setting")
        
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
                whisparr_logger.error(f"Unsupported HTTP method: {method}")
                return None
            
            # If we get a 404, try with v3 path instead
            if response.status_code == 404:
                api_base = "api/v3"
                v3_url = f"{api_url.rstrip('/')}/{api_base}/{endpoint.lstrip('/')}"
                whisparr_logger.debug(f"Standard path returned 404, trying with V3 path: {v3_url}")
                
                if method == "GET":
                    response = session.get(v3_url, headers=headers, timeout=api_timeout, verify=verify_ssl)
                elif method == "POST":
                    response = session.post(v3_url, headers=headers, json=data, timeout=api_timeout, verify=verify_ssl)
                elif method == "PUT":
                    response = session.put(v3_url, headers=headers, json=data, timeout=api_timeout, verify=verify_ssl)
                elif method == "DELETE":
                    response = session.delete(v3_url, headers=headers, timeout=api_timeout, verify=verify_ssl)
                
                whisparr_logger.debug(f"V3 path request returned status code: {response.status_code}")
            
            # Check if the request was successful
            try:
                response.raise_for_status()
                
                # Increment API counter only if count_api is True and request was successful
                if count_api:
                    try:
                        from src.primary.stats_manager import increment_hourly_cap
                        increment_hourly_cap("whisparr")
                    except Exception as e:
                        whisparr_logger.warning(f"Failed to increment API counter for whisparr: {e}")
                        
            except requests.exceptions.HTTPError as e:
                whisparr_logger.error(f"Error during {method} request to {endpoint}: {e}, Status Code: {response.status_code}")
                whisparr_logger.debug(f"Response content: {response.text[:200]}")
                return None
            
            # Try to parse JSON response
            try:
                if response.text:
                    result = response.json()
                    whisparr_logger.debug(f"Response from {response.url}: Status {response.status_code}, JSON parsed successfully")
                    return result
                else:
                    whisparr_logger.debug(f"Response from {response.url}: Status {response.status_code}, Empty response")
                    return {}
            except json.JSONDecodeError:
                whisparr_logger.error(f"Invalid JSON response from API: {response.text[:200]}")
                return None
            
        except requests.exceptions.RequestException as e:
            whisparr_logger.error(f"Request failed: {e}")
            return None
    except Exception as e:
        whisparr_logger.error(f"Unexpected error during API request: {e}")
        return None

def get_download_queue_size(api_url: str, api_key: str, api_timeout: int) -> int:
    """
    Get the current size of the download queue.

    Args:
        api_url: The base URL of the Whisparr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request

    Returns:
        The number of items in the download queue, or -1 if the request failed
    """
    response = arr_request(api_url, api_key, api_timeout, "queue", count_api=False)
    
    if response is None:
        return -1
    
    # V2 API uses records in queue response
    if isinstance(response, dict) and "records" in response:
        return len(response["records"])
    elif isinstance(response, list):
        return len(response)
    else:
        return -1

def get_items_with_missing(api_url: str, api_key: str, api_timeout: int, monitored_only: bool) -> List[Dict[str, Any]]:
    """
    Get a list of items with missing files (not downloaded/available).

    Args:
        api_url: The base URL of the Whisparr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        monitored_only: If True, only return monitored items.

    Returns:
        A list of item objects with missing files, or None if the request failed.
    """
    try:
        whisparr_logger.debug(f"Retrieving missing items...")
        
        # Endpoint parameters - always use v2 format
        endpoint = "wanted/missing?pageSize=1000&sortKey=airDateUtc&sortDirection=descending"
        
        response = arr_request(api_url, api_key, api_timeout, endpoint, count_api=False)
        
        if response is None:
            return None
        
        # Extract the episodes/items
        items = []
        if isinstance(response, dict) and "records" in response:
            items = response["records"]
        
        # Filter monitored if needed
        if monitored_only:
            items = [item for item in items if item.get("monitored", False)]
        
        whisparr_logger.debug(f"Found {len(items)} missing items")
        return items
        
    except Exception as e:
        whisparr_logger.error(f"Error retrieving missing items: {str(e)}")
        return None

def get_cutoff_unmet_items(api_url: str, api_key: str, api_timeout: int, monitored_only: bool) -> List[Dict[str, Any]]:
    """
    Get a list of items that don't meet their quality profile cutoff.

    Args:
        api_url: The base URL of the Whisparr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        monitored_only: If True, only return monitored items.

    Returns:
        A list of item objects that need quality upgrades, or None if the request failed.
    """
    try:
        whisparr_logger.debug(f"Retrieving cutoff unmet items...")
        
        # Endpoint - always use v2 format
        endpoint = "wanted/cutoff?pageSize=1000&sortKey=airDateUtc&sortDirection=descending"
        
        response = arr_request(api_url, api_key, api_timeout, endpoint, count_api=False)
        
        if response is None:
            return None
        
        # Extract the episodes/items
        items = []
        if isinstance(response, dict) and "records" in response:
            items = response["records"]
        
        whisparr_logger.debug(f"Found {len(items)} cutoff unmet items")
        
        # Just filter monitored if needed
        if monitored_only:
            items = [item for item in items if item.get("monitored", False)]
            whisparr_logger.debug(f"Found {len(items)} cutoff unmet items after filtering monitored")
        
        return items
        
    except Exception as e:
        whisparr_logger.error(f"Error retrieving cutoff unmet items: {str(e)}")
        return None

def refresh_item(api_url: str, api_key: str, api_timeout: int, item_id: int) -> int:
    """
    Refresh functionality has been removed as it was a performance bottleneck.
    This function now returns a placeholder command ID without making any API calls.
    
    Args:
        api_url: The base URL of the Whisparr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        item_id: The ID of the item to refresh
        
    Returns:
        A placeholder command ID (123) to simulate success
    """
    whisparr_logger.debug(f"Refresh functionality disabled for item ID: {item_id}")
    # Return a placeholder command ID to simulate success without actually refreshing
    return 123

def item_search(api_url: str, api_key: str, api_timeout: int, item_ids: List[int]) -> int:
    """
    Trigger a search for one or more items.
    
    Args:
        api_url: The base URL of the Whisparr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        item_ids: A list of item IDs to search for
        
    Returns:
        The command ID if the search command was triggered successfully, None otherwise
    """
    
    # Check API limit before making request
    try:
        from src.primary.stats_manager import check_hourly_cap_exceeded
        if check_hourly_cap_exceeded("whisparr"):
            whisparr_logger.warning(f"🛑 Whisparr API hourly limit reached - skipping item search for {len(item_ids)} items")
            return None
    except Exception as e:
        whisparr_logger.error(f"Error checking hourly API cap: {e}")
        # Continue with request if cap check fails - safer than skipping
    
    try:
        whisparr_logger.debug(f"Searching for items with IDs: {item_ids}")
        
        # Always use the same payload format since we're always using v2 API
        payload = {
            "name": "EpisodeSearch",
            "episodeIds": item_ids
        }
        
        # For commands, we need to directly try both path formats
        command_endpoint = "command"
        url = f"{api_url.rstrip('/')}/api/{command_endpoint}"
        backup_url = f"{api_url.rstrip('/')}/api/v3/{command_endpoint}"
        
        headers = {
            "X-Api-Key": api_key,
            "Content-Type": "application/json"
        }
        
        # Try standard API path first
        whisparr_logger.debug(f"Attempting command with standard API path: {url}")
        try:
            response = session.post(url, headers=headers, json=payload, timeout=api_timeout, verify=verify_ssl)
            # If we get a 404 or 405, try the v3 path
            if response.status_code in [404, 405]:
                whisparr_logger.debug(f"Standard path returned {response.status_code}, trying with V3 path: {backup_url}")
                response = session.post(backup_url, headers=headers, json=payload, timeout=api_timeout, verify=verify_ssl)
                
            response.raise_for_status()
            result = response.json()
            
            if result and "id" in result:
                command_id = result["id"]
                whisparr_logger.debug(f"Search command triggered with ID {command_id}")
                
                # Increment API counter after successful request
                try:
                    from src.primary.stats_manager import increment_hourly_cap
                    increment_hourly_cap("whisparr", 1)
                    whisparr_logger.debug(f"Incremented Whisparr hourly API cap for item search ({len(item_ids)} items)")
                except Exception as cap_error:
                    whisparr_logger.error(f"Failed to increment hourly API cap for item search: {cap_error}")
                
                return command_id
            else:
                whisparr_logger.error("Failed to trigger search command - no command ID returned")
                return None
        except requests.exceptions.HTTPError as e:
            whisparr_logger.error(f"HTTP error during search command: {e}, Status Code: {response.status_code}")
            whisparr_logger.debug(f"Response content: {response.text[:200]}")
            return None
        except Exception as e:
            whisparr_logger.error(f"Error sending search command: {e}")
            return None
        
    except Exception as e:
        whisparr_logger.error(f"Error searching for items: {str(e)}")
        return None

def get_command_status(api_url: str, api_key: str, api_timeout: int, command_id: int) -> Optional[Dict]:
    """
    Get the status of a specific command.

    Args:
        api_url: The base URL of the Whisparr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        command_id: The ID of the command to check

    Returns:
        A dictionary containing the command status, or None if the request failed.
    """
    if not command_id:
        whisparr_logger.error("No command ID provided for status check.")
        return None
        
    try:
        # For commands, we need to directly try both path formats
        command_endpoint = f"command/{command_id}"
        url = f"{api_url.rstrip('/')}/api/{command_endpoint}"
        backup_url = f"{api_url.rstrip('/')}/api/v3/{command_endpoint}"
        
        headers = {
            "X-Api-Key": api_key,
            "Content-Type": "application/json"
        }
        verify_ssl = get_ssl_verify_setting()
        if not verify_ssl:
            whisparr_logger.debug("SSL verification disabled by user setting")
        
        # Try standard API path first
        whisparr_logger.debug(f"Checking command status with standard API path: {url}")
        try:
            response = session.get(url, headers=headers, timeout=api_timeout, verify=verify_ssl)
            # If we get a 404, try the v3 path
            if response.status_code == 404:
                whisparr_logger.debug(f"Standard path returned 404, trying with V3 path: {backup_url}")
                response = session.get(backup_url, headers=headers, timeout=api_timeout, verify=verify_ssl)
                
            response.raise_for_status()
            result = response.json()
            
            whisparr_logger.debug(f"Command {command_id} status: {result.get('status', 'unknown')}")
            return result
        except requests.exceptions.HTTPError as e:
            whisparr_logger.error(f"HTTP error getting command status: {e}, Status Code: {response.status_code}")
            whisparr_logger.debug(f"Response content: {response.text[:200]}")
            return None
        except Exception as e:
            whisparr_logger.error(f"Error getting command status: {e}")
            return None
            
    except Exception as e:
        whisparr_logger.error(f"Error getting command status for ID {command_id}: {e}")
        return None

def check_connection(api_url: str, api_key: str, api_timeout: int) -> bool:
    """
    Check the connection to Whisparr V2 API.
    
    Args:
        api_url: The base URL of the Whisparr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        verify_ssl: Optional override for SSL verification
        
    Returns:
        True if the connection is successful, False otherwise
    """
    try:
        # For Whisparr V2, we need to handle both regular and v3 API formats
        whisparr_logger.debug(f"Checking connection to Whisparr V2 instance at {api_url}")
        verify_ssl = get_ssl_verify_setting()
        if not verify_ssl:
            whisparr_logger.debug("SSL verification disabled by user setting")
        
        # First try with standard path
        endpoint = "system/status"
        response = arr_request(api_url, api_key, api_timeout, endpoint, count_api=False)
  
        # If that failed, try with v3 path format
        if response is None:
            whisparr_logger.debug("Standard API path failed, trying v3 format...")
            # Try direct HTTP request to v3 endpoint without using arr_request
            url = f"{api_url.rstrip('/')}/api/v3/system/status"
            headers = {'X-Api-Key': api_key}
            try:
                resp = session.get(url, headers=headers, timeout=api_timeout, verify=verify_ssl)
                resp.raise_for_status()
                response = resp.json()
            except Exception as e:
                whisparr_logger.debug(f"V3 API path also failed: {str(e)}")
                return False
        
        if response is not None:
            # Get the version information if available
            version = response.get("version", "unknown")
            
            # Check if this is a v2.x version
            if version and version.startswith('2'):
                whisparr_logger.debug(f"Successfully connected to Whisparr V2 API version: {version}")
                return True
            else:
                whisparr_logger.warning(f"Connected to Whisparr but found unexpected version: {version}, expected 2.x")
                return False
        else:
            whisparr_logger.error("Failed to connect to Whisparr V2 API")
            return False
            
    except Exception as e:
        whisparr_logger.error(f"Error checking connection to Whisparr V2 API: {str(e)}")
        return False

def get_or_create_tag(api_url: str, api_key: str, api_timeout: int, tag_label: str) -> Optional[int]:
    """
    Get existing tag ID or create a new tag in Whisparr.
    
    Args:
        api_url: The base URL of the Whisparr API
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
                    whisparr_logger.debug(f"Found existing tag '{tag_label}' with ID: {tag_id}")
                    return tag_id
        
        # Tag doesn't exist, create it
        tag_data = {"label": tag_label}
        response = arr_request(api_url, api_key, api_timeout, "tag", method="POST", data=tag_data, count_api=False)
        if response and 'id' in response:
            tag_id = response['id']
            whisparr_logger.info(f"Created new tag '{tag_label}' with ID: {tag_id}")
            return tag_id
        else:
            whisparr_logger.error(f"Failed to create tag '{tag_label}'. Response: {response}")
            return None
            
    except Exception as e:
        whisparr_logger.error(f"Error managing tag '{tag_label}': {e}")
        return None

def add_tag_to_series(api_url: str, api_key: str, api_timeout: int, series_id: int, tag_id: int) -> bool:
    """
    Add a tag to a series in Whisparr.
    
    Args:
        api_url: The base URL of the Whisparr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        series_id: The ID of the series to tag
        tag_id: The ID of the tag to add
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # First get the current series data
        series_data = arr_request(api_url, api_key, api_timeout, f"series/{series_id}", count_api=False)
        if not series_data:
            whisparr_logger.error(f"Failed to get series data for ID: {series_id}")
            return False
        
        # Check if the tag is already present
        current_tags = series_data.get('tags', [])
        if tag_id in current_tags:
            whisparr_logger.debug(f"Tag {tag_id} already exists on series {series_id}")
            return True
        
        # Add the new tag to the list
        current_tags.append(tag_id)
        series_data['tags'] = current_tags
        
        # Update the series with the new tags
        response = arr_request(api_url, api_key, api_timeout, f"series/{series_id}", method="PUT", data=series_data, count_api=False)
        if response:
            whisparr_logger.debug(f"Successfully added tag {tag_id} to series {series_id}")
            return True
        else:
            whisparr_logger.error(f"Failed to update series {series_id} with tag {tag_id}")
            return False
            
    except Exception as e:
        whisparr_logger.error(f"Error adding tag {tag_id} to series {series_id}: {e}")
        return False

def tag_processed_series(api_url: str, api_key: str, api_timeout: int, series_id: int, tag_label: str = "huntarr-missing") -> bool:
    """
    Tag a series in Whisparr with the specified tag.
    
    Args:
        api_url: The base URL of the Whisparr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        series_id: The ID of the series to tag
        tag_label: The tag to apply (huntarr-missing, huntarr-upgraded)
        
    Returns:
        True if the tagging was successful, False otherwise
    """
    try:
        # Get or create the tag
        tag_id = get_or_create_tag(api_url, api_key, api_timeout, tag_label)
        if tag_id is None:
            whisparr_logger.error(f"Failed to get or create tag '{tag_label}' in Whisparr")
            return False
            
        # Add the tag to the series
        success = add_tag_to_series(api_url, api_key, api_timeout, series_id, tag_id)
        if success:
            whisparr_logger.debug(f"Successfully tagged Whisparr series {series_id} with '{tag_label}'")
            return True
        else:
            whisparr_logger.error(f"Failed to add tag '{tag_label}' to Whisparr series {series_id}")
            return False
            
    except Exception as e:
        whisparr_logger.error(f"Error tagging Whisparr series {series_id} with '{tag_label}': {e}")
        return False

def get_quality_profiles(api_url: str, api_key: str, api_timeout: int) -> Optional[List[Dict]]:
    """
    Get all quality profiles configured in Whisparr.

    Args:
        api_url: The base URL of the Whisparr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request

    Returns:
        A list of quality profile objects, or None if the request failed.
        Each profile contains: id, name, upgradeAllowed, cutoff, items, etc.
    """
    try:
        whisparr_logger.debug("Fetching quality profiles from Whisparr...")
        
        # Use the qualityProfile endpoint - this doesn't count toward API limits since it's configuration data
        profiles = arr_request(api_url, api_key, api_timeout, "qualityProfile", count_api=False)
        
        if profiles is None:
            whisparr_logger.error("Failed to retrieve quality profiles from Whisparr API.")
            return None
        
        whisparr_logger.debug(f"Found {len(profiles)} quality profiles in Whisparr")
        
        # Log profile names for debugging
        profile_names = [profile.get('name', 'Unknown') for profile in profiles]
        whisparr_logger.debug(f"Quality profiles: {', '.join(profile_names)}")
        
        return profiles
        
    except Exception as e:
        whisparr_logger.error(f"Error retrieving quality profiles: {str(e)}")
        return None