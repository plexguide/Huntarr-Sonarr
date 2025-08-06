#!/usr/bin/env python3
"""
Cycle Tracker for Huntarr
Manages cycle timing and sleep data for all apps
Now uses SQLite database instead of JSON files for better performance and reliability.
"""

import datetime
import threading
from typing import Dict, Any, Optional
from src.primary.utils.logger import get_logger
from src.primary.utils.database import get_database

logger = get_logger("cycle_tracker")

# Lock for thread-safe operations
_lock = threading.Lock()

def _get_user_timezone():
    """Get the user's configured timezone"""
    try:
        from src.primary.settings_manager import load_settings
        general_settings = load_settings("general")
        timezone_str = general_settings.get("timezone", "UTC")
        
        import pytz
        return pytz.timezone(timezone_str)
    except Exception as e:
        logger.warning(f"Error getting user timezone, defaulting to UTC: {e}")
        import pytz
        return pytz.UTC

def update_sleep_json(app_type: str, next_cycle_time: datetime.datetime, cyclelock: bool = None) -> None:
    """
    Update the sleep/cycle data in the database
    
    Args:
        app_type: The type of app (sonarr, radarr, etc.)
        next_cycle_time: When the next cycle will begin
        cyclelock: If provided, sets the cycle lock state (True = running, False = waiting)
    """
    try:
        logger.debug(f"Updating sleep data for {app_type}, cyclelock: {cyclelock}")
        
        # Ensure next_cycle_time is timezone-aware and in user's selected timezone
        user_tz = _get_user_timezone()
        
        if next_cycle_time.tzinfo is None:
            # If naive datetime, assume it's in user's timezone
            next_cycle_time = user_tz.localize(next_cycle_time)
        elif next_cycle_time.tzinfo != user_tz:
            # Convert to user's timezone if it's in a different timezone
            next_cycle_time = next_cycle_time.astimezone(user_tz)
        
        # Remove microseconds for clean timestamps
        next_cycle_time = next_cycle_time.replace(microsecond=0)
        
        # Calculate current time in user's timezone for consistency
        now_user_tz = datetime.datetime.now(user_tz).replace(microsecond=0)
        
        # Store in database
        db = get_database()
        
        # Get current data to preserve existing values
        current_data = db.get_sleep_data(app_type)
        
        # Determine cyclelock value
        if cyclelock is None:
            # If not explicitly set, preserve existing value or default to True (cycle starting)
            cyclelock = current_data.get('cycle_lock', True)
        
        # Update the database
        db.set_sleep_data(
            app_type=app_type,
            next_cycle_time=next_cycle_time.isoformat(),
            cycle_lock=cyclelock,
            last_cycle_start=current_data.get('last_cycle_start'),
            last_cycle_end=current_data.get('last_cycle_end')
        )
        
        logger.debug(f"Updated sleep data for {app_type}: next_cycle={next_cycle_time.isoformat()}, cyclelock={cyclelock}")
        
    except Exception as e:
        logger.error(f"Error updating sleep data for {app_type}: {e}")

def update_next_cycle(app_type: str, next_cycle_time: datetime.datetime) -> None:
    """
    Update the next cycle time for an app
    
    Args:
        app_type: The type of app (sonarr, radarr, etc.)
        next_cycle_time: When the next cycle will begin
    """
    with _lock:
        # Get user's timezone for consistent timestamp formatting
        user_tz = _get_user_timezone()
        
        # Ensure next_cycle_time is timezone-aware and in user's timezone
        if next_cycle_time.tzinfo is None:
            # If naive datetime, assume it's in user's timezone
            next_cycle_time = user_tz.localize(next_cycle_time)
        elif next_cycle_time.tzinfo != user_tz:
            # Convert to user's timezone if it's in a different timezone
            next_cycle_time = next_cycle_time.astimezone(user_tz)
        
        # Remove microseconds for clean timestamps
        next_cycle_time = next_cycle_time.replace(microsecond=0)
        
        # Update database
        update_sleep_json(app_type, next_cycle_time)

def get_cycle_status(app_type: Optional[str] = None) -> Dict[str, Any]:
    """
    Get the cycle status for all apps or a specific app
    
    Args:
        app_type: Optional app type to filter for
    
    Returns:
        Dict with cycle status information including cyclelock status
    """
    with _lock:
        try:
            db = get_database()
            
            if app_type:
                # Return data for a specific app
                data = db.get_sleep_data(app_type)
                if data:
                    return {
                        "app": app_type,
                        "next_cycle": data.get("next_cycle_time"),
                        "updated_at": data.get("last_cycle_end") or data.get("last_cycle_start"),
                        "cyclelock": data.get("cycle_lock", True)
                    }
                else:
                    return {
                        "app": app_type,
                        "error": f"No cycle data available for {app_type}"
                    }
            else:
                # Return data for all apps
                all_data = db.get_sleep_data()
                result = {}
                for app, data in all_data.items():
                    result[app] = {
                        "next_cycle": data.get("next_cycle_time"),
                        "updated_at": data.get("last_cycle_end") or data.get("last_cycle_start"),
                        "cyclelock": data.get("cycle_lock", True)
                    }
                return result
        except Exception as e:
            logger.error(f"Error getting cycle status: {e}")
            return {"error": str(e)}

def start_cycle(app_type: str) -> None:
    """
    Mark that a cycle has started for an app (set cyclelock to True)
    
    Args:
        app_type: The app that is starting a cycle
    """
    try:
        db = get_database()
        current_data = db.get_sleep_data(app_type)
        
        # Get current time for last_cycle_start
        user_tz = _get_user_timezone()
        now_user_tz = datetime.datetime.now(user_tz).replace(microsecond=0)
        
        # Update with cycle started
        db.set_sleep_data(
            app_type=app_type,
            next_cycle_time=current_data.get('next_cycle_time'),
            cycle_lock=True,
            last_cycle_start=now_user_tz.isoformat(),
            last_cycle_end=current_data.get('last_cycle_end')
        )
        
        logger.info(f"Started cycle for {app_type} (cyclelock = True)")
    except Exception as e:
        logger.error(f"Error starting cycle for {app_type}: {e}")

def end_cycle(app_type: str, next_cycle_time: datetime.datetime) -> None:
    """
    Mark that a cycle has ended for an app (set cyclelock to False) and update next cycle time
    
    Args:
        app_type: The app that finished its cycle
        next_cycle_time: When the next cycle will begin
    """
    try:
        logger.debug(f"Ending cycle for {app_type}, next cycle at {next_cycle_time.isoformat()}")
        
        db = get_database()
        current_data = db.get_sleep_data(app_type)
        
        # Get current time for last_cycle_end
        user_tz = _get_user_timezone()
        now_user_tz = datetime.datetime.now(user_tz).replace(microsecond=0)
        
        # Ensure next_cycle_time is timezone-aware
        if next_cycle_time.tzinfo is None:
            next_cycle_time = user_tz.localize(next_cycle_time)
        elif next_cycle_time.tzinfo != user_tz:
            next_cycle_time = next_cycle_time.astimezone(user_tz)
        
        next_cycle_time = next_cycle_time.replace(microsecond=0)
        
        # Update with cycle ended
        db.set_sleep_data(
            app_type=app_type,
            next_cycle_time=next_cycle_time.isoformat(),
            cycle_lock=False,
            last_cycle_start=current_data.get('last_cycle_start'),
            last_cycle_end=now_user_tz.isoformat()
        )
        
        logger.debug(f"Ended cycle for {app_type} (cyclelock = False)")
    except Exception as e:
        logger.error(f"Error ending cycle for {app_type}: {e}")

def reset_cycle(app_type: str) -> bool:
    """
    Reset the cycle for a specific app (delete its cycle data and set cyclelock to True)
    
    Args:
        app_type: The app to reset
    
    Returns:
        True if successful, False otherwise
    """
    with _lock:
        try:
            db = get_database()
            
            # Get current time
            user_tz = _get_user_timezone()
            now = datetime.datetime.now(user_tz).replace(microsecond=0)
            future_time = now + datetime.timedelta(minutes=15)  # Default 15 minutes
            
            # Reset the app's data - set cyclelock to True (cycle should start)
            db.set_sleep_data(
                app_type=app_type,
                next_cycle_time=future_time.isoformat(),
                cycle_lock=True,
                last_cycle_start=None,
                last_cycle_end=None
            )
            
            logger.info(f"Reset cycle for {app_type} - set cyclelock to True")
            return True
        except Exception as e:
            logger.error(f"Error resetting cycle for {app_type}: {e}")
            return False


