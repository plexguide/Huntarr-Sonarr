#!/usr/bin/env python3
"""
Settings manager for Huntarr
Handles loading, saving, and providing settings from SQLite database
Supports default configurations for different Arr applications
"""

import os
import json
import pathlib
import logging
import time
from typing import Dict, Any, Optional, List

# Create a simple logger for settings_manager
settings_logger = logging.getLogger("settings_manager")

# Database integration
from src.primary.utils.database import get_database

# Default configs location
DEFAULT_CONFIGS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), 'default_configs'))

# Known app types
KNOWN_APP_TYPES = ["sonarr", "radarr", "lidarr", "readarr", "whisparr", "eros", "swaparr", "general"]

# Add a settings cache with timestamps to avoid excessive database reads
settings_cache = {}  # Format: {app_name: {'timestamp': timestamp, 'data': settings_dict}}
CACHE_TTL = 5  # Cache time-to-live in seconds

def clear_cache(app_name=None):
    """Clear the settings cache for a specific app or all apps."""
    global settings_cache
    if app_name:
        if app_name in settings_cache:
            settings_logger.debug(f"Clearing cache for {app_name}")
            settings_cache.pop(app_name, None)
    else:
        settings_logger.debug("Clearing entire settings cache")
        settings_cache = {}

def get_default_config_path(app_name: str) -> pathlib.Path:
    """Get the path to the default config file for a specific app."""
    return pathlib.Path(DEFAULT_CONFIGS_DIR) / f"{app_name}.json"

def load_default_app_settings(app_name: str) -> Dict[str, Any]:
    """Load default settings for a specific app from its JSON file."""
    default_file = get_default_config_path(app_name)
    if default_file.exists():
        try:
            with open(default_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            settings_logger.error(f"Error loading default settings for {app_name} from {default_file}: {e}")
            return {}
    else:
        settings_logger.warning(f"Default settings file not found for {app_name}: {default_file}")
        return {}

def _ensure_config_exists(app_name: str) -> None:
    """Ensure the config exists for an app in the database."""
    try:
        db = get_database()
        
        if app_name == 'general':
            # Check if general settings exist
            existing_settings = db.get_general_settings()
            if not existing_settings:
                # Load defaults and store in database
                default_settings = load_default_app_settings(app_name)
                if default_settings:
                    db.save_general_settings(default_settings)
                    settings_logger.info(f"Created default general settings in database")
                else:
                    settings_logger.warning(f"No default config found for general settings")
        else:
            # Check if app config exists
            config = db.get_app_config(app_name)
            if config is None:
                # Load defaults and store in database
                default_settings = load_default_app_settings(app_name)
                if default_settings:
                    db.save_app_config(app_name, default_settings)
                    settings_logger.info(f"Created default settings in database for {app_name}")
                else:
                    # Create empty config in database
                    db.save_app_config(app_name, {})
                    settings_logger.warning(f"No default config found for {app_name}. Created empty database entry.")
    except Exception as e:
        settings_logger.error(f"Database error for {app_name}: {e}")
        raise

def load_settings(app_type, use_cache=True):
    """
    Load settings for a specific app type from database
    
    Args:
        app_type: The app type to load settings for
        use_cache: Whether to use the cached settings if available and recent
        
    Returns:
        Dict containing the app settings
    """
    global settings_cache
    
    # Only log unexpected app types that are not 'general'
    if app_type not in KNOWN_APP_TYPES and app_type != "general":
        settings_logger.warning(f"load_settings called with unexpected app_type: {app_type}")
    
    # Check if we have a valid cache entry
    if use_cache and app_type in settings_cache:
        cache_entry = settings_cache[app_type]
        cache_age = time.time() - cache_entry.get('timestamp', 0)
        
        if cache_age < CACHE_TTL:
            settings_logger.debug(f"Using cached settings for {app_type} (age: {cache_age:.1f}s)")
            return cache_entry['data']
        else:
            settings_logger.debug(f"Cache expired for {app_type} (age: {cache_age:.1f}s)")
    
    # No valid cache entry, load from database
    current_settings = {}
    
    try:
        db = get_database()
        
        if app_type == 'general':
            current_settings = db.get_general_settings()
            if not current_settings:
                # Config doesn't exist in database, create it
                _ensure_config_exists(app_type)
                current_settings = db.get_general_settings()
        else:
            current_settings = db.get_app_config(app_type)
            if current_settings is None:
                # Config doesn't exist in database, create it
                _ensure_config_exists(app_type)
                current_settings = db.get_app_config(app_type) or {}
            
        settings_logger.debug(f"Loaded {app_type} settings from database")
        
    except Exception as e:
        settings_logger.error(f"Database error loading {app_type}: {e}")
        raise
    
    # Load defaults to check for missing keys
    default_settings = load_default_app_settings(app_type)
    
    # Add missing keys from defaults without overwriting existing values
    updated = False
    for key, value in default_settings.items():
        if key not in current_settings:
            current_settings[key] = value
            updated = True
    
    # Apply Lidarr migration (artist -> album) for Huntarr 7.5.0+
    if app_type == "lidarr":
        if current_settings.get("hunt_missing_mode") == "artist":
            settings_logger.info("Migrating Lidarr hunt_missing_mode from 'artist' to 'album' (Huntarr 7.5.0+)")
            current_settings["hunt_missing_mode"] = "album"
            updated = True
    
    # If keys were added, save the updated settings
    if updated:
        settings_logger.info(f"Added missing default keys to {app_type} settings")
        save_settings(app_type, current_settings)
    
    # Update cache
    settings_cache[app_type] = {
        'timestamp': time.time(),
        'data': current_settings
    }
        
    return current_settings

def save_settings(app_name: str, settings_data: Dict[str, Any]) -> bool:
    """Save settings for a specific app to database."""
    if app_name not in KNOWN_APP_TYPES:
         settings_logger.error(f"Attempted to save settings for unknown app type: {app_name}")
         return False
    
    # Debug: Log the data being saved, especially for general settings
    if app_name == 'general':
        settings_logger.debug(f"Saving general settings: {settings_data}")
        settings_logger.debug(f"Apprise URLs being saved: {settings_data.get('apprise_urls', 'NOT_FOUND')}")
    
    # Validate and enforce hourly_cap maximum limit of 400
    if 'hourly_cap' in settings_data:
        original_cap = settings_data['hourly_cap']
        if isinstance(original_cap, (int, float)) and original_cap > 400:
            settings_data['hourly_cap'] = 400
            settings_logger.warning(f"Hourly cap for {app_name} was {original_cap}, automatically reduced to maximum allowed value of 400")
    
    # Validate and enforce minimum values (no negative numbers allowed)
    numeric_fields = [
        'hourly_cap', 'hunt_missing_items', 'hunt_upgrade_items',
        'hunt_missing_movies', 'hunt_upgrade_movies', 'hunt_missing_books', 'hunt_upgrade_books'
    ]
    
    # Special validation for sleep_duration (minimum 600 seconds = 10 minutes)
    if 'sleep_duration' in settings_data:
        original_value = settings_data['sleep_duration']
        if isinstance(original_value, (int, float)) and original_value < 600:
            settings_data['sleep_duration'] = 600
            settings_logger.warning(f"Sleep duration for {app_name} was {original_value} seconds, automatically set to minimum allowed value of 600 seconds (10 minutes)")
    
    for field in numeric_fields:
        if field in settings_data:
            original_value = settings_data[field]
            if isinstance(original_value, (int, float)) and original_value < 0:
                settings_data[field] = 0
                settings_logger.warning(f"{field} for {app_name} was {original_value}, automatically set to minimum allowed value of 0")
    
    # Also validate numeric fields in instances array
    if 'instances' in settings_data and isinstance(settings_data['instances'], list):
        for i, instance in enumerate(settings_data['instances']):
            if isinstance(instance, dict):
                # Special validation for sleep_duration in instances
                if 'sleep_duration' in instance:
                    original_value = instance['sleep_duration']
                    if isinstance(original_value, (int, float)) and original_value < 600:
                        instance['sleep_duration'] = 600
                        settings_logger.warning(f"Sleep duration for {app_name} instance {i+1} was {original_value} seconds, automatically set to minimum allowed value of 600 seconds (10 minutes)")
                
                for field in numeric_fields:
                    if field in instance:
                        original_value = instance[field]
                        if isinstance(original_value, (int, float)) and original_value < 0:
                            instance[field] = 0
                            settings_logger.warning(f"{field} for {app_name} instance {i+1} was {original_value}, automatically set to minimum allowed value of 0")
    
    try:
        db = get_database()
        
        if app_name == 'general':
            db.save_general_settings(settings_data)
        else:
            # For app configs, check if instance names have changed and migrate state management data
            if 'instances' in settings_data and isinstance(settings_data['instances'], list):
                _migrate_instance_state_management_if_needed(app_name, settings_data, db)
            
            db.save_app_config(app_name, settings_data)
            
        # Auto-save enabled - no need to log every successful save
        success = True
        
    except Exception as e:
        settings_logger.error(f"Database error saving {app_name}: {e}")
        return False
    
    if success:
        # Clear cache for this app to ensure fresh reads
        clear_cache(app_name)
        
        # If general settings were saved, also clear timezone cache
        if app_name == 'general':
            try:
                from src.primary.utils.timezone_utils import clear_timezone_cache
                clear_timezone_cache()
                settings_logger.debug("Timezone cache cleared")
            except Exception as e:
                settings_logger.warning(f"Could not clear timezone cache: {e}")
    
    return success

def get_setting(app_name: str, key: str, default: Optional[Any] = None) -> Any:
    """Get a specific setting value for an app."""
    settings = load_settings(app_name)
    return settings.get(key, default)

def get_api_url(app_name: str) -> Optional[str]:
    """Get the API URL for a specific app."""
    return get_setting(app_name, "api_url", "")

def get_api_key(app_name: str) -> Optional[str]:
    """Get the API Key for a specific app."""
    return get_setting(app_name, "api_key", "")

def get_all_settings() -> Dict[str, Dict[str, Any]]:
    """Load settings for all known apps."""
    all_settings = {}
    for app_name in KNOWN_APP_TYPES:
        # Only include apps if their config exists or can be created from defaults
        settings = load_settings(app_name)
        if settings: # Only add if settings were successfully loaded
             all_settings[app_name] = settings
    return all_settings

def get_configured_apps() -> List[str]:
    """Return a list of app names that have basic configuration (API URL and Key)."""
    configured = []
    for app_name in KNOWN_APP_TYPES:
        if app_name == 'general':
            continue  # Skip general settings
            
        settings = load_settings(app_name)
        
        # First check if there are valid instances configured (multi-instance mode)
        if "instances" in settings and isinstance(settings["instances"], list) and settings["instances"]:
            for instance in settings["instances"]:
                if instance.get("enabled", True) and instance.get("api_url") and instance.get("api_key"):
                    configured.append(app_name)
                    break  # One valid instance is enough to consider the app configured
            continue  # Skip the single-instance check if we already checked instances
                
        # Fallback to legacy single-instance config
        if settings.get("api_url") and settings.get("api_key"):
            configured.append(app_name)
    
    settings_logger.debug(f"Configured apps: {configured}")
    return configured

def apply_timezone(timezone: str) -> bool:
    """Apply the specified timezone to the application.
    
    Args:
        timezone: The timezone to set (e.g., 'UTC', 'America/New_York')
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Set TZ environment variable (this works in all environments and is sufficient)
        os.environ['TZ'] = timezone
        
        # Force Python to reload time zone information
        try:
            import time
            time.tzset()
        except AttributeError:
            # tzset() is not available on Windows
            pass
        
        # Clear timezone cache to ensure fresh timezone is loaded
        try:
            from src.primary.utils.timezone_utils import clear_timezone_cache
            clear_timezone_cache()
            settings_logger.debug("Timezone cache cleared")
        except Exception as e:
            settings_logger.warning(f"Could not clear timezone cache: {e}")
        
        # Refresh all logger formatters to use the new timezone immediately
        try:
            from src.primary.utils.logger import refresh_timezone_formatters
            refresh_timezone_formatters()
            settings_logger.debug("Logger timezone formatters refreshed")
        except Exception as e:
            settings_logger.warning(f"Could not refresh logger formatters: {e}")
        
        # Note: Database logs now store timestamps in UTC and convert timezone on-the-fly,
        # eliminating the need for formatter refreshing
        
        # Try to update system timezone files only in Docker containers where we have permissions
        # This is optional - the TZ environment variable is sufficient for Python timezone handling
        system_files_updated = False
        try:
            # Only attempt system file changes if we have write access to /etc
            if os.access("/etc", os.W_OK):
                zoneinfo_path = f"/usr/share/zoneinfo/{timezone}"
                if os.path.exists(zoneinfo_path):
                    # Remove existing symlink if it exists
                    if os.path.exists("/etc/localtime"):
                        os.remove("/etc/localtime")
                    
                    # Create new symlink
                    os.symlink(zoneinfo_path, "/etc/localtime")
                    
                    # Also update /etc/timezone file
                    with open("/etc/timezone", "w") as f:
                        f.write(f"{timezone}\n")
                    
                    system_files_updated = True
                    settings_logger.debug(f"System timezone files updated to {timezone}")
                else:
                    settings_logger.debug(f"Timezone file not found: {zoneinfo_path}, using TZ environment variable only")
            else:
                settings_logger.debug(f"No write access to /etc, using TZ environment variable only for {timezone}")
        except Exception as e:
            # Silently handle any errors with system files - TZ env var is sufficient
            settings_logger.debug(f"Could not update system timezone files: {str(e)}, using TZ environment variable only")
        
        # Always return True - TZ environment variable is sufficient for timezone handling
        if system_files_updated:
            settings_logger.info(f"Timezone fully applied to {timezone} (system files + TZ env var)")
        else:
            settings_logger.info(f"Timezone applied to {timezone} (TZ environment variable)")
        
        return True
        
    except Exception as e:
        settings_logger.error(f"Critical error setting timezone: {str(e)}")
        return False

def validate_timezone(timezone_str: str) -> bool:
    """
    Validate if a timezone string is valid using pytz.
    
    Args:
        timezone_str: The timezone string to validate (e.g., 'Europe/Bucharest')
        
    Returns:
        bool: True if valid, False otherwise
    """
    if not timezone_str:
        return False
        
    try:
        import pytz
        pytz.timezone(timezone_str)
        return True
    except pytz.UnknownTimeZoneError:
        return False
    except Exception as e:
        settings_logger.warning(f"Error validating timezone {timezone_str}: {e}")
        return False

def get_safe_timezone(timezone_str: str, fallback: str = "UTC") -> str:
    """
    Get a safe timezone string, falling back to a default if invalid.
    
    Args:
        timezone_str: The timezone string to validate
        fallback: The fallback timezone if validation fails (default: UTC)
        
    Returns:
        str: A valid timezone string
    """
    if validate_timezone(timezone_str):
        return timezone_str
    
    if timezone_str != fallback:
        settings_logger.warning(f"Invalid timezone '{timezone_str}', falling back to '{fallback}'")
    
    # Ensure fallback is also valid
    if validate_timezone(fallback):
        return fallback
    
    # Ultimate fallback to UTC if even the fallback is invalid
    settings_logger.error(f"Fallback timezone '{fallback}' is also invalid, using UTC")
    return "UTC"

def initialize_timezone_from_env():
    """Initialize timezone setting from TZ environment variable if not already set."""
    try:
        # Get the TZ environment variable
        tz_env = os.environ.get('TZ')
        if not tz_env:
            settings_logger.info("No TZ environment variable found, using default UTC")
            return
        
        # Load current general settings
        general_settings = load_settings("general")
        current_timezone = general_settings.get("timezone")
        
        # If timezone is not set in settings, initialize it from TZ environment variable
        if not current_timezone or current_timezone == "UTC":
            settings_logger.info(f"Initializing timezone from TZ environment variable: {tz_env}")
            
            # Use safe timezone validation
            safe_timezone = get_safe_timezone(tz_env)
            
            if safe_timezone == tz_env:
                settings_logger.info(f"TZ environment variable '{tz_env}' is valid")
            else:
                settings_logger.warning(f"TZ environment variable '{tz_env}' is invalid, using '{safe_timezone}' instead")
            
            # Update the settings with the safe timezone
            general_settings["timezone"] = safe_timezone
            save_settings("general", general_settings)
            
            # Apply the timezone to the system
            apply_timezone(safe_timezone)
            
            settings_logger.info(f"Successfully initialized timezone to {safe_timezone}")
        else:
            settings_logger.info(f"Timezone already set in settings: {current_timezone}")
            
            # Validate the existing timezone setting
            safe_timezone = get_safe_timezone(current_timezone)
            if safe_timezone != current_timezone:
                settings_logger.warning(f"Existing timezone setting '{current_timezone}' is invalid, updating to '{safe_timezone}'")
                general_settings["timezone"] = safe_timezone
                save_settings("general", general_settings)
                apply_timezone(safe_timezone)
            
    except Exception as e:
        settings_logger.error(f"Error initializing timezone from environment: {e}")

def initialize_base_url_from_env():
    """Initialize base_url setting from BASE_URL environment variable if not already set."""
    try:
        # Get the BASE_URL environment variable
        base_url_env = os.environ.get('BASE_URL')
        if not base_url_env:
            settings_logger.info("No BASE_URL environment variable found, using default (no subpath)")
            return

        # Clean up the environment variable value
        base_url_env = base_url_env.strip()
        
        # Ensure it starts with / if not empty
        if base_url_env and not base_url_env.startswith('/'):
            base_url_env = f'/{base_url_env}'
        
        # Remove trailing slash if present (except for root)
        if base_url_env and base_url_env != '/' and base_url_env.endswith('/'):
            base_url_env = base_url_env.rstrip('/')

        # Load current general settings
        general_settings = load_settings("general")
        current_base_url = general_settings.get("base_url", "").strip()
        
        # If base_url is not set in settings, initialize it from BASE_URL environment variable
        if not current_base_url:
            settings_logger.info(f"Initializing base_url from BASE_URL environment variable: {base_url_env}")
           
            # Update the settings with the base_url
            general_settings["base_url"] = base_url_env
            save_settings("general", general_settings)
            
            # Clear cache to ensure new settings are loaded
            clear_cache("general")
            
            settings_logger.info(f"Successfully initialized base_url to {base_url_env}")
        else:
            settings_logger.debug(f"Base URL already configured in settings: {current_base_url}, not overriding with environment variable")
            
    except Exception as e:
        settings_logger.error(f"Error initializing base_url from environment: {e}")

# Add a list of known advanced settings for clarity and documentation
ADVANCED_SETTINGS = [
    "api_timeout", 
    "command_wait_delay", 
    "command_wait_attempts", 
    "minimum_download_queue_size",
    "log_refresh_interval_seconds",
    "stateful_management_hours",
    "hourly_cap",
    "ssl_verify",  # Add SSL verification setting
    "base_url"     # Add base URL setting
]

def get_advanced_setting(setting_name, default_value=None):
    """
    Get an advanced setting from general settings.
    
    Advanced settings are now centralized in general settings and no longer stored
    in individual app settings files. This function provides a consistent way to
    access these settings from anywhere in the codebase.
    
    Args:
        setting_name: The name of the advanced setting to retrieve
        default_value: The default value to return if the setting is not found
        
    Returns:
        The value of the advanced setting, or default_value if not found
    """
    if setting_name not in ADVANCED_SETTINGS:
        settings_logger.warning(f"get_advanced_setting called with unknown setting: {setting_name}")
    
    general_settings = load_settings("general")
    return general_settings.get(setting_name, default_value)

def get_ssl_verify_setting():
    """
    Get the SSL verification setting from general settings.
    
    Returns:
        bool: True if SSL verification is enabled, False otherwise
    """
    return get_advanced_setting("ssl_verify", True)  # Default to True for security

def get_custom_tag(app_name: str, tag_type: str, default: str) -> str:
    """
    Get a custom tag for a specific app and tag type.
    
    Args:
        app_name: The name of the app (e.g., 'sonarr', 'radarr')
        tag_type: The type of tag (e.g., 'missing', 'upgrade')
        default: The default tag to return if not found
        
    Returns:
        str: The custom tag or the default if not found
    """
    settings = load_settings(app_name)
    custom_tags = settings.get("custom_tags", {})
    return custom_tags.get(tag_type, default)

def initialize_database():
    """Initialize database with default configurations if needed"""
    from .utils.database import get_database
    from pathlib import Path
    
    # Get database instance and ensure it exists
    db = get_database()
    db.ensure_database_exists()
    
    # Initialize database with default configurations
    defaults_dir = Path(__file__).parent / "default_configs"
    db.initialize_from_defaults(defaults_dir)
    
    # Start database maintenance scheduler for integrity monitoring
    try:
        db.schedule_maintenance()
        settings_logger.info("Database maintenance scheduler initialized")
    except Exception as e:
        settings_logger.warning(f"Failed to start database maintenance scheduler: {e}")
    
    settings_logger.info("Database initialization completed successfully")

def _migrate_instance_state_management_if_needed(app_name: str, new_settings_data: Dict[str, Any], db) -> None:
    """
    Check if instance names have changed and migrate state management data if needed.
    
    Args:
        app_name: The app type (e.g., 'sonarr', 'radarr')
        new_settings_data: The new settings data being saved
        db: Database instance
    """
    try:
        # Get current settings from database to compare
        current_settings = db.get_app_config(app_name)
        if not current_settings or 'instances' not in current_settings:
            # No existing instances to migrate from
            return
        
        current_instances = current_settings.get('instances', [])
        new_instances = new_settings_data.get('instances', [])
        
        if not isinstance(current_instances, list) or not isinstance(new_instances, list):
            return
        
        # Create mappings of instances by their position/index and identify name changes
        for i, (current_instance, new_instance) in enumerate(zip(current_instances, new_instances)):
            if not isinstance(current_instance, dict) or not isinstance(new_instance, dict):
                continue
            
            current_name = current_instance.get('name', f'Instance {i+1}')
            new_name = new_instance.get('name', f'Instance {i+1}')
            
            # If name has changed, migrate the state management data
            if current_name != new_name and current_name and new_name:
                settings_logger.info(f"Detected instance name change for {app_name} instance {i+1}: '{current_name}' -> '{new_name}'")
                
                # Attempt to migrate state management data
                migration_success = db.migrate_instance_state_management(app_name, current_name, new_name)
                
                if migration_success:
                    settings_logger.info(f"Successfully migrated state management data for {app_name} from '{current_name}' to '{new_name}'")
                else:
                    settings_logger.warning(f"Failed to migrate state management data for {app_name} from '{current_name}' to '{new_name}' - user may need to reset state management")
        
        # Handle case where instances were removed (we don't migrate in this case, just log)
        if len(current_instances) > len(new_instances):
            removed_count = len(current_instances) - len(new_instances)
            settings_logger.info(f"Detected {removed_count} removed instances for {app_name} - state management data for removed instances will remain in database")
            
    except Exception as e:
        settings_logger.error(f"Error checking for instance name changes in {app_name}: {e}")
        # Don't fail the save operation if migration checking fails



# Example usage (for testing purposes, remove later)
if __name__ == "__main__":
    settings_logger.info(f"Known app types: {KNOWN_APP_TYPES}")
    
    # Ensure defaults are copied if needed
    for app in KNOWN_APP_TYPES:
        _ensure_config_exists(app)

    # Test loading Sonarr settings
    sonarr_settings = load_settings("sonarr")
    settings_logger.info(f"Loaded Sonarr settings: {json.dumps(sonarr_settings, indent=2)}")

    # Test getting a specific setting
    sonarr_sleep = get_setting("sonarr", "sleep_duration", 999)
    settings_logger.info(f"Sonarr sleep duration: {sonarr_sleep}")

    # Test saving updated settings (example)
    if sonarr_settings:
        sonarr_settings["sleep_duration"] = 850
        save_settings("sonarr", sonarr_settings)
        reloaded_sonarr_settings = load_settings("sonarr")
        settings_logger.info(f"Reloaded Sonarr settings after save: {json.dumps(reloaded_sonarr_settings, indent=2)}")


    # Test getting all settings
    all_app_settings = get_all_settings()
    settings_logger.info(f"All loaded settings: {json.dumps(all_app_settings, indent=2)}")

    # Test getting configured apps
    configured_list = get_configured_apps()
    settings_logger.debug(f"Configured apps: {configured_list}")