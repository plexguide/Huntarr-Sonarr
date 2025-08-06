#!/usr/bin/env python3
"""
Logging configuration for Huntarr
Supports separate log files for each application type
"""

import logging
import sys
import os
import pathlib
import time
from typing import Dict, Optional

# Use the centralized path configuration
from src.primary.utils.config_paths import LOG_DIR

# Log directory is already created by config_paths module
# LOG_DIR already exists as pathlib.Path object pointing to the correct location

# Default log file for general messages
MAIN_LOG_FILE = LOG_DIR / "huntarr.log"

# App-specific log files
APP_LOG_FILES = {
    "sonarr": LOG_DIR / "sonarr.log", # Updated filename
    "radarr": LOG_DIR / "radarr.log", # Updated filename
    "lidarr": LOG_DIR / "lidarr.log", # Updated filename
    "readarr": LOG_DIR / "readarr.log", # Updated filename
    "whisparr": LOG_DIR / "whisparr.log", # Added Whisparr
    "eros": LOG_DIR / "eros.log",      # Added Eros for Whisparr V3
    "swaparr": LOG_DIR / "swaparr.log",  # Added Swaparr for stalled download management
}

# Global logger instances
logger: Optional[logging.Logger] = None
app_loggers: Dict[str, logging.Logger] = {}

# Custom formatter that uses user's selected timezone instead of UTC
class LocalTimeFormatter(logging.Formatter):
    """Custom formatter that uses user's selected timezone for log timestamps"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.converter = time.localtime  # Still use local time as fallback
    
    def _get_user_timezone(self):
        """Get the user's selected timezone from general settings"""
        try:
            from src.primary.utils.timezone_utils import get_user_timezone
            return get_user_timezone()
        except Exception:
            # Final fallback if timezone_utils can't be imported
            import pytz
            return pytz.UTC
    
    def formatTime(self, record, datefmt=None):
        try:
            # Try to use user's selected timezone
            user_tz = self._get_user_timezone()
            import datetime
            ct = datetime.datetime.fromtimestamp(record.created, tz=user_tz)
            
            if datefmt:
                s = ct.strftime(datefmt)
            else:
                # Use timezone-aware format
                s = ct.strftime("%Y-%m-%d %H:%M:%S")
                
            
            return s
        except Exception:
            # Fallback to system local time if timezone handling fails
            ct = self.converter(record.created)
            if datefmt:
                s = time.strftime(datefmt, ct)
            else:
                s = time.strftime("%Y-%m-%d %H:%M:%S", ct)
                
                
            return s

def get_log_level():
    """Get the logging level from LOG_LEVEL environment variable with fallback to INFO."""
    # Check LOG_LEVEL environment variable
    log_level_str = os.environ.get('LOG_LEVEL', '').upper()
    if log_level_str in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
        return getattr(logging, log_level_str)
        
    # Default to INFO level
    return logging.INFO

def configure_root_logger():
    """Configure root logger to respect LOG_LEVEL environment variable."""
    root_logger = logging.getLogger()
    log_level = get_log_level()
    root_logger.setLevel(log_level)
    
    # Configure all existing handlers to use the new level
    for handler in root_logger.handlers:
        handler.setLevel(log_level)

def setup_main_logger():
    """Set up the main Huntarr logger."""
    global logger
    log_name = "huntarr"
    log_file = MAIN_LOG_FILE

    # Get log level from environment with INFO as default
    use_log_level = get_log_level()

    # Get or create the main logger instance
    current_logger = logging.getLogger(log_name)

    # Reset handlers to avoid duplicates
    current_logger.handlers.clear()
    current_logger.setLevel(use_log_level)
    
    # Prevent propagation to root logger to avoid duplicate messages
    current_logger.propagate = False

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(use_log_level)

    # Create file handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(use_log_level)

    # Set format for the main logger
    log_format = "%(asctime)s - huntarr - %(levelname)s - %(message)s"
    formatter = LocalTimeFormatter(log_format, datefmt="%Y-%m-%d %H:%M:%S")
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)

    # Add handlers to the main logger
    current_logger.addHandler(console_handler)
    current_logger.addHandler(file_handler)

    current_logger.debug("Debug logging enabled for main logger")

    logger = current_logger # Assign to the global variable
    
    # Configure root logger to ensure all loggers respect LOG_LEVEL
    configure_root_logger()
    
    return current_logger

def get_logger(app_type: str) -> logging.Logger:
    """
    Get or create a logger for a specific app type.
    
    Args:
        app_type: The app type (e.g., 'sonarr', 'radarr').
        
    Returns:
        A logger specific to the app type, or the main logger if app_type is invalid.
    """
    if app_type not in APP_LOG_FILES:
        # Fallback to main logger if the app type is not recognized
        global logger
        if logger is None:
            # Ensure main logger is initialized if accessed before module-level setup
            setup_main_logger()
        # We checked logger is not None, so we can assert its type
        assert logger is not None
        return logger

    log_name = f"huntarr.{app_type}"
    if log_name in app_loggers:
        # Return cached logger instance
        return app_loggers[log_name]
    
    # If not cached, set up a new logger for this app type
    app_logger = logging.getLogger(log_name)
    
    # Prevent propagation to the main 'huntarr' logger or root logger
    app_logger.propagate = False
    
    # Get log level from environment with INFO as default
    log_level = get_log_level()
        
    app_logger.setLevel(log_level)
    
    # Reset handlers in case this logger existed before but wasn't cached
    # (e.g., across restarts without clearing logging._handlers)
    for handler in app_logger.handlers[:]:
        app_logger.removeHandler(handler)

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    
    # Create file handler for the specific app log file
    log_file = APP_LOG_FILES[app_type]
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    
    # Set a distinct format for this app log
    log_format = f"%(asctime)s - huntarr.{app_type} - %(levelname)s - %(message)s"
    formatter = LocalTimeFormatter(log_format, datefmt="%Y-%m-%d %H:%M:%S")
    
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)
    
    # Add the handlers specific to this app logger
    app_logger.addHandler(console_handler)
    app_logger.addHandler(file_handler)
    
    # Cache the configured logger
    app_loggers[log_name] = app_logger

    app_logger.debug(f"Debug logging enabled for {app_type} logger")
        
    return app_logger

def update_logging_levels():
    """
    Update all logger levels based on environment configuration.
    """
    # Get log level from environment
    level = get_log_level()
    
    # Set level for main logger
    if logger:
        logger.setLevel(level)
    
    # Set level for all app loggers
    for app_logger in app_loggers.values():
        app_logger.setLevel(level)
    
    print(f"[Logger] Updated all logger levels to {logging.getLevelName(level)}")

def refresh_timezone_formatters():
    """
    Force refresh of all logger formatters to use updated timezone settings.
    This should be called when the timezone setting changes.
    """
    print("[Logger] Refreshing timezone formatters for all loggers")
    
    # Create new formatter with updated timezone handling
    log_format = "%(asctime)s - huntarr - %(levelname)s - %(message)s"
    new_formatter = LocalTimeFormatter(log_format, datefmt="%Y-%m-%d %H:%M:%S")
    
    # Update main logger handlers
    if logger:
        for handler in logger.handlers:
            handler.setFormatter(new_formatter)
    
    # Update all app logger handlers
    for app_name, app_logger in app_loggers.items():
        app_type = app_name.split('.')[-1] if '.' in app_name else app_name
        app_format = f"%(asctime)s - huntarr.{app_type} - %(levelname)s - %(message)s"
        app_formatter = LocalTimeFormatter(app_format, datefmt="%Y-%m-%d %H:%M:%S")
        
        for handler in app_logger.handlers:
            handler.setFormatter(app_formatter)
    
    print("[Logger] Timezone formatters refreshed for all loggers")

def debug_log(message: str, data: object = None, app_type: Optional[str] = None) -> None:
    """
    Log debug messages with optional data.
    
    Args:
        message: The message to log.
        data: Optional data to include with the message.
        app_type: Optional app type to log to a specific app's log file.
    """
    current_logger = get_logger(app_type) if app_type else logger
    
    if current_logger.level <= logging.DEBUG:
        if data is not None:
            try:
                import json
                as_json = json.dumps(data)
                if len(as_json) > 500:
                    as_json = as_json[:500] + "..."
                # Combine message and data in single log entry to prevent fragmentation
                current_logger.debug(f"{message} | Data: {as_json}")
            except:
                data_str = str(data)
                if len(data_str) > 500:
                    data_str = data_str[:500] + "..."
                # Combine message and data in single log entry to prevent fragmentation
                current_logger.debug(f"{message} | Data: {data_str}")
        else:
            current_logger.debug(f"{message}")

# Initialize the main logger instance when the module is imported
logger = setup_main_logger()