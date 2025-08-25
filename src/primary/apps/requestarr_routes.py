"""
Requestarr routes for media search and request functionality
"""

from flask import Blueprint, request, jsonify
import logging
from src.primary.apps.requestarr import requestarr_api

logger = logging.getLogger(__name__)

# Create blueprint
requestarr_bp = Blueprint('requestarr', __name__, url_prefix='/api/requestarr')

@requestarr_bp.route('/search', methods=['GET'])
def search_media():
    """Search for media using TMDB with availability checking"""
    try:
        query = request.args.get('q', '').strip()
        app_type = request.args.get('app_type', '').strip()
        instance_name = request.args.get('instance_name', '').strip()
        
        if not query:
            return jsonify({'results': []})
        
        if not app_type or not instance_name:
            return jsonify({'error': 'App type and instance name are required'}), 400
        
        results = requestarr_api.search_media_with_availability(query, app_type, instance_name)
        return jsonify({'results': results})
        
    except Exception as e:
        logger.error(f"Error searching media: {e}")
        return jsonify({'error': 'Search failed'}), 500

@requestarr_bp.route('/search/stream', methods=['GET'])
def search_media_stream():
    """Stream search results as they become available"""
    from flask import Response
    import json
    
    try:
        query = request.args.get('q', '').strip()
        app_type = request.args.get('app_type', '').strip()
        instance_name = request.args.get('instance_name', '').strip()
        
        if not query:
            return jsonify({'error': 'Query parameter is required'}), 400
        
        if not app_type or not instance_name:
            return jsonify({'error': 'App type and instance name are required'}), 400
        
        def generate():
            try:
                for result in requestarr_api.search_media_with_availability_stream(query, app_type, instance_name):
                    yield f"data: {json.dumps(result)}\n\n"
            except Exception as e:
                logger.error(f"Error in streaming search: {e}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
        
        return Response(generate(), mimetype='text/plain')
        
    except Exception as e:
        logger.error(f"Error setting up streaming search: {e}")
        return jsonify({'error': 'Search failed'}), 500

@requestarr_bp.route('/instances', methods=['GET'])
def get_enabled_instances():
    """Get enabled Sonarr and Radarr instances"""
    try:
        instances = requestarr_api.get_enabled_instances()
        return jsonify(instances)
    except Exception as e:
        logger.error(f"Error getting instances: {e}")
        return jsonify({'error': 'Failed to get instances'}), 500

@requestarr_bp.route('/request', methods=['POST'])
def request_media():
    """Request media through app instance"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['tmdb_id', 'media_type', 'title', 'app_type', 'instance_name']
        for field in required_fields:
            if field not in data:
                return jsonify({'success': False, 'error': f'Missing required field: {field}'}), 400
        
        result = requestarr_api.request_media(
            tmdb_id=data['tmdb_id'],
            media_type=data['media_type'],
            title=data['title'],
            year=data.get('year'),
            overview=data.get('overview', ''),
            poster_path=data.get('poster_path', ''),
            backdrop_path=data.get('backdrop_path', ''),
            app_type=data['app_type'],
            instance_name=data['instance_name']
        )
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Error requesting media: {e}")
        return jsonify({'success': False, 'error': 'Request failed'}), 500

@requestarr_bp.route('/requests', methods=['GET'])
def get_requests():
    """Get paginated list of requests"""
    try:
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 20))
        
        requests_data = requestarr_api.db.get_requests(page, page_size)
        return jsonify(requests_data)
        
    except Exception as e:
        logger.error(f"Error getting requests: {e}")
        return jsonify({'error': 'Failed to get requests'}), 500

@requestarr_bp.route('/series/<int:tmdb_id>/details', methods=['GET'])
def get_series_details(tmdb_id):
    """Get detailed season and episode information for a TV series"""
    try:
        app_type = request.args.get('app_type')
        instance_name = request.args.get('instance_name')
        
        if not app_type or not instance_name:
            return jsonify({'error': 'App type and instance name are required'}), 400
        
        if app_type != 'sonarr':
            return jsonify({'error': 'Series details only available for Sonarr instances'}), 400
        
        details = requestarr_api.get_series_details(tmdb_id, app_type, instance_name)
        return jsonify(details)
        
    except Exception as e:
        logger.error(f"Error getting series details: {e}")
        return jsonify({'error': 'Failed to get series details'}), 500

# Requestarr is always enabled with hardcoded TMDB API key
logger.info("Requestarr initialized with hardcoded TMDB API key") 