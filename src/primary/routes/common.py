#!/usr/bin/env python3
"""
Common routes blueprint for Huntarr web interface
"""

import os
import json
import base64
import io
import qrcode
import pyotp
import logging
# Add render_template, send_from_directory, session
from flask import Blueprint, request, jsonify, make_response, redirect, url_for, current_app, render_template, send_from_directory, session, send_file
from ..auth import (
    verify_user, create_session, get_username_from_session, SESSION_COOKIE_NAME,
    change_username as auth_change_username, change_password as auth_change_password,
    validate_password_strength, logout, verify_session, disable_2fa_with_password_and_otp,
    user_exists, create_user, generate_2fa_secret, verify_2fa_code, is_2fa_enabled # Add missing auth imports
)
from ..utils.logger import logger # Ensure logger is imported
from .. import settings_manager # Import settings_manager
from ..cycle_tracker import _SLEEP_DATA_PATH # Import sleep data path

common_bp = Blueprint('common', __name__)

# --- Static File Serving --- #

@common_bp.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory(common_bp.static_folder, filename)

@common_bp.route('/favicon.ico')
def favicon():
    return send_from_directory(common_bp.static_folder, 'favicon.ico', mimetype='image/vnd.microsoft.icon')

@common_bp.route('/logo/<path:filename>')
def logo_files(filename):
    logo_dir = os.path.join(common_bp.static_folder, 'logo')
    return send_from_directory(logo_dir, filename)

# --- API Routes --- #

@common_bp.route('/api/sleep.json', methods=['GET'])
def api_get_sleep_json():
    """API endpoint to directly serve the sleep.json file for frontend access"""
    try:
        if os.path.exists(_SLEEP_DATA_PATH):
            # Add CORS headers to allow any origin to access this resource
            response = send_file(_SLEEP_DATA_PATH, mimetype='application/json')
            response.headers.add('Access-Control-Allow-Origin', '*')
            return response
        else:
            # If file doesn't exist, create it and return empty object
            logger.info(f"[API] sleep.json not found at {_SLEEP_DATA_PATH}, creating it")
            os.makedirs(os.path.dirname(_SLEEP_DATA_PATH), exist_ok=True)
            with open(_SLEEP_DATA_PATH, 'w') as f:
                json.dump({}, f, indent=2)
            return jsonify({}), 200
    except Exception as e:
        logger.error(f"Error serving sleep.json from {_SLEEP_DATA_PATH}: {e}")
        # Return empty object instead of error to prevent UI breaking
        return jsonify({}), 200

# --- Authentication Routes --- #

@common_bp.route('/login', methods=['GET', 'POST'])
def login_route():
    if request.method == 'POST':
        try: # Wrap the POST logic in a try block for better error handling
            data = request.json
            username = data.get('username')
            password = data.get('password')
            twoFactorCode = data.get('twoFactorCode') # Changed from 'otp_code' to match frontend form

            if not username or not password:
                 logger.warning("Login attempt with missing username or password.")
                 return jsonify({"success": False, "error": "Username and password are required"}), 400

            # Call verify_user which now returns (auth_success, needs_2fa)
            auth_success, needs_2fa = verify_user(username, password, twoFactorCode)
            
            logger.debug(f"Auth result for '{username}': success={auth_success}, needs_2fa={needs_2fa}")

            if auth_success:
                # User is authenticated (password correct, and 2FA if needed was correct)
                session_token = create_session(username)
                session[SESSION_COOKIE_NAME] = session_token # Store token in Flask session immediately
                response = jsonify({"success": True, "redirect": "./"}) # Add redirect URL
                response.set_cookie(SESSION_COOKIE_NAME, session_token, httponly=True, samesite='Lax', path='/') # Add path
                logger.info(f"User '{username}' logged in successfully.")
                return response
            elif needs_2fa:
                # Authentication failed *because* 2FA was required (or code was invalid)
                # The specific reason (missing vs invalid code) is logged in verify_user
                logger.warning(f"Login failed for '{username}': 2FA required or invalid.")
                logger.debug(f"Returning 2FA required response: {{\"success\": False, \"requires_2fa\": True, \"requiresTwoFactor\": True, \"error\": \"Invalid or missing 2FA code\"}}")
                
                # Use all common variations of the 2FA flag to ensure compatibility
                return jsonify({
                    "success": False, 
                    "requires_2fa": True, 
                    "requiresTwoFactor": True,
                    "requires2fa": True,
                    "requireTwoFactor": True,
                    "error": "Two-factor authentication code required"
                }), 401
            else:
                # Authentication failed for other reasons (e.g., wrong password, user not found)
                # Specific reason logged in verify_user
                logger.warning(f"Login failed for '{username}': Invalid credentials or other error.")
                return jsonify({"success": False, "error": "Invalid username or password"}), 401 # Use 401

        except Exception as e:
            logger.error(f"Unexpected error during login POST for user '{username if 'username' in locals() else 'unknown'}': {e}", exc_info=True)
            return jsonify({"success": False, "error": "An internal server error occurred during login."}), 500
    else:
        # GET request - show login page
        # If user already exists, show login, otherwise redirect to setup
        if not user_exists():
             logger.info("No user exists, redirecting to setup.")
             return redirect(url_for('common.setup'))
        logger.debug("Displaying login page.")
        return render_template('login.html')

@common_bp.route('/logout', methods=['POST'])
def logout_route():
    try:
        session_token = request.cookies.get(SESSION_COOKIE_NAME)
        if session_token:
            logger.info(f"Logging out session token: {session_token[:8]}...") # Log part of token
            logout(session_token) # Call the logout function from auth.py
        else:
            logger.warning("Logout attempt without session cookie.")

        response = jsonify({"success": True})
        # Ensure cookie deletion happens even if logout function had issues
        response.delete_cookie(SESSION_COOKIE_NAME, path='/', samesite='Lax') # Specify path and samesite
        logger.info("Logout successful, cookie deleted.")
        return response
    except Exception as e:
        logger.error(f"Error during logout: {e}", exc_info=True)
        # Return a JSON error response
        return jsonify({"success": False, "error": "An internal server error occurred during logout."}), 500

@common_bp.route('/setup', methods=['GET', 'POST'])
def setup():
    if user_exists(): # This function should now be defined via import
        # If a user already exists, redirect to login or home
        logger.info("Setup page accessed but user already exists. Redirecting to login.")
        return redirect(url_for('common.login_route'))

    if request.method == 'POST':
        username = None # Initialize username for logging in case of early failure
        try: # Add try block to catch potential errors during user creation
            data = request.json
            username = data.get('username')
            password = data.get('password')
            confirm_password = data.get('confirm_password')
            proxy_auth_bypass = data.get('proxy_auth_bypass', False)  # Get proxy auth bypass setting

            # Basic validation
            if not username or not password or not confirm_password:
                return jsonify({"success": False, "error": "Missing required fields"}), 400
            
            # Add username length validation
            if len(username.strip()) < 3:
                return jsonify({"success": False, "error": "Username must be at least 3 characters long"}), 400

            if password != confirm_password:
                return jsonify({"success": False, "error": "Passwords do not match"}), 400

            # Validate password strength using the backend function
            password_error = validate_password_strength(password)
            if password_error:
                return jsonify({"success": False, "error": password_error}), 400

            logger.info(f"Attempting to create user '{username}' during setup.")
            if create_user(username, password): # This function should now be defined via import
                # If proxy auth bypass is enabled, update general settings
                if proxy_auth_bypass:
                    try:
                        from src.primary import settings_manager
                        
                        # Load current general settings
                        general_settings = settings_manager.load_settings('general')
                        
                        # Update the proxy_auth_bypass setting
                        general_settings['proxy_auth_bypass'] = True
                        
                        # Save the updated settings
                        settings_manager.save_settings('general', general_settings)
                        logger.debug("Proxy auth bypass setting enabled during setup")
                    except Exception as e:
                        logger.error(f"Error saving proxy auth bypass setting: {e}", exc_info=True)
                
                # Automatically log in the user after setup
                logger.info(f"User '{username}' created successfully during setup. Creating session.")
                session_token = create_session(username)
                # Explicitly set username in Flask session - might not be needed if using token correctly
                # session['username'] = username
                session[SESSION_COOKIE_NAME] = session_token # Store token in session
                response = jsonify({"success": True})
                # Set cookie in the response
                response.set_cookie(SESSION_COOKIE_NAME, session_token, httponly=True, samesite='Lax', path='/') # Add path
                return response
            else:
                # create_user itself failed, but didn't raise an exception
                logger.error(f"create_user function returned False for user '{username}' during setup.")
                return jsonify({"success": False, "error": "Failed to create user (internal reason)"}), 500
        except Exception as e:
            # Catch any unexpected exception during the process
            logger.error(f"Unexpected error during setup POST for user '{username if username else 'unknown'}': {e}", exc_info=True)
            return jsonify({"success": False, "error": f"An unexpected server error occurred: {e}"}), 500
    else:
        # GET request - show setup page
        logger.info("Displaying setup page.")
        return render_template('setup.html') # This function should now be defined via import

# --- User Management API Routes --- #

@common_bp.route('/api/user/info', methods=['GET'])
def get_user_info_route():
    # Use session token to get username
    session_token = request.cookies.get(SESSION_COOKIE_NAME)
    username = get_username_from_session(session_token) # Use auth function

    if not username:
        logger.debug("Attempt to get user info failed: Not authenticated (no valid session).")
        return jsonify({"error": "Not authenticated"}), 401

    # Pass username to is_2fa_enabled
    two_fa_status = is_2fa_enabled(username) # This function should now be defined via import
    logger.debug(f"Retrieved user info for '{username}'. 2FA enabled: {two_fa_status}")
    return jsonify({"username": username, "is_2fa_enabled": two_fa_status})

@common_bp.route('/api/user/change-username', methods=['POST'])
def change_username_route():
    # Use session token to get username
    session_token = request.cookies.get(SESSION_COOKIE_NAME)
    current_username = get_username_from_session(session_token)

    if not current_username:
        logger.warning("Username change attempt failed: Not authenticated.")
        return jsonify({"error": "Not authenticated"}), 401

    data = request.json
    new_username = data.get('username')
    password = data.get('password') # Get password from request

    if not new_username or not password: # Check if password is provided
        return jsonify({"success": False, "error": "New username and current password are required"}), 400

    # Add username length validation
    if len(new_username.strip()) < 3:
        return jsonify({"success": False, "error": "Username must be at least 3 characters long"}), 400

    # Call the change_username function from auth.py
    if auth_change_username(current_username, new_username, password):
        # Update session? The session stores a token, not the username directly.
        # If the username is needed frequently, maybe re-create session or update session data if stored there.
        # For now, assume token remains valid.
        logger.info(f"Username changed successfully for '{current_username}' to '{new_username}'.")
        # Re-fetch username to confirm change for response? Or trust change_username?
        # Fetch updated info to send back
        updated_username = new_username # Assume success means it changed
        return jsonify({"success": True, "username": updated_username}) # Return new username
    else:
        logger.warning(f"Username change failed for '{current_username}'. Check logs in auth.py for details.")
        return jsonify({"success": False, "error": "Failed to change username. Check password or logs."}), 400

@common_bp.route('/api/user/change-password', methods=['POST'])
def change_password_route():
    # Use session token to get username - needed? change_password might not need it if single user
    session_token = request.cookies.get(SESSION_COOKIE_NAME)
    username = get_username_from_session(session_token) # Get username for logging

    if not username: # Check if session is valid even if function doesn't need username
         logger.warning("Password change attempt failed: Not authenticated.")
         return jsonify({"error": "Not authenticated"}), 401

    data = request.json
    current_password = data.get('current_password')
    new_password = data.get('new_password')

    if not current_password or not new_password:
        logger.warning(f"Password change attempt for user '{username}' failed: Missing current or new password.")
        return jsonify({"success": False, "error": "Current and new passwords are required"}), 400

    logger.info(f"Attempting to change password for user '{username}'.")
    # Pass username? change_password might not need it. Assuming it doesn't for now.
    if auth_change_password(current_password, new_password):
        logger.info(f"Password changed successfully for user '{username}'.")
        return jsonify({"success": True})
    else:
        logger.warning(f"Password change failed for user '{username}'. Check logs in auth.py for details.")
        return jsonify({"success": False, "error": "Failed to change password. Check current password or logs."}), 400

# --- 2FA Management API Routes --- #

@common_bp.route('/api/user/2fa/setup', methods=['POST'])
def setup_2fa():
    # Use session token to get username
    session_token = request.cookies.get(SESSION_COOKIE_NAME)
    username = get_username_from_session(session_token)

    if not username:
        logger.warning("2FA setup attempt failed: No username in session.") # Add logging
        return jsonify({"error": "Not authenticated"}), 401

    try:
        logger.info(f"Generating 2FA setup for user: {username}") # Add logging
        # Pass username to generate_2fa_secret
        secret, qr_code_data_uri = generate_2fa_secret(username) # This function should now be defined via import

        # Return secret and QR code data URI
        return jsonify({"success": True, "secret": secret, "qr_code_url": qr_code_data_uri}) # Match frontend expectation 'qr_code_url'

    except Exception as e:
        logger.error(f"Error during 2FA setup generation for user '{username}': {e}", exc_info=True)
        return jsonify({"success": False, "error": "Failed to generate 2FA setup information."}), 500

@common_bp.route('/api/user/2fa/verify', methods=['POST'])
def verify_2fa():
    # Use session token to get username
    session_token = request.cookies.get(SESSION_COOKIE_NAME)
    username = get_username_from_session(session_token)

    if not username:
        logger.warning("2FA verify attempt failed: No username in session.") # Add logging
        return jsonify({"error": "Not authenticated"}), 401

    data = request.json
    otp_code = data.get('code') # Match frontend key 'code'

    if not otp_code or len(otp_code) != 6 or not otp_code.isdigit(): # Add validation
        logger.warning(f"2FA verification for '{username}' failed: Invalid code format provided.")
        return jsonify({"success": False, "error": "Invalid or missing 6-digit OTP code"}), 400

    logger.info(f"Attempting to verify 2FA code for user '{username}'.")
    # Pass username to verify_2fa_code
    if verify_2fa_code(username, otp_code, enable_on_verify=True): # This function should now be defined via import
        logger.info(f"Successfully verified and enabled 2FA for user: {username}") # Add logging
        return jsonify({"success": True})
    else:
        # Reason logged in verify_2fa_code
        logger.warning(f"2FA verification failed for user: {username}. Check logs in auth.py.")
        return jsonify({"success": False, "error": "Invalid OTP code"}), 400 # Use 400 for bad request

@common_bp.route('/api/user/2fa/disable', methods=['POST'])
def disable_2fa_route():
    session_token = request.cookies.get(SESSION_COOKIE_NAME)
    username = get_username_from_session(session_token)

    if not username:
        logger.warning("2FA disable attempt failed: Not authenticated.")
        return jsonify({"error": "Not authenticated"}), 401

    data = request.json
    password = data.get('password')
    otp_code = data.get('code')

    # Require BOTH password and OTP code
    if not password or not otp_code:
         logger.warning(f"2FA disable attempt for '{username}' failed: Missing password or OTP code.")
         return jsonify({"success": False, "error": "Both password and current OTP code are required to disable 2FA"}), 400

    if not (len(otp_code) == 6 and otp_code.isdigit()):
        logger.warning(f"2FA disable attempt for '{username}' failed: Invalid OTP code format.")
        return jsonify({"success": False, "error": "Invalid 6-digit OTP code format"}), 400

    # Call a function that verifies both password and OTP
    if disable_2fa_with_password_and_otp(username, password, otp_code):
        logger.info(f"2FA disabled successfully for user '{username}' using password and OTP.")
        return jsonify({"success": True})
    else:
        # Reason logged in disable_2fa_with_password_and_otp
        logger.warning(f"Failed to disable 2FA for user '{username}' using password and OTP. Check logs.")
        # Provide a more specific error if possible, otherwise generic
        # The auth function should log the specific reason (bad pass, bad otp)
        return jsonify({"success": False, "error": "Failed to disable 2FA. Invalid password or OTP code."}), 400

# --- Theme Setting Route ---
@common_bp.route('/api/settings/theme', methods=['POST'])
def set_theme():
    # Authentication check
    session_token = request.cookies.get(SESSION_COOKIE_NAME)
    if not verify_session(session_token):
         logger.warning("Theme setting attempt failed: Not authenticated.")
         return jsonify({"error": "Unauthorized"}), 401

    try:
        data = request.json
        dark_mode = data.get('dark_mode')

        if dark_mode is None or not isinstance(dark_mode, bool):
            logger.warning("Invalid theme setting received.")
            return jsonify({"success": False, "error": "Invalid 'dark_mode' value"}), 400

        # Here you would typically save this preference to a user profile or global setting
        # For now, just log it. A real implementation would persist this.
        username = get_username_from_session(session_token) # Get username for logging
        logger.info(f"User '{username}' set dark mode preference to: {dark_mode}")

        # Example: Saving to a hypothetical global config (replace with actual persistence)
        # global_settings = settings_manager.load_global_settings() # Assuming such a function exists
        # global_settings['ui']['dark_mode'] = dark_mode
        # settings_manager.save_global_settings(global_settings) # Assuming such a function exists

        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"Error setting theme preference: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Failed to set theme preference"}), 500

# --- Local Access Bypass Status API Route --- #

@common_bp.route('/api/get_local_access_bypass_status', methods=['GET'])
def get_local_access_bypass_status_route():
    """API endpoint to get the status of the local network authentication bypass setting.
    Also checks proxy_auth_bypass to hide user menu in both bypass modes."""
    try:
        # Get both bypass settings from the 'general' section, default to False if not found
        local_access_bypass = settings_manager.get_setting('general', 'local_access_bypass', False)
        proxy_auth_bypass = settings_manager.get_setting('general', 'proxy_auth_bypass', False)
        
        # Enable if either bypass mode is active
        bypass_enabled = local_access_bypass or proxy_auth_bypass
        
        logger.debug(f"Retrieved bypass status: local={local_access_bypass}, proxy={proxy_auth_bypass}, combined={bypass_enabled}")
        # Return status in the format expected by the frontend
        return jsonify({"isEnabled": bypass_enabled})
    except Exception as e:
        logger.error(f"Error retrieving local_access_bypass status: {e}", exc_info=True)
        # Return a generic error to the client
        return jsonify({"error": "Failed to retrieve bypass status"}), 500

# --- Stats Management API Routes --- #
@common_bp.route('/api/stats', methods=['GET'])
def get_stats_api():
    """API endpoint to get media statistics"""
    try:
        # Import here to avoid circular imports
        from ..stats_manager import get_stats
        
        # Get stats from stats_manager
        stats = get_stats()
        logger.debug(f"Retrieved stats for API response: {stats}")
        
        # Return success response with stats
        return jsonify({"success": True, "stats": stats})
    except Exception as e:
        logger.error(f"Error retrieving stats: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500

@common_bp.route('/api/stats/reset', methods=['POST'])
def reset_stats_api():
    """API endpoint to reset media statistics"""
    try:
        # Import here to avoid circular imports
        from ..stats_manager import reset_stats
        
        # Check if authenticated
        session_token = request.cookies.get(SESSION_COOKIE_NAME)
        if not verify_session(session_token):
            logger.warning("Stats reset attempt failed: Not authenticated.")
            return jsonify({"error": "Unauthorized"}), 401
            
        # Get app type from request if provided
        data = request.json or {}
        app_type = data.get('app_type')  # None will reset all
        
        if app_type is not None and app_type not in ["sonarr", "radarr", "lidarr", "readarr", "whisparr"]:
            logger.warning(f"Invalid app_type for stats reset: {app_type}")
            return jsonify({"success": False, "error": "Invalid app_type"}), 400
            
        # Reset stats
        if reset_stats(app_type):
            message = f"Reset statistics for {app_type}" if app_type else "Reset all statistics"
            logger.info(message)
            return jsonify({"success": True, "message": message})
        else:
            error_msg = f"Failed to reset statistics for {app_type}" if app_type else "Failed to reset all statistics"
            logger.error(error_msg)
            return jsonify({"success": False, "error": error_msg}), 500
    except Exception as e:
        logger.error(f"Error resetting stats: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500

# Ensure all routes previously in this file that interact with settings
# are either moved to web_server.py or updated here using the new settings_manager functions.

# REMOVED DUPLICATE BLUEPRINT DEFINITION AND CONFLICTING ROUTES BELOW THIS LINE
