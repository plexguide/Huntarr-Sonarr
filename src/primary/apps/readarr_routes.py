#!/usr/bin/env python3

from flask import Blueprint, request, jsonify
import datetime, os, requests
from src.primary import keys_manager
from src.primary.state import get_state_file_path, reset_state_file
from src.primary.utils.logger import get_logger
import traceback
import socket
from urllib.parse import urlparse
from src.primary.utils.ssl_settings import get_ssl_verify

readarr_bp = Blueprint('readarr', __name__)
readarr_logger = get_logger("readarr")

# Get SSL verification setting
ssl_verify = get_ssl_verify()

# Make sure we're using the correct state files
PROCESSED_MISSING_FILE = get_state_file_path("readarr", "processed_missing") 
PROCESSED_UPGRADES_FILE = get_state_file_path("readarr", "processed_upgrades")

@readarr_bp.route('/test-connection', methods=['POST'])
def test_connection():
    """Test connection to a Readarr API instance"""
    data = request.json
    api_url = data.get('api_url')
    api_key = data.get('api_key')
    
    if not api_url or not api_key:
        return jsonify({"success": False, "message": "API URL and API Key are required"}), 400
        
    readarr_logger.info(f"Testing connection to Readarr API at {api_url}")
    
    # Validate URL format
    if not (api_url.startswith('http://') or api_url.startswith('https://')):
        error_msg = "API URL must start with http:// or https://"
        readarr_logger.error(error_msg)
        return jsonify({"success": False, "message": error_msg}), 400
    
    # For Readarr, use api/v1
    url = f"{api_url}/api/v1/system/status"
    headers = {
        "X-Api-Key": api_key,
        "Content-Type": "application/json"
    }
    
    try:
        # First check if the host is reachable at all
        parsed_url = urlparse(api_url)
        hostname = parsed_url.hostname
        port = parsed_url.port or (443 if parsed_url.scheme == 'https' else 80)
        
        # Try to establish a socket connection first to provide a better error message for connection issues
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)  # Short timeout for quick feedback
            result = sock.connect_ex((hostname, port))
            sock.close()
            
            if result != 0:
                error_msg = f"Connection refused - Unable to connect to {hostname}:{port}. Please check if the server is running and the port is correct."
                readarr_logger.error(error_msg)
                return jsonify({"success": False, "message": error_msg}), 404
        except socket.gaierror:
            error_msg = f"DNS resolution failed - Cannot resolve hostname: {hostname}. Please check your URL."
            readarr_logger.error(error_msg)
            return jsonify({"success": False, "message": error_msg}), 404
        except Exception as e:
            # Log the socket testing error but continue with the full request
            readarr_logger.debug(f"Socket test error, continuing with full request: {str(e)}")
            
        # Now proceed with the actual API request
        response = requests.get(url, headers=headers, timeout=10, verify=ssl_verify)
        
        # For HTTP errors, provide more specific feedback
        if response.status_code == 401:
            error_msg = "Authentication failed: Invalid API key"
            readarr_logger.error(error_msg)
            return jsonify({"success": False, "message": error_msg}), 401
        elif response.status_code == 403:
            error_msg = "Access forbidden: Check API key permissions"
            readarr_logger.error(error_msg)
            return jsonify({"success": False, "message": error_msg}), 403
        elif response.status_code == 404:
            error_msg = "API endpoint not found: This doesn't appear to be a valid Readarr server. Check your URL."
            readarr_logger.error(error_msg)
            return jsonify({"success": False, "message": error_msg}), 404
        elif response.status_code >= 500:
            error_msg = f"Readarr server error (HTTP {response.status_code}): The Readarr server is experiencing issues"
            readarr_logger.error(error_msg)
            return jsonify({"success": False, "message": error_msg}), response.status_code
            
        # Raise for other HTTP errors
        response.raise_for_status()
        
        try:
            response_data = response.json()
            version = response_data.get('version', 'unknown')
            readarr_logger.info(f"Successfully connected to Readarr API version: {version}")
            
            return jsonify({
                "success": True,
                "message": "Successfully connected to Readarr API",
                "version": version
            })
        except ValueError:
            error_msg = "Invalid JSON response from Readarr API - This doesn't appear to be a valid Readarr server"
            readarr_logger.error(f"{error_msg}. Response content: {response.text[:200]}")
            return jsonify({"success": False, "message": error_msg}), 500
            
    except requests.exceptions.ConnectionError as e:
        # Handle different types of connection errors
        error_details = str(e)
        if "Connection refused" in error_details:
            error_msg = f"Connection refused - Readarr is not running on {api_url} or the port is incorrect"
        elif "Name or service not known" in error_details or "getaddrinfo failed" in error_details:
            error_msg = f"DNS resolution failed - Cannot find host '{urlparse(api_url).hostname}'. Check your URL."
        else:
            error_msg = f"Connection error - Check if Readarr is running: {error_details}"
            
        readarr_logger.error(error_msg)
        return jsonify({"success": False, "message": error_msg}), 404
    except requests.exceptions.Timeout:
        error_msg = f"Connection timed out - Readarr took too long to respond"
        readarr_logger.error(error_msg)
        return jsonify({"success": False, "message": error_msg}), 504
    except requests.exceptions.RequestException as e:
        error_msg = f"Connection test failed: {str(e)}"
        readarr_logger.error(error_msg)
        return jsonify({"success": False, "message": error_msg}), 500
