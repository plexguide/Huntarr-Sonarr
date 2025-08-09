#!/usr/bin/env python3
"""
Huntarr - Main entry point for the application
Supports multiple Arr applications running concurrently
"""

import time
import sys
import os
# import socket # No longer used directly
import signal
import importlib
import logging
import threading
from typing import Dict, List, Optional, Callable, Union, Tuple
import datetime
import traceback
import pytz

# Define the version number
__version__ = "1.0.0" # Consider updating this based on changes

# Set up logging first
from src.primary.utils.logger import setup_main_logger, get_logger # Import get_logger
logger = setup_main_logger()

# Import necessary modules
from src.primary import config, settings_manager
# Removed keys_manager import as settings_manager handles API details
from src.primary.state import check_state_reset, calculate_reset_time
from src.primary.stats_manager import check_hourly_cap_exceeded
# Instance list generator has been removed
from src.primary.scheduler_engine import start_scheduler, stop_scheduler

# from src.primary.utils.app_utils import get_ip_address # No longer used here

# Global state for managing app threads and their status
app_threads: Dict[str, threading.Thread] = {}
stop_event = threading.Event() # Use an event for clearer stop signaling

# Hourly cap scheduler thread
hourly_cap_scheduler_thread = None

# Swaparr processing thread
swaparr_thread = None

# Instance list generator has been removed

def _get_user_timezone():
    """Get the user's selected timezone from general settings"""
    try:
        from src.primary.utils.timezone_utils import get_user_timezone
        return get_user_timezone()
    except Exception:
        return pytz.UTC

def app_specific_loop(app_type: str) -> None:
    """
    Main processing loop for a specific Arr application.

    Args:
        app_type: The type of Arr application (sonarr, radarr, lidarr, readarr)
    """
    from src.primary.cycle_tracker import update_next_cycle
    
    app_logger = get_logger(app_type)
    app_logger.info(f"=== [{app_type.upper()}] Thread starting ===")

    # Dynamically import app-specific modules
    process_missing = None
    process_upgrades = None
    get_queue_size = None
    check_connection = None
    get_instances_func = None # Default: No multi-instance function found
    hunt_missing_setting = ""
    hunt_upgrade_setting = ""

    try:
        # Import the main app module first to check for get_configured_instances
        app_module = importlib.import_module(f'src.primary.apps.{app_type}')
        api_module = importlib.import_module(f'src.primary.apps.{app_type}.api')
        missing_module = importlib.import_module(f'src.primary.apps.{app_type}.missing')
        upgrade_module = importlib.import_module(f'src.primary.apps.{app_type}.upgrade')

        # Try to get the multi-instance function from the main app module
        try:
            get_instances_func = getattr(app_module, 'get_configured_instances')
        except AttributeError:
            get_instances_func = None # Explicitly set to None if not found

        check_connection = getattr(api_module, 'check_connection')
        get_queue_size = getattr(api_module, 'get_download_queue_size', lambda api_url, api_key, api_timeout: 0) # Default if not found

        if app_type == "sonarr":
            missing_module = importlib.import_module('src.primary.apps.sonarr.missing')
            upgrade_module = importlib.import_module('src.primary.apps.sonarr.upgrade')
            process_missing = getattr(missing_module, 'process_missing_episodes')
            process_upgrades = getattr(upgrade_module, 'process_cutoff_upgrades')
            hunt_missing_setting = "hunt_missing_items"
            hunt_upgrade_setting = "hunt_upgrade_items"
        elif app_type == "radarr":
            missing_module = importlib.import_module('src.primary.apps.radarr.missing')
            upgrade_module = importlib.import_module('src.primary.apps.radarr.upgrade')
            process_missing = getattr(missing_module, 'process_missing_movies')
            process_upgrades = getattr(upgrade_module, 'process_cutoff_upgrades')
            hunt_missing_setting = "hunt_missing_movies"
            hunt_upgrade_setting = "hunt_upgrade_movies"
        elif app_type == "lidarr":
            missing_module = importlib.import_module('src.primary.apps.lidarr.missing')
            upgrade_module = importlib.import_module('src.primary.apps.lidarr.upgrade')
            # Use process_missing_albums as the function name
            process_missing = getattr(missing_module, 'process_missing_albums') 
            process_upgrades = getattr(upgrade_module, 'process_cutoff_upgrades')
            hunt_missing_setting = "hunt_missing_items"
            # Use hunt_upgrade_items
            hunt_upgrade_setting = "hunt_upgrade_items" 
        elif app_type == "readarr":
            missing_module = importlib.import_module('src.primary.apps.readarr.missing')
            upgrade_module = importlib.import_module('src.primary.apps.readarr.upgrade')
            process_missing = getattr(missing_module, 'process_missing_books')
            process_upgrades = getattr(upgrade_module, 'process_cutoff_upgrades')
            hunt_missing_setting = "hunt_missing_books"
            hunt_upgrade_setting = "hunt_upgrade_books"
        elif app_type == "whisparr":
            missing_module = importlib.import_module('src.primary.apps.whisparr.missing')
            upgrade_module = importlib.import_module('src.primary.apps.whisparr.upgrade')
            process_missing = getattr(missing_module, 'process_missing_items')
            process_upgrades = getattr(upgrade_module, 'process_cutoff_upgrades')
            hunt_missing_setting = "hunt_missing_items"  # Updated to new name
            hunt_upgrade_setting = "hunt_upgrade_items"  # Updated to new name
        elif app_type == "eros":
            missing_module = importlib.import_module('src.primary.apps.eros.missing')
            upgrade_module = importlib.import_module('src.primary.apps.eros.upgrade')
            process_missing = getattr(missing_module, 'process_missing_items')
            process_upgrades = getattr(upgrade_module, 'process_cutoff_upgrades')
            hunt_missing_setting = "hunt_missing_items"
            hunt_upgrade_setting = "hunt_upgrade_items"

        else:
            app_logger.error(f"Unsupported app_type: {app_type}")
            return # Exit thread if app type is invalid

    except (ImportError, AttributeError) as e:
        app_logger.error(f"Failed to import modules or functions for {app_type}: {e}", exc_info=True)
        return # Exit thread if essential modules fail to load

    # Create app-specific logger using provided function
    app_logger = logging.getLogger(f"huntarr.{app_type}")
    
    while not stop_event.is_set():
        # --- Load Settings for this Cycle --- #
        try:
            # Load all settings for this app for the current cycle
            app_settings = settings_manager.load_settings(app_type) # Corrected function name
            if not app_settings: # Handle case where loading fails
                app_logger.error("Failed to load settings. Skipping cycle.")
                stop_event.wait(60) # Wait a minute before retrying
                continue

            # Get global settings needed for cycle timing
            sleep_duration = app_settings.get("sleep_duration", 900)
            api_timeout = app_settings.get("api_timeout", 120) # Default to 120 seconds

        except Exception as e:
            app_logger.error(f"Error loading settings for cycle: {e}", exc_info=True)
            stop_event.wait(60) # Wait before retrying
            continue

        # --- State Reset Check --- #
        check_state_reset(app_type)

        app_logger.info(f"=== Starting {app_type.upper()} cycle ===")

        # Mark cycle as started (set cyclelock to True)
        try:
            from src.primary.cycle_tracker import start_cycle
            start_cycle(app_type)
        except Exception as e:
            app_logger.warning(f"Failed to mark cycle start for {app_type}: {e}")
            # Non-critical, continue execution

        # Check if we need to use multi-instance mode
        instances_to_process = []
        
        # Use the dynamically loaded function (if found)
        if get_instances_func:
            # Multi-instance mode supported
            try:
                instances_to_process = get_instances_func() # Call the dynamically loaded function
                if instances_to_process:
                    # Instance count logging removed to reduce log spam
                    pass
                else:
                    # No instances found via get_configured_instances
                    app_logger.debug(f"No configured {app_type} instances found. Skipping cycle.")
                    stop_event.wait(sleep_duration)
                    continue
            except Exception as e:
                app_logger.error(f"Error calling get_configured_instances function: {e}", exc_info=True)
                stop_event.wait(60)
                continue
        else:
            # get_instances_func is None (either not defined in app module or import failed earlier)
            # Fallback to single instance mode using base settings if available
            api_url = app_settings.get("api_url")
            api_key = app_settings.get("api_key")
            instance_name = app_settings.get("name", f"{app_type.capitalize()} Default") # Use 'name' or default
            
            if api_url and api_key:
                app_logger.info(f"Processing {app_type} as single instance: {instance_name}")
                # Create a list with a single dict matching the multi-instance structure
                instances_to_process = [{
                    "instance_name": instance_name, 
                    "api_url": api_url, 
                    "api_key": api_key
                }]
            else:
                app_logger.warning(f"No 'get_configured_instances' function found and no valid single instance config (URL/Key) for {app_type}. Skipping cycle.")
                stop_event.wait(sleep_duration)
                continue
            
        # If after all checks, instances_to_process is still empty
        if not instances_to_process:
            app_logger.warning(f"No valid {app_type} instances to process this cycle (unexpected state). Skipping.")
            stop_event.wait(sleep_duration)
            continue
            
        # Process each instance dictionary returned by get_configured_instances
        processed_any_items = False
        enabled_instances = []
        
        for instance_details in instances_to_process:
            if stop_event.is_set():
                break
                
            instance_name = instance_details.get("instance_name", "Default") # Use the dict from get_configured_instances
            app_logger.info(f"Processing {app_type} instance: {instance_name}")
            
            # Get instance-specific settings from the instance_details dict
            api_url = instance_details.get("api_url", "")
            api_key = instance_details.get("api_key", "")

            # Get global/shared settings from app_settings loaded at the start of the loop
            # Example: monitored_only = app_settings.get("monitored_only", True)

            # --- Connection Check --- #
            if not api_url or not api_key:
                app_logger.warning(f"Missing API URL or Key for instance '{instance_name}'. Skipping.")
                continue
            try:
                # Use instance details for connection check
                app_logger.debug(f"Checking connection to {app_type} instance '{instance_name}' at {api_url} with timeout {api_timeout}s")
                connected = check_connection(api_url, api_key, api_timeout=api_timeout)
                if not connected:
                    app_logger.warning(f"Failed to connect to {app_type} instance '{instance_name}' at {api_url}. Skipping.")
                    continue
                app_logger.debug(f"Successfully connected to {app_type} instance: {instance_name}")
            except Exception as e:
                app_logger.error(f"Error connecting to {app_type} instance '{instance_name}': {e}", exc_info=True)
                continue # Skip this instance if connection fails
                
            # --- API Cap Check --- #
            try:
                # Check if hourly API cap is exceeded
                if check_hourly_cap_exceeded(app_type):
                    # Get the current cap status for logging
                    from src.primary.stats_manager import get_hourly_cap_status
                    cap_status = get_hourly_cap_status(app_type)
                    app_logger.info(f"{app_type.upper()} hourly cap reached {cap_status['current_usage']} of {cap_status['limit']} (app-specific limit). Skipping cycle!")
                    continue # Skip this instance if API cap is exceeded
            except Exception as e:
                app_logger.error(f"Error checking hourly API cap for {app_type}: {e}", exc_info=True)
                # Continue with the cycle even if cap check fails - safer than skipping

            # --- Check if Hunt Modes are Enabled --- #
            # For per-instance settings, get values from instance details
            # For apps without per-instance settings, fall back to global app settings
            if app_type == "sonarr":
                hunt_missing_value = instance_details.get("hunt_missing_items", 1)  # Default to 1
                hunt_upgrade_value = instance_details.get("hunt_upgrade_items", 0)  # Default to 0
            elif app_type == "radarr":
                hunt_missing_value = instance_details.get("hunt_missing_movies", 1)  # Default to 1
                hunt_upgrade_value = instance_details.get("hunt_upgrade_movies", 0)  # Default to 0
            elif app_type == "lidarr":
                hunt_missing_value = instance_details.get("hunt_missing_items", 1)  # Default to 1
                hunt_upgrade_value = instance_details.get("hunt_upgrade_items", 0)  # Default to 0
            elif app_type == "readarr":
                hunt_missing_value = instance_details.get("hunt_missing_books", 1)  # Default to 1
                hunt_upgrade_value = instance_details.get("hunt_upgrade_books", 0)  # Default to 0
            elif app_type == "whisparr":
                hunt_missing_value = instance_details.get("hunt_missing_items", 1)  # Default to 1
                hunt_upgrade_value = instance_details.get("hunt_upgrade_items", 0)  # Default to 0
            elif app_type == "eros":
                hunt_missing_value = instance_details.get("hunt_missing_items", 1)  # Default to 1
                hunt_upgrade_value = instance_details.get("hunt_upgrade_items", 0)  # Default to 0
            else:
                # Fall back to global settings for other apps
                hunt_missing_value = app_settings.get(hunt_missing_setting, 0)
                hunt_upgrade_value = app_settings.get(hunt_upgrade_setting, 0)

            hunt_missing_enabled = hunt_missing_value > 0
            hunt_upgrade_enabled = hunt_upgrade_value > 0
            
            # Debug logging for per-instance hunt values
            app_logger.debug(f"Instance '{instance_name}' - Missing: {hunt_missing_value} (enabled: {hunt_missing_enabled}), Upgrade: {hunt_upgrade_value} (enabled: {hunt_upgrade_enabled})")

            # --- Queue Size Check --- # Moved inside loop
            # Get maximum_download_queue_size from general settings (still using minimum_download_queue_size key for backward compatibility)
            general_settings = settings_manager.load_settings('general')
            max_queue_size = general_settings.get("minimum_download_queue_size", -1)
    
            
            if max_queue_size >= 0:
                try:
                    # Use instance details for queue check
                    current_queue_size = get_queue_size(api_url, api_key, api_timeout)
                    if current_queue_size >= max_queue_size:
                        app_logger.info(f"Download queue size ({current_queue_size}) meets or exceeds maximum ({max_queue_size}) for {instance_name}. Skipping cycle for this instance.")
                        continue # Skip processing for this instance
                    else:
                        app_logger.info(f"Queue size ({current_queue_size}) is below maximum ({max_queue_size}). Proceeding.")
                except Exception as e:
                    app_logger.warning(f"Could not get download queue size for {instance_name}. Proceeding anyway. Error: {e}", exc_info=False) # Log less verbosely
            
            # Prepare args dictionary for processing functions
            # Combine instance details with general app settings for the processing functions
            # Assuming app_settings already contains most general settings, add instance specifics
            combined_settings = app_settings.copy() # Start with general settings
            combined_settings.update(instance_details) # Add/overwrite with instance specifics (name, url, key)
            
            # Ensure settings from database are consistently used for all apps
            combined_settings["api_timeout"] = settings_manager.get_advanced_setting("api_timeout", 120)
            combined_settings["command_wait_delay"] = settings_manager.get_advanced_setting("command_wait_delay", 1)
            combined_settings["command_wait_attempts"] = settings_manager.get_advanced_setting("command_wait_attempts", 600)
            
            # Define the stop check function
            stop_check_func = stop_event.is_set

            # --- Process Missing --- #
            if hunt_missing_enabled and process_missing:
                try:
                    # Extract settings for direct function calls
                    api_url = combined_settings.get("api_url", "").strip()
                    api_key = combined_settings.get("api_key", "").strip()
                    api_timeout = combined_settings.get("api_timeout", 120)
                    monitored_only = combined_settings.get("monitored_only", True)
                    skip_future_episodes = combined_settings.get("skip_future_episodes", True)
                    hunt_missing_items = hunt_missing_value  # Use per-instance value
                    hunt_missing_mode = instance_details.get("hunt_missing_mode", "seasons_packs")
                    command_wait_delay = combined_settings.get("command_wait_delay", 1)
                    command_wait_attempts = combined_settings.get("command_wait_attempts", 600)
                    
                    if app_type == "sonarr":
                        processed_missing = process_missing(
                            api_url=api_url,
                            api_key=api_key,
                            instance_name=instance_name,  # Added the required instance_name parameter
                            api_timeout=api_timeout,
                            monitored_only=monitored_only,
                            skip_future_episodes=skip_future_episodes,
                            hunt_missing_items=hunt_missing_items,
                            hunt_missing_mode=hunt_missing_mode,
                            command_wait_delay=command_wait_delay,
                            command_wait_attempts=command_wait_attempts,
                            stop_check=stop_check_func
                        )
                    else:
                        # For other apps that still use the old signature
                        processed_missing = process_missing(app_settings=combined_settings, stop_check=stop_check_func)
                        
                    if processed_missing:
                        processed_any_items = True
                except Exception as e:
                    app_logger.error(f"Error during missing processing for {instance_name}: {e}", exc_info=True)

            # --- Process Upgrades --- #
            if hunt_upgrade_enabled and process_upgrades:
                try:
                    # Extract settings for direct function calls (only for Sonarr)
                    if app_type == "sonarr":
                        api_url = combined_settings.get("api_url", "").strip()
                        api_key = combined_settings.get("api_key", "").strip()
                        api_timeout = combined_settings.get("api_timeout", 120)
                        monitored_only = combined_settings.get("monitored_only", True)
                        hunt_upgrade_items = hunt_upgrade_value  # Use per-instance value
                        upgrade_mode = instance_details.get("upgrade_mode", "seasons_packs")
                        command_wait_delay = combined_settings.get("command_wait_delay", 1)
                        command_wait_attempts = combined_settings.get("command_wait_attempts", 600)
                        
                        processed_upgrades = process_upgrades(
                            api_url=api_url,
                            api_key=api_key,
                            instance_name=instance_name,  # Added the required instance_name parameter
                            api_timeout=api_timeout,
                            monitored_only=monitored_only,
                            hunt_upgrade_items=hunt_upgrade_items,
                            upgrade_mode=upgrade_mode,
                            command_wait_delay=command_wait_delay,
                            command_wait_attempts=command_wait_attempts,
                            stop_check=stop_check_func
                        )
                    else:
                        # For other apps that still use the old signature
                        processed_upgrades = process_upgrades(app_settings=combined_settings, stop_check=stop_check_func)
                        
                    if processed_upgrades:
                        processed_any_items = True
                except Exception as e:
                    app_logger.error(f"Error during upgrade processing for {instance_name}: {e}", exc_info=True)



            # Small delay between instances if needed (optional)
            if not stop_event.is_set():
                 time.sleep(1) # Short pause
            enabled_instances.append(instance_name)

        # --- Cycle End & Sleep --- #
        calculate_reset_time(app_type) # Pass app_type here if needed by the function

        # Log cycle completion
        if processed_any_items:
            app_logger.info(f"=== {app_type.upper()} cycle finished. Processed items across instances. ===")
        else:
            app_logger.debug(f"=== {app_type.upper()} cycle finished. No items processed in any instance. ===")
            
        # Add state management summary logging for user clarity (only for hunting apps, not Swaparr)
        if app_type != "swaparr":
            try:
                from src.primary.stateful_manager import get_state_management_summary
                
                # Get summary for each enabled instance with per-instance settings
                instance_summaries = []
                total_processed = 0
                has_any_processed = False
                
                for instance_name in enabled_instances:
                    # Get per-instance settings
                    instance_hours = None
                    instance_enabled = True
                    instance_mode = "custom"
                    
                    try:
                        # Look up the instance in the configured instances
                        if configured_instances and app_type in configured_instances:
                            for instance_details in configured_instances[app_type]:
                                if instance_details.get("instance_name") == instance_name:
                                    instance_hours = instance_details.get("state_management_hours", 168)
                                    instance_mode = instance_details.get("state_management_mode", "custom")
                                    instance_enabled = (instance_mode != "disabled")
                                    break
                    except Exception as e:
                        app_logger.warning(f"Could not load instance settings for {instance_name}: {e}")
                        instance_hours = 168  # Default fallback
                    
                    # Get summary for this instance
                    summary = get_state_management_summary(app_type, instance_name, instance_hours)
                    
                    # Store instance-specific information
                    instance_summaries.append({
                        "name": instance_name,
                        "enabled": instance_enabled,
                        "mode": instance_mode,
                        "hours": instance_hours,
                        "processed_count": summary["processed_count"],
                        "next_reset_time": summary["next_reset_time"],
                        "has_processed_items": summary["has_processed_items"]
                    })
                    
                    # Only count if state management is enabled for this instance
                    if instance_enabled and summary["has_processed_items"]:
                        total_processed += summary["processed_count"]
                        has_any_processed = True
                
                # Log per-instance state management info
                if instance_summaries:
                    app_logger.debug(f"=== STATE MANAGEMENT SUMMARY FOR {app_type.upper()} ===")
                    
                    for inst in instance_summaries:
                        if inst["enabled"]:
                            if inst["processed_count"] > 0:
                                app_logger.debug(f"  {inst['name']}: {inst['processed_count']} items tracked, next reset: {inst['next_reset_time']} ({inst['hours']}h interval)")
                            else:
                                app_logger.debug(f"  {inst['name']}: No items tracked yet, next reset: {inst['next_reset_time']} ({inst['hours']}h interval)")
                        else:
                            app_logger.debug(f"  {inst['name']}: State management disabled")
                    
                    # Overall summary
                    if not processed_any_items and has_any_processed:
                        # Items were skipped due to state management
                        app_logger.debug(f"RESULT: {total_processed} items skipped due to state management (already processed)")
                    elif processed_any_items:
                        # Items were processed, show summary
                        app_logger.debug(f"RESULT: Items processed successfully. Total tracked across instances: {total_processed}")
                    else:
                        # No items processed and no state management blocking
                        if total_processed > 0:
                            app_logger.debug(f"RESULT: No new items found. Total tracked across instances: {total_processed}")
                        else:
                            app_logger.debug(f"RESULT: No items to process and no items tracked yet")
                    
            except Exception as e:
                app_logger.warning(f"Could not generate state management summary: {e}")
        else:
            # Swaparr uses its own state management for strikes and removed downloads
            app_logger.debug(f"Swaparr uses its own strike/removal tracking, not the hunting state manager")
            
        # Calculate sleep duration (use configured or default value)
        sleep_seconds = app_settings.get("sleep_duration", 900)  # Default to 15 minutes
                
        # Sleep with periodic checks for reset file
        # Calculate and format the time when the next cycle will begin
        # Use user's selected timezone for all time operations
        
        # Get user's selected timezone
        user_tz = _get_user_timezone()
        
        # Get current time in user's timezone - remove microseconds for clean timestamps
        now_user_tz = datetime.datetime.now(user_tz).replace(microsecond=0)
        
        # Calculate next cycle time in user's timezone without microseconds
        next_cycle_time = now_user_tz + datetime.timedelta(seconds=sleep_seconds)
        
        app_logger.debug(f"Current time ({user_tz}): {now_user_tz.strftime('%Y-%m-%d %H:%M:%S')}")
        app_logger.debug(f"Next cycle will begin at {next_cycle_time.strftime('%Y-%m-%d %H:%M:%S')} ({user_tz})")
        app_logger.debug(f"Sleep duration: {sleep_seconds} seconds")
        
        # Update cycle tracking with user timezone time
        next_cycle_naive = next_cycle_time.replace(tzinfo=None) if next_cycle_time.tzinfo else next_cycle_time
        update_next_cycle(app_type, next_cycle_naive)
        
        # Mark cycle as ended (set cyclelock to False) and update next cycle time
        # Use user's timezone for internal storage consistency
        try:
            from src.primary.cycle_tracker import end_cycle
            # Convert timezone-aware datetime to naive for clean timestamp generation
            next_cycle_naive = next_cycle_time.replace(tzinfo=None) if next_cycle_time.tzinfo else next_cycle_time
            end_cycle(app_type, next_cycle_naive)
        except Exception as e:
            app_logger.warning(f"Failed to mark cycle end for {app_type}: {e}")
            # Non-critical, continue execution
        
        app_logger.debug(f"Sleeping for {sleep_seconds} seconds before next cycle...")
                
        # Use shorter sleep intervals and check for reset file
        wait_interval = 1  # Check every second to be more responsive
        elapsed = 0
        while elapsed < sleep_seconds:
            # Check if stop event is set
            if stop_event.is_set():
                app_logger.info("Stop event detected during sleep. Breaking out of sleep cycle.")
                break
                        
            # Check for database reset request
            try:
                from src.primary.utils.database import get_database
                db = get_database()
                reset_timestamp = db.get_pending_reset_request(app_type)
                if reset_timestamp:
                    app_logger.info(f"!!! RESET REQUEST DETECTED !!! Manual cycle reset triggered for {app_type} (timestamp: {reset_timestamp}). Starting new cycle immediately.")
                    
                    # Mark the reset request as processed
                    db.mark_reset_request_processed(app_type)
                    app_logger.info(f"Reset request processed for {app_type}. Starting new cycle now.")
                    break
            except Exception as e:
                app_logger.error(f"Error checking reset request for {app_type}: {e}", exc_info=True)
                        
            # Sleep for a short interval
            stop_event.wait(wait_interval)
            elapsed += wait_interval
                    
            # If we've slept for at least 30 seconds, update the logger message every 30 seconds
            if elapsed > 0 and elapsed % 30 == 0:
                app_logger.debug(f"Still sleeping, {sleep_seconds - elapsed} seconds remaining before next cycle...")
                
    app_logger.info(f"=== [{app_type.upper()}] Thread stopped ====")

def reset_app_cycle(app_type: str) -> bool:
    """
    Trigger a manual reset of an app's cycle.
    
    Args:
        app_type: The type of Arr application (sonarr, radarr, lidarr, readarr, etc.)
        
    Returns:
        bool: True if the reset was triggered, False if the app is not running
    """
    logger.info(f"Manual cycle reset requested for {app_type} - Creating reset request")
    
    # Create a reset request in the database
    try:
        from src.primary.utils.database import get_database
        db = get_database()
        success = db.create_reset_request(app_type)
        if success:
            logger.info(f"Reset request created for {app_type}. Cycle will reset on next check.")
        return success
    except Exception as e:
        logger.error(f"Error creating reset request for {app_type}: {e}", exc_info=True)
        return False

def start_app_threads():
    """Start threads for all configured and enabled apps."""
    configured_apps_list = settings_manager.get_configured_apps() # Corrected function name
    configured_apps = {app: True for app in configured_apps_list} # Convert list to dict format expected below

    for app_type, is_configured in configured_apps.items():
        if is_configured:
            # Optional: Add an explicit 'enabled' setting check if desired
            # enabled = settings_manager.get_setting(app_type, "enabled", True)
            # if not enabled:
            #     logger.info(f"Skipping {app_type} thread as it is disabled in settings.")
            #     continue

            if app_type not in app_threads or not app_threads[app_type].is_alive():
                if app_type in app_threads: # If it existed but died
                    logger.warning(f"{app_type} thread died, restarting...")
                    del app_threads[app_type]
                else: # Starting for the first time
                    logger.info(f"Starting thread for {app_type}...")

                thread = threading.Thread(target=app_specific_loop, args=(app_type,), name=f"{app_type}-Loop", daemon=True)
                app_threads[app_type] = thread
                thread.start()
        elif app_type in app_threads and app_threads[app_type].is_alive():
             # If app becomes un-configured, stop its thread? Or let it fail connection check?
             # For now, let it run and fail connection check.
             logger.warning(f"{app_type} is no longer configured. Thread will likely stop after failing connection checks.")
        # else: # App not configured and no thread running - do nothing
            # logger.debug(f"{app_type} is not configured. No thread started.")
        pass # Corrected indentation

def check_and_restart_threads():
    """Check if any threads have died and restart them if the app is still configured."""
    configured_apps_list = settings_manager.get_configured_apps() # Corrected function name
    configured_apps = {app: True for app in configured_apps_list} # Convert list to dict format expected below

    for app_type, thread in list(app_threads.items()):
        if not thread.is_alive():
            logger.warning(f"{app_type} thread died unexpectedly.")
            del app_threads[app_type] # Remove dead thread
            # Only restart if it's still configured
            if configured_apps.get(app_type, False):
                logger.info(f"Restarting thread for {app_type}...")
                new_thread = threading.Thread(target=app_specific_loop, args=(app_type,), name=f"{app_type}-Loop", daemon=True)
                app_threads[app_type] = new_thread
                new_thread.start()
            else:
                logger.info(f"Not restarting {app_type} thread as it is no longer configured.")

def shutdown_handler(signum, frame):
    """Handle termination signals (SIGINT, SIGTERM)."""
    signal_name = "SIGINT" if signum == signal.SIGINT else "SIGTERM" if signum == signal.SIGTERM else f"Signal {signum}"
    logger.info(f"Received {signal_name}. Initiating background tasks shutdown...")
    stop_event.set() # Signal all threads to stop
    
    # Log shutdown progress for Docker diagnostics
    logger.info("Background shutdown initiated - threads will stop gracefully")

def shutdown_threads():
    """Wait for all threads to finish."""
    import time
    shutdown_start = time.time()
    logger.info("Waiting for all app threads to stop...")
    
    # Stop the hourly API cap scheduler
    global hourly_cap_scheduler_thread
    if hourly_cap_scheduler_thread and hourly_cap_scheduler_thread.is_alive():
        # The thread should exit naturally due to the stop_event being set
        logger.info("Waiting for hourly API cap scheduler to stop...")
        hourly_cap_scheduler_thread.join(timeout=5.0)
        if hourly_cap_scheduler_thread.is_alive():
            logger.warning("Hourly API cap scheduler did not stop gracefully")
        else:
            logger.info("Hourly API cap scheduler stopped")
    
    # Stop the Swaparr processing thread
    global swaparr_thread
    if swaparr_thread and swaparr_thread.is_alive():
        # The thread should exit naturally due to the stop_event being set
        logger.info("Waiting for Swaparr thread to stop...")
        swaparr_thread.join(timeout=5.0)
        if swaparr_thread.is_alive():
            logger.warning("Swaparr thread did not stop gracefully")
        else:
            logger.info("Swaparr thread stopped")
    
    # Stop the scheduler engine
    try:
        logger.info("Stopping schedule action engine...")
        stop_scheduler()
        logger.info("Schedule action engine stopped successfully")
    except Exception as e:
        logger.error(f"Error stopping schedule action engine: {e}")
    
    # Wait for all app threads to terminate
    active_threads = [name for name, thread in app_threads.items() if thread.is_alive()]
    if active_threads:
        logger.info(f"Waiting for {len(active_threads)} app threads to stop: {', '.join(active_threads)}")
        
        for name, thread in app_threads.items():
            if thread.is_alive():
                logger.debug(f"Waiting for {name} thread to stop...")
                thread.join(timeout=10.0)
                if thread.is_alive():
                    logger.warning(f"{name} thread did not stop gracefully within 10 seconds")
                else:
                    logger.debug(f"{name} thread stopped successfully")
    
    shutdown_duration = time.time() - shutdown_start
    logger.info(f"All app threads stopped. Shutdown completed in {shutdown_duration:.2f} seconds")

def hourly_cap_scheduler_loop():
    """Main loop for the hourly API cap scheduler thread
    Checks time every 30 seconds and resets caps if needed at the top of the hour
    """
    logger.info("Starting hourly API cap scheduler loop")
    
    try:
        from src.primary.stats_manager import reset_hourly_caps
        
        # Initial check in case we're starting right at the top of an hour
        current_time = datetime.datetime.now()
        if current_time.minute == 0:
            logger.debug(f"Initial hourly reset triggered at {current_time.hour}:00")
            reset_hourly_caps()
        
        # Main monitoring loop
        while not stop_event.is_set():
            try:
                # Sleep for 30 seconds between checks
                # This ensures we won't miss the top of the hour
                stop_event.wait(30)
                
                if stop_event.is_set():
                    break
                    
                # Check if it's the top of the hour (00 minute mark)
                current_time = datetime.datetime.now()
                if current_time.minute == 0:
                    logger.debug(f"Hourly reset triggered at {current_time.hour}:00")
                    success = reset_hourly_caps()
                    if success:
                        logger.debug(f"Successfully reset hourly API caps at {current_time.hour}:00")
                    else:
                        logger.error(f"Failed to reset hourly API caps at {current_time.hour}:00")
                
            except Exception as e:
                logger.error(f"Error in hourly cap scheduler: {e}")
                logger.error(traceback.format_exc())
                # Sleep briefly to avoid spinning in case of repeated errors
                time.sleep(5)
                
    except Exception as e:
        logger.error(f"Fatal error in hourly cap scheduler: {e}")
        logger.error(traceback.format_exc())
    
    logger.info("Hourly API cap scheduler stopped")

def swaparr_app_loop():
    """Dedicated Swaparr processing loop that follows same patterns as other apps"""
    swaparr_logger = get_logger("swaparr")
    swaparr_logger.info("Swaparr thread started")
    
    try:
        from src.primary.apps.swaparr.handler import run_swaparr
        from src.primary.settings_manager import load_settings
        from src.primary.cycle_tracker import start_cycle, end_cycle, update_next_cycle
        
        while not stop_event.is_set():
            try:
                # Load Swaparr settings
                swaparr_settings = load_settings("swaparr")
                
                if not swaparr_settings or not swaparr_settings.get("enabled", False):
                    # Swaparr is disabled - no need to log this repeatedly
                    # Sleep for 30 seconds when disabled, then check again
                    if not stop_event.wait(30):
                        continue
                    else:
                        break
                
                # Get sleep duration from settings
                sleep_duration = swaparr_settings.get("sleep_duration", 900)
                
                # Get user's timezone
                user_tz = _get_user_timezone()
                
                # Calculate next cycle time in user's timezone
                now_user_tz = datetime.datetime.now(user_tz).replace(microsecond=0)
                next_cycle_time = now_user_tz + datetime.timedelta(seconds=sleep_duration)
                
                # Start cycle tracking
                start_cycle("swaparr")
                
                # Start cycle
                swaparr_logger.info("=== SWAPARR cycle started. Processing stalled downloads across all instances. ===")
                
                try:
                    # Run Swaparr processing
                    run_swaparr()
                    swaparr_logger.info("=== SWAPARR cycle finished. Processed stalled downloads across instances. ===")
                except Exception as e:
                    swaparr_logger.error(f"Error during Swaparr processing: {e}", exc_info=True)
                    swaparr_logger.info("=== SWAPARR cycle finished with errors. ===")
                
                # End cycle tracking
                next_cycle_naive = next_cycle_time.replace(tzinfo=None) if next_cycle_time.tzinfo else next_cycle_time
                end_cycle("swaparr", next_cycle_naive)
                update_next_cycle("swaparr", next_cycle_naive)
                
                # Sleep duration and next cycle info (like other apps)
                swaparr_logger.debug(f"Current time ({user_tz}): {now_user_tz.strftime('%Y-%m-%d %H:%M:%S')}")
                swaparr_logger.debug(f"Next cycle will begin at {next_cycle_time.strftime('%Y-%m-%d %H:%M:%S')} ({user_tz})")
                swaparr_logger.debug(f"Sleep duration: {sleep_duration} seconds")
                
                # Sleep with responsiveness to stop events and reset requests (like other apps)
                elapsed = 0
                wait_interval = 5  # Check every 5 seconds for responsiveness
                while elapsed < sleep_duration and not stop_event.is_set():
                    # Check for database reset request (same logic as other apps)
                    try:
                        from src.primary.utils.database import get_database
                        db = get_database()
                        reset_timestamp = db.get_pending_reset_request("swaparr")
                        if reset_timestamp:
                            swaparr_logger.info(f"!!! RESET REQUEST DETECTED !!! Manual cycle reset triggered for swaparr (timestamp: {reset_timestamp}). Starting new cycle immediately.")
                            
                            # Mark the reset request as processed
                            db.mark_reset_request_processed("swaparr")
                            swaparr_logger.info(f"Reset request processed for swaparr. Starting new cycle now.")
                            break
                    except Exception as e:
                        swaparr_logger.error(f"Error checking reset request for swaparr: {e}", exc_info=True)
                    
                    # Check for stop event
                    if stop_event.is_set():
                        swaparr_logger.info("Stop event detected during sleep. Breaking out of sleep cycle.")
                        break
                    
                    # Sleep for a short interval
                    stop_event.wait(wait_interval)
                    elapsed += wait_interval
                    
                    # Log progress every 30 seconds (like other apps)
                    if elapsed > 0 and elapsed % 30 == 0:
                        swaparr_logger.debug(f"Still sleeping, {sleep_duration - elapsed} seconds remaining before next cycle...")
                    
            except Exception as e:
                swaparr_logger.error(f"Unexpected error in Swaparr loop: {e}", exc_info=True)
                # Sleep briefly to avoid spinning in case of repeated errors
                time.sleep(60)
                
    except Exception as e:
        swaparr_logger.error(f"Fatal error in Swaparr thread: {e}", exc_info=True)
    
    swaparr_logger.info("Swaparr thread stopped")



def start_hourly_cap_scheduler():
    """Start the hourly API cap scheduler thread"""
    global hourly_cap_scheduler_thread
    
    if hourly_cap_scheduler_thread and hourly_cap_scheduler_thread.is_alive():
        logger.info("Hourly API cap scheduler already running")
        return
    
    # Create and start the scheduler thread
    hourly_cap_scheduler_thread = threading.Thread(
        target=hourly_cap_scheduler_loop, 
        name="HourlyCapScheduler", 
        daemon=True
    )
    hourly_cap_scheduler_thread.start()
    
    logger.info(f"Hourly API cap scheduler started. Thread is alive: {hourly_cap_scheduler_thread.is_alive()}")

def start_swaparr_thread():
    """Start the dedicated Swaparr processing thread"""
    global swaparr_thread
    
    if swaparr_thread and swaparr_thread.is_alive():
        logger.info("Swaparr thread already running")
        return
    
    # Create and start the Swaparr thread
    swaparr_thread = threading.Thread(
        target=swaparr_app_loop, 
        name="SwaparrApp", 
        daemon=True
    )
    swaparr_thread.start()
    
    logger.info(f"Swaparr thread started. Thread is alive: {swaparr_thread.is_alive()}")

def start_huntarr():
    """Main entry point for Huntarr background tasks."""
    logger.info(f"--- Starting Huntarr Background Tasks v{__version__} --- ")
    

    # Migration environment variable no longer used
        
    # Start the hourly API cap scheduler
    try:
        start_hourly_cap_scheduler()
        logger.info("Hourly API cap scheduler started successfully")
    except Exception as e:
        logger.error(f"Failed to start hourly API cap scheduler: {e}")
        
    # Start the Swaparr processing thread
    try:
        start_swaparr_thread()
        logger.info("Swaparr thread started successfully")
    except Exception as e:
        logger.error(f"Failed to start Swaparr thread: {e}")
        
    # Start the scheduler engine
    try:
        start_scheduler()
        logger.info("Schedule action engine started successfully")
    except Exception as e:
        logger.error(f"Failed to start schedule action engine: {e}")
        
    # Configuration logging has been disabled to reduce log spam
    # Settings are loaded and used internally without verbose logging

    try:
        # Main loop: Start and monitor app threads
        while not stop_event.is_set():
            start_app_threads() # Start/Restart threads for configured apps
            # check_and_restart_threads() # This is implicitly handled by start_app_threads checking is_alive
            stop_event.wait(15) # Check for stop signal every 15 seconds

    except Exception as e:
        logger.exception(f"Unexpected error in main monitoring loop: {e}")
    finally:
        logger.info("Background task main loop exited. Shutting down threads...")
        if not stop_event.is_set():
             stop_event.set() # Ensure stop is signaled if loop exited unexpectedly
        shutdown_threads()
        logger.info("--- Huntarr Background Tasks stopped --- ")