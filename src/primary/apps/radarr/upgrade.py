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
    api_url = app_settings.get("api_url")
    api_key = app_settings.get("api_key")
    api_timeout = app_settings.get("api_timeout", 90)  # Default timeout
    monitored_only = app_settings.get("monitored_only", True)
    skip_movie_refresh = app_settings.get("skip_movie_refresh", False)
    random_upgrades = app_settings.get("random_upgrades", False)
    hunt_upgrade_movies = app_settings.get("hunt_upgrade_movies", 0)
    command_wait_delay = app_settings.get("command_wait_delay", 5)
    command_wait_attempts = app_settings.get("command_wait_attempts", 12)
    
    # Get movies eligible for upgrade
    radarr_logger.info("Retrieving movies eligible for cutoff upgrade...")
    upgrade_eligible_data = radarr_api.get_cutoff_unmet_movies(api_url, api_key, api_timeout, monitored_only)
    
    if not upgrade_eligible_data:
        radarr_logger.info("No movies found eligible for upgrade or error retrieving them.")
        return False
        
    radarr_logger.info(f"Found {len(upgrade_eligible_data)} movies eligible for upgrade.")

    # Select movies to process
    unprocessed_movies = upgrade_eligible_data
    
    if not unprocessed_movies:
        radarr_logger.info("No upgradeable movies found to process (after potential filtering). Skipping.")
        return False
        
    if random_upgrades:
        radarr_logger.info(f"Randomly selecting up to {hunt_upgrade_movies} movies for upgrade search.")
        movies_to_process = random.sample(unprocessed_movies, min(hunt_upgrade_movies, len(unprocessed_movies)))
    else:
        radarr_logger.info(f"Selecting the first {hunt_upgrade_movies} movies for upgrade search (order based on API return).")
        movies_to_process = unprocessed_movies[:hunt_upgrade_movies]
        
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
        
        # Refresh movie (optional)
        if not skip_movie_refresh:
            radarr_logger.info(f"  - Refreshing movie info...")
            refresh_result = radarr_api.refresh_movie(api_url, api_key, movie_id, api_timeout)
            time.sleep(5) # Basic wait
            if not refresh_result:
                 radarr_logger.warning(f"  - Failed to trigger movie refresh. Continuing search anyway.")
        else:
             radarr_logger.info(f"  - Skipping movie refresh (skip_movie_refresh=true)")
             
        # Perform the movie search
        radarr_logger.info("  - Searching for upgrade for movie...")
        # Corrected function name
        search_command_id = radarr_api.movie_search(api_url, api_key, api_timeout, [movie_id])
        
        if search_command_id:
            radarr_logger.info(f"  - Search command triggered (ID: {search_command_id}). Waiting for completion...")
            increment_stat("radarr", "upgraded") # Assuming 'upgraded' stat exists
            processed_count += 1
            processed_something = True
            radarr_logger.info(f"Processed {processed_count}/{len(movies_to_process)} movie upgrades this cycle.")
        else:
            radarr_logger.error(f"Failed to trigger search for movie {movie_title} ({movie_year}) upgrade.")

        if processed_count >= hunt_upgrade_movies:
            radarr_logger.info(f"Reached target of {hunt_upgrade_movies} movies processed for upgrade this cycle.")
            break
            
    radarr_logger.info(f"Completed processing {processed_count} movies for upgrade this cycle.")
    
    return processed_something