#!/usr/bin/env python3
"""
Stateful Manager for Huntarr
Handles storing and retrieving processed media IDs to prevent reprocessing
Now uses SQLite database instead of JSON files for better performance and reliability.
"""

import time
import datetime
import logging
from typing import Dict, Any, List, Optional, Set

# Import the Huntarr logger system
from src.primary.utils.logger import get_logger

# Create logger for stateful_manager using Huntarr logger system
stateful_logger = get_logger("huntarr")  # Use main huntarr logger for now

# Constants
DEFAULT_HOURS = 168  # Default 7 days (168 hours)

# App types
APP_TYPES = ["sonarr", "radarr", "lidarr", "readarr", "whisparr", "eros"]

# Import database
from src.primary.utils.database import get_database
from src.primary.settings_manager import get_advanced_setting

def initialize_lock_file() -> None:
    """Initialize the lock file with the current timestamp if it doesn't exist."""
    db = get_database()
    lock_info = db.get_stateful_lock_info()
    
    if not lock_info:
        try:
            current_time = int(time.time())
            # Get the expiration hours setting
            expiration_hours = get_advanced_setting("stateful_management_hours", DEFAULT_HOURS)
            
            expires_at = current_time + (expiration_hours * 3600)
            
            db.set_stateful_lock_info(current_time, expires_at)
            stateful_logger.info(f"Initialized stateful lock in database with expiration in {expiration_hours} hours")
        except Exception as e:
            stateful_logger.error(f"Error initializing stateful lock: {e}")
            
def get_lock_info() -> Dict[str, Any]:
    """Get the current lock information."""
    initialize_lock_file()
    db = get_database()
    
    try:
        lock_info = db.get_stateful_lock_info()
        
        # Validate the structure and ensure required fields exist
        if not lock_info or "created_at" not in lock_info:
            current_time = int(time.time())
            expiration_hours = get_advanced_setting("stateful_management_hours", DEFAULT_HOURS)
            expires_at = current_time + (expiration_hours * 3600)
            
            lock_info = {
                "created_at": current_time,
                "expires_at": expires_at
            }
            db.set_stateful_lock_info(current_time, expires_at)
            
        if "expires_at" not in lock_info or lock_info["expires_at"] is None:
            # Recalculate expiration if missing
            expiration_hours = get_advanced_setting("stateful_management_hours", DEFAULT_HOURS)
            expires_at = lock_info["created_at"] + (expiration_hours * 3600)
            lock_info["expires_at"] = expires_at
            
            # Save the updated info
            db.set_stateful_lock_info(lock_info["created_at"], expires_at)
            
        return lock_info
    except Exception as e:
        stateful_logger.error(f"Error reading lock info from database: {e}")
        # Return default values if there's an error
        current_time = int(time.time())
        expiration_hours = get_advanced_setting("stateful_management_hours", DEFAULT_HOURS)
        expires_at = current_time + (expiration_hours * 3600)
        
        return {
            "created_at": current_time,
            "expires_at": expires_at
        }

def update_lock_expiration(hours: int = None) -> bool:
    """Update the lock expiration based on the hours setting."""
    if hours is None:
        expiration_hours = get_advanced_setting("stateful_management_hours", DEFAULT_HOURS)
    else:
        expiration_hours = hours
    
    lock_info = get_lock_info()
    created_at = lock_info.get("created_at", int(time.time()))
    expires_at = created_at + (expiration_hours * 3600)
    
    try:
        db = get_database()
        db.set_stateful_lock_info(created_at, expires_at)
        stateful_logger.info(f"Updated lock expiration to {datetime.datetime.fromtimestamp(expires_at)}")
        return True
    except Exception as e:
        stateful_logger.error(f"Error updating lock expiration: {e}")
        return False

def reset_stateful_management() -> bool:
    """
    Reset the stateful management system.

    This involves:
    1. Creating a new lock file with the current timestamp and a calculated expiration time
       based on the 'stateful_management_hours' setting.
    2. Deleting all stored processed ID data from the database.

    Returns:
        bool: True if the reset was successful, False otherwise.
    """
    try:
        db = get_database()
        
        # Get the expiration hours setting BEFORE writing the lock info
        expiration_hours = get_advanced_setting("stateful_management_hours", DEFAULT_HOURS)
        
        # Create new lock info with calculated expiration
        current_time = int(time.time())
        expires_at = current_time + (expiration_hours * 3600)
        
        # Clear all stateful data and set new lock info
        db.clear_all_stateful_data()
        db.set_stateful_lock_info(current_time, expires_at)
        
        stateful_logger.info(f"Successfully reset stateful management. New expiration: {datetime.datetime.fromtimestamp(expires_at)}")
        return True
    except Exception as e:
        stateful_logger.error(f"Error resetting stateful management: {e}")
        return False

def check_expiration() -> bool:
    """
    Check if the stateful management has expired.
    
    Returns:
        bool: True if expired, False otherwise
    """
    lock_info = get_lock_info()
    expires_at = lock_info.get("expires_at")
    
    # If expires_at is None, update it based on settings
    if expires_at is None:
        update_lock_expiration()
        lock_info = get_lock_info()
        expires_at = lock_info.get("expires_at")
    
    current_time = int(time.time())
    
    if current_time >= expires_at:
        stateful_logger.info("Stateful management has expired, resetting...")
        reset_stateful_management()
        return True
    
    return False

def get_processed_ids(app_type: str, instance_name: str) -> Set[str]:
    """
    Get the set of processed media IDs for a specific app instance.
    
    Args:
        app_type: The type of app (sonarr, radarr, etc.)
        instance_name: The name of the instance
        
    Returns:
        Set[str]: Set of processed media IDs
    """
    if app_type not in APP_TYPES:
        stateful_logger.warning(f"Unknown app type: {app_type}")
        return set()
    
    try:
        db = get_database()
        processed_ids_set = db.get_processed_ids(app_type, instance_name)
        stateful_logger.debug(f"[get_processed_ids] Read {len(processed_ids_set)} IDs from database for {app_type}/{instance_name}: {processed_ids_set}")
        return processed_ids_set
    except Exception as e:
        stateful_logger.error(f"Error reading processed IDs for {instance_name} from database: {e}")
        return set()

def add_processed_id(app_type: str, instance_name: str, media_id: str) -> bool:
    """
    Add a media ID to the processed list for a specific app instance.
    
    Args:
        app_type: The type of app (sonarr, radarr, etc.)
        instance_name: The name of the instance
        media_id: The ID of the processed media
        
    Returns:
        bool: True if successful, False otherwise (or if state management is disabled)
    """
    if app_type not in APP_TYPES:
        stateful_logger.warning(f"Unknown app type: {app_type}")
        return False
    
    try:
        # First check if state management is enabled for this instance
        instance_hours = 168  # Default
        instance_mode = "custom"
        
        try:
            from src.primary.settings_manager import load_settings
            settings = load_settings(app_type)
            
            if settings and 'instances' in settings:
                # Find the matching instance
                for instance in settings['instances']:
                    if instance.get('name') == instance_name:
                        instance_mode = instance.get('state_management_mode', 'custom')
                        instance_hours = instance.get('state_management_hours', 168)
                        
                        # If state management is disabled for this instance, don't add to processed list
                        if instance_mode == 'disabled':
                            stateful_logger.debug(f"State management disabled for {app_type}/{instance_name}, not adding item {media_id} to processed list")
                            return True  # Return True to indicate "success" (no error), but item wasn't actually added
                        break
        except Exception as e:
            stateful_logger.warning(f"Could not check state management mode for {app_type}/{instance_name}: {e}")
            # Fall back to adding anyway if we can't determine the mode
        
        db = get_database()
        
        # Initialize per-instance state management if not already done
        db.initialize_instance_state_management(app_type, instance_name, instance_hours)
        
        # Check if this instance's state has expired
        if db.check_instance_expiration(app_type, instance_name):
            stateful_logger.info(f"State management expired for {app_type}/{instance_name}, resetting before adding new ID...")
            db.reset_instance_state_management(app_type, instance_name, instance_hours)
        
        # Check if already processed
        if db.is_processed(app_type, instance_name, media_id):
            stateful_logger.debug(f"[add_processed_id] ID {media_id} already in database for {app_type}/{instance_name}")
            return True
        
        # Add the new ID
        success = db.add_processed_id(app_type, instance_name, media_id)
        if success:
            stateful_logger.debug(f"[add_processed_id] Added ID {media_id} to database for {app_type}/{instance_name}")
        
        return success
    except Exception as e:
        stateful_logger.error(f"Error adding media ID {media_id} to database: {e}")
        return False

def is_processed(app_type: str, instance_name: str, media_id: str) -> bool:
    """
    Check if a media ID has already been processed.
    
    Args:
        app_type: The type of app (sonarr, radarr, etc.)
        instance_name: The name of the instance
        media_id: The ID of the media to check
        
    Returns:
        bool: True if already processed, False otherwise (or if state management is disabled)
    """
    try:
        # First check if state management is enabled for this instance
        instance_hours = 168  # Default
        instance_mode = "custom"
        
        try:
            from src.primary.settings_manager import load_settings
            settings = load_settings(app_type)
            
            if settings and 'instances' in settings:
                # Find the matching instance
                for instance in settings['instances']:
                    if instance.get('name') == instance_name:
                        instance_mode = instance.get('state_management_mode', 'custom')
                        instance_hours = instance.get('state_management_hours', 168)
                        
                        # If state management is disabled for this instance, always return False (not processed)
                        if instance_mode == 'disabled':
                            stateful_logger.debug(f"State management disabled for {app_type}/{instance_name}, treating item {media_id} as unprocessed")
                            return False
                        break
        except Exception as e:
            stateful_logger.warning(f"Could not check state management mode for {app_type}/{instance_name}: {e}")
            # Fall back to checking anyway if we can't determine the mode
        
        db = get_database()
        
        # Initialize per-instance state management if not already done
        db.initialize_instance_state_management(app_type, instance_name, instance_hours)
        
        # Check if this instance's state has expired
        if db.check_instance_expiration(app_type, instance_name):
            stateful_logger.info(f"State management expired for {app_type}/{instance_name}, resetting...")
            db.reset_instance_state_management(app_type, instance_name, instance_hours)
            # After reset, item is not processed
            return False
        
        # Converting media_id to string since some callers might pass an integer
        media_id_str = str(media_id)
        is_in_db = db.is_processed(app_type, instance_name, media_id_str)
        
        # Get total count for logging
        processed_ids = db.get_processed_ids(app_type, instance_name)
        total_count = len(processed_ids)
        
        stateful_logger.debug(f"is_processed check: {app_type}/{instance_name}, ID:{media_id_str}, Found:{is_in_db}, Total IDs:{total_count}")
        
        return is_in_db
    except Exception as e:
        stateful_logger.error(f"Error checking if processed for {app_type}/{instance_name}, ID:{media_id}: {e}")
        return False

def get_stateful_management_info() -> Dict[str, Any]:
    """Get information about the stateful management system."""
    lock_info = get_lock_info()
    created_at_ts = lock_info.get("created_at")
    expires_at_ts = lock_info.get("expires_at")
    
    # Get the interval setting
    expiration_hours = get_advanced_setting("stateful_management_hours", DEFAULT_HOURS)

    return {
        "created_at_ts": created_at_ts,
        "expires_at_ts": expires_at_ts,
        "interval_hours": expiration_hours
    }

def get_state_management_summary(app_type: str, instance_name: str, instance_hours: int = None) -> Dict[str, Any]:
    """
    Get a summary of stateful management for an app instance.
    
    Args:
        app_type: The type of app (sonarr, radarr, etc.)
        instance_name: The name of the instance
        instance_hours: Custom hours for this instance (if provided)
        
    Returns:
        Dict containing processed count, next reset time, and other useful info
    """
    try:
        db = get_database()
        
        # Use per-instance hours if provided, otherwise fall back to global setting
        if instance_hours is not None:
            expiration_hours = instance_hours
        else:
            expiration_hours = get_advanced_setting("stateful_management_hours", DEFAULT_HOURS)
        
        # Initialize per-instance state management if not already done
        db.initialize_instance_state_management(app_type, instance_name, expiration_hours)
        
        # Get processed IDs count
        processed_ids = get_processed_ids(app_type, instance_name)
        processed_count = len(processed_ids)
        
        # Get per-instance lock info for accurate next reset time
        lock_info = db.get_instance_lock_info(app_type, instance_name)
        if lock_info and lock_info.get("expires_at"):
            import datetime
            expires_at = lock_info["expires_at"]
            # Convert to user timezone for display
            user_tz = _get_user_timezone()
            utc_time = datetime.datetime.fromtimestamp(expires_at, tz=datetime.timezone.utc)
            local_time = utc_time.astimezone(user_tz)
            next_reset_time = local_time.strftime('%Y-%m-%d %H:%M:%S')
        else:
            # This should not happen since initialize_instance_state_management was called above
            stateful_logger.warning(f"No lock info found for {app_type}/{instance_name} after initialization")
            next_reset_time = None
        
        return {
            "processed_count": processed_count,
            "next_reset_time": next_reset_time,
            "expiration_hours": expiration_hours,
            "has_processed_items": processed_count > 0
        }
    except Exception as e:
        stateful_logger.error(f"Error getting state management summary for {app_type}/{instance_name}: {e}")
        return {
            "processed_count": 0,
            "next_reset_time": None,
            "expiration_hours": instance_hours or DEFAULT_HOURS,
            "has_processed_items": False
        }

def _get_user_timezone():
    """Get the user's selected timezone from general settings"""
    try:
        from src.primary.utils.timezone_utils import get_user_timezone
        return get_user_timezone()
    except Exception as e:
        stateful_logger.warning(f"Could not get user timezone, defaulting to UTC: {e}")
        import pytz
        return pytz.UTC



def get_next_reset_time() -> Optional[str]:
    """
    Get the next state management reset time as a formatted string in user's timezone.
    
    Returns:
        Formatted reset time string or None if unable to calculate
    """
    try:
        # Import here to avoid circular imports
        from src.primary.state import get_last_reset_time
        
        # Get user's timezone
        user_tz = _get_user_timezone()
        
        # Get reset interval in hours
        reset_interval = get_advanced_setting("stateful_management_hours", DEFAULT_HOURS)
        
        # Get last reset time and calculate next reset (use 'sonarr' as default for global state)
        last_reset = get_last_reset_time('sonarr')  # Pass app_type parameter
        
        # Check if last_reset is valid (not Unix epoch or too old)
        unix_epoch = datetime.datetime(1970, 1, 1)
        one_year_ago = datetime.datetime.now() - datetime.timedelta(days=365)
        
        if last_reset and last_reset > one_year_ago and last_reset != unix_epoch:
            # Convert last reset to user timezone (assuming it was stored in UTC)
            import pytz
            last_reset_utc = pytz.UTC.localize(last_reset) if last_reset.tzinfo is None else last_reset
            next_reset_user_tz = last_reset_utc.astimezone(user_tz) + datetime.timedelta(hours=reset_interval)
            return next_reset_user_tz.strftime('%Y-%m-%d %H:%M:%S')
        else:
            # If no valid last reset time, calculate from now
            stateful_logger.info("No valid last reset time found, calculating next reset from current time")
            now_user_tz = datetime.datetime.now(user_tz)
            next_reset = now_user_tz + datetime.timedelta(hours=reset_interval)
            return next_reset.strftime('%Y-%m-%d %H:%M:%S')
    except Exception as e:
        stateful_logger.error(f"Error calculating next reset time: {e}")
        return None

def get_next_reset_time_for_instance(instance_hours: int, app_type: str = None) -> Optional[str]:
    """
    Get the next state management reset time for a specific instance based on custom hours.
    
    Args:
        instance_hours: Custom reset interval hours for this instance
        app_type: The app type for getting last reset time (optional, defaults to 'sonarr')
        
    Returns:
        Formatted reset time string or None if unable to calculate
    """
    try:
        # Import here to avoid circular imports
        from src.primary.state import get_last_reset_time
        
        # Get user's timezone
        user_tz = _get_user_timezone()
        
        # Default to 'sonarr' if no app_type provided (for backward compatibility)
        if app_type is None:
            app_type = 'sonarr'
        
        # Get last reset time and calculate next reset
        last_reset = get_last_reset_time(app_type)  # Pass app_type parameter
        
        # Check if last_reset is valid (not Unix epoch or too old)
        unix_epoch = datetime.datetime(1970, 1, 1)
        one_year_ago = datetime.datetime.now() - datetime.timedelta(days=365)
        
        if last_reset and last_reset > one_year_ago and last_reset != unix_epoch:
            # Convert last reset to user timezone (assuming it was stored in UTC)
            import pytz
            last_reset_utc = pytz.UTC.localize(last_reset) if last_reset.tzinfo is None else last_reset
            next_reset_user_tz = last_reset_utc.astimezone(user_tz) + datetime.timedelta(hours=instance_hours)
            return next_reset_user_tz.strftime('%Y-%m-%d %H:%M:%S')
        else:
            # If no valid last reset time, calculate from now
            stateful_logger.info(f"No valid last reset time found for {app_type}, calculating next reset from current time using {instance_hours} hours")
            now_user_tz = datetime.datetime.now(user_tz)
            next_reset = now_user_tz + datetime.timedelta(hours=instance_hours)
            return next_reset.strftime('%Y-%m-%d %H:%M:%S')
    except Exception as e:
        stateful_logger.error(f"Error calculating next reset time for instance ({instance_hours} hours): {e}")
        return None

def initialize_stateful_system():
    """Perform a complete initialization of the stateful management system."""
    stateful_logger.info("Initializing stateful management system")
    
    # Initialize the database and lock info
    try:
        initialize_lock_file()
        # Update expiration time
        expiration_hours = get_advanced_setting("stateful_management_hours", DEFAULT_HOURS)
        update_lock_expiration(expiration_hours)
        stateful_logger.info(f"Stateful lock initialized in database with {expiration_hours} hour expiration")
    except Exception as e:
        stateful_logger.error(f"Failed to initialize stateful lock: {e}")
    
    # Check for existing processed IDs in database
    try:
        db = get_database()
        total_ids = 0
        for app_type in APP_TYPES:
            # Get a sample of instance names to count processed IDs
            # This is a rough count since we don't track instance names separately
            processed_ids = db.get_processed_ids(app_type, "Default")  # Check default instance
            total_ids += len(processed_ids)
        
        if total_ids > 0:
            stateful_logger.info(f"Found {total_ids} existing processed IDs in database")
        else:
            stateful_logger.info("No existing processed IDs found in database")
    except Exception as e:
        stateful_logger.error(f"Failed to check for existing processed IDs: {e}")
    
    stateful_logger.info("Stateful management system initialization complete")

# Initialize the stateful system on module import
initialize_stateful_system()
