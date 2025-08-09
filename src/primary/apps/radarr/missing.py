#!/usr/bin/env python3
"""
Missing Movies Processing for Radarr
Handles searching for missing movies in Radarr
"""

import os
import time
import random
import datetime
from typing import List, Dict, Any, Set, Callable
from src.primary.utils.logger import get_logger
from src.primary.apps.radarr import api as radarr_api
from src.primary.stats_manager import increment_stat_only, check_hourly_cap_exceeded
from src.primary.stateful_manager import is_processed, add_processed_id
from src.primary.utils.history_utils import log_processed_media
from src.primary.settings_manager import load_settings, get_advanced_setting

# Get logger for the app
radarr_logger = get_logger("radarr")

def parse_date(date_str):
    """Parse date string, handling various ISO formats from Radarr API"""
    if not date_str:
        return None
    
    try:
        # Handle milliseconds (e.g., "2024-01-01T00:00:00.000Z")
        clean_date_str = date_str
        if '.' in clean_date_str and 'Z' in clean_date_str:
            clean_date_str = clean_date_str.split('.')[0] + 'Z'
        
        # Handle different timezone formats
        if clean_date_str.endswith('Z'):
            clean_date_str = clean_date_str[:-1] + '+00:00'
        elif '+' not in clean_date_str and '-' not in clean_date_str[-6:]:
            # No timezone info, assume UTC
            clean_date_str += '+00:00'
        
        # Parse the release date
        return datetime.datetime.fromisoformat(clean_date_str)
    except (ValueError, TypeError):
        return None

def process_missing_movies(
    app_settings: Dict[str, Any],
    stop_check: Callable[[], bool] # Function to check if stop is requested
) -> bool:
    """
    Process missing movies in Radarr based on provided settings.
    
    Args:
        app_settings: Dictionary containing all settings for Radarr
        stop_check: A function that returns True if the process should stop
    
    Returns:
        True if any movies were processed, False otherwise.
    """
    processed_any = False
    
    # Get instance name - check for instance_name first, fall back to legacy "name" key if needed
    instance_name = app_settings.get("instance_name", app_settings.get("name", "Radarr Default"))
    
    # Load settings to check if tagging is enabled
    radarr_settings = load_settings("radarr")
    tag_processed_items = radarr_settings.get("tag_processed_items", True)
    
    # Log important settings
    radarr_logger.debug("=== Radarr Missing Movies Settings ===")
    radarr_logger.debug(f"Instance Name: {instance_name}")
    
    # Extract necessary settings
    api_url = app_settings.get("api_url", "").strip()
    api_key = app_settings.get("api_key", "").strip()
    api_timeout = get_advanced_setting("api_timeout", 120)  # Use database value
    monitored_only = app_settings.get("monitored_only", True)
    skip_future_releases = app_settings.get("skip_future_releases", True)
    # skip_movie_refresh setting removed as it was a performance bottleneck
    hunt_missing_movies = app_settings.get("hunt_missing_movies", 0)
    
    # Use advanced settings from database for command operations
    command_wait_delay = get_advanced_setting("command_wait_delay", 1)
    command_wait_attempts = get_advanced_setting("command_wait_attempts", 600)
    
    # Configuration logging removed to reduce log spam
    
    radarr_logger.info("Starting missing movies processing cycle for Radarr.")
    
    if not api_url or not api_key:
        radarr_logger.error("API URL or Key not configured in settings. Cannot process missing movies.")
        return False

    # Skip if hunt_missing_movies is set to 0
    if hunt_missing_movies <= 0:
        radarr_logger.info("'hunt_missing_movies' setting is 0 or less. Skipping missing movie processing.")
        return False

    # Check for stop signal
    if stop_check():
        radarr_logger.info("Stop requested before starting missing movies. Aborting...")
        return False
    
    # Get missing movies 
    radarr_logger.debug("Retrieving movies with missing files...")
    # Use efficient random page selection instead of fetching all movies
    missing_movies = radarr_api.get_movies_with_missing_random_page(
        api_url, api_key, api_timeout, monitored_only, hunt_missing_movies * 2
    ) 
    
    if missing_movies is None: # API call failed
        radarr_logger.error("Failed to retrieve missing movies from Radarr API.")
        return False
        
    if not missing_movies:
        radarr_logger.info("No missing movies found.")
        return False
    
    radarr_logger.debug(f"Retrieved {len(missing_movies)} missing movies from random page selection.")
    
    # Skip future releases if enabled
    if skip_future_releases:
        radarr_logger.debug("Filtering out future releases...")
        now = datetime.datetime.now(datetime.timezone.utc)
        
        filtered_movies = []
        skipped_count = 0
        no_date_count = 0
        for movie in missing_movies:
            movie_id = movie.get('id')
            movie_title = movie.get('title', 'Unknown Title')
            release_date_str = movie.get('releaseDate')
            
            if release_date_str:
                release_date = parse_date(release_date_str)
                if release_date:
                    if release_date > now:
                        # Movie has a future release date, skip it
                        radarr_logger.debug(f"Skipping future movie ID {movie_id} ('{movie_title}') - releaseDate is in the future: {release_date}")
                        skipped_count += 1
                        continue
                    else:
                        # Movie release date is in the past, include it
                        radarr_logger.debug(f"Movie ID {movie_id} ('{movie_title}') releaseDate is in the past: {release_date}, including in search")
                        filtered_movies.append(movie)
                else:
                    # Could not parse release date, treat as no date
                    radarr_logger.debug(f"Movie ID {movie_id} ('{movie_title}') has unparseable releaseDate '{release_date_str}' - treating as no release date")
                    if app_settings.get('process_no_release_dates', False):
                        radarr_logger.debug(f"Movie ID {movie_id} ('{movie_title}') has no valid release date but process_no_release_dates is enabled - including in search")
                        filtered_movies.append(movie)
                    else:
                        radarr_logger.debug(f"Skipping movie ID {movie_id} ('{movie_title}') - no valid release date and process_no_release_dates is disabled")
                        no_date_count += 1
            else:
                # No release date available at all
                if app_settings.get('process_no_release_dates', False):
                    radarr_logger.debug(f"Movie ID {movie_id} ('{movie_title}') has no releaseDate field but process_no_release_dates is enabled - including in search")
                    filtered_movies.append(movie)
                else:
                    radarr_logger.debug(f"Skipping movie ID {movie_id} ('{movie_title}') - no releaseDate field and process_no_release_dates is disabled")
                    no_date_count += 1
        
        radarr_logger.debug(f"Filtered out {skipped_count} future releases and {no_date_count} movies with no release dates")
        radarr_logger.debug(f"After filtering: {len(filtered_movies)} movies remaining from {len(missing_movies)} original")
        missing_movies = filtered_movies
    else:
        radarr_logger.debug("Skip future releases is disabled - processing all movies regardless of release date")

    if not missing_movies:
        radarr_logger.debug("No missing movies left to process after filtering future releases.")
        return False
        
    movies_processed = 0
    processing_done = False
    
    # Filter out already processed movies using stateful management
    unprocessed_movies = []
    for movie in missing_movies:
        movie_id = str(movie.get("id"))
        if not is_processed("radarr", instance_name, movie_id):
            unprocessed_movies.append(movie)
        else:
            radarr_logger.debug(f"Skipping already processed movie ID: {movie_id}")
    
    radarr_logger.debug(f"Found {len(unprocessed_movies)} unprocessed missing movies out of {len(missing_movies)} total.")
    
    if not unprocessed_movies:
        radarr_logger.debug("No unprocessed missing movies found. All available movies have been processed.")
        return False
    
    # Always use random selection for missing movies
    radarr_logger.debug(f"Using random selection for missing movies")
    if len(unprocessed_movies) > hunt_missing_movies:
        movies_to_process = random.sample(unprocessed_movies, hunt_missing_movies)
    else:
        movies_to_process = unprocessed_movies
    
    radarr_logger.debug(f"Selected {len(movies_to_process)} movies to process.")
    
    # Add detailed logging for selected movies
    if movies_to_process:
        radarr_logger.info(f"Movies selected for processing in this cycle:")
        for idx, movie in enumerate(movies_to_process):
            movie_id = movie.get("id")
            movie_title = movie.get("title", "Unknown Title")
            year = movie.get("year", "Unknown Year")
            radarr_logger.info(f"  {idx+1}. {movie_title} ({year}) - ID: {movie_id}")
    
    # Process each movie
    for movie in movies_to_process:
        if stop_check():
            radarr_logger.info("Stop requested during processing. Aborting...")
            break
        
        # Check API limit before processing each movie
        try:
            if check_hourly_cap_exceeded("radarr"):
                radarr_logger.warning(f"🛑 Radarr API hourly limit reached - stopping missing movies processing after {movies_processed} movies")
                break
        except Exception as e:
            radarr_logger.error(f"Error checking hourly API cap: {e}")
            # Continue processing if cap check fails - safer than stopping
            
        movie_id = movie.get("id")
        movie_title = movie.get("title", "Unknown Title")
        
        # Refresh functionality has been removed as it was identified as a performance bottleneck
        
        # Search for the movie
        radarr_logger.info(f"Searching for movie '{movie_title}' (ID: {movie_id})...")
        search_success = radarr_api.movie_search(api_url, api_key, api_timeout, [movie_id])
        
        if search_success:
            radarr_logger.info(f"Successfully triggered search for movie '{movie_title}'")
            
            # Tag the movie if enabled
            if tag_processed_items:
                from src.primary.settings_manager import get_custom_tag
                custom_tag = get_custom_tag("radarr", "missing", "huntarr-missing")
                try:
                    radarr_api.tag_processed_movie(api_url, api_key, api_timeout, movie_id, custom_tag)
                    radarr_logger.debug(f"Tagged movie {movie_id} with '{custom_tag}'")
                except Exception as e:
                    radarr_logger.warning(f"Failed to tag movie {movie_id} with '{custom_tag}': {e}")
            
            # Immediately add to processed IDs to prevent duplicate processing
            success = add_processed_id("radarr", instance_name, str(movie_id))
            radarr_logger.debug(f"Added processed ID: {movie_id}, success: {success}")
            
            # Log to history system
            year = movie.get("year", "Unknown Year")
            media_name = f"{movie_title} ({year})"
            log_processed_media("radarr", media_name, movie_id, instance_name, "missing")
            radarr_logger.debug(f"Logged history entry for movie: {media_name}")
            
            increment_stat_only("radarr", "hunted")
            movies_processed += 1
            processed_any = True
        else:
            radarr_logger.warning(f"Failed to trigger search for movie '{movie_title}'")
    
    radarr_logger.info(f"Finished processing missing movies. Processed {movies_processed} of {len(movies_to_process)} selected movies.")
    return processed_any
