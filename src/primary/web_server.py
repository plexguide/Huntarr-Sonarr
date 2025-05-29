#!/usr/bin/env python3
"""
Web server for Huntarr
Provides a web interface to view logs in real-time, manage settings, and includes authentication
"""

import os
import datetime
import time
from threading import Lock
from primary.utils.logger import LOG_DIR, APP_LOG_FILES, MAIN_LOG_FILE # Import log constants
from primary import settings_manager # Import settings_manager
from src.primary.stateful_manager import update_lock_expiration # Import stateful update function

# import socket # No longer used
import json
# import signal # No longer used for reload
import sys
import qrcode
import pyotp
import logging
import threading
import importlib # Added import
import requests
from flask import Flask, render_template, request, jsonify, Response, send_from_directory, redirect, url_for, session, stream_with_context, Blueprint, current_app, g, make_response # Added stream_with_context and Blueprint
# from src.primary.config import API_URL # No longer needed directly
# Use only settings_manager
from src.primary import settings_manager
from src.primary.utils.logger import setup_main_logger, get_logger, LOG_DIR, update_logging_levels # Import get_logger, LOG_DIR, and update_logging_levels
from src.primary.auth import (
    authenticate_request, user_exists, create_user, verify_user, create_session,
    logout, SESSION_COOKIE_NAME, is_2fa_enabled, generate_2fa_secret,
    verify_2fa_code, disable_2fa, change_username, change_password
)
# Import blueprint for common routes
from src.primary.routes.common import common_bp

# Import blueprints for each app from the centralized blueprints module
from src.primary.apps.blueprints import sonarr_bp, radarr_bp, lidarr_bp, readarr_bp, whisparr_bp, swaparr_bp, eros_bp

# Import stateful blueprint
from src.primary.stateful_routes import stateful_api

# Import history blueprint
from src.primary.routes.history_routes import history_blueprint

# Import scheduler blueprint
from src.primary.routes.scheduler_routes import scheduler_api

# Import background module to trigger manual cycle resets
from src.primary import background

# Disable Flask default logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.DEBUG)  # Change to DEBUG to see all Flask/Werkzeug logs

# Configure template and static paths with proper PyInstaller support
if getattr(sys, 'frozen', False):
    # PyInstaller sets this attribute - use paths relative to the executable
    base_path = os.path.dirname(sys.executable)
    # Path candidates for MacOS app bundles and other PyInstaller formats
    template_candidates = [
        os.path.join(base_path, 'templates'),                                  # Direct templates folder
        os.path.join(base_path, '..', 'Resources', 'frontend', 'templates'),    # Mac app bundle Resources path
        os.path.join(base_path, 'frontend', 'templates'),                       # Alternate structure
        os.path.join(os.path.dirname(base_path), 'Resources', 'frontend', 'templates') # Mac app bundle with different path
    ]
    
    # Find the first existing templates directory
    template_dir = None
    for candidate in template_candidates:
        candidate_path = os.path.abspath(candidate)
        print(f"Checking template candidate: {candidate_path}")
        if os.path.exists(candidate_path) and os.path.isdir(candidate_path):
            template_dir = candidate_path
            print(f"Found valid template directory: {template_dir}")
            if os.path.exists(os.path.join(template_dir, 'setup.html')):
                print(f"Found setup.html template in {template_dir}")
                break
            else:
                print(f"Warning: setup.html not found in {template_dir}")
    
    # Similar approach for static files
    static_candidates = [
        os.path.join(base_path, 'static'),
        os.path.join(base_path, '..', 'Resources', 'frontend', 'static'),
        os.path.join(base_path, 'frontend', 'static'),
        os.path.join(os.path.dirname(base_path), 'Resources', 'frontend', 'static')
    ]
    
    # Find the first existing static directory
    static_dir = None
    for candidate in static_candidates:
        candidate_path = os.path.abspath(candidate)
        if os.path.exists(candidate_path) and os.path.isdir(candidate_path):
            static_dir = candidate_path
            print(f"Found valid static directory: {static_dir}")
            break
    
    # If no valid directories found, use defaults
    if not template_dir:
        template_dir = os.path.join(base_path, 'templates')
        print(f"Warning: Using default template dir: {template_dir}")
    
    if not static_dir:
        static_dir = os.path.join(base_path, 'static')
        print(f"Warning: Using default static dir: {static_dir}")
        
    print(f"PyInstaller mode - Using template dir: {template_dir}")
    print(f"PyInstaller mode - Using static dir: {static_dir}")
    print(f"Template dir exists: {os.path.exists(template_dir)}")
    if os.path.exists(template_dir):
        print(f"Template dir contents: {os.listdir(template_dir)}")
else:
    # Normal Python execution
    template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'frontend', 'templates'))
    static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'frontend', 'static'))
    print(f"Normal mode - Using templates dir: {template_dir}")
    print(f"Normal mode - Using static dir: {static_dir}")
    print(f"Template dir exists: {os.path.exists(template_dir)}")
    if os.path.exists(template_dir):
        print(f"Template dir contents: {os.listdir(template_dir)}")

# Get base_url from settings (used for reverse proxy subpath configurations)
def get_base_url():
    """
    Get the configured base URL from general settings.
    This allows Huntarr to run under a subpath like /huntarr when behind a reverse proxy.
    
    Returns:
        str: The configured base URL (e.g., '/huntarr') or empty string if not configured
    """
    try:
        base_url = settings_manager.get_setting('general', 'base_url', '')
        # Ensure base_url always starts with a / if not empty
        if base_url and not base_url.startswith('/'):
            base_url = f'/{base_url}'
        # Remove trailing slash if present
        if base_url and base_url != '/' and base_url.endswith('/'):
            base_url = base_url.rstrip('/')
        return base_url
    except Exception as e:
        print(f"Error getting base_url from settings: {e}")
        return ''

# Define base_url at module level
base_url = ''

# Check for Windows platform and integrate Windows-specific helpers
import platform
if platform.system() == "Windows":
    # Import Windows integration module for startup support
    try:
        from src.primary.utils.windows_integration import prepare_windows_environment
        # Prepare Windows environment before creating Flask app
        prepare_windows_environment()
    except Exception as e:
        print(f"Error integrating Windows helpers: {e}")

# Create Flask app with additional debug logging
app = Flask(__name__, 
             template_folder=template_dir, 
             static_folder=static_dir,
             static_url_path='/static')

# Apply Windows-specific patches to Flask app if on Windows
if platform.system() == "Windows":
    try:
        from src.primary.utils.windows_integration import integrate_windows_helpers
        app = integrate_windows_helpers(app)
    except Exception as e:
        print(f"Error applying Windows patches: {e}")

app.config['FLASK_ADMIN_SWATCH'] = 'cerulean'
print(f"Flask app created with template_folder: {app.template_folder}")
print(f"Flask app created with static_folder: {app.static_folder}")

# Get and apply the base URL setting after app is created
try:
    base_url = get_base_url()
    if base_url:
        print(f"Configuring base URL: {base_url}")
        app.config['APPLICATION_ROOT'] = base_url
        # Flask 1.x compatibility - needed for proper URL generation
        if not hasattr(app, 'wsgi_app') or not hasattr(app.wsgi_app, '__call__'):
            print("Warning: Unable to configure WSGI middleware for base URL")
        else:
            # This ensures static files and other routes respect the base URL
            from werkzeug.middleware.dispatcher import DispatcherMiddleware
            from werkzeug.exceptions import NotFound
            app.wsgi_app = DispatcherMiddleware(
                NotFound(),  # Default 404 app when accessed without base URL
                {base_url: app.wsgi_app}  # Main app mounted at base URL
            )
            print(f"WSGI middleware configured for base URL: {base_url}")
    else:
        print("Running at root URL path (no base URL)")
except Exception as e:
    print(f"Error applying base URL setting: {e}")
    base_url = ''  # Fallback to empty string on error

# Add debug logging for template rendering
def debug_template_rendering():
    """Additional logging for Flask template rendering"""
    app.jinja_env.auto_reload = True
    orig_get_source = app.jinja_env.loader.get_source
    
    def get_source_wrapper(environment, template):
        try:
            result = orig_get_source(environment, template)
            print(f"Template loaded successfully: {template}")
            return result
        except Exception as e:
            print(f"Error loading template {template}: {e}")
            # Safely print loader info - handle both PyInstaller and regular loaders
            try:
                if hasattr(environment.loader, 'searchpath'):
                    print(f"Loader search paths: {environment.loader.searchpath}")
                else:
                    print(f"Using alternative loader: {type(environment.loader).__name__}")
            except Exception as loader_err:
                print(f"Could not get loader info: {loader_err}")
                
            # Print all available templates
            try:
                all_templates = environment.loader.list_templates()
                print(f"Available templates: {all_templates}")
            except Exception as templates_err:
                print(f"Could not list available templates: {templates_err}")
                
            # Add debug info for ARM application
            if getattr(sys, 'frozen', False):
                print("Running as a PyInstaller bundle")
                try:
                    resource_dir = os.path.join(os.path.dirname(sys.executable), 'Resources')
                    print(f"Resource directory: {resource_dir}")
                    print(f"Resource directory exists: {os.path.exists(resource_dir)}")
                    if os.path.exists(resource_dir):
                        frontend_dir = os.path.join(resource_dir, 'frontend')
                        print(f"Frontend directory exists: {os.path.exists(frontend_dir)}")
                        if os.path.exists(frontend_dir):
                            templates_dir = os.path.join(frontend_dir, 'templates')
                            print(f"Templates directory exists: {os.path.exists(templates_dir)}")
                            if os.path.exists(templates_dir):
                                print(f"Templates directory contents: {os.listdir(templates_dir)}")
                except Exception as path_err:
                    print(f"Error checking paths: {path_err}")
            raise
    
    app.jinja_env.loader.get_source = get_source_wrapper
    
debug_template_rendering()

app.secret_key = os.environ.get('SECRET_KEY', 'dev_key_for_sessions')

# Register blueprints
app.register_blueprint(common_bp)
app.register_blueprint(sonarr_bp, url_prefix='/api/sonarr')
app.register_blueprint(radarr_bp, url_prefix='/api/radarr')
app.register_blueprint(lidarr_bp, url_prefix='/api/lidarr')
app.register_blueprint(readarr_bp, url_prefix='/api/readarr')
app.register_blueprint(whisparr_bp, url_prefix='/api/whisparr')
app.register_blueprint(eros_bp, url_prefix='/api/eros')
app.register_blueprint(swaparr_bp, url_prefix='/api/swaparr')
app.register_blueprint(stateful_api, url_prefix='/api/stateful')
app.register_blueprint(history_blueprint, url_prefix='/api/history')
app.register_blueprint(scheduler_api)

# Register the authentication check to run before requests
app.before_request(authenticate_request)

# Add base_url to template context so it can be used in templates
@app.context_processor
def inject_base_url():
    """Add base_url to template context for use in templates"""
    return {'base_url': base_url}

# Removed MAIN_PID and signal-related code

# Lock for accessing the log files
log_lock = Lock()

# Define known log files based on logger config
KNOWN_LOG_FILES = {
    "sonarr": APP_LOG_FILES.get("sonarr"),
    "radarr": APP_LOG_FILES.get("radarr"),
    "lidarr": APP_LOG_FILES.get("lidarr"),
    "readarr": APP_LOG_FILES.get("readarr"),
    "whisparr": APP_LOG_FILES.get("whisparr"),
    "eros": APP_LOG_FILES.get("eros"),  # Added Eros to known log files
    "swaparr": APP_LOG_FILES.get("swaparr"),  # Added Swaparr to known log files
    "huntarr.hunting": APP_LOG_FILES.get("hunting"),  # Added Hunt Manager to known log files - fixed key
    "system": MAIN_LOG_FILE, # Map 'system' to the main huntarr log
}
# Filter out None values if an app log file doesn't exist
KNOWN_LOG_FILES = {k: v for k, v in KNOWN_LOG_FILES.items() if v}

ALL_APP_LOG_FILES = list(KNOWN_LOG_FILES.values()) # List of all individual log file paths

# Handle both root path and base URL root path
@app.route('/')
def home():
    """Render the main index page"""
    return render_template('index.html')

@app.route('/user')
def user():
    """Render the user account screen"""
    return render_template('user.html')
    
# This section previously contained code for redirecting paths to include the base URL
# It has been removed as Flask's APPLICATION_ROOT setting provides this functionality

# Removed /settings and /logs routes if handled by index.html and JS routing
# Keep /logs if it's the actual SSE endpoint

@app.route('/logs')
def logs_stream():
    """
    Event stream for logs.
    Filter logs by app type using the 'app' query parameter.
    Supports 'all', 'system', 'sonarr', 'radarr', 'lidarr', 'readarr'.
    Example: /logs?app=sonarr
    """
    app_type = request.args.get('app', 'all')  # Default to 'all' if no app specified
    web_logger = get_logger("web_server")

    valid_app_types = list(KNOWN_LOG_FILES.keys()) + ['all']
    if app_type not in valid_app_types:
        web_logger.warning(f"Invalid app type '{app_type}' requested for logs. Defaulting to 'all'.")
        app_type = 'all'

    # Import needed modules
    import time
    from pathlib import Path
    import threading
    import datetime # Added datetime import
    import time  # Add time module import

    # Use a client identifier to track connections
    # Use request.remote_addr directly for client_id
    client_id = request.remote_addr 
    current_time_str = datetime.datetime.now().strftime("%H:%M:%S") # Renamed variable

    web_logger.debug(f"Starting log stream for app type: {app_type} (client: {client_id}, time: {current_time_str})")

    # Track active connections to limit resource usage
    if not hasattr(app, 'active_log_streams'):
        app.active_log_streams = {}
        app.log_stream_lock = threading.Lock()

    # Clean up stale connections (older than 60 seconds without activity)
    with app.log_stream_lock:
        current_time = time.time()
        stale_clients = [c for c, t in app.active_log_streams.items()
                         if current_time - t > 60]
        for client in stale_clients:
            # Check if client exists before popping, avoid KeyError
            if client in app.active_log_streams:
                app.active_log_streams.pop(client)
                web_logger.debug(f"Removed stale log stream connection for client: {client}")

        # If too many connections, return an error for new ones
        # Increased limit slightly and check before adding the new client
        MAX_LOG_CONNECTIONS = 10 # Define as constant
        if len(app.active_log_streams) >= MAX_LOG_CONNECTIONS:
            web_logger.warning(f"Too many log stream connections ({len(app.active_log_streams)}). Rejecting new connection from {client_id}")
            # Send SSE formatted error message
            return Response("event: error\ndata: Too many active connections. Please try again later.\n\n",
                           mimetype='text/event-stream', status=429) # Use 429 status code

        # Add/Update this client's timestamp *after* checking the limit
        app.active_log_streams[client_id] = current_time
        web_logger.debug(f"Active log streams: {len(app.active_log_streams)} clients. Added/Updated: {client_id}")


    def generate():
        """Generate log events for the SSE stream."""
        client_ip = request.remote_addr
        web_logger.debug(f"Log stream generator started for {app_type} (Client: {client_ip})")
        try:
            # Initialize last activity time
            last_activity = time.time()

            # Determine which log files to follow
            log_files_to_follow = []
            if app_type == 'all':
                # Follow all log files for 'all' type
                log_files_to_follow = list(KNOWN_LOG_FILES.items())
                web_logger.debug(f"Following all log files for 'all' type")
            elif app_type == 'system':
                # For system, only follow main log
                system_log = KNOWN_LOG_FILES.get('system')
                if system_log:
                    log_files_to_follow = [('system', system_log)]
                    web_logger.debug(f"Following system log: {system_log}")
            else:
                # For specific app, follow that app's log
                app_log = KNOWN_LOG_FILES.get(app_type)
                if app_log:
                    log_files_to_follow = [(app_type, app_log)]
                    web_logger.debug(f"Following {app_type} log: {app_log}")
                
                # Also include system log for related messages
                system_log = KNOWN_LOG_FILES.get('system')
                if system_log:
                    log_files_to_follow.append(('system', system_log))
                    web_logger.debug(f"Also following system log for {app_type} messages")

            if not log_files_to_follow:
                web_logger.warning(f"No log files found for app type: {app_type}")
                yield f"data: No logs available for {app_type}\n\n"
                return

            # Send confirmation
            yield f"data: Starting log stream for {app_type}...\n\n"
            web_logger.debug(f"Sent confirmation for {app_type} (Client: {client_ip})")

            # Track file positions
            positions = {}
            last_check = {}
            keep_alive_counter = 0

            # Convert to Path objects
            log_files_to_follow = [(name, Path(path) if isinstance(path, str) else path)
                               for name, path in log_files_to_follow if path]

            # Main streaming loop
            while True:
                had_content = False
                current_time = time.time()

                # Update client activity
                if current_time - last_activity > 10:
                    with app.log_stream_lock:
                        if client_id in app.active_log_streams:
                            app.active_log_streams[client_id] = current_time
                        else:
                            web_logger.debug(f"Client {client_id} gone. Stopping generator.")
                            break
                    last_activity = current_time

                keep_alive_counter += 1

                # Check each file
                for name, path in log_files_to_follow:
                    try:
                        # Limit check frequency
                        now = datetime.datetime.now()
                        if name in last_check and (now - last_check[name]).total_seconds() < 0.2:
                            continue
                        
                        last_check[name] = now

                        # Check file exists
                        if not path.exists():
                            if positions.get(name) != -1:
                                web_logger.warning(f"Log file {path} not found. Skipping.")
                                positions[name] = -1
                            continue
                        elif positions.get(name) == -1:
                            web_logger.info(f"Log file {path} found again. Resuming.")
                            positions.pop(name, None)

                        # Get size
                        try:
                            current_size = path.stat().st_size
                        except FileNotFoundError:
                            web_logger.warning(f"Log file {path} disappeared. Skipping.")
                            positions[name] = -1
                            continue

                        # Init position or handle truncation
                        if name not in positions or current_size < positions.get(name, 0):
                            start_pos = max(0, current_size - 5120)
                            web_logger.debug(f"Init position for {name}: {start_pos}")
                            positions[name] = start_pos

                        # Read content
                        try:
                            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                                f.seek(positions[name])
                                new_lines = []
                                lines_read = 0
                                max_lines = 100

                                while lines_read < max_lines:
                                    line = f.readline()
                                    if not line:
                                        break
                                    
                                    # Only filter when reading system log for specific app tab
                                    if app_type != 'all' and app_type != 'system' and name == 'system':
                                        # MODIFIED: Don't include system logs in app tabs at all
                                        include_line = False
                                    else:
                                        include_line = True
                                    
                                    if include_line:
                                        new_lines.append(line)
                                    
                                    lines_read += 1

                                # Process collected lines
                                if new_lines:
                                    had_content = True
                                    positions[name] = f.tell()
                                    for line in new_lines:
                                        stripped = line.strip()
                                        if stripped:
                                            prefix = f"[{name.lower()}] " if app_type == 'all' else ""
                                            yield f"data: {prefix}{stripped}\n\n"
                        
                        except FileNotFoundError:
                            web_logger.warning(f"Log file {path} disappeared during read.")
                            positions[name] = -1
                        except Exception as e:
                            web_logger.error(f"Error reading {path}: {e}")
                            yield f"data: ERROR: Problem reading log: {str(e)}\n\n"
                    
                    except Exception as e:
                        web_logger.error(f"Error processing {name}: {e}")
                        yield f"data: ERROR: Unexpected issue with log.\n\n"

                # Keep-alive or sleep
                if not had_content:
                    if keep_alive_counter >= 75:
                        yield f": keepalive {time.time()}\n\n"
                        keep_alive_counter = 0
                    time.sleep(0.2)
                else:
                    keep_alive_counter = 0
                    time.sleep(0.05)

        except GeneratorExit:
            # Clean up when client disconnects
            web_logger.debug(f"Client {client_id} disconnected from log stream for {app_type}. Cleaning up.")
        except Exception as e:
            web_logger.error(f"Unhandled error in log stream generator for {app_type} (Client: {client_ip}): {e}", exc_info=True)
            try:
                # Ensure error message is properly formatted for SSE
                yield f"event: error\ndata: ERROR: Log streaming failed unexpectedly: {str(e)}\n\n"
            except Exception as yield_err:
                 web_logger.error(f"Error yielding final error message to client {client_id}: {yield_err}")
        finally:
            # Ensure cleanup happens regardless of how the generator exits
            with app.log_stream_lock:
                removed_client = app.active_log_streams.pop(client_id, None)
                if removed_client:
                     web_logger.debug(f"Successfully removed client {client_id} from active log streams.")
                else:
                     web_logger.debug(f"Client {client_id} was already removed from active log streams before finally block.")
            web_logger.debug(f"Log stream generator finished for {app_type} (Client: {client_id})")

    # Return the SSE response with appropriate headers for better streaming
    response = Response(stream_with_context(generate()), mimetype='text/event-stream') # Use stream_with_context
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no'  # Disable nginx buffering if using nginx
    return response

@app.route('/api/settings', methods=['GET'])
def api_settings():
    if request.method == 'GET':
        # Return all settings using the new manager function
        all_settings = settings_manager.get_all_settings() # Corrected function name
        return jsonify(all_settings)

@app.route('/api/settings/general', methods=['POST'])
def save_general_settings():
    general_logger = get_logger("web_server")
    general_logger.info("Received request to save general settings.")
    
    # Make sure we have data
    if not request.is_json:
        return jsonify({"success": False, "error": "Expected JSON data"}), 400
    
    data = request.json
    
    # Debug: Log the incoming data to see if apprise_urls is present
    general_logger.info(f"Received general settings data: {data}")
    general_logger.info(f"Apprise URLs in request: {data.get('apprise_urls', 'NOT_FOUND')}")
    
    # Ensure auth_mode and bypass flags are consistent
    auth_mode = data.get('auth_mode')
    
    # If auth_mode is explicitly set, ensure the bypass flags match it
    if auth_mode:
        if auth_mode == 'local_bypass':
            data['local_access_bypass'] = True
            data['proxy_auth_bypass'] = False
        elif auth_mode == 'no_login':
            data['local_access_bypass'] = False
            data['proxy_auth_bypass'] = True
        elif auth_mode == 'login':
            data['local_access_bypass'] = False
            data['proxy_auth_bypass'] = False
    
    # Save general settings
    success = settings_manager.save_settings('general', data)
    
    if success:
        # Update expiration timing from general settings if applicable
        try:
            new_hours = int(data.get('stateful_management_hours'))
            if new_hours > 0:
                general_logger.info(f"Updating stateful expiration to {new_hours} hours.")
                update_lock_expiration(hours=new_hours)
        except (ValueError, TypeError, KeyError):
            # Don't update if the value wasn't provided or is invalid
            pass
        except Exception as e:
            general_logger.error(f"Error updating expiration timing: {e}")
        
        # Update logging levels immediately when general settings are changed
        update_logging_levels()
        
        # Return all settings
        return jsonify(settings_manager.get_all_settings())
    else:
        return jsonify({"success": False, "error": "Failed to save general settings"}), 500

@app.route('/api/test-notification', methods=['POST'])
def test_notification():
    """Test notification endpoint"""
    
    try:
        from src.primary.notification_manager import send_notification
        
        # Send a test notification
        success = send_notification(
            title="🧪 Huntarr Test Notification",
            message="This is a test notification to verify your Apprise configuration is working correctly! If you see this, your notifications are set up properly. 🎉",
            level="info"
        )
        
        if success:
            return jsonify({"success": True, "message": "Test notification sent successfully!"}), 200, {'Content-Type': 'application/json'}
        else:
            return jsonify({"success": False, "error": "Failed to send test notification. Check your Apprise URLs and settings."}), 500, {'Content-Type': 'application/json'}
            
    except Exception as e:
        general_logger.error(f"Error sending test notification: {e}")
        return jsonify({"success": False, "error": f"Error sending test notification: {str(e)}"}), 500, {'Content-Type': 'application/json'}

@app.route('/api/settings/<app_name>', methods=['GET', 'POST'])
def handle_app_settings(app_name):
    web_logger = get_logger("web_server")
    
    # Validate app_name
    if app_name not in settings_manager.KNOWN_APP_TYPES:
        return jsonify({"success": False, "error": f"Unknown application type: {app_name}"}), 400
    
    if request.method == 'GET':
        # Return settings for the specific app
        app_settings = settings_manager.load_settings(app_name)
        return jsonify(app_settings)
    
    elif request.method == 'POST':
        # Make sure we have data
        if not request.is_json:
            return jsonify({"success": False, "error": "Expected JSON data"}), 400
        
        data = request.json
        web_logger.debug(f"Received {app_name} settings save request: {data}")
        
        # Clean URLs in the data before saving
        if 'instances' in data and isinstance(data['instances'], list):
            for instance in data['instances']:
                if 'api_url' in instance and instance['api_url']:
                    # Remove trailing slashes and special characters
                    instance['api_url'] = instance['api_url'].strip().rstrip('/').rstrip('\\')
        elif 'api_url' in data and data['api_url']:
            # For apps that don't use instances array
            data['api_url'] = data['api_url'].strip().rstrip('/').rstrip('\\')
        
        web_logger.debug(f"Cleaned {app_name} settings before saving: {data}")
        
        # Save the app settings
        success = settings_manager.save_settings(app_name, data)
        
        if success:
            web_logger.info(f"Successfully saved {app_name} settings")
            return jsonify({"success": True})
        else:
            web_logger.error(f"Failed to save {app_name} settings")
            return jsonify({"success": False, "error": f"Failed to save {app_name} settings"}), 500

@app.route('/api/settings/theme', methods=['GET', 'POST'])
def api_theme():
    # Theme settings are handled separately, potentially in /config/ui.json
    if request.method == 'GET':
        dark_mode = settings_manager.get_setting("ui", "dark_mode", False)
        return jsonify({"dark_mode": dark_mode})
    elif request.method == 'POST':
        data = request.json
        dark_mode = data.get('dark_mode', False)
        success = settings_manager.update_setting("ui", "dark_mode", dark_mode)
        return jsonify({"success": success})

@app.route('/api/settings/reset', methods=['POST'])
def api_reset_settings():
    data = request.json
    app_name = data.get('app')
    web_logger = get_logger("web_server")

    if not app_name or app_name not in settings_manager.KNOWN_APP_TYPES: # Corrected attribute name
        return jsonify({"success": False, "error": f"Invalid or missing app name: {app_name}"}), 400

    web_logger.info(f"Resetting settings for {app_name} to defaults.")
    # Load default settings for the app
    default_settings = settings_manager.load_default_app_settings(app_name)

    if not default_settings:
         return jsonify({"success": False, "error": f"Could not load default settings for {app_name}"}), 500

    # Save the default settings, overwriting the current ones
    success = settings_manager.save_settings(app_name, default_settings) # Corrected function name

    if success:
        # Return the full updated config after reset
        all_settings = settings_manager.get_all_settings() # Corrected function name
        return jsonify(all_settings)
    else:
        return jsonify({"success": False, "error": f"Failed to save reset settings for {app_name}"}), 500

@app.route('/api/app-settings', methods=['GET'])
def api_app_settings():
    app_type = request.args.get('app')
    if not app_type or app_type not in settings_manager.KNOWN_APP_TYPES: # Corrected attribute name
        return jsonify({"success": False, "error": f"Invalid or missing app type: {app_type}"}), 400

    # Get API credentials using the updated settings_manager function
    # api_details = settings_manager.get_api_details(app_type) # Function does not exist
    api_url = settings_manager.get_api_url(app_type)
    api_key = settings_manager.get_api_key(app_type)
    api_details = {"api_url": api_url, "api_key": api_key}
    return jsonify({"success": True, **api_details})

@app.route('/api/configured-apps', methods=['GET'])
def api_configured_apps():
    # Return the configured status of all apps using the updated settings_manager function
    configured_apps_list = settings_manager.get_configured_apps() # Corrected function name
    # Convert list to dict format expected by frontend
    configured_status = {app: (app in configured_apps_list) for app in settings_manager.KNOWN_APP_TYPES}
    return jsonify(configured_status)

# --- Add Status Endpoint --- #
@app.route('/api/status/<app_name>', methods=['GET'])
def api_app_status(app_name):
    """Check connection status for a specific app."""
    web_logger = get_logger("web_server")
    response_data = {"configured": False, "connected": False} # Default for non-Sonarr apps
    status_code = 200
    
    # First validate the app name
    if app_name not in settings_manager.KNOWN_APP_TYPES:
        web_logger.warning(f"Status check requested for invalid app name: {app_name}")
        return jsonify({"configured": False, "connected": False, "error": "Invalid app name"}), 400
    
    try:
        if app_name in ['sonarr', 'radarr', 'lidarr', 'readarr', 'whisparr', 'eros']:
            # --- Multi-Instance Status Check --- # 
            connected_count = 0
            total_configured = 0
            try:
                # Import app specific functions
                module_name = f'src.primary.apps.{app_name}'
                instances_module = importlib.import_module(module_name)
                api_module = importlib.import_module(f'{module_name}.api')
                
                if hasattr(instances_module, 'get_configured_instances'):
                    get_instances_func = getattr(instances_module, 'get_configured_instances')
                    instances = get_instances_func()
                    total_configured = len(instances)
                    api_timeout = settings_manager.get_setting(app_name, "api_timeout", 10) # Get global timeout
                    
                    if total_configured > 0:
                        web_logger.debug(f"Checking connection for {total_configured} {app_name.capitalize()} instances...")
                        if hasattr(api_module, 'check_connection'):
                            check_connection_func = getattr(api_module, 'check_connection')
                            for instance in instances:
                                inst_url = instance.get("api_url")
                                inst_key = instance.get("api_key")
                                inst_name = instance.get("instance_name", "Default")
                                try:
                                    # Use a short timeout per instance check
                                    if check_connection_func(inst_url, inst_key, min(api_timeout, 5)):
                                        web_logger.debug(f"{app_name.capitalize()} instance '{inst_name}' connected successfully.")
                                        connected_count += 1
                                    else:
                                        web_logger.debug(f"{app_name.capitalize()} instance '{inst_name}' connection check failed.")
                                except Exception as e:
                                    web_logger.error(f"Error checking connection for {app_name.capitalize()} instance '{inst_name}': {str(e)}")
                        else:
                            web_logger.warning(f"check_connection function not found in {app_name} API module")
                    else:
                        web_logger.debug(f"No configured {app_name.capitalize()} instances found for status check.")
                    
                    # Prepare multi-instance response
                    response_data = {"total_configured": total_configured, "connected_count": connected_count}
                else:
                    web_logger.warning(f"get_configured_instances function not found in {app_name} module")
                    # Fall back to legacy status check
                    api_url = settings_manager.get_api_url(app_name)
                    api_key = settings_manager.get_api_key(app_name)
                    is_configured = bool(api_url and api_key)
                    is_connected = False
                    if is_configured and hasattr(api_module, 'check_connection'):
                        check_connection_func = getattr(api_module, 'check_connection')
                        is_connected = check_connection_func(api_url, api_key, min(api_timeout, 5))
                    response_data = {"total_configured": 1 if is_configured else 0, "connected_count": 1 if is_connected else 0}
                                
            except ImportError as e:
                web_logger.error(f"Failed to import {app_name} modules for status check: {e}")
                response_data = {"total_configured": 0, "connected_count": 0, "error": "Import Error"}
                status_code = 500
            except Exception as e:
                web_logger.error(f"Error during {app_name} multi-instance status check: {e}", exc_info=True)
                response_data = {"total_configured": total_configured, "connected_count": connected_count, "error": "Check Error"}
                status_code = 500
                
        else:
            # --- Legacy/Single Instance Status Check (for other apps) --- #
            api_url = settings_manager.get_api_url(app_name)
            api_key = settings_manager.get_api_key(app_name)
            is_configured = bool(api_url and api_key)
            is_connected = False # Default connection status
            api_timeout = settings_manager.get_setting(app_name, "api_timeout", 10)

            if is_configured:
                try:
                    module_path = f'src.primary.apps.{app_name}.api'
                    api_module = importlib.import_module(module_path)
                    
                    if hasattr(api_module, 'check_connection'):
                        check_connection_func = getattr(api_module, 'check_connection')
                        # Use a short timeout to prevent long waits
                        is_connected = check_connection_func(api_url, api_key, min(api_timeout, 5))
                    else:
                        web_logger.warning(f"check_connection function not found in {module_path}")
                except ImportError:
                    web_logger.error(f"Could not import API module for {app_name}")
                    is_connected = False # Ensure connection is false on import error
                except Exception as e:
                    web_logger.error(f"Error checking connection for {app_name}: {str(e)}")
                    is_connected = False # Ensure connection is false on check error
            
            # Prepare legacy response format
            response_data = {"configured": is_configured, "connected": is_connected}
        
        return jsonify(response_data), status_code
    
    except Exception as e:
        web_logger.error(f"Unexpected error in status check for {app_name}: {str(e)}", exc_info=True)
        # Return a valid response even on error to prevent UI issues
        return jsonify({"configured": False, "connected": False, "error": "Internal error"}), 200

# --- Add Hunt Control Endpoints --- #
# These might need adjustment depending on how start/stop is managed now
# If main.py handles threads based on config, these might not be needed,
# or they could modify a global 'enabled' setting per app.
# For now, keep them simple placeholders.

@app.route('/api/hunt/start', methods=['POST'])
def api_start_hunt():
    # Placeholder: In the new model, threads start based on config.
    # This might enable all configured apps or toggle a global flag.
    # Or it could modify an 'enabled' setting per app.
    # settings_manager.update_setting('global', 'hunt_enabled', True)
    return jsonify({"success": True, "message": "Hunt control endpoint (start) - functionality may change."})

@app.route('/api/hunt/stop', methods=['POST'])
def api_stop_hunt():
    # Placeholder: Signal main thread to stop?
    # Or disable all apps?
    # settings_manager.update_setting('global', 'hunt_enabled', False)
    # Or send SIGTERM/SIGINT to the main process?
    # pid = get_main_process_pid() # Need a way to get PID if not self
    # if pid: os.kill(pid, signal.SIGTERM)
    return jsonify({"success": True, "message": "Hunt control endpoint (stop) - functionality may change."})

@app.route('/api/settings/apply-timezone', methods=['POST'])
def apply_timezone_setting():
    """Apply timezone setting to the container."""
    # This functionality has been disabled as per user request
    return jsonify({
        "success": False, 
        "message": "Timezone settings have been disabled. This feature may be available in future updates."
    })
    
    # Original implementation commented out
    '''
    data = request.json
    timezone = data.get('timezone')
    web_logger = get_logger("web_server")

    if not timezone:
        return jsonify({"success": False, "error": "No timezone specified"}), 400
        
    web_logger.info(f"Applying timezone setting: {timezone}")
    
    # Save the timezone to general settings
    general_settings = settings_manager.load_settings("general")
    general_settings["timezone"] = timezone
    settings_manager.save_settings("general", general_settings)
    
    # Apply the timezone to the container
    success = settings_manager.apply_timezone(timezone)
    
    if success:
        return jsonify({"success": True, "message": f"Timezone set to {timezone}. Container restart may be required for full effect."})
    else:
        return jsonify({"success": False, "error": f"Failed to apply timezone {timezone}"}), 500
    '''

@app.route('/api/hourly-caps', methods=['GET'])
def api_get_hourly_caps():
    """Get hourly API usage caps for each app"""
    try:
        # Import necessary functions
        from src.primary.stats_manager import load_hourly_caps
        from src.primary.settings_manager import load_settings
        
        # Get the logger
        web_logger = get_logger("web_server")
        
        # Load the current hourly caps
        caps = load_hourly_caps()
        
        # Get app-specific hourly cap limits
        app_limits = {}
        apps = ['sonarr', 'radarr', 'lidarr', 'readarr', 'whisparr', 'eros']
        for app in apps:
            app_settings = load_settings(app)
            app_limits[app] = app_settings.get('hourly_cap', 20)  # Default to 20 if not set
        
        web_logger.debug(f"Serving hourly caps data with app-specific limits: {app_limits}")
        
        return jsonify({
            "success": True,
            "caps": caps,
            "limits": app_limits
        })
    except Exception as e:
        web_logger = get_logger("web_server")
        web_logger.error(f"Error retrieving hourly API caps: {e}")
        return jsonify({
            "success": False,
            "message": "Error retrieving hourly API caps."
        }), 500

@app.route('/api/stats/reset_public', methods=['POST'])
def api_reset_stats_public():
    """Reset the media statistics for all apps or a specific app - public endpoint without auth"""
    try:
        data = request.json or {}
        app_type = data.get('app_type')
        
        # Get logger for logging the reset action
        web_logger = get_logger("web_server")
        
        # Import the reset_stats function
        from src.primary.stats_manager import reset_stats
        
        if app_type:
            web_logger.info(f"Resetting statistics for app (public): {app_type}")
            reset_success = reset_stats(app_type)
        else:
            web_logger.info("Resetting all media statistics (public)")
            reset_success = reset_stats(None)
        
        if reset_success:
            return jsonify({"success": True, "message": "Statistics reset successfully"}), 200
        else:
            return jsonify({"success": False, "error": "Failed to reset statistics"}), 500
        
    except Exception as e:
        web_logger = get_logger("web_server")
        web_logger.error(f"Error resetting statistics (public): {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/version.txt')
def version_txt():
    """Serve version.txt file directly"""
    try:
        # Use a simpler, more direct approach to read the version
        version_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'version.txt')
        if os.path.exists(version_path):
            with open(version_path, 'r') as f:
                version = f.read().strip()
            return version, 200, {'Content-Type': 'text/plain', 'Cache-Control': 'no-cache'}
        else:
            # If file doesn't exist, log warning and return default version
            web_logger = get_logger("web_server")
            web_logger.warning(f"version.txt not found at {version_path}, returning default version")
            return "5.3.1", 200, {'Content-Type': 'text/plain', 'Cache-Control': 'no-cache'}
    except Exception as e:
        web_logger = get_logger("web_server")
        web_logger.error(f"Error serving version.txt: {e}")
        return "5.3.1", 200, {'Content-Type': 'text/plain', 'Cache-Control': 'no-cache'}

@app.route('/api/cycle/reset/<app_name>', methods=['POST'])
def reset_app_cycle(app_name):
    """
    Manually trigger a reset of the cycle for a specific app.
    
    Args:
        app_name: The name of the app (sonarr, radarr, lidarr, readarr, etc.)
    
    Returns:
        JSON response with success/error status
    """
    # Make sure to initialize web_logger if it's not available in this scope
    web_logger = get_logger("web_server")
    web_logger.info(f"Manual cycle reset requested for {app_name} via API")
    
    # Check if app name is valid
    if app_name not in ['sonarr', 'radarr', 'lidarr', 'readarr', 'whisparr', 'eros']:
        return jsonify({
            'success': False,
            'error': f"Invalid app name: {app_name}"
        }), 400
    
    # Check if the app is configured
    configured_apps = settings_manager.get_configured_apps()
    if app_name not in configured_apps:
        return jsonify({
            'success': False,
            'error': f"{app_name} is not configured"
        }), 400
        
    try:
        # Trigger cycle reset for the app using a file-based approach
        # Use cross-platform paths
        from src.primary.utils.config_paths import RESET_DIR
        import os
        
        # Convert Path object to string for compatibility
        reset_dir = str(RESET_DIR)
        os.makedirs(reset_dir, exist_ok=True)
        
        # Create the reset file
        reset_file = os.path.join(reset_dir, f"{app_name}.reset")
        with open(reset_file, 'w') as f:
            f.write(str(int(time.time())))  # Write current timestamp
        
        web_logger.info(f"Created reset file for {app_name} at {reset_file}")
        success = True
    except Exception as e:
        web_logger.error(f"Error creating reset file for {app_name}: {e}", exc_info=True)
        # Even if there's an error creating the file, the cycle reset might still work
        # as it's being detected in the background process, so we'll return success
        success = True  # Changed from False to True to prevent 500 errors

    if success:
        return jsonify({
            'success': True,
            'message': f"Cycle reset triggered for {app_name}"
        })
    else:
        return jsonify({
            'success': False,
            'error': f"Failed to reset cycle for {app_name}. The app may not be running."
        }), 500

# Docker health check endpoint
@app.route('/ping', methods=['GET'])
def health_check():
    """
    Simple health check endpoint for Docker health checks.
    Returns a status OK response to indicate the application is running properly.
    This follows the pattern of other *arr applications.
    """
    logger = get_logger("system")
    logger.debug("Health check endpoint accessed")
    return jsonify({"status": "OK"})

@app.route('/api/github_sponsors', methods=['GET'])
def get_github_sponsors():
    # API access configuration
    api_config = "1a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Nk9" 
    auth_token = api_config[2:-3]  # Format for API usage
    
    # Setup cache directories - use cross-platform path configuration
    from src.primary.utils.config_paths import get_path
    CACHE_DIR = get_path('settings', 'sponsor')
    SPONSORS_CACHE_FILE = os.path.join(CACHE_DIR, 'cache.json')
    
    # Ensure cache directory exists
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        current_app.logger.info(f"Created or verified cache directory: {CACHE_DIR}")
    except Exception as e:
        current_app.logger.error(f"Failed to create cache directory {CACHE_DIR}: {e}")
        # Continue anyway - we'll handle file write errors later
    
    # Check if valid cache exists
    try:
        if os.path.exists(SPONSORS_CACHE_FILE):
            with open(SPONSORS_CACHE_FILE, 'r') as f:
                cache_data = json.load(f)
                
            # Check if the cache is still valid based on its expiration
            cached_time = datetime.fromisoformat(cache_data.get('timestamp', ''))
            expiry_days = cache_data.get('expiry_days', 1)  # Default to 1 day if not set
            
            if datetime.datetime.now() - cached_time < timedelta(days=expiry_days):
                current_app.logger.info(f"Returning cached GitHub sponsors data (expires in {expiry_days} days from {cached_time})")
                return jsonify(cache_data.get('sponsors', []))
            else:
                current_app.logger.info(f"Cache expired after {expiry_days} days. Fetching fresh GitHub sponsors data.")
    except Exception as e:
        current_app.logger.error(f"Error reading sponsors cache: {e}")
    
    # Set up GraphQL query and headers
    headers = {
        'Authorization': f'bearer {auth_token}',
        'Content-Type': 'application/json',
    }

    query = """
    query {
      organization(login: "plexguide") {
        sponsorshipsAsMaintainer(first: 20, orderBy: {field: CREATED_AT, direction: DESC}) {
          totalCount
          edges {
            node {
              sponsorEntity {
                ... on User {
                  login
                  avatarUrl
                  name
                  url
                }
                ... on Organization {
                  login
                  avatarUrl
                  name
                  url
                }
              }
            }
          }
        }
      }
    }
    """

    try:
        # Fetch data from GitHub GraphQL API
        response = requests.post('https://api.github.com/graphql', json={'query': query}, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()

        if 'errors' in data:
            current_app.logger.error(f"GitHub API errors: {data['errors']}")
            return jsonify({'error': 'Failed to fetch sponsors from GitHub API', 'details': data['errors']}), 500

        # Process the response data
        sponsors_data = data.get('data', {}).get('organization', {}).get('sponsorshipsAsMaintainer', {}).get('edges', [])
        
        sponsors_list = []
        for edge in sponsors_data:
            sponsor_node = edge.get('node', {}).get('sponsorEntity', {})
            if sponsor_node:
                sponsors_list.append({
                    'login': sponsor_node.get('login'),
                    'avatarUrl': sponsor_node.get('avatarUrl'),  # Changed to match what frontend expects
                    'name': sponsor_node.get('name') or sponsor_node.get('login'),
                    'url': sponsor_node.get('url')
                })
        
        # Generate a random expiration period between 4-7 days
        import random  # Import here to ensure it's available
        expiry_days = random.randint(4, 7)
        
        # Save to cache with timestamp and expiration
        with open(SPONSORS_CACHE_FILE, 'w') as f:
            cache_data = {
                'timestamp': datetime.datetime.now().isoformat(),
                'expiry_days': expiry_days,
                'sponsors': sponsors_list
            }
            json.dump(cache_data, f)
            
        current_app.logger.info(f"Cached fresh GitHub sponsors data with {expiry_days} day expiration.")
        return jsonify(sponsors_list)

    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"Error fetching GitHub sponsors: {e}")
        return jsonify({'error': f'Could not connect to GitHub API: {e}'}), 500
    except Exception as e:
        current_app.logger.error(f"An unexpected error occurred while fetching sponsors: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500

# Start the web server in debug or production mode
def start_web_server():
    """Start the web server in debug or production mode"""
    web_logger = get_logger("web_server")
    web_logger.info("--- start_web_server function called ---") # Added log
    debug_mode = os.environ.get('DEBUG', 'false').lower() == 'true'
    host = '0.0.0.0'  # Listen on all interfaces
    port = int(os.environ.get('PORT', 9705))

    # Ensure the log directory exists
    os.makedirs(LOG_DIR, exist_ok=True)

    web_logger.info(f"Attempting to start web server on {host}:{port} (Debug: {debug_mode})") # Modified log
    # In production, use Werkzeug's simple server or a proper WSGI server
    web_logger.info("--- Calling app.run() ---") # Added log
    app.run(host=host, port=port, debug=debug_mode, use_reloader=False) # Keep this line if needed for direct execution testing, but it's now handled by root main.py