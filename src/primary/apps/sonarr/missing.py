#!/usr/bin/env python3
"""
Sonarr missing episode processing
Handles all missing episode operations for Sonarr
"""

import os
import time
import random
import datetime
from typing import List, Dict, Any, Optional, Callable
from src.primary.utils.logger import get_logger
from src.primary.settings_manager import load_settings, get_advanced_setting
from src.primary.utils.history_utils import log_processed_media
from src.primary.stats_manager import increment_stat, increment_stat_only, check_hourly_cap_exceeded
from src.primary.stateful_manager import is_processed, add_processed_id
from src.primary.apps.sonarr import api as sonarr_api

# Get logger for the Sonarr app
sonarr_logger = get_logger("sonarr")

def process_missing_episodes(
    api_url: str,
    api_key: str,
    instance_name: str,
    api_timeout: int = get_advanced_setting("api_timeout", 120),
    monitored_only: bool = True,
    skip_future_episodes: bool = True,

    hunt_missing_items: int = 5,
    hunt_missing_mode: str = "seasons_packs",
    command_wait_delay: int = get_advanced_setting("command_wait_delay", 1),
    command_wait_attempts: int = get_advanced_setting("command_wait_attempts", 600),
    stop_check: Callable[[], bool] = lambda: False
) -> bool:
    """
    Process missing episodes for Sonarr.
    Supports seasons_packs, shows, and episodes modes.
    Episodes mode has been reinstated in 7.5.1+ as a non-default option with limitations.
    """
    if hunt_missing_items <= 0:
        sonarr_logger.info("'hunt_missing_items' setting is 0 or less. Skipping missing processing.")
        return False
        
    sonarr_logger.debug(f"Checking for {hunt_missing_items} missing episodes in {hunt_missing_mode} mode for instance '{instance_name}'...")

    # Handle different modes
    if hunt_missing_mode == "seasons_packs":
        # Handle season pack searches (using SeasonSearch command)
        sonarr_logger.debug("Season [Packs] mode selected - searching for complete season packs")
        return process_missing_seasons_packs_mode(
            api_url, api_key, instance_name, api_timeout, monitored_only, 
            skip_future_episodes, hunt_missing_items,
            command_wait_delay, command_wait_attempts, stop_check
        )
    elif hunt_missing_mode == "shows":
        # Handle show-based missing items (all episodes from a show)
        sonarr_logger.debug("Show-based missing mode selected")
        return process_missing_shows_mode(
            api_url, api_key, instance_name, api_timeout, monitored_only, 
            skip_future_episodes, hunt_missing_items,
            command_wait_delay, command_wait_attempts, stop_check
        )
    elif hunt_missing_mode == "episodes":
        # Handle individual episode processing (reinstated with warnings)
        sonarr_logger.warning("Episodes mode selected - WARNING: This mode makes excessive API calls and does not support tagging. Consider using Season Packs mode instead.")
        return process_missing_episodes_mode(
            api_url, api_key, instance_name, api_timeout, monitored_only, 
            skip_future_episodes, hunt_missing_items,
            command_wait_delay, command_wait_attempts, stop_check
        )
    else:
        sonarr_logger.error(f"Invalid hunt_missing_mode: {hunt_missing_mode}. Valid options are 'seasons_packs', 'shows', or 'episodes'.")
        return False

def process_missing_seasons_packs_mode(
    api_url: str,
    api_key: str,
    instance_name: str,
    api_timeout: int,
    monitored_only: bool,
    skip_future_episodes: bool,
    hunt_missing_items: int,
    command_wait_delay: int,
    command_wait_attempts: int,
    stop_check: Callable[[], bool]
) -> bool:
    """
    Process missing seasons using the SeasonSearch command
    This mode is optimized for torrent users who rely on season packs
    Uses a direct episode lookup approach which is much more efficient
    """
    processed_any = False
    
    # Load settings to check if tagging is enabled
    sonarr_settings = load_settings("sonarr")
    tag_processed_items = sonarr_settings.get("tag_processed_items", True)
    
    # Get all missing episodes using efficient random page selection instead of fetching all
    missing_episodes = sonarr_api.get_missing_episodes_random_page(
        api_url, api_key, api_timeout, monitored_only, hunt_missing_items * 20  # Get more episodes to increase chance of finding full seasons
    )
    if not missing_episodes:
        sonarr_logger.info("No missing episodes found")
        return False
    
    sonarr_logger.debug(f"Retrieved {len(missing_episodes)} missing episodes from random page selection.")

    # Filter out future episodes if configured
    if skip_future_episodes:
        now_unix = time.time()
        original_count = len(missing_episodes)
        filtered_episodes = []
        skipped_count = 0
        
        for episode in missing_episodes:
            air_date_str = episode.get('airDateUtc')
            if air_date_str:
                try:
                    # Parse the air date and check if it's in the past
                    air_date_unix = time.mktime(time.strptime(air_date_str, '%Y-%m-%dT%H:%M:%SZ'))
                    if air_date_unix < now_unix:
                        filtered_episodes.append(episode)
                    else:
                        skipped_count += 1
                        sonarr_logger.debug(f"Skipping future episode ID {episode.get('id')} with air date: {air_date_str}")
                except (ValueError, TypeError) as e:
                    sonarr_logger.warning(f"Could not parse air date '{air_date_str}' for episode ID {episode.get('id')}. Error: {e}. Including it.")
                    filtered_episodes.append(episode)  # Keep if date is invalid
            else:
                filtered_episodes.append(episode)  # Keep if no air date
        
        missing_episodes = filtered_episodes
        if skipped_count > 0:
            sonarr_logger.info(f"Skipped {skipped_count} future episodes based on air date.")
    
    if not missing_episodes:
        sonarr_logger.info("No missing episodes left to process after filtering future episodes.")
        return False
    
    # Group episodes by series and season
    missing_seasons = {}
    for episode in missing_episodes:
        if monitored_only and not episode.get('monitored', False):
            continue
            
        series_id = episode.get('seriesId')
        if not series_id:
            continue
            
        season_number = episode.get('seasonNumber')
        series_title = episode.get('series', {}).get('title', 'Unknown Series')
        
        key = f"{series_id}:{season_number}"
        if key not in missing_seasons:
            missing_seasons[key] = {
                'series_id': series_id,
                'season_number': season_number,
                'series_title': series_title,
                'episode_count': 0
            }
        missing_seasons[key]['episode_count'] += 1
    
    # Convert to list and sort by episode count (most missing episodes first)
    seasons_list = list(missing_seasons.values())
    seasons_list.sort(key=lambda x: x['episode_count'], reverse=True)
    
    # Filter out already processed seasons
    unprocessed_seasons = []
    for season in seasons_list:
        season_id = f"{season['series_id']}_{season['season_number']}"
        if not is_processed("sonarr", instance_name, season_id):
            unprocessed_seasons.append(season)
        else:
            sonarr_logger.debug(f"Skipping already processed season ID: {season_id}")
    
    sonarr_logger.debug(f"Found {len(unprocessed_seasons)} unprocessed seasons with missing episodes out of {len(seasons_list)} total.")
    
    if not unprocessed_seasons:
        sonarr_logger.info("All seasons with missing episodes have been processed.")
        return False
    
    # Apply randomization if requested
    random.shuffle(unprocessed_seasons)
    
    # Process up to hunt_missing_items seasons
    processed_count = 0
    
    # Add user-friendly logging for selected seasons
    if unprocessed_seasons and hunt_missing_items > 0:
        seasons_to_process = unprocessed_seasons[:hunt_missing_items]
        sonarr_logger.info(f"Seasons selected for processing in this cycle ({min(len(unprocessed_seasons), hunt_missing_items)} of {len(unprocessed_seasons)} available):")
        
        for idx, season in enumerate(seasons_to_process):
            sonarr_logger.info(f"  {idx+1}. {season['series_title']} - Season {season['season_number']} ({season['episode_count']} missing episodes) (Series ID: {season['series_id']})")
    
    for season in unprocessed_seasons:
        if processed_count >= hunt_missing_items:
            break
            
        if stop_check():
            sonarr_logger.info("Stop signal received, halting processing.")
            break
        
        # Check API limit before processing each season
        try:
            if check_hourly_cap_exceeded("sonarr"):
                sonarr_logger.warning(f"🛑 Sonarr API hourly limit reached - stopping season pack processing after {processed_count} seasons")
                break
        except Exception as e:
            sonarr_logger.error(f"Error checking hourly API cap: {e}")
            # Continue processing if cap check fails - safer than stopping
            
        series_id = season['series_id']
        season_number = season['season_number']
        series_title = season['series_title']
        episode_count = season['episode_count']
        
        # Refresh functionality has been removed as it was identified as a performance bottleneck
        
        sonarr_logger.debug(f"Searching for season pack: {series_title} - Season {season_number} (contains {episode_count} missing episodes)")
        
        # Trigger an API call to search for the entire season
        command_id = sonarr_api.search_season(api_url, api_key, api_timeout, series_id, season_number)
        
        if command_id:
            processed_any = True
            processed_count += 1
            
            # Add season to processed list
            season_id = f"{series_id}_{season_number}"
            success = add_processed_id("sonarr", instance_name, season_id)
            sonarr_logger.debug(f"Added season ID {season_id} to processed list for {instance_name}, success: {success}")
            
                    # Tag the series if enabled
        if tag_processed_items:
            from src.primary.settings_manager import get_custom_tag
            custom_tag = get_custom_tag("sonarr", "missing", "huntarr-missing")
            try:
                sonarr_api.tag_processed_series(api_url, api_key, api_timeout, series_id, custom_tag)
                sonarr_logger.debug(f"Tagged series {series_id} with '{custom_tag}'")
            except Exception as e:
                sonarr_logger.warning(f"Failed to tag series {series_id} with '{custom_tag}': {e}")
            
            # Log to history system
            media_name = f"{series_title} - Season {season_number} (contains {episode_count} missing episodes)"
            log_processed_media("sonarr", media_name, season_id, instance_name, "missing")
            sonarr_logger.debug(f"Logged history entry for season pack: {media_name}")
            
            # CRITICAL FIX: Use increment_stat_only to avoid double-counting API calls
            # The API call is already tracked in search_season(), so we only increment stats here
            for i in range(episode_count):
                increment_stat_only("sonarr", "hunted")
            sonarr_logger.debug(f"Incremented sonarr hunted statistics for {episode_count} episodes in season pack (API call already tracked separately)")
            
            # Wait for command to complete if configured
            if command_wait_delay > 0 and command_wait_attempts > 0:
                if wait_for_command(
                    api_url, api_key, api_timeout, command_id, 
                    command_wait_delay, command_wait_attempts, "Season Search", stop_check
                ):
                    pass
        else:
            sonarr_logger.error(f"Failed to trigger search for {series_title}.")
    
    sonarr_logger.info(f"Finished processing missing episodes. Processed {processed_count} season packs.")
    return processed_any

def process_missing_shows_mode(
    api_url: str,
    api_key: str,
    instance_name: str,
    api_timeout: int,
    monitored_only: bool,
    skip_future_episodes: bool,
    hunt_missing_items: int,
    command_wait_delay: int,
    command_wait_attempts: int,
    stop_check: Callable[[], bool]
) -> bool:
    """Process missing episodes in show mode - gets all missing episodes for entire shows."""
    processed_any = False
    
    # Load settings to check if tagging is enabled
    sonarr_settings = load_settings("sonarr")
    tag_processed_items = sonarr_settings.get("tag_processed_items", True)
    
    # Get series with missing episodes
    sonarr_logger.debug("Retrieving series with missing episodes...")
    series_with_missing = sonarr_api.get_series_with_missing_episodes(
        api_url, api_key, api_timeout, monitored_only, random_mode=True)
    
    if not series_with_missing:
        sonarr_logger.info("No series with missing episodes found.")
        return False
    
    # Filter out shows that have been processed
    unprocessed_series = []
    for series in series_with_missing:
        series_id = str(series.get("series_id"))
        if not is_processed("sonarr", instance_name, series_id):
            unprocessed_series.append(series)
        else:
            sonarr_logger.debug(f"Skipping already processed series ID: {series_id}")
    
    sonarr_logger.debug(f"Found {len(unprocessed_series)} unprocessed series with missing episodes out of {len(series_with_missing)} total.")
    
    if not unprocessed_series:
        sonarr_logger.info("All series with missing episodes have been processed.")
        return False
        
    # Select the shows to process (random or sequential)
    shows_to_process = random.sample(
        unprocessed_series, 
        min(len(unprocessed_series), hunt_missing_items)
    )
    
    # Add user-friendly logging for selected shows
    if shows_to_process:
        sonarr_logger.info(f"Shows selected for processing in this cycle ({len(shows_to_process)} of {len(unprocessed_series)} available):")
        for idx, show in enumerate(shows_to_process):
            show_id = show.get('series_id')
            show_title = show.get('series_title', 'Unknown Show')
            # Count total missing episodes across all seasons
            episode_count = sum(season.get('episode_count', 0) for season in show.get('seasons', []))
            sonarr_logger.info(f"  {idx+1}. {show_title} ({episode_count} missing episodes) (Show ID: {show_id})")
    
    # Process each show
    for show in shows_to_process:
        if stop_check():
            sonarr_logger.info("Stop signal received, halting processing.")
            break
        
        # Check API limit before processing each show
        try:
            if check_hourly_cap_exceeded("sonarr"):
                sonarr_logger.warning(f"🛑 Sonarr API hourly limit reached - stopping shows processing")
                break
        except Exception as e:
            sonarr_logger.error(f"Error checking hourly API cap: {e}")
            # Continue processing if cap check fails - safer than stopping
            
        show_id = show.get("series_id")
        show_title = show.get("series_title", "Unknown Show")
        
        # Get missing episodes for this show
        missing_episodes = []
        for season in show.get('seasons', []):
            missing_episodes.extend(season.get('episodes', []))
        
        # Filter out future episodes if needed
        if skip_future_episodes:
            now_unix = time.time()
            original_count = len(missing_episodes)
            missing_episodes = [
                ep for ep in missing_episodes
                if ep.get('airDateUtc') and time.mktime(time.strptime(ep['airDateUtc'], '%Y-%m-%dT%H:%M:%SZ')) < now_unix
            ]
            skipped_count = original_count - len(missing_episodes)
            if skipped_count > 0:
                sonarr_logger.info(f"Skipped {skipped_count} future episodes for {show_title} based on air date.")
        
        if not missing_episodes:
            sonarr_logger.info(f"No eligible missing episodes found for {show_title} after filtering.")
            continue
        
        # Log episodes to be processed
        sonarr_logger.info(f"Processing {len(missing_episodes)} missing episodes for show: {show_title}")
        for idx, episode in enumerate(missing_episodes[:5]):  # Only log first 5 for brevity
            season = episode.get('seasonNumber', 'Unknown')
            ep_num = episode.get('episodeNumber', 'Unknown')
            title = episode.get('title', 'Unknown Title')
            sonarr_logger.debug(f"  {idx+1}. S{season:02d}E{ep_num:02d} - {title}")
        
        if len(missing_episodes) > 5:
            sonarr_logger.debug(f"  ... and {len(missing_episodes)-5} more episodes.")
        
        # Series refresh functionality has been completely removed
        # No longer performing refresh before search to avoid API rate limiting and unnecessary delays
        
        # Extract episode IDs to search
        episode_ids = [episode.get('id') for episode in missing_episodes if episode.get('id')]
        
        if not episode_ids:
            sonarr_logger.warning(f"No valid episode IDs found for {show_title}.")
            continue
        
        # Search for all episodes in the show
        sonarr_logger.info(f"Searching for {len(episode_ids)} missing episodes for {show_title}...")
        search_successful = sonarr_api.search_episode(api_url, api_key, api_timeout, episode_ids)
        
        if search_successful:
            processed_any = True
            sonarr_logger.info(f"Successfully processed {len(episode_ids)} missing episodes in {show_title}")
            
                    # Tag the series if enabled
        if tag_processed_items:
            from src.primary.settings_manager import get_custom_tag
            custom_tag = get_custom_tag("sonarr", "shows_missing", "huntarr-shows-missing")
            try:
                sonarr_api.tag_processed_series(api_url, api_key, api_timeout, show_id, custom_tag)
                sonarr_logger.debug(f"Tagged series {show_id} with '{custom_tag}'")
            except Exception as e:
                sonarr_logger.warning(f"Failed to tag series {show_id} with '{custom_tag}': {e}")
            
            # Add episode IDs to stateful manager IMMEDIATELY after processing each batch
            for episode_id in episode_ids:
                # Force flush to disk by calling add_processed_id immediately for each ID
                success = add_processed_id("sonarr", instance_name, str(episode_id))
                sonarr_logger.debug(f"Added processed ID: {episode_id}, success: {success}")
                
                # Log each episode to history
                # Find the corresponding episode data 
                for episode in missing_episodes:
                    if episode.get('id') == episode_id:
                        season = episode.get('seasonNumber', 'Unknown')
                        ep_num = episode.get('episodeNumber', 'Unknown')
                        title = episode.get('title', 'Unknown Title')
                        
                        try:
                            season_episode = f"S{season:02d}E{ep_num:02d}"
                        except (ValueError, TypeError):
                            season_episode = f"S{season}E{ep_num}"
                            
                        media_name = f"{show_title} - {season_episode} - {title}"
                        log_processed_media("sonarr", media_name, str(episode_id), instance_name, "missing")
                        sonarr_logger.debug(f"Logged history entry for episode: {media_name}")
                        break
            
            # Add series ID to processed list
            success = add_processed_id("sonarr", instance_name, str(show_id))
            sonarr_logger.debug(f"Added series ID {show_id} to processed list for {instance_name}, success: {success}")
            
            # Also log the entire show to history
            media_name = f"{show_title} - Complete Series ({len(episode_ids)} episodes)"
            log_processed_media("sonarr", media_name, str(show_id), instance_name, "missing")
            sonarr_logger.debug(f"Logged history entry for complete series: {media_name}")
            
            # Increment the hunted statistics
            increment_stat("sonarr", "hunted", len(episode_ids))
            sonarr_logger.debug(f"Incremented sonarr hunted statistics by {len(episode_ids)}")
        else:
            sonarr_logger.error(f"Failed to trigger search for {show_title}.")
    
    sonarr_logger.info("Show-based missing episode processing complete.")
    return processed_any

def process_missing_episodes_mode(
    api_url: str,
    api_key: str,
    instance_name: str,
    api_timeout: int,
    monitored_only: bool,
    skip_future_episodes: bool,
    hunt_missing_items: int,
    command_wait_delay: int,
    command_wait_attempts: int,
    stop_check: Callable[[], bool]
) -> bool:
    """
    Process missing episodes in individual episode mode.
    
    WARNING: This mode is less efficient than season packs mode and makes more API calls.
    It does not support tagging functionality due to the way it processes individual episodes.
    
    This mode searches for individual missing episodes rather than complete seasons,
    which can be useful for targeting specific episodes but is not recommended for most users.
    """
    processed_any = False
    
    sonarr_logger.warning("Using Episodes mode - This will make more API calls and does not support tagging")
    
    # Get missing episodes using random page selection for efficiency
    missing_episodes = sonarr_api.get_missing_episodes_random_page(
        api_url, api_key, api_timeout, monitored_only, hunt_missing_items * 2
    )
    
    if not missing_episodes:
        sonarr_logger.info("No missing episodes found for individual processing.")
        return False
    
    # Filter out future episodes if configured
    if skip_future_episodes:
        now_unix = time.time()
        original_count = len(missing_episodes)
        filtered_episodes = []
        skipped_count = 0
        
        for episode in missing_episodes:
            air_date_str = episode.get('airDateUtc')
            if air_date_str:
                try:
                    # Parse the air date and check if it's in the past
                    air_date_unix = time.mktime(time.strptime(air_date_str, '%Y-%m-%dT%H:%M:%SZ'))
                    if air_date_unix < now_unix:
                        filtered_episodes.append(episode)
                    else:
                        skipped_count += 1
                        sonarr_logger.debug(f"Skipping future episode ID {episode.get('id')} with air date: {air_date_str}")
                except (ValueError, TypeError) as e:
                    sonarr_logger.warning(f"Could not parse air date '{air_date_str}' for episode ID {episode.get('id')}. Error: {e}. Including it.")
                    filtered_episodes.append(episode)  # Keep if date is invalid
            else:
                filtered_episodes.append(episode)  # Keep if no air date
        
        missing_episodes = filtered_episodes
        if skipped_count > 0:
            sonarr_logger.info(f"Skipped {skipped_count} future episodes based on air date.")
    
    if not missing_episodes:
        sonarr_logger.info("No missing episodes left to process after filtering future episodes.")
        return False
    
    # Filter out already processed episodes
    unprocessed_episodes = []
    for episode in missing_episodes:
        episode_id = str(episode.get('id'))
        if not is_processed("sonarr", instance_name, episode_id):
            unprocessed_episodes.append(episode)
        else:
            sonarr_logger.debug(f"Skipping already processed episode ID: {episode_id}")
    
    sonarr_logger.debug(f"Found {len(unprocessed_episodes)} unprocessed episodes out of {len(missing_episodes)} total.")
    
    if not unprocessed_episodes:
        sonarr_logger.info("All missing episodes have been processed.")
        return False
    
    # Apply randomization and limit
    random.shuffle(unprocessed_episodes)
    episodes_to_process = unprocessed_episodes[:hunt_missing_items]
    
    sonarr_logger.info(f"Episodes selected for processing in this cycle ({len(episodes_to_process)} of {len(unprocessed_episodes)} available)")
    
    # Process each episode individually
    processed_count = 0
    for episode in episodes_to_process:
        if stop_check():
            sonarr_logger.info("Stop requested. Aborting episode processing.")
            break
        
        # Check API limit before processing each episode
        try:
            if check_hourly_cap_exceeded("sonarr"):
                sonarr_logger.warning(f"🛑 Sonarr API hourly limit reached - stopping episodes processing after {processed_count} episodes")
                break
        except Exception as e:
            sonarr_logger.error(f"Error checking hourly API cap: {e}")
            # Continue processing if cap check fails - safer than stopping
        
        episode_id = episode.get('id')
        series_info = episode.get('series', {})
        series_title = series_info.get('title', 'Unknown Series')
        season_number = episode.get('seasonNumber', 'Unknown')
        episode_number = episode.get('episodeNumber', 'Unknown')
        episode_title = episode.get('title', 'Unknown Episode')
        
        try:
            season_episode = f"S{season_number:02d}E{episode_number:02d}"
        except (ValueError, TypeError):
            season_episode = f"S{season_number}E{episode_number}"
        
        sonarr_logger.info(f"Processing episode: {series_title} - {season_episode} - {episode_title}")
        
        # Search for this specific episode
        search_successful = sonarr_api.search_episode(api_url, api_key, api_timeout, [episode_id])
        
        if search_successful:
            processed_any = True
            processed_count += 1
            
            # Mark episode as processed
            success = add_processed_id("sonarr", instance_name, str(episode_id))
            sonarr_logger.debug(f"Added episode ID {episode_id} to processed list, success: {success}")
            
            # Log to history system
            media_name = f"{series_title} - {season_episode} - {episode_title}"
            log_processed_media("sonarr", media_name, str(episode_id), instance_name, "missing")
            sonarr_logger.debug(f"Logged history entry for episode: {media_name}")
            
            # Increment statistics
            increment_stat("sonarr", "hunted")
            sonarr_logger.debug(f"Incremented sonarr hunted statistics for episode {episode_id}")
            
            # Note: No tagging is performed in episodes mode as it would be inefficient
            # and could overwhelm the API with individual episode tag operations
            
        else:
            sonarr_logger.error(f"Failed to trigger search for episode: {series_title} - {season_episode}")
    
    sonarr_logger.info(f"Processed {processed_count} individual missing episodes for Sonarr.")
    sonarr_logger.warning("Episodes mode processing complete - consider using Season Packs mode for better efficiency")
    return processed_any

def wait_for_command(
    api_url: str,
    api_key: str,
    api_timeout: int,
    command_id: int,
    wait_delay: int,
    max_attempts: int,
    command_name: str = "Command",
    stop_check: Callable[[], bool] = lambda: False
) -> bool:
    """
    Wait for a Sonarr command to complete or timeout.
    
    Args:
        api_url: The Sonarr API URL
        api_key: The Sonarr API key
        api_timeout: API request timeout
        command_id: The ID of the command to monitor
        wait_delay: Seconds to wait between status checks
        max_attempts: Maximum number of status check attempts
        command_name: Name of the command (for logging)
        stop_check: Optional function to check if operation should be aborted
        
    Returns:
        True if command completed successfully, False otherwise
    """
    if wait_delay <= 0 or max_attempts <= 0:
        sonarr_logger.debug(f"Not waiting for command to complete (wait_delay={wait_delay}, max_attempts={max_attempts})")
        return True  # Return as if successful since we're not checking
    
    sonarr_logger.debug(f"Waiting for {command_name} to complete (command ID: {command_id}). Checking every {wait_delay}s for up to {max_attempts} attempts")
    
    # Wait for command completion
    attempts = 0
    while attempts < max_attempts:
        if stop_check():
            sonarr_logger.info(f"Stopping wait for {command_name} due to stop request")
            return False
            
        command_status = sonarr_api.get_command_status(api_url, api_key, api_timeout, command_id)
        if not command_status:
            sonarr_logger.warning(f"Failed to get status for {command_name} (ID: {command_id}), attempt {attempts+1}")
            attempts += 1
            time.sleep(wait_delay)
            continue
            
        status = command_status.get('status')
        if status == 'completed':
            sonarr_logger.debug(f"Sonarr {command_name} (ID: {command_id}) completed successfully")
            return True
        elif status in ['failed', 'aborted']:
            sonarr_logger.warning(f"Sonarr {command_name} (ID: {command_id}) {status}")
            return False
        
        sonarr_logger.debug(f"Sonarr {command_name} (ID: {command_id}) status: {status}, attempt {attempts+1}/{max_attempts}")
        
        attempts += 1
        time.sleep(wait_delay)
    
    sonarr_logger.error(f"Sonarr command '{command_name}' (ID: {command_id}) timed out after {max_attempts} attempts.")
    return False