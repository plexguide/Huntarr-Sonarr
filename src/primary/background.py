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
from typing import Dict, List, Optional

# Define the version number
__version__ = "1.0.0" # Consider updating this based on changes

# Set up logging first
from src.primary.utils.logger import setup_logger, get_logger # Import get_logger
logger = setup_logger()

# Import necessary modules
from src.primary import config, settings_manager
# Removed keys_manager import as settings_manager handles API details
from src.primary.state import check_state_reset, calculate_reset_time
# from src.primary.utils.app_utils import get_ip_address # No longer used here

# Track active threads and stop flag
app_threads: Dict[str, threading.Thread] = {}
stop_event = threading.Event() # Use an event for clearer stop signaling

# Removed old signal handler and restart_cycles logic
# Settings changes are now handled by reloading settings within the loop

def app_specific_loop(app_type: str) -> None:
    """
    Main processing loop for a specific Arr application.

    Args:
        app_type: The type of Arr application (sonarr, radarr, lidarr, readarr)
    """
    app_logger = get_logger(app_type)
    app_logger.info(f"=== [{app_type.upper()}] Thread starting ===")

    # Dynamically import app-specific modules
    process_missing = None
    process_upgrades = None
    get_queue_size = None
    check_connection = None
    get_configured_instances = None  # For multiple instances support
    hunt_missing_setting = ""
    hunt_upgrade_setting = ""

    try:
        api_module = importlib.import_module(f'src.primary.apps.{app_type}.api')
        check_connection = getattr(api_module, 'check_connection')
        get_queue_size = getattr(api_module, 'get_download_queue_size', lambda: 0) # Default if not found

        # Import app-specific main module for multi-instance support
        try:
            app_main_module = importlib.import_module(f'src.primary.apps.{app_type}')
            get_configured_instances = getattr(app_main_module, 'get_configured_instances', None)
        except (ImportError, AttributeError):
            app_logger.debug(f"No get_configured_instances found for {app_type}, will use single instance mode")

        if app_type == "sonarr":
            missing_module = importlib.import_module('src.primary.apps.sonarr.missing')
            upgrade_module = importlib.import_module('src.primary.apps.sonarr.upgrade')
            process_missing = getattr(missing_module, 'process_missing_episodes')
            process_upgrades = getattr(upgrade_module, 'process_cutoff_upgrades')
            hunt_missing_setting = "hunt_missing_shows"
            hunt_upgrade_setting = "hunt_upgrade_episodes"
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
            # Use process_missing_content as the function name might change based on mode
            process_missing = getattr(missing_module, 'process_missing_content') 
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
            process_missing = getattr(missing_module, 'process_missing_scenes')
            process_upgrades = getattr(upgrade_module, 'process_cutoff_upgrades')
            hunt_missing_setting = "hunt_missing_scenes"
            hunt_upgrade_setting = "hunt_upgrade_scenes"
        else:
            app_logger.error(f"Unsupported app_type: {app_type}")
            return # Exit thread if app type is invalid

    except (ImportError, AttributeError) as e:
        app_logger.error(f"Failed to import modules or functions for {app_type}: {e}", exc_info=True)
        return # Exit thread if essential modules fail to load

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

        except Exception as e:
            app_logger.error(f"Error loading settings for cycle: {e}", exc_info=True)
            stop_event.wait(60) # Wait before retrying
            continue

        # --- State Reset Check --- #
        check_state_reset(app_type)

        app_logger.info(f"=== Starting {app_type.upper()} cycle ===")

        # Check if we need to use multi-instance mode
        instances_to_process = []
        
        if get_configured_instances:
            # Multi-instance mode supported
            try:
                instances_to_process = get_configured_instances()
                if instances_to_process:
                    app_logger.info(f"Found {len(instances_to_process)} configured {app_type} instances to process")
                else:
                    # No instances found via get_configured_instances
                    app_logger.warning(f"No configured {app_type} instances found. Skipping cycle.")
                    stop_event.wait(sleep_duration)
                    continue
            except Exception as e:
                app_logger.error(f"Error getting configured instances: {e}", exc_info=True)
                stop_event.wait(60)
                continue
        else:
            # get_configured_instances function doesn't exist for this app type
            app_logger.error(f"Multi-instance support function 'get_configured_instances' not found for {app_type}. Cannot process.")
            stop_event.wait(sleep_duration)
            continue
            
        # If after all checks, instances_to_process is still empty (shouldn't happen if logic above is correct, but good safety check)
        if not instances_to_process:
            app_logger.warning(f"No valid {app_type} instances to process this cycle (unexpected state). Skipping.")
            stop_event.wait(sleep_duration)
            continue
            
        # Process each instance dictionary returned by get_configured_instances
        cycle_processed_anything = False
        for instance_details in instances_to_process:
            if stop_event.is_set():
                break
                
            instance_name = instance_details.get("instance_name", "Default") # Use the dict from get_configured_instances
            app_logger.info(f"Processing {app_type} instance: {instance_name}")
            
            # Get instance-specific settings from the instance_details dict
            api_url = instance_details.get("api_url", "")
            api_key = instance_details.get("api_key", "")
            
            # Get global/shared settings from app_settings loaded at the start of the loop
            api_timeout = app_settings.get("api_timeout", 10) # Fetch from app_settings
            min_download_queue_size = app_settings.get("minimum_download_queue_size", -1) # Fetch from app_settings
            hunt_missing_count = app_settings.get(hunt_missing_setting, 0) # Fetch from app_settings
            hunt_upgrade_count = app_settings.get(hunt_upgrade_setting, 0) # Fetch from app_settings
            # Add any other necessary global settings here, fetched from app_settings
            monitored_only = app_settings.get("monitored_only", True)
            skip_future_episodes = app_settings.get("skip_future_episodes", True) # Example for Sonarr
            skip_series_refresh = app_settings.get("skip_series_refresh", True) # Example for Sonarr
            random_missing = app_settings.get("random_missing", False)
            random_upgrades = app_settings.get("random_upgrades", False)
            command_wait_delay = app_settings.get("command_wait_delay", 5)
            command_wait_attempts = app_settings.get("command_wait_attempts", 12)
            state_reset_interval_hours = app_settings.get("state_reset_interval_hours", 168)
            skip_cutoff_unmet = app_settings.get("skip_cutoff_unmet", True) # Example for Sonarr upgrade

            # --- Connection Check for this instance --- #
            api_connected = False
            connection_attempts = 0
            max_connection_attempts = 3
            while not api_connected and connection_attempts < max_connection_attempts and not stop_event.is_set():
                try:
                    # Pass loaded URL, Key, and Timeout explicitly
                    api_connected = check_connection(api_url, api_key, api_timeout)
                except Exception as e:
                    app_logger.error(f"Error during connection check for {instance_name}: {e}", exc_info=True)
                    api_connected = False # Ensure it's false on exception

                if not api_connected:
                    connection_attempts += 1
                    app_logger.error(f"{app_type.title()} instance {instance_name} connection failed (Attempt {connection_attempts}/{max_connection_attempts}). Check API URL/Key.")
                    if connection_attempts < max_connection_attempts:
                        app_logger.info(f"Retrying connection in 10 seconds...")
                        # Wait for 10 seconds, but check stop_event frequently
                        stop_event.wait(10)
                    else:
                        app_logger.warning(f"Max connection attempts reached for instance {instance_name}. Skipping this instance.")
                        break # Exit connection loop

            if not api_connected:
                # Skip this instance and move to the next one
                app_logger.info(f"Skipping {app_type} instance {instance_name} due to connection failure.")
                continue

            # --- Processing Logic for this instance --- #
            instance_processed_anything = False
            try:
                # Get download queue size
                download_queue_size = get_queue_size(api_url, api_key, api_timeout)

                if min_download_queue_size < 0 or download_queue_size <= min_download_queue_size:
                    # Process Missing
                    if process_missing and hunt_missing_count > 0:
                        app_logger.info(f"Checking for {hunt_missing_count} missing items in {instance_name}...")
                        try:
                            # Construct the settings dictionary expected by the processing functions
                            merged_settings = {
                                "api_url": api_url,
                                "api_key": api_key,
                                "api_timeout": api_timeout,
                                "monitored_only": monitored_only,
                                "skip_future_episodes": skip_future_episodes, # Specific to sonarr missing
                                "skip_series_refresh": skip_series_refresh, # Specific to sonarr missing
                                "random_missing": random_missing,
                                "hunt_missing_shows": hunt_missing_count, # Pass the actual count
                                "command_wait_delay": command_wait_delay,
                                "command_wait_attempts": command_wait_attempts,
                                "state_reset_interval_hours": state_reset_interval_hours
                            }
                            # Pass the merged settings dictionary and the stop check function
                            if process_missing(merged_settings, stop_event.is_set):
                                instance_processed_anything = True
                                cycle_processed_anything = True
                            else:
                                app_logger.info(f"No missing items processed for instance {instance_name}.")
                        except Exception as e:
                            app_logger.error(f"Error processing missing items for instance {instance_name}: {e}", exc_info=True)

                    if stop_event.is_set(): break # Check if stopped during processing

                    # Process Upgrades
                    if process_upgrades and hunt_upgrade_count > 0:
                        app_logger.info(f"Checking for {hunt_upgrade_count} items needing upgrade in {instance_name}...")
                        try:
                            # Construct the settings dictionary expected by the processing functions
                            merged_settings = {
                                "api_url": api_url,
                                "api_key": api_key,
                                "api_timeout": api_timeout,
                                "monitored_only": monitored_only,
                                "random_upgrades": random_upgrades,
                                "hunt_upgrade_items": hunt_upgrade_count, # Pass the actual count
                                "command_wait_delay": command_wait_delay,
                                "command_wait_attempts": command_wait_attempts,
                                "state_reset_interval_hours": state_reset_interval_hours,
                                "skip_cutoff_unmet": skip_cutoff_unmet # Specific to sonarr upgrade
                                # Add other settings needed by process_upgrades if any
                            }
                            # Pass the merged settings dictionary and the stop check function
                            if process_upgrades(merged_settings, stop_event.is_set):
                                instance_processed_anything = True
                                cycle_processed_anything = True
                            else:
                                app_logger.info(f"No quality upgrades processed for instance {instance_name}.")
                        except Exception as e:
                            app_logger.error(f"Error processing quality upgrades for instance {instance_name}: {e}", exc_info=True)

                else:
                    app_logger.info(f"Download queue size ({download_queue_size}) exceeds minimum ({min_download_queue_size}) for instance {instance_name}. Skipping processing.")

            except Exception as e:
                app_logger.error(f"Error during processing logic for instance {instance_name}: {e}", exc_info=True)
                # Continue to the next instance

            # Log instance completion
            if instance_processed_anything:
                app_logger.info(f"=== {app_type.upper()} instance {instance_name} finished. Processed items. ===")
            else:
                app_logger.info(f"=== {app_type.upper()} instance {instance_name} finished. No items processed. ===")

        # --- Cycle End & Sleep --- #
        calculate_reset_time(app_type) # Pass app_type here if needed by the function

        # Log cycle completion
        if cycle_processed_anything:
            app_logger.info(f"=== {app_type.upper()} cycle finished. Processed items across instances. ===")
        else:
            app_logger.info(f"=== {app_type.upper()} cycle finished. No items processed in any instance. ===")

        # Sleep until the next cycle, checking stop_event periodically
        app_logger.info(f"Sleeping for {sleep_duration} seconds before next cycle...")
        stop_event.wait(sleep_duration) # Use wait() for interruptible sleep

    app_logger.info(f"=== [{app_type.upper()}] Thread stopped ====")

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
    logger.info(f"Received signal {signum}. Initiating shutdown...")
    stop_event.set() # Signal all threads to stop

def shutdown_threads():
    """Wait for all threads to finish."""
    logger.info("Waiting for app threads to finish...")
    active_thread_list = list(app_threads.values())
    for thread in active_thread_list:
        thread.join(timeout=15) # Wait up to 15 seconds per thread
        if thread.is_alive():
            logger.warning(f"Thread {thread.name} did not stop gracefully.")
    logger.info("All app threads stopped.")

def start_huntarr():
    """Main entry point for Huntarr background tasks."""
    logger.info(f"--- Starting Huntarr Background Tasks v{__version__} --- ")

    # Perform initial settings migration if specified (e.g., via env var or arg)
    if os.environ.get("HUNTARR_RUN_MIGRATION", "false").lower() == "true":
        logger.info("Running settings migration from huntarr.json (if found)...")
        settings_manager.migrate_from_huntarr_json()

    # Log initial configuration for all known apps
    for app_name in settings_manager.KNOWN_APP_TYPES: # Corrected attribute name
        try:
            config.log_configuration(app_name)
        except Exception as e:
            logger.error(f"Error logging initial configuration for {app_name}: {e}")

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