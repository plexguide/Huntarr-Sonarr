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
        
        response = requests.get(full_url, headers={"X-Api-Key": api_key}, timeout=api_timeout)
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        logger.info("Successfully connected to Readarr.")
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
            
            # Make the request
            response = session.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            
            # Parse JSON response
            data = response.json()
            if "totalRecords" in data:
                return data["totalRecords"]
            return 0
        else:
            # Use the arr_request function if API URL and key aren't provided
            response = arr_request("queue")
            if response and "totalRecords" in response:
                return response["totalRecords"]
            return 0
    except Exception as e:
        logger.error(f"Error getting download queue size: {e}")
        return 0

def arr_request(endpoint: str, method: str = "GET", data: Dict = None, app_type: str = "readarr") -> Any:
    """
    Make a request to the Readarr API.
    
    Args:
        endpoint: The API endpoint to call
        method: HTTP method (GET, POST, PUT, DELETE)
        data: Optional data to send with the request
        app_type: The app type (readarr by default)
        
    Returns:
        The JSON response from the API, or None if the request failed
    """
    # Load settings for this app
    settings = load_settings(app_type)
    api_url = settings.get('api_url', '')
    api_key = settings.get('api_key', '')
    api_timeout = settings.get('api_timeout', 60)
    
    if not api_url or not api_key:
        logger.error("API URL or API key is missing. Check your settings.")
        return None
    
    # Ensure api_url has a scheme
    if not (api_url.startswith('http://') or api_url.startswith('https://')):
        logger.error(f"Invalid URL format: {api_url} - URL must start with http:// or https://")
        return None
    
    # Determine the API version
    api_base = "api/v1"  # Readarr uses v1
    
    # Full URL
    url = f"{api_url.rstrip('/')}/{api_base}/{endpoint.lstrip('/')}"
    
    # Headers
    headers = {
        "X-Api-Key": api_key,
        "Content-Type": "application/json"
    }
    
    try:
        if method == "GET":
            response = session.get(url, headers=headers, timeout=api_timeout)
        elif method == "POST":
            response = session.post(url, headers=headers, json=data, timeout=api_timeout)
        elif method == "PUT":
            response = session.put(url, headers=headers, json=data, timeout=api_timeout)
        elif method == "DELETE":
            response = session.delete(url, headers=headers, timeout=api_timeout)
        else:
            logger.error(f"Unsupported HTTP method: {method}")
            return None
        
        # Check for errors
        response.raise_for_status()
        
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
    books = arr_request("book")
    if not books:
        return []
    
    # Filter for books with missing files
    missing_books = []
    for book in books:
        # Check if book is monitored and doesn't have a file
        if book.get("monitored", False) and not book.get("bookFile", None):
            missing_books.append(book)
    
    return missing_books

def get_cutoff_unmet_books() -> List[Dict]:
    """
    Get a list of books that don't meet their quality profile cutoff.
    
    Returns:
        A list of book objects that need quality upgrades
    """
    # The cutoffUnmet endpoint in Readarr
    params = "cutoffUnmet=true"
    books = arr_request(f"wanted/cutoff?{params}")
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
    headers = {"X-Api-Key": api_key}

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
            response = requests.get(url, headers=headers, params=params, timeout=api_timeout)
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

def refresh_author(author_id: int) -> bool:
    """
    Refresh an author in Readarr.
    
    Args:
        author_id: The ID of the author to refresh
        
    Returns:
        True if the refresh was successful, False otherwise
    """
    endpoint = f"command"
    data = {
        "name": "RefreshAuthor",
        "authorId": author_id
    }
    
    response = arr_request(endpoint, method="POST", data=data)
    if response:
        logger.debug(f"Refreshed author ID {author_id}")
        return True
    return False

def book_search(book_ids: List[int]) -> bool:
    """
    Trigger a search for one or more books.
    
    Args:
        book_ids: A list of book IDs to search for
        
    Returns:
        True if the search command was successful, False otherwise
    """
    endpoint = "command"
    data = {
        "name": "BookSearch",
        "bookIds": book_ids
    }
    
    response = arr_request(endpoint, method="POST", data=data)
    if response:
        logger.debug(f"Triggered search for book IDs: {book_ids}")
        return True
    return False

def get_author_details(api_url: str, api_key: str, author_id: int, api_timeout: int = 120) -> Optional[Dict]:
    """Fetches details for a specific author from the Readarr API."""
    endpoint = f"{api_url}/api/v1/author/{author_id}"
    headers = {'X-Api-Key': api_key}
    try:
        response = requests.get(endpoint, headers=headers, timeout=api_timeout)
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
    endpoint = f"{api_url}/api/v1/command"
    headers = {'X-Api-Key': api_key}
    payload = {
        'name': 'BookSearch',
        'bookIds': book_ids
    }
    try:
        response = requests.post(endpoint, headers=headers, json=payload, timeout=api_timeout)
        response.raise_for_status()
        command_data = response.json()
        command_id = command_data.get('id')
        logger.info(f"Successfully triggered BookSearch command for book IDs: {book_ids}. Command ID: {command_id}")
        return command_data # Return the full command object which includes the ID
    except requests.exceptions.RequestException as e:
        logger.error(f"Error triggering BookSearch command for book IDs {book_ids} via {endpoint}: {e}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred triggering BookSearch for book IDs {book_ids}: {e}")
        return None

# Function to get wanted/missing books with pagination
def get_wanted_missing_books(api_url: str, api_key: str, api_timeout: int = 120, monitored_only: bool = True) -> Optional[List[Dict]]:
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
    headers = {"X-Api-Key": api_key}

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
            response = requests.get(url, headers=headers, params=params, timeout=api_timeout)
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