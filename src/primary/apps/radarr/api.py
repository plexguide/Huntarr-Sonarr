#!/usr/bin/env python3
"""
Radarr-specific API functions
Handles all communication with the Radarr API
"""

import requests
import json
import sys
import time
import traceback
from typing import List, Dict, Any, Optional, Union
# Correct the import path
from src.primary.utils.logger import get_logger
from src.primary.settings_manager import get_ssl_verify_setting

# Get logger for the Radarr app
radarr_logger = get_logger("radarr")

# Use a session for better performance
session = requests.Session()

def arr_request(api_url: str, api_key: str, api_timeout: int, endpoint: str, method: str = "GET",  data: Optional[Dict] = None, params: Optional[Dict] = None, count_api: bool = True) -> Any:
    """
    Make a request to the Radarr API.
    
    Args:
        api_url: The base URL of the Radarr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        endpoint: The API endpoint to call (without /api/v3/)
        method: HTTP method (GET, POST, PUT, DELETE)
        data: Optional data payload for POST/PUT requests
        params: Optional query parameters for GET requests
        count_api: Whether the request counts toward API tally
    
    Returns:
        The parsed JSON response or None if the request failed
    """
    try:
        if not api_url or not api_key:
            radarr_logger.error("No URL or API key provided")
            return None
        
        # Check API limit before making request
        from src.primary.stats_manager import check_hourly_cap_exceeded, increment_hourly_cap
        if check_hourly_cap_exceeded("radarr"):
            radarr_logger.warning("\U0001F6D1 Radarr API hourly limit reached - skipping request")
            return None
        
        # Construct the full URL properly
        full_url = f"{api_url.rstrip('/')}/api/v3/{endpoint.lstrip('/')}"
        
    
        
        # Set up headers with the API key
        headers = {
            "X-Api-Key": api_key,
            "Content-Type": "application/json",
            "User-Agent": "Huntarr/1.0 (https://github.com/plexguide/Huntarr.io)"
        }
        
        # Get SSL verification setting
        verify_ssl = get_ssl_verify_setting()
        
        if not verify_ssl:
            radarr_logger.debug("SSL verification disabled by global user setting")
        
        # Make the request based on the method
        if method.upper() == "GET":
            response = session.get(full_url, headers=headers, params=params, timeout=api_timeout, verify=verify_ssl)
        elif method.upper() == "POST":
            response = session.post(full_url, headers=headers, json=data, timeout=api_timeout, verify=verify_ssl)
        elif method.upper() == "PUT":
            response = session.put(full_url, headers=headers, json=data, timeout=api_timeout, verify=verify_ssl)
        elif method.upper() == "DELETE":
            response = session.delete(full_url, headers=headers, timeout=api_timeout, verify=verify_ssl)
        else:
            radarr_logger.error(f"Unsupported HTTP method: {method}")
            return None
        
        # Check for errors
        response.raise_for_status()
        
        # Increment API usage counter only after successful request
        if count_api:
            increment_hourly_cap("radarr")
        
        # Parse JSON response
        if response.text:
            return response.json()
        return {}
        
    except requests.exceptions.RequestException as e:
        radarr_logger.error(f"API request failed: {e}")
        return None

def get_download_queue_size(api_url: str, api_key: str, api_timeout: int) -> int:
    """
    Get the current size of the download queue.

    Args:
        api_url: The base URL of the Radarr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request

    Returns:
        The number of items in the download queue, or -1 if the request failed
    """
    if not api_url or not api_key:
        radarr_logger.error("Radarr API URL or API Key not provided for queue size check.")
        return -1
    try:
        # Radarr uses /api/v3/queue
        params = {
            "page": 1,
            "pageSize": 1000 # Fetch a large page size to get all items
        }

        queue_data = arr_request(api_url, api_key, api_timeout, "queue", params=params)
        queue_size = queue_data.get('totalRecords', 0)
        radarr_logger.debug(f"Radarr download queue size: {queue_size}")
        return queue_size
    except requests.exceptions.RequestException as e:
        radarr_logger.error(f"Error getting Radarr download queue size: {e}")
        return -1 # Return -1 to indicate an error
    except Exception as e:
        radarr_logger.error(f"An unexpected error occurred while getting Radarr queue size: {e}")
        return -1

def get_quality_profiles(api_url: str, api_key: str, api_timeout: int) -> Optional[List[Dict]]:
    """
    Get all quality profiles configured in Radarr.

    Args:
        api_url: The base URL of the Radarr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request

    Returns:
        A list of quality profile objects, or None if the request failed.
        Each profile contains: id, name, upgradeAllowed, cutoff, items, etc.
    """
    try:
        radarr_logger.debug("Fetching quality profiles from Radarr...")
        
        # Use the qualityProfile endpoint - this doesn't count toward API limits since it's configuration data
        profiles = arr_request(api_url, api_key, api_timeout, "qualityProfile", count_api=False)
        
        if profiles is None:
            radarr_logger.error("Failed to retrieve quality profiles from Radarr API.")
            return None
        
        radarr_logger.debug(f"Found {len(profiles)} quality profiles in Radarr")
        
        # Log profile names for debugging
        profile_names = [profile.get('name', 'Unknown') for profile in profiles]
        radarr_logger.debug(f"Quality profiles: {', '.join(profile_names)}")
        
        return profiles
        
    except Exception as e:
        radarr_logger.error(f"Error retrieving quality profiles: {str(e)}")
        return None

def get_quality_profile_names(api_url: str, api_key: str, api_timeout: int) -> List[str]:
    """
    Get a simple list of quality profile names for UI dropdowns.

    Args:
        api_url: The base URL of the Radarr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request

    Returns:
        A list of quality profile names, or empty list if the request failed.
    """
    profiles = get_quality_profiles(api_url, api_key, api_timeout)
    if profiles is None:
        return []
    
    return [profile.get('name', 'Unknown') for profile in profiles]

def get_movies_with_missing(api_url: str, api_key: str, api_timeout: int, monitored_only: bool) -> Optional[List[Dict]]:
    """
    Get a list of movies with missing files (not downloaded/available).

    Args:
        api_url: The base URL of the Radarr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        monitored_only: If True, only return monitored movies.

    Returns:
        A list of movie objects with missing files, or None if the request failed.
    """
    # Use the updated arr_request with passed arguments
    # Use arr_request with count_api=False for data fetching (doesn't count toward API tally)
    movies = arr_request(api_url, api_key, api_timeout, "movie", count_api=False)
    if movies is None: # Check for None explicitly, as an empty list is valid
        radarr_logger.error("Failed to retrieve movies from Radarr API.")
        return None
    
    missing_movies = []
    for movie in movies:
        is_monitored = movie.get("monitored", False)
        has_file = movie.get("hasFile", False)
        # Apply monitored_only filter if requested
        if not has_file and (not monitored_only or is_monitored):
            missing_movies.append(movie)
    
    radarr_logger.debug(f"Found {len(missing_movies)} missing movies (monitored_only={monitored_only}).")
    return missing_movies

def get_cutoff_unmet_movies(api_url: str, api_key: str, api_timeout: int, monitored_only: bool) -> Optional[List[Dict]]:
    """
    Get a list of movies that don't meet their quality profile cutoff using the proper API endpoint.

    Args:
        api_url: The base URL of the Radarr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        monitored_only: If True, only return monitored movies.

    Returns:
        A list of movie objects that need quality upgrades, or None if the request failed.
    """

    # Use Radarr's dedicated cutoff endpoint
    radarr_logger.debug(f"Fetching cutoff unmet movies (monitored_only={monitored_only})...")
    
    # Set up pagination parameters - start with reasonable page size
    page = 1
    page_size = 100  # Reasonable batch size for processing
    all_cutoff_movies = []
    
    while True:
        # Use the proper wanted/cutoff endpoint with pagination
        params = {
            'page': page,
            'pageSize': page_size,
            'monitored': monitored_only
        }
        
        # Use arr_request for proper API tracking and limit checking
        response = arr_request(api_url, api_key, api_timeout, "wanted/cutoff", params=params, count_api=False)
        
        if response is None:
            radarr_logger.error("Failed to retrieve cutoff unmet movies from Radarr API.")
            return None if page == 1 else all_cutoff_movies  # Return partial results if we got some data
            
        # Handle paginated response structure
        records = response.get('records', [])
        total_records = response.get('totalRecords', 0)
        
        if not records:
            break  # No more records
            
        all_cutoff_movies.extend(records)
        
        # Log progress for large datasets
        if total_records > page_size:
            radarr_logger.debug(f"Retrieved {len(all_cutoff_movies)}/{total_records} cutoff unmet movies...")
        
        # Check if we've got all records
        if len(all_cutoff_movies) >= total_records:
            break
            
        page += 1
        
        # Safety check to prevent infinite loops
        if page > 1000:  # Reasonable upper limit
            radarr_logger.warning("Reached maximum page limit (1000) while fetching cutoff unmet movies")
            break

    radarr_logger.debug(f"Found {len(all_cutoff_movies)} cutoff unmet movies (monitored_only={monitored_only}).")
    return all_cutoff_movies

def get_cutoff_unmet_movies_random_page(api_url: str, api_key: str, api_timeout: int, monitored_only: bool, count: int = 50) -> Optional[List[Dict]]:
    """
    Get a random sample of cutoff unmet movies from a random page instead of fetching all pages.
    This dramatically reduces API calls while still providing fair movie selection.
    Note: Uses count_api=False for page fetching so only upgrade requests count toward API tally.
    
    Args:
        api_url: Radarr API URL
        api_key: Radarr API key
        api_timeout: Request timeout in seconds
        monitored_only: Only return monitored movies
        count: Maximum number of movies to return (default: 50)
        
    Returns:
        List of movie dictionaries representing cutoff unmet movies, or None if error
    """
    import random
    
    radarr_logger.debug(f"Fetching random sample of cutoff unmet movies (monitored_only={monitored_only}, count={count})...")
    
    # First, get the first page to determine total pages/records
    params = {
        'page': 1,
        'pageSize': count,  # Use requested count as page size
        'monitored': monitored_only
    }
    
    # Use arr_request for proper API tracking and limit checking
    response = arr_request(api_url, api_key, api_timeout, "wanted/cutoff", params=params, count_api=False)
    
    if response is None:
        radarr_logger.error("Failed to retrieve cutoff unmet movies from Radarr API.")
        return None
        
    records = response.get('records', [])
    total_records = response.get('totalRecords', 0)
    page_size = count
    total_pages = max(1, (total_records + page_size - 1) // page_size)  # Calculate total pages
    
    radarr_logger.info(f"📊 Found {total_records} total cutoff unmet movies across {total_pages} pages")
    
    # If we have few enough records that they fit in one page, just return them
    if total_records <= page_size:
        radarr_logger.info(f"🎯 All {len(records)} movies fit in one page, returning them directly")
        return records
    
    # Pick a random page (excluding page 1 since we already have it)
    if total_pages > 1:
        random_page = random.randint(1, total_pages)
        radarr_logger.info(f"🎲 Randomly selected page {random_page} of {total_pages}")
        
        # If we didn't pick page 1, fetch the random page
        if random_page != 1:
            params['page'] = random_page
            response = arr_request(api_url, api_key, api_timeout, "wanted/cutoff", params=params, count_api=False)
            
            if response is None:
                radarr_logger.warning(f"Failed to fetch random page {random_page}, using page 1 data")
                # Fall back to page 1 data we already have
            else:
                records = response.get('records', [])
                radarr_logger.info(f"📄 Retrieved {len(records)} movies from page {random_page}")
    
    # Randomly sample from the page if we have more than requested
    if len(records) > count:
        records = random.sample(records, count)
        radarr_logger.info(f"🎯 Randomly selected {len(records)} movies from the page")
    
    radarr_logger.info(f"✅ Returning {len(records)} cutoff unmet movies from random sampling")
    return records

def refresh_movie(api_url: str, api_key: str, api_timeout: int, movie_id: int, 
                 command_wait_delay: int = 1, command_wait_attempts: int = 600) -> Optional[int]:
    """
    Refresh functionality has been removed as it was a performance bottleneck.
    This function now returns a placeholder success value without making any API calls.
    
    Args:
        api_url: The base URL of the Radarr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        movie_id: The ID of the movie to refresh
        command_wait_delay: Seconds to wait between command status checks
        command_wait_attempts: Maximum number of status check attempts
        
    Returns:
        A placeholder command ID (123) to simulate success
    """
    radarr_logger.debug(f"Refresh functionality disabled for movie ID: {movie_id}")
    # Return a placeholder command ID (123) to simulate success without actually refreshing
    return 123

def movie_search(api_url: str, api_key: str, api_timeout: int, movie_ids: List[int]) -> Optional[int]:
    """
    Trigger a search for one or more movies.
    
    Args:
        api_url: The base URL of the Radarr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        movie_ids: A list of movie IDs to search for
        
    Returns:
        The command ID if the search command was triggered successfully, None otherwise
    """
    if not movie_ids:
        radarr_logger.warning("No movie IDs provided for search.")
        return None
        
    endpoint = "command"
    data = {
        "name": "MoviesSearch",
        "movieIds": movie_ids
    }
    
    # Use the updated arr_request
    response = arr_request(api_url, api_key, api_timeout, endpoint, method="POST", data=data)
    if response and 'id' in response:
        command_id = response['id']
        radarr_logger.debug(f"Triggered search for movie IDs: {movie_ids}. Command ID: {command_id}")
        return command_id
    else:
        radarr_logger.error(f"Failed to trigger search command for movie IDs {movie_ids}. Response: {response}")
        return None 

def check_connection(api_url: str, api_key: str, api_timeout: int) -> bool:
    """Checks connection by fetching system status."""
    if not api_url:
        radarr_logger.error("API URL is empty or not set")
        return False
    if not api_key:
        radarr_logger.error("API Key is empty or not set")
        return False

    try:
        # Use a shorter timeout for a quick connection check
        quick_timeout = min(api_timeout, 15) 
        status = get_system_status(api_url, api_key, quick_timeout)
        if status and isinstance(status, dict) and 'version' in status:
             # Log success only if debug is enabled to avoid clutter
             radarr_logger.debug(f"Connection check successful for {api_url}. Version: {status.get('version')}")
             return True
        else:
             # Log details if the status response was unexpected
             radarr_logger.warning(f"Connection check for {api_url} returned unexpected status: {str(status)[:200]}")
             return False
    except Exception as e:
        # Error should have been logged by arr_request, just indicate failure
        radarr_logger.error(f"Connection check failed for {api_url}")
        return False


def get_system_status(api_url: str, api_key: str, api_timeout: int) -> Dict:
    """
    Get Radarr system status.
    
    Args:
        api_url: The base URL of the Radarr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
    
    Returns:
        System status information or empty dict if request failed
    """
    response = arr_request(api_url, api_key, api_timeout, "system/status")
    if response:
        return response
    return {}

def wait_for_command(api_url: str, api_key: str, api_timeout: int, command_id: int, 
                    delay_seconds: int = 1, max_attempts: int = 600) -> bool:
    """
    Wait for a command to complete.
    
    Args:
        api_url: The base URL of the Radarr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        command_id: The ID of the command to wait for
        delay_seconds: Seconds to wait between command status checks
        max_attempts: Maximum number of status check attempts
        
    Returns:
        True if the command completed successfully, False if timed out
    """
    attempts = 0
    while attempts < max_attempts:
        response = arr_request(api_url, api_key, api_timeout, f"command/{command_id}")
        if response and 'state' in response:
            state = response['state']
            if state == "completed":
                return True
            elif state == "failed":
                radarr_logger.error(f"Command {command_id} failed")
                return False
        time.sleep(delay_seconds)
        attempts += 1
    radarr_logger.warning(f"Timed out waiting for command {command_id} to complete")
    return False

def get_or_create_tag(api_url: str, api_key: str, api_timeout: int, tag_label: str) -> Optional[int]:
    """
    Get existing tag ID or create a new tag in Radarr.
    
    Args:
        api_url: The base URL of the Radarr API
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
                    radarr_logger.debug(f"Found existing tag '{tag_label}' with ID: {tag_id}")
                    return tag_id
        
        # Tag doesn't exist, create it
        tag_data = {"label": tag_label}
        response = arr_request(api_url, api_key, api_timeout, "tag", method="POST", data=tag_data, count_api=False)
        if response and 'id' in response:
            tag_id = response['id']
            radarr_logger.info(f"Created new tag '{tag_label}' with ID: {tag_id}")
            return tag_id
        else:
            radarr_logger.error(f"Failed to create tag '{tag_label}'. Response: {response}")
            return None
            
    except Exception as e:
        radarr_logger.error(f"Error managing tag '{tag_label}': {e}")
        return None

def add_tag_to_movie(api_url: str, api_key: str, api_timeout: int, movie_id: int, tag_id: int) -> bool:
    """
    Add a tag to a movie in Radarr.
    
    Args:
        api_url: The base URL of the Radarr API
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
            radarr_logger.error(f"Failed to get movie data for ID: {movie_id}")
            return False
        
        # Check if the tag is already present
        current_tags = movie_data.get('tags', [])
        if tag_id in current_tags:
            radarr_logger.debug(f"Tag {tag_id} already exists on movie {movie_id}")
            return True
        
        # Add the new tag to the list
        current_tags.append(tag_id)
        movie_data['tags'] = current_tags
        
        # Update the movie with the new tags
        response = arr_request(api_url, api_key, api_timeout, f"movie/{movie_id}", method="PUT", data=movie_data, count_api=False)
        if response:
            radarr_logger.debug(f"Successfully added tag {tag_id} to movie {movie_id}")
            return True
        else:
            radarr_logger.error(f"Failed to update movie {movie_id} with tag {tag_id}")
            return False
            
    except Exception as e:
        radarr_logger.error(f"Error adding tag {tag_id} to movie {movie_id}: {e}")
        return False

def tag_processed_movie(api_url: str, api_key: str, api_timeout: int, movie_id: int, tag_label: str = "huntarr-missing") -> bool:
    """
    Tag a movie in Radarr with the specified tag.
    
    Args:
        api_url: The base URL of the Radarr API
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
            radarr_logger.error(f"Failed to get or create tag '{tag_label}' in Radarr")
            return False
            
        # Add the tag to the movie
        success = add_tag_to_movie(api_url, api_key, api_timeout, movie_id, tag_id)
        if success:
            radarr_logger.debug(f"Successfully tagged Radarr movie {movie_id} with '{tag_label}'")
            return True
        else:
            radarr_logger.error(f"Failed to add tag '{tag_label}' to Radarr movie {movie_id}")
            return False
            
    except Exception as e:
        radarr_logger.error(f"Error tagging Radarr movie {movie_id} with '{tag_label}': {e}")
        return False

def get_movies_with_missing_random_page(api_url: str, api_key: str, api_timeout: int, monitored_only: bool, count: int) -> Optional[List[Dict]]:
    """
    Get a random sample of missing movies by using the wanted/missing endpoint with random page selection.
    This is much more efficient than fetching all movies for very large libraries.
    
    Args:
        api_url: The base URL of the Radarr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        monitored_only: If True, only return monitored movies
        count: Maximum number of movies to return
        
    Returns:
        A list of movie objects with missing files, or None if the request failed
    """
    import random
    
    radarr_logger.debug(f"Fetching random sample of missing movies (monitored_only={monitored_only}, count={count})...")
    
    # Use Radarr's wanted/missing endpoint with pagination
    endpoint = "wanted/missing"
    page_size = 100  # Smaller page size for better performance
    retries = 2
    retry_delay = 3
    
    # First, make a request to get just the total record count (page 1 with size=1)
    params = {
        'page': 1,
        'pageSize': 1,
        'monitored': monitored_only
    }
    
    for attempt in range(retries + 1):
        try:
            # Get total record count from a minimal query
            radarr_logger.debug(f"Getting missing movies count (attempt {attempt+1}/{retries+1})")
            response = arr_request(api_url, api_key, api_timeout, endpoint, params=params, count_api=False)
            
            if not response or not isinstance(response, dict):
                radarr_logger.warning(f"Invalid response when getting missing count (attempt {attempt+1})")
                if attempt < retries:
                    time.sleep(retry_delay)
                    continue
                return None
                
            total_records = response.get('totalRecords', 0)
            
            if total_records == 0:
                radarr_logger.info("No missing movies found in Radarr.")
                return []
                
            # Calculate total pages with our desired page size
            total_pages = (total_records + page_size - 1) // page_size
            radarr_logger.info(f"📊 Found {total_records} total missing movies across {total_pages} pages")
            
            if total_pages == 0:
                return []
                
            # Select a random page
            random_page = random.randint(1, total_pages)
            radarr_logger.info(f"🎲 Randomly selected page {random_page} of {total_pages} for missing movies")
            
            # Get movies from the random page
            params = {
                'page': random_page,
                'pageSize': page_size,
                'monitored': monitored_only
            }
            
            response = arr_request(api_url, api_key, api_timeout, endpoint, params=params, count_api=False)
            
            if not response or not isinstance(response, dict):
                radarr_logger.warning(f"Invalid response when getting missing movies page {random_page}")
                return None
                
            records = response.get('records', [])
            radarr_logger.info(f"📄 Retrieved {len(records)} missing movies from page {random_page}")
            
            # Apply monitored filter if requested (though the API should handle this)
            if monitored_only:
                filtered_records = [
                    movie for movie in records
                    if movie.get('monitored', False)
                ]
                radarr_logger.debug(f"Filtered to {len(filtered_records)} monitored missing movies")
                records = filtered_records
            
            # Select random movies from this page
            if len(records) > count:
                selected_records = random.sample(records, count)
                radarr_logger.info(f"🎯 Randomly selected {len(selected_records)} missing movies from page {random_page}")
                return selected_records
            else:
                # If we have fewer movies than requested, return all of them
                radarr_logger.info(f"✅ Returning all {len(records)} missing movies from page {random_page} (fewer than requested {count})")
                return records
                
        except Exception as e:
            radarr_logger.error(f"Error getting missing movies from Radarr (attempt {attempt+1}): {str(e)}")
            if attempt < retries:
                time.sleep(retry_delay)
                continue
            return None
    
    # If we get here, all retries failed
    radarr_logger.error("All attempts to get missing movies failed")
    return None