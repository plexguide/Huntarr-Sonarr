#!/usr/bin/env python3
"""
Readarr-specific API functions
Handles all communication with the Readarr API
"""

import requests
import json
import time
import datetime
from typing import List, Dict, Any, Optional, Union
# Correct the import path
from src.primary.utils.logger import get_logger
# Import load_settings
from src.primary.settings_manager import load_settings, get_ssl_verify_setting
import importlib
import random

# Get app-specific logger
logger = get_logger("readarr")

# Use a session for better performance
session = requests.Session()

# Default API timeout in seconds - used as fallback only
API_TIMEOUT = 30

def check_connection(api_url: str, api_key: str, api_timeout: int) -> bool:
    """Check the connection to Readarr API."""
    try:
        # Ensure api_url is properly formatted
        if not api_url:
            logger.error("API URL is empty or not set")
            return False
            
        # Make sure api_url has a scheme
        if not (api_url.startswith('http://') or api_url.startswith('https://')):
            logger.error(f"Invalid URL format: {api_url} - URL must start with http:// or https://")
            return False
            
        # Ensure URL doesn't end with a slash before adding the endpoint
        base_url = api_url.rstrip('/')
        full_url = f"{base_url}/api/v1/system/status"
        
        # Add User-Agent header to identify Huntarr
        headers = {
            "X-Api-Key": api_key,
            "User-Agent": "Huntarr/1.0 (https://github.com/plexguide/Huntarr.io)"
        }
        
        response = requests.get(full_url, headers=headers, timeout=api_timeout, verify=get_ssl_verify_setting())
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        logger.debug("Successfully connected to Readarr.")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Error connecting to Readarr: {e}")
        return False
    except Exception as e:
        logger.error(f"An unexpected error occurred during Readarr connection check: {e}")
        return False

def get_download_queue_size(api_url: str = None, api_key: str = None, timeout: int = 30) -> int:
    """
    Get the current size of the download queue.
    
    Args:
        api_url: Optional API URL (if not provided, will be fetched from settings)
        api_key: Optional API key (if not provided, will be fetched from settings)
        timeout: Timeout in seconds for the request
    
    Returns:
        The number of items in the download queue, or 0 if the request failed
    """
    try:
        # If API URL and key are provided, use them directly
        if api_url and api_key:
            # Clean up API URL
            api_url = api_url.rstrip('/')
            url = f"{api_url}/api/v1/queue"
            
            # Headers
            headers = {
                "X-Api-Key": api_key,
                "Content-Type": "application/json"
            }
            verify_ssl = get_ssl_verify_setting()
            # Make the request
            response = session.get(url, headers=headers, timeout=timeout, verify=verify_ssl)
            response.raise_for_status()
            
            # Parse JSON response
            data = response.json()
            if "totalRecords" in data:
                return data["totalRecords"]
            return 0
        else:
            # Use the arr_request function if API URL and key aren't provided
            response = arr_request("queue", count_api=False)
            if response and "totalRecords" in response:
                return response["totalRecords"]
            return 0
    except Exception as e:
        logger.error(f"Error getting download queue size: {e}")
        return 0

def arr_request(endpoint: str, method: str = "GET", data: Dict = None, app_type: str = "readarr",
                api_url: str = None, api_key: str = None, api_timeout: int = None, 
                params: Dict = None, instance_data: Dict = None, count_api: bool = True) -> Any:
    """
    Make a request to the Readarr API.
    
    This function handles making API requests to Readarr, with automatic
    instance detection or manual override of API details.
    
    Args:
        endpoint: The API endpoint to call (relative path)
        method: HTTP method (GET, POST, PUT, DELETE)
        data: Optional data payload for POST/PUT requests
        app_type: Application type (default: readarr)
        api_url: Optional URL override (if not using instances)
        api_key: Optional API key override (if not using instances)
        api_timeout: Optional timeout override
        params: Optional query parameters
        instance_data: Optional specific instance data to use
        
    Returns:
        The parsed JSON response or None if the request failed
    """
    # Initialize logger
    logger = get_logger(app_type)
    
    # Try to get instance data if not provided directly
    if not instance_data and not (api_url and api_key):
        # Import at function level to avoid circular imports
        try:
            module_name = f'src.primary.apps.{app_type}'
            module = importlib.import_module(module_name)
            if hasattr(module, 'get_configured_instances'):
                instances = module.get_configured_instances()
                if instances:
                    # Use the first instance by default
                    instance_data = instances[0]
        except (ImportError, AttributeError) as e:
            logger.error(f"Error importing module for {app_type}: {e}")
    
    # Get the API details - either from instance_data, direct parameters, or by loading settings
    if instance_data:
        # Instance data directly provided or loaded above
        url = instance_data.get('api_url', '')
        key = instance_data.get('api_key', '')
        timeout = api_timeout or 60  # Default timeout
    elif api_url and api_key:
        # Direct parameters provided
        url = api_url
        key = api_key
        timeout = api_timeout or 60  # Default timeout
    else:
        # No valid parameters, try loading from settings
        try:
            from src.primary.settings_manager import load_settings
            settings = load_settings(app_type)
            url = settings.get('api_url', '')
            key = settings.get('api_key', '')
            timeout = api_timeout or settings.get('api_timeout', 60)
        except Exception as e:
            logger.error(f"Error loading {app_type} settings: {e}")
            return None
    
    # Validate the required parameters
    if not url or not key:
        logger.error(f"Missing API URL or key for {app_type}")
        return None
    
    # Normalize the URL
    url = url.rstrip('/')
    
    # Ensure endpoint starts correctly
    endpoint = endpoint.lstrip('/')
    
    # API version path - different for each app
    api_version = "v1"  # Default for Readarr
    
    # Construct the full URL
    full_url = f"{url}/api/{api_version}/{endpoint}"
    
    # Set up headers
    headers = {
        "X-Api-Key": key,
        "Content-Type": "application/json",
        "User-Agent": f"Huntarr/1.0 ({app_type})"
    }
    
    # Get SSL verification setting
    verify_ssl = get_ssl_verify_setting()
    if not verify_ssl:
        logger.debug("SSL verification disabled by user setting")
    
    # Log the request
    logger.debug(f"Making {method} request to {full_url}")
    
    # Make the request with appropriate method
    try:
        if method.upper() == "GET":
            response = requests.get(full_url, headers=headers, params=params, timeout=timeout, verify=verify_ssl)
        elif method.upper() == "POST":
            response = requests.post(full_url, headers=headers, json=data, timeout=timeout, verify=verify_ssl)
        elif method.upper() == "PUT":
            response = requests.put(full_url, headers=headers, json=data, timeout=timeout, verify=verify_ssl)
        elif method.upper() == "DELETE":
            response = requests.delete(full_url, headers=headers, timeout=timeout, verify=verify_ssl)
        else:
            logger.error(f"Unsupported HTTP method: {method}")
            return None
        
        # Check for errors
        response.raise_for_status()
        
        # Increment API counter only if count_api is True and request was successful
        if count_api:
            try:
                from src.primary.stats_manager import increment_hourly_cap
                increment_hourly_cap("readarr")
            except Exception as e:
                logger.warning(f"Failed to increment API counter for readarr: {e}")
        
        # Parse JSON response
        if response.text:
            return response.json()
        return {}
        
    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed: {e}")
        return None

def get_books_with_missing_files() -> List[Dict]:
    """
    Get a list of books with missing files (not downloaded/available).
    
    Returns:
        A list of book objects with missing files
    """
    # First, get all books
    books = arr_request("book", count_api=False)
    if not books:
        return []
    
    # Filter for books with missing files
    missing_books = []
    for book in books:
        # Check if book is monitored and doesn't have a file
        if book.get("monitored", False) and not book.get("bookFile", None):
            missing_books.append(book)
    
    return missing_books

def get_cutoff_unmet_books(api_url: Optional[str] = None, api_key: Optional[str] = None, api_timeout: Optional[int] = None) -> List[Dict]:
    """
    Get a list of books that don't meet their quality profile cutoff.
    Accepts optional API credentials.
    
    Args:
        api_url: Optional API URL
        api_key: Optional API key
        api_timeout: Optional API timeout
        
    Returns:
        A list of book objects that need quality upgrades
    """
    # The cutoffUnmet endpoint in Readarr
    params = "cutoffUnmet=true"
    # Pass credentials to arr_request
    books = arr_request(f"wanted/cutoff?{params}", api_url=api_url, api_key=api_key, api_timeout=api_timeout, count_api=False)
    if not books or "records" not in books:
        return []
    
    return books.get("records", [])

def get_wanted_missing_books(api_url: str, api_key: str, api_timeout: int, monitored_only: bool = True) -> List[Dict]:
    """
    Get wanted/missing books from Readarr, handling pagination.

    Args:
        api_url: The base URL of the Readarr API.
        api_key: The API key for authentication.
        api_timeout: Timeout for the API request.
        monitored_only: If True, only return monitored books (Readarr API default seems to handle this).

    Returns:
        A list of dictionaries, each representing a missing book, or an empty list on error.
    """
    all_missing_books = []
    page = 1
    page_size = 100 # Adjust as needed, check Readarr API limits
    endpoint = "wanted/missing"

    # Ensure api_url is properly formatted
    if not (api_url.startswith('http://') or api_url.startswith('https://')):
        logger.error(f"Invalid URL format: {api_url}")
        return []
    base_url = api_url.rstrip('/')
    url = f"{base_url}/api/v1/{endpoint.lstrip('/')}"
    # Add User-Agent header to identify Huntarr
    headers = {
        "X-Api-Key": api_key,
        "User-Agent": "Huntarr/1.0 (https://github.com/plexguide/Huntarr.io)",
        "Content-Type": "application/json"
    }

    while True:
        params = {
            'page': page,
            'pageSize': page_size,
            # Removed sorting parameters due to potential API issues
            # 'sortKey': 'author.sortName',
            # 'sortDirection': 'ascending',
            # 'monitored': monitored_only # Note: Check if Readarr API supports this directly for wanted/missing
        }
        try:
            response = requests.get(url, headers=headers, params=params, timeout=api_timeout, verify=get_ssl_verify_setting())
            response.raise_for_status()
            data = response.json()

            if not data or 'records' not in data or not data['records']:
                break # No more data or unexpected format

            all_missing_books.extend(data['records'])

            total_records = data.get('totalRecords', 0)
            if len(all_missing_books) >= total_records:
                break # We have fetched all records

            page += 1

        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching missing books (page {page}) from {url}: {e}")
            return [] # Return empty list on error
        except json.JSONDecodeError:
            logger.error(f"Error decoding JSON response from {url} (page {page}). Response: {response.text[:200]}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching missing books (page {page}): {e}", exc_info=True)
            return []

    logger.info(f"Successfully fetched {len(all_missing_books)} missing books from Readarr.")
    return all_missing_books

def get_wanted_missing_books_random_page(api_url: str, api_key: str, api_timeout: int, monitored_only: bool, count: int) -> List[Dict]:
    """
    Get a specified number of random missing books by selecting a random page.
    This is much more efficient for very large libraries.
    
    Args:
        api_url: The base URL of the Readarr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        monitored_only: Whether to include only monitored books
        count: How many books to return
        
    Returns:
        A list of randomly selected missing books, up to the requested count
    """
    endpoint = "wanted/missing"
    page_size = 100  # Smaller page size for better performance
    retries = 2
    retry_delay = 3
    
    # Ensure api_url is properly formatted
    if not (api_url.startswith('http://') or api_url.startswith('https://')):
        logger.error(f"Invalid URL format: {api_url}")
        return []
    base_url = api_url.rstrip('/')
    url = f"{base_url}/api/v1/{endpoint.lstrip('/')}"
    
    # Add User-Agent header to identify Huntarr
    headers = {
        "X-Api-Key": api_key,
        "User-Agent": "Huntarr/1.0 (https://github.com/plexguide/Huntarr.io)",
        "Content-Type": "application/json"
    }
    
    # First, make a request to get just the total record count (page 1 with size=1)
    params = {
        'page': 1,
        'pageSize': 1
    }
    
    for attempt in range(retries + 1):
        try:
            # Get total record count from a minimal query
            logger.debug(f"Getting missing books count (attempt {attempt+1}/{retries+1})")
            response = requests.get(url, headers=headers, params=params, timeout=api_timeout)
            response.raise_for_status()
            
            if not response.content:
                logger.warning(f"Empty response when getting missing count (attempt {attempt+1})")
                if attempt < retries:
                    time.sleep(retry_delay)
                    continue
                return []
                
            try:
                data = response.json()
                total_records = data.get('totalRecords', 0)
                
                if total_records == 0:
                    logger.info("No missing books found in Readarr.")
                    return []
                    
                # Calculate total pages with our desired page size
                total_pages = (total_records + page_size - 1) // page_size
                logger.info(f"Found {total_records} total missing books across {total_pages} pages")
                
                if total_pages == 0:
                    return []
                    
                # Select a random page
                random_page = random.randint(1, total_pages)
                logger.info(f"Selected random page {random_page} of {total_pages} for missing books")
                
                # Get books from the random page
                params = {
                    'page': random_page,
                    'pageSize': page_size
                }
                
                response = requests.get(url, headers=headers, params=params, timeout=api_timeout)
                response.raise_for_status()
                
                if not response.content:
                    logger.warning(f"Empty response when getting missing books page {random_page}")
                    return []
                    
                try:
                    data = response.json()
                    records = data.get('records', [])
                    logger.info(f"Retrieved {len(records)} missing books from page {random_page}")
                    
                    # Apply monitored filter if requested (Readarr API may not support this directly)
                    if monitored_only:
                        filtered_records = [
                            book for book in records
                            if book.get('monitored', False)
                        ]
                        logger.debug(f"Filtered to {len(filtered_records)} monitored missing books")
                        records = filtered_records
                    
                    # Select random books from this page
                    if len(records) > count:
                        selected_records = random.sample(records, count)
                        logger.debug(f"Randomly selected {len(selected_records)} missing books from page {random_page}")
                        return selected_records
                    else:
                        # If we have fewer books than requested, return all of them
                        logger.debug(f"Returning all {len(records)} missing books from page {random_page} (fewer than requested {count})")
                        return records
                        
                except json.JSONDecodeError as jde:
                    logger.error(f"Failed to decode JSON response for missing books page {random_page}: {str(jde)}")
                    if attempt < retries:
                        time.sleep(retry_delay)
                        continue
                    return []
                    
            except json.JSONDecodeError as jde:
                logger.error(f"Failed to decode JSON response for missing books count: {str(jde)}")
                if attempt < retries:
                    time.sleep(retry_delay)
                    continue
                return []
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting missing books from Readarr (attempt {attempt+1}): {str(e)}")
            if attempt < retries:
                time.sleep(retry_delay)
                continue
            return []
            
        except Exception as e:
            logger.error(f"Unexpected error getting missing books (attempt {attempt+1}): {str(e)}", exc_info=True)
            if attempt < retries:
                time.sleep(retry_delay)
                continue
            return []
    
    # If we get here, all retries failed
    logger.error("All attempts to get missing books failed")
    return []

def refresh_author(author_id: int, api_url: Optional[str] = None, api_key: Optional[str] = None, api_timeout: Optional[int] = None) -> bool:
    """
    Refresh functionality has been removed as it was a performance bottleneck.
    This function now returns a success value without making any API calls.
    
    Args:
        author_id: The ID of the author to refresh
        api_url: Optional API URL
        api_key: Optional API key
        api_timeout: Optional API timeout
        
    Returns:
        Always returns True to simulate success
    """
    logger.debug(f"Refresh functionality disabled for author ID: {author_id}")
    # Always return success without making any API calls
    return True

def book_search(book_ids: List[int], api_url: Optional[str] = None, api_key: Optional[str] = None, api_timeout: Optional[int] = None) -> bool:
    """
    Trigger a search for one or more books.
    Accepts optional API credentials.
    
    Args:
        book_ids: A list of book IDs to search for
        api_url: Optional API URL
        api_key: Optional API key
        api_timeout: Optional API timeout
        
    Returns:
        True if the search command was successful, False otherwise
    """
    endpoint = "command"
    data = {
        "name": "BookSearch",
        "bookIds": book_ids
    }
    
    # Pass credentials to arr_request
    response = arr_request(endpoint, method="POST", data=data, api_url=api_url, api_key=api_key, api_timeout=api_timeout, count_api=False)
    # Return the response object (contains command ID) instead of just True/False
    # The calling function expects the command object now.
    return response 

def get_author_details(api_url: str, api_key: str, author_id: int, api_timeout: int = 120) -> Optional[Dict]:
    """Fetches details for a specific author from the Readarr API."""
    endpoint = f"{api_url}/api/v1/author/{author_id}"
    headers = {'X-Api-Key': api_key}
    try:
        response = requests.get(endpoint, headers=headers, timeout=api_timeout, verify=get_ssl_verify_setting())
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        author_data = response.json()
        logger.debug(f"Successfully fetched details for author ID {author_id}.")
        return author_data
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching author details for ID {author_id} from {endpoint}: {e}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred fetching author details for ID {author_id}: {e}")
        return None

def search_books(api_url: str, api_key: str, book_ids: List[int], api_timeout: int = 120) -> Optional[Dict]:
    """Triggers a search for specific book IDs in Readarr."""
    
    # Check API limit before making request
    try:
        from src.primary.stats_manager import check_hourly_cap_exceeded
        if check_hourly_cap_exceeded("readarr"):
            logger.warning(f"🛑 Readarr API hourly limit reached - skipping book search for {len(book_ids)} books")
            return None
    except Exception as e:
        logger.error(f"Error checking hourly API cap: {e}")
        # Continue with request if cap check fails - safer than skipping
    
    endpoint = f"{api_url}/api/v1/command" # This uses the full URL, not arr_request
    headers = {'X-Api-Key': api_key}
    payload = {
        'name': 'BookSearch',
        'bookIds': book_ids
    }
    try:
        # This uses requests.post directly, not arr_request. It's already correct.
        response = requests.post(endpoint, headers=headers, json=payload, timeout=api_timeout, verify=get_ssl_verify_setting())
        response.raise_for_status()
        command_data = response.json()
        command_id = command_data.get('id')
        logger.info(f"Successfully triggered BookSearch command for book IDs: {book_ids}. Command ID: {command_id}")
        
        # Increment API counter after successful request
        try:
            from src.primary.stats_manager import increment_hourly_cap
            increment_hourly_cap("readarr", 1)
            logger.debug(f"Incremented Readarr hourly API cap for book search ({len(book_ids)} books)")
        except Exception as cap_error:
            logger.error(f"Failed to increment hourly API cap for book search: {cap_error}")
        
        return command_data # Return the full command object which includes the ID
    except requests.exceptions.RequestException as e:
        logger.error(f"Error triggering BookSearch command for book IDs {book_ids} via {endpoint}: {e}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred triggering BookSearch for book IDs {book_ids}: {e}")
        return None

def get_or_create_tag(api_url: str, api_key: str, api_timeout: int, tag_label: str) -> Optional[int]:
    """
    Get existing tag ID or create a new tag in Readarr.
    
    Args:
        api_url: The base URL of the Readarr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        tag_label: The label/name of the tag to create or find
        
    Returns:
        The tag ID if successful, None otherwise
    """
    try:
        # First, check if the tag already exists
        response = arr_request("tag", api_url=api_url, api_key=api_key, api_timeout=api_timeout, count_api=False)
        if response:
            for tag in response:
                if tag.get('label') == tag_label:
                    tag_id = tag.get('id')
                    logger.debug(f"Found existing tag '{tag_label}' with ID: {tag_id}")
                    return tag_id
        
        # Tag doesn't exist, create it
        tag_data = {"label": tag_label}
        response = arr_request("tag", method="POST", data=tag_data, api_url=api_url, api_key=api_key, api_timeout=api_timeout, count_api=False)
        if response and 'id' in response:
            tag_id = response['id']
            logger.info(f"Created new tag '{tag_label}' with ID: {tag_id}")
            return tag_id
        else:
            logger.error(f"Failed to create tag '{tag_label}'. Response: {response}")
            return None
            
    except Exception as e:
        logger.error(f"Error managing tag '{tag_label}': {e}")
        return None

def add_tag_to_author(api_url: str, api_key: str, api_timeout: int, author_id: int, tag_id: int) -> bool:
    """
    Add a tag to an author in Readarr.
    
    Args:
        api_url: The base URL of the Readarr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        author_id: The ID of the author to tag
        tag_id: The ID of the tag to add
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # First get the current author data
        author_data = arr_request(f"author/{author_id}", api_url=api_url, api_key=api_key, api_timeout=api_timeout, count_api=False)
        if not author_data:
            logger.error(f"Failed to get author data for ID: {author_id}")
            return False
        
        # Check if the tag is already present
        current_tags = author_data.get('tags', [])
        if tag_id in current_tags:
            logger.debug(f"Tag {tag_id} already exists on author {author_id}")
            return True
        
        # Add the new tag to the list
        current_tags.append(tag_id)
        author_data['tags'] = current_tags
        
        # Update the author with the new tags
        response = arr_request(f"author/{author_id}", method="PUT", data=author_data, api_url=api_url, api_key=api_key, api_timeout=api_timeout, count_api=False)
        if response:
            logger.debug(f"Successfully added tag {tag_id} to author {author_id}")
            return True
        else:
            logger.error(f"Failed to update author {author_id} with tag {tag_id}")
            return False
            
    except Exception as e:
        logger.error(f"Error adding tag {tag_id} to author {author_id}: {e}")
        return False

def tag_processed_author(api_url: str, api_key: str, api_timeout: int, author_id: int, tag_label: str = "huntarr-missing") -> bool:
    """
    Tag an author in Readarr with the specified tag.
    
    Args:
        api_url: The base URL of the Readarr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        author_id: The ID of the author to tag
        tag_label: The tag to apply (huntarr-missing, huntarr-upgraded)
        
    Returns:
        True if the tagging was successful, False otherwise
    """
    try:
        # Get or create the tag
        tag_id = get_or_create_tag(api_url, api_key, api_timeout, tag_label)
        if tag_id is None:
            logger.error(f"Failed to get or create tag '{tag_label}' in Readarr")
            return False
            
        # Add the tag to the author
        success = add_tag_to_author(api_url, api_key, api_timeout, author_id, tag_id)
        if success:
            logger.debug(f"Successfully tagged Readarr author {author_id} with '{tag_label}'")
            return True
        else:
            logger.error(f"Failed to add tag '{tag_label}' to Readarr author {author_id}")
            return False
            
    except Exception as e:
        logger.error(f"Error tagging Readarr author {author_id} with '{tag_label}': {e}")
        return False

def get_quality_profiles(api_url: str, api_key: str, api_timeout: int) -> Optional[List[Dict]]:
    """
    Get all quality profiles configured in Readarr.

    Args:
        api_url: The base URL of the Readarr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request

    Returns:
        A list of quality profile objects, or None if the request failed.
        Each profile contains: id, name, upgradeAllowed, cutoff, items, etc.
    """
    try:
        logger.debug("Fetching quality profiles from Readarr...")
        
        # Use the qualityProfile endpoint - this doesn't count toward API limits since it's configuration data
        # Note: Readarr uses API v1, not v3 like Sonarr/Radarr
        profiles = arr_request("qualityProfile", api_url=api_url, api_key=api_key, api_timeout=api_timeout, count_api=False)
        
        if profiles is None:
            logger.error("Failed to retrieve quality profiles from Readarr API.")
            return None
        
        logger.debug(f"Found {len(profiles)} quality profiles in Readarr")
        
        # Log profile names for debugging
        profile_names = [profile.get('name', 'Unknown') for profile in profiles]
        logger.debug(f"Quality profiles: {', '.join(profile_names)}")
        
        return profiles
        
    except Exception as e:
        logger.error(f"Error retrieving quality profiles: {str(e)}")
        return None