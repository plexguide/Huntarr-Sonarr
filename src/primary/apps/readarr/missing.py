#!/usr/bin/env python3
"""
Missing Books Processing for Readarr
Handles searching for missing books in Readarr
"""

import time
import random
from typing import List, Dict, Any, Set, Callable
from src.primary.utils.logger import get_logger
from src.primary.apps.readarr import api as readarr_api
from src.primary.stats_manager import increment_stat, check_hourly_cap_exceeded
from src.primary.stateful_manager import is_processed, add_processed_id
from src.primary.utils.history_utils import log_processed_media
from src.primary.settings_manager import load_settings, get_advanced_setting
from src.primary.state import check_state_reset

# Get logger for the app
readarr_logger = get_logger("readarr")

def process_missing_books(
    app_settings: Dict[str, Any],
    stop_check: Callable[[], bool] # Function to check if stop is requested
) -> bool:
    """
    Process missing books in Readarr based on provided settings.
    
    Args:
        app_settings: Dictionary containing all settings for Readarr
        stop_check: A function that returns True if the process should stop
    
    Returns:
        True if any books were processed, False otherwise.
    """
    readarr_logger.debug("Starting missing books processing cycle for Readarr.")
    processed_any = False
    
    # Reset state files if enough time has passed
    check_state_reset("readarr")
    
    # Load settings to check if tagging is enabled
    readarr_settings = load_settings("readarr")
    tag_processed_items = readarr_settings.get("tag_processed_items", True)
    
    # Get the settings for the instance
    general_settings = readarr_api.load_settings('general')
    
    # Extract necessary settings
    api_url = app_settings.get("api_url", "").strip()
    api_key = app_settings.get("api_key", "").strip()
    api_timeout = get_advanced_setting("api_timeout", 120)  # Use database value
    instance_name = app_settings.get("instance_name", "Readarr Default")
    
    readarr_logger.debug(f"Using API timeout of {api_timeout} seconds for Readarr")
    
    monitored_only = app_settings.get("monitored_only", True)
    skip_future_releases = app_settings.get("skip_future_releases", True)
    hunt_missing_books = app_settings.get("hunt_missing_books", 0)
    
    # Use advanced settings from database for command operations
    command_wait_delay = get_advanced_setting("command_wait_delay", 1)
    command_wait_attempts = get_advanced_setting("command_wait_attempts", 600)

    # Configuration logging removed to reduce log spam

    if not api_url or not api_key:
        readarr_logger.error("API URL or Key not configured in settings. Cannot process missing books.")
        return False

    # Skip if hunt_missing_books is set to 0
    if hunt_missing_books <= 0:
        readarr_logger.info("'hunt_missing_books' setting is 0 or less. Skipping missing book processing.")
        return False

    # Check for stop signal
    if stop_check():
        readarr_logger.info("Stop requested before starting missing books. Aborting...")
        return False

    # Get missing books
    readarr_logger.debug(f"Retrieving books with missing files...")
    # Use efficient random page selection instead of fetching all books
    missing_books_data = readarr_api.get_wanted_missing_books_random_page(
        api_url, api_key, api_timeout, monitored_only, hunt_missing_books * 2
    )
    
    if missing_books_data is None or not missing_books_data: # API call failed or no books
        if missing_books_data is None:
            readarr_logger.error("Failed to retrieve missing books from Readarr API.")
        else:
            readarr_logger.info("No missing books found.")
        return False
    
    readarr_logger.debug(f"Retrieved {len(missing_books_data)} missing books from random page selection.")

    # Check for stop signal after retrieving books
    if stop_check():
        readarr_logger.info("Stop requested after retrieving missing books. Aborting...")
        return False

    # Filter out already processed books using stateful management (now book-based instead of author-based)
    unprocessed_books = []
    for book in missing_books_data:
        book_id = str(book.get("id"))
        if not is_processed("readarr", instance_name, book_id):
            unprocessed_books.append(book)
        else:
            readarr_logger.debug(f"Skipping already processed book ID: {book_id}")

    readarr_logger.info(f"Found {len(unprocessed_books)} unprocessed missing books out of {len(missing_books_data)} total.")
    
    if not unprocessed_books:
        readarr_logger.info("No unprocessed missing books found. All available books have been processed.")
        return False

    # Select individual books to process (fixed: was selecting authors, now selects books)
    readarr_logger.info(f"Randomly selecting up to {hunt_missing_books} individual books to search.")
    books_to_process = random.sample(unprocessed_books, min(hunt_missing_books, len(unprocessed_books)))

    readarr_logger.info(f"Selected {len(books_to_process)} individual books to search for missing items.")
    
    # Add detailed logging for selected books
    if books_to_process:
        readarr_logger.info(f"Books selected for processing in this cycle:")
        for idx, book in enumerate(books_to_process):
            book_id = book.get("id")
            book_title = book.get("title", "Unknown Title")
            author_id = book.get("authorId", "Unknown")
            readarr_logger.info(f"  {idx+1}. '{book_title}' (ID: {book_id}, Author ID: {author_id})")

    processed_count = 0
    processed_books = [] # Track book titles processed

    # Process each individual book
    for book in books_to_process:
        if stop_check():
            readarr_logger.info("Stop signal received, aborting Readarr missing cycle.")
            break
        
        # Check API limit before processing each book
        try:
            if check_hourly_cap_exceeded("readarr"):
                readarr_logger.warning(f"🛑 Readarr API hourly limit reached - stopping missing books processing after {processed_count} books")
                break
        except Exception as e:
            readarr_logger.error(f"Error checking hourly API cap: {e}")
            # Continue processing if cap check fails - safer than stopping

        book_id = book.get("id")
        book_title = book.get("title", f"Unknown Book ID {book_id}")
        author_id = book.get("authorId")
        
        # Get author name for logging
        author_info = readarr_api.get_author_details(api_url, api_key, author_id, api_timeout) if author_id else None
        author_name = author_info.get("authorName", f"Author ID {author_id}") if author_info else "Unknown Author"

        readarr_logger.info(f"Processing missing book: '{book_title}' by {author_name} (Book ID: {book_id})")

        # Search for this individual book (fixed: was searching all books by author)
        readarr_logger.info(f"  - Searching for individual book: '{book_title}'...")
        
        # Mark book as processed BEFORE triggering search to prevent duplicates
        add_processed_id("readarr", instance_name, str(book_id))
        readarr_logger.debug(f"Added book ID {book_id} to processed list for {instance_name}")
        
        # Search for the specific book (using book search instead of author search)
        search_command_result = readarr_api.search_books(api_url, api_key, [book_id], api_timeout)

        if search_command_result:
            # Extract command ID if the result is a dictionary, otherwise use the result directly
            command_id = search_command_result.get('id') if isinstance(search_command_result, dict) else search_command_result
            readarr_logger.info(f"Triggered book search command {command_id} for '{book_title}' by {author_name}.")
            increment_stat("readarr", "hunted")
            
            # Tag the book's author if enabled (keep author tagging as it's still useful)
            if tag_processed_items and author_id:
                from src.primary.settings_manager import get_custom_tag
                custom_tag = get_custom_tag("readarr", "missing", "huntarr-missing")
                try:
                    readarr_api.tag_processed_author(api_url, api_key, api_timeout, author_id, custom_tag)
                    readarr_logger.debug(f"Tagged author {author_id} with '{custom_tag}'")
                except Exception as e:
                    readarr_logger.warning(f"Failed to tag author {author_id} with '{custom_tag}': {e}")
            
            # Log history entry for this specific book
            media_name = f"{author_name} - {book_title}"
            log_processed_media("readarr", media_name, book_id, instance_name, "missing")
            readarr_logger.debug(f"Logged missing book history entry: {media_name} (ID: {book_id})")
            
            processed_count += 1
            processed_books.append(f"'{book_title}' by {author_name}")
            processed_any = True
            readarr_logger.info(f"Processed {processed_count}/{len(books_to_process)} books for missing search this cycle.")
        else:
            readarr_logger.error(f"Failed to trigger search for book '{book_title}' by {author_name}.")

        if processed_count >= hunt_missing_books:
            readarr_logger.info(f"Reached target of {hunt_missing_books} books processed for this cycle.")
            break

    if processed_books:
        # Log first few books, then summarize if there are many
        if len(processed_books) <= 3:
            books_list = ', '.join(processed_books)
            readarr_logger.info(f'Completed processing {processed_count} books for missing search this cycle: {books_list}')
        else:
            first_books = ', '.join(processed_books[:3])
            readarr_logger.info(f'Completed processing {processed_count} books for missing search this cycle: {first_books} and {len(processed_books)-3} others')
    else:
        readarr_logger.info(f"Completed processing {processed_count} books for missing search this cycle.")

    return processed_any