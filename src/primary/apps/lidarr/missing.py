#!/usr/bin/env python3
"""
Lidarr missing content processing module for Huntarr
Handles missing albums or artists based on configuration.
"""

import time
import random
import datetime
from typing import Dict, Any, Callable
from src.primary.utils.logger import get_logger
from src.primary.apps.lidarr import api as lidarr_api
from src.primary.stats_manager import increment_stat

# Get the logger for the Lidarr module
lidarr_logger = get_logger(__name__) # Use __name__ for correct logger hierarchy


def process_missing_albums(
    app_settings: Dict[str, Any],      # Combined settings dictionary
    stop_check: Callable[[], bool]      # Function to check for stop signal
) -> bool:
    """
    Processes missing albums for a specific Lidarr instance based on settings.

    Args:
        app_settings (dict): Dictionary containing combined instance and general settings.
        stop_check (Callable[[], bool]): Function to check if shutdown is requested.

    Returns:
        bool: True if any items were processed, False otherwise.
    """
    
    # Extract instance-specific details from app_settings
    instance_name = app_settings.get("instance_name", "Lidarr Default")
    api_url = app_settings.get("api_url")
    api_key = app_settings.get("api_key")

    # Extract general settings from app_settings
    hunt_missing_items = app_settings.get("hunt_missing_items", 0)
    hunt_missing_mode = app_settings.get("hunt_missing_mode", "artist") # 'artist' or 'album'
    monitored_only = app_settings.get("monitored_only", True)
    skip_future_releases = app_settings.get("skip_future_releases", True)
    random_missing = app_settings.get("random_missing", True)
    api_timeout = app_settings.get("api_timeout", 120) # Use general timeout
    command_wait_delay = app_settings.get("command_wait_delay", 1)
    command_wait_attempts = app_settings.get("command_wait_attempts", 600)

    lidarr_logger.debug(f"Processing missing for instance: {instance_name}")
    lidarr_logger.debug(f"App Settings: {app_settings}")

    # Check if API URL or Key are missing
    if not api_url or not api_key:
        lidarr_logger.error(f"Missing API URL or Key for instance '{instance_name}'. Cannot process missing albums.")
        return False # Cannot proceed without API details

    # Check if missing items hunting is enabled
    if hunt_missing_items <= 0:
        lidarr_logger.info(f"'hunt_missing_items' is {hunt_missing_items} or less. Skipping missing processing for {instance_name}.")
        return False # Skip if setting is 0 or less

    processed_count = 0
    total_items_to_process = hunt_missing_items
    processed_artists_or_albums = set()

    try:
        # Fetch all missing albums first
        lidarr_logger.info(f"Fetching all missing albums for {instance_name}...")
        missing_items = lidarr_api.get_missing_albums(
            api_url,
            api_key,
            monitored_only=monitored_only,
            api_timeout=api_timeout
        )

        if missing_items is None: # API call failed or returned None
            lidarr_logger.error(f"Failed to get missing items from Lidarr API for {instance_name}.")
            return False

        if not missing_items:
            lidarr_logger.info(f"No missing albums found for {instance_name} after initial fetch and filtering.")
            return False

        lidarr_logger.info(f"Found {len(missing_items)} potentially missing albums for {instance_name} after initial fetch.")

        # --- Filter Future Releases --- #
        original_count = len(missing_items)
        if skip_future_releases:
            now = datetime.datetime.now(datetime.timezone.utc)
            valid_missing_items = []
            skipped_count = 0
            for item in missing_items:
                release_date_str = item.get('releaseDate')
                if release_date_str:
                    try:
                        # Lidarr dates often include 'Z' for UTC
                        release_date = datetime.datetime.fromisoformat(release_date_str.replace('Z', '+00:00'))
                        if release_date <= now:
                            valid_missing_items.append(item)
                        else:
                            # lidarr_logger.debug(f"Skipping future album ID {item.get('id')} ('{item.get('title')}') release: {release_date_str}")
                            skipped_count += 1
                    except ValueError as e:
                        lidarr_logger.warning(f"Could not parse release date '{release_date_str}' for album ID {item.get('id')}. Error: {e}. Including it.")
                        valid_missing_items.append(item) # Keep if date is invalid
                else:
                    valid_missing_items.append(item) # Keep if no release date
            
            missing_items = valid_missing_items # Replace with filtered list
            if skipped_count > 0:
                lidarr_logger.info(f"Skipped {skipped_count} future albums based on release date. {len(missing_items)} remaining.")
        else:
             lidarr_logger.debug("Skipping future release filtering as 'skip_future_releases' is False.")
        
        # Check if any items remain after filtering
        if not missing_items:
            lidarr_logger.info(f"No missing albums left after filtering future releases for {instance_name}.")
            return False

        # Process based on mode
        lidarr_logger.info(f"Processing missing items in '{hunt_missing_mode}' mode.")

        target_entities = []
        search_entity_type = "album" # Default to album

        if hunt_missing_mode == "artist":
            search_entity_type = "artist"
            # Group by artist ID
            items_by_artist = {}
            for item in missing_items: # Use the potentially filtered missing_items list
                artist_id = item.get('artistId')
                if artist_id:
                    if artist_id not in items_by_artist:
                        items_by_artist[artist_id] = []
                    items_by_artist[artist_id].append(item)
            target_entities = list(items_by_artist.keys()) # List of artist IDs
            lidarr_logger.debug(f"Grouped missing albums into {len(target_entities)} artists.")
        else: # Album mode
            target_entities = [item['id'] for item in missing_items] # Use the potentially filtered missing_items list

        # Select entities to search
        if not target_entities:
            lidarr_logger.info(f"No {search_entity_type}s found to process after grouping/filtering.")
            return False

        if random_missing:
            entities_to_search_ids = random.sample(target_entities, min(len(target_entities), total_items_to_process))
            lidarr_logger.debug(f"Randomly selected {len(entities_to_search_ids)} {search_entity_type}s to search.")
        else:
            # Sort by ID for consistent selection if not random (optional, API order might suffice)
            # target_entities.sort() # Example: sort IDs numerically
            entities_to_search_ids = target_entities[:total_items_to_process]
            lidarr_logger.debug(f"Selected first {len(entities_to_search_ids)} {search_entity_type}s to search.")

        if not entities_to_search_ids:
            lidarr_logger.info(f"No {search_entity_type}s selected for search after applying limit/randomization.")
            return False

        # --- Trigger Search (Artist or Album) ---
        if hunt_missing_mode == "artist":
            lidarr_logger.info(f"Triggering Artist Search for {len(entities_to_search_ids)} artists on {instance_name}...")
            for artist_id in entities_to_search_ids:
                if stop_check(): # Use the new stop_check function
                    lidarr_logger.warning("Shutdown requested during artist search trigger.")
                    break

                artist_name = f"Artist ID {artist_id}" # Placeholder, could fetch name if needed
                lidarr_logger.info(f"Triggering Artist Search for '{artist_name}' (ID: {artist_id}) on instance {instance_name}")
                try:
                    # Use the correct API function name
                    command_id = lidarr_api.search_artist(api_url, api_key, artist_id, api_timeout)
                    if command_id:
                        lidarr_logger.info(f"Artist search triggered for ID {artist_id} on {instance_name}. Command ID: {command_id}")
                        increment_stat("lidarr", "missing") # Increment per artist search triggered
                        processed_count += 1 # Count artists searched
                        processed_artists_or_albums.add(artist_id)
                        time.sleep(0.1) # Small delay between triggers
                except Exception as e:
                    lidarr_logger.warning(f"Failed to trigger artist search for ID {artist_id} on {instance_name}: {e}")

        else: # Album mode
            album_ids_to_search = list(entities_to_search_ids)
            if stop_check(): # Use the new stop_check function
                lidarr_logger.warning("Shutdown requested before album search trigger.")
                return False

            lidarr_logger.info(f"Triggering Album Search for {len(album_ids_to_search)} albums (album mode) on instance {instance_name}: {album_ids_to_search}")
            command_id = lidarr_api.trigger_album_search(api_url, api_key, album_ids_to_search, api_timeout)
            if command_id:
                lidarr_logger.debug(f"Album search command triggered with ID: {command_id} for albums: {album_ids_to_search}")
                increment_stat("lidarr", "missing") # Increment once for the batch
                processed_count += len(album_ids_to_search) # Count albums searched
                processed_artists_or_albums.update(album_ids_to_search)
                time.sleep(command_wait_delay) # Basic delay after the single command
            else:
                lidarr_logger.warning(f"Failed to trigger album search for IDs {album_ids_to_search} on {instance_name}.")

    except Exception as e:
        lidarr_logger.error(f"An error occurred during missing album processing for {instance_name}: {e}", exc_info=True)
        return False

    lidarr_logger.info(f"Missing album processing finished for {instance_name}. Processed {processed_count} items/searches ({len(processed_artists_or_albums)} unique {search_entity_type}s).")
    return processed_count > 0