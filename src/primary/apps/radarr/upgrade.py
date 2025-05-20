#!/usr/bin/env python3
"""
Quality Upgrade Processing for Radarr
Handles searching for movies that need quality upgrades in Radarr
"""

import time
import random
from typing import List, Dict, Any, Set, Callable
from src.primary.utils.logger import get_logger
from src.primary.apps.radarr import api as radarr_api
from src.primary.stats_manager import increment_stat
from src.primary.stateful_manager import is_processed, add_processed_id
from src.primary.utils.history_utils import log_processed_media
from src.primary.settings_manager import get_advanced_setting, get_dry_run_mode

# Get logger for the app
radarr_logger = get_logger("radarr")

def process_cutoff_upgrades(
    app_settings: Dict[str, Any],
    stop_check: Callable[[], bool] # Function to check if stop is requested
) -> bool:
    """
    Process quality cutoff upgrades for Radarr based on settings.
    
    Args:
        app_settings: Dictionary containing all settings for Radarr
        stop_check: A function that returns True if the process should stop
        
    Returns:
        True if any movies were processed for upgrades, False otherwise.
    """
    radarr_logger.info("Starting quality cutoff upgrades processing cycle for Radarr.")
    processed_any = False
    
    # Extract necessary settings
    api_url = app_settings.get("api_url", "").strip()
    api_key = app_settings.get("api_key", "").strip()
    api_timeout = get_advanced_setting("api_timeout", 120)  # Use general.json value
    monitored_only = app_settings.get("monitored_only", True)
    # skip_movie_refresh setting removed as it was a performance bottleneck
    hunt_upgrade_movies = app_settings.get("hunt_upgrade_movies", 0)
    
    # Use advanced settings from general.json for command operations
    command_wait_delay = get_advanced_setting("command_wait_delay", 1)
    command_wait_attempts = get_advanced_setting("command_wait_attempts", 600)
    
    # Get instance name - check for instance_name first, fall back to legacy "name" key if needed
    instance_name = app_settings.get("instance_name", app_settings.get("name", "Radarr Default"))
    
    # Get movies eligible for upgrade
    radarr_logger.info("Retrieving movies eligible for cutoff upgrade...")
    upgrade_eligible_data = radarr_api.get_cutoff_unmet_movies(api_url, api_key, api_timeout, monitored_only)
    
    if not upgrade_eligible_data:
        radarr_logger.info("No movies found eligible for upgrade or error retrieving them.")
        return False
        
    radarr_logger.info(f"Found {len(upgrade_eligible_data)} movies eligible for upgrade.")

    # Filter out already processed movies using stateful management
    unprocessed_movies = []
    for movie in upgrade_eligible_data:
        movie_id = str(movie.get("id"))
        if not is_processed("radarr", instance_name, movie_id):
            unprocessed_movies.append(movie)
        else:
            radarr_logger.debug(f"Skipping already processed movie ID: {movie_id}")
    
    radarr_logger.info(f"Found {len(unprocessed_movies)} unprocessed movies for upgrade out of {len(upgrade_eligible_data)} total.")
    
    if not unprocessed_movies:
        radarr_logger.info("No upgradeable movies found to process (after filtering already processed). Skipping.")
        return False
        
    radarr_logger.info(f"Randomly selecting up to {hunt_upgrade_movies} movies for upgrade search.")
    movies_to_process = random.sample(unprocessed_movies, min(hunt_upgrade_movies, len(unprocessed_movies)))
        
    radarr_logger.info(f"Selected {len(movies_to_process)} movies to search for upgrades.")
    processed_count = 0
    processed_something = False
    
    for movie in movies_to_process:
        if stop_check():
            radarr_logger.info("Stop signal received, aborting Radarr upgrade cycle.")
            break
            
        movie_id = movie.get("id")
        movie_title = movie.get("title")
        movie_year = movie.get("year")
        
        radarr_logger.info(f"Processing upgrade for movie: \"{movie_title}\" ({movie_year}) (Movie ID: {movie_id})")
        
        # Refresh functionality has been removed as it was identified as a performance bottleneck
        
        # Search for cutoff upgrade
        radarr_logger.info(f"  - Searching for quality upgrade...")
        search_result = radarr_api.movie_search(api_url, api_key, api_timeout, [movie_id])
        
        if search_result:
            radarr_logger.info(f"  - Successfully triggered search for quality upgrade.")
            add_processed_id("radarr", instance_name, str(movie_id))
            increment_stat("radarr", "upgraded")
            
            # Log to history so the upgrade appears in the history UI
            media_name = f"{movie_title} ({movie_year})"
            log_processed_media("radarr", media_name, movie_id, instance_name, "upgrade")
            radarr_logger.debug(f"Logged quality upgrade to history for movie ID {movie_id}")
            
            processed_count += 1
            processed_something = True
        else:
            radarr_logger.warning(f"  - Failed to trigger search for quality upgrade.")
            
    # Log final status
    radarr_logger.info(f"Completed processing {processed_count} movies for quality upgrades.")
    
    return processed_something