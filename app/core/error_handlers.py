"""
Error handlers for SmartPark application
"""
import logging
from flask import render_template, jsonify, request
from werkzeug.exceptions import HTTPException

logger = logging.getLogger(__name__)

def register_error_handlers(app):
    """Register error handlers with the Flask app"""
    
    @app.errorhandler(400)
    def bad_request(error):
        logger.warning(f"Bad request from {request.remote_addr}: {error}")
        if request.is_json:
            return jsonify({
                'success': False,
                'error': 'Bad Request',
                'message': 'The request could not be understood by the server.'
            }), 400
        return render_template('errors/400.html'), 400
    
    @app.errorhandler(401)
    def unauthorized(error):
        logger.warning(f"Unauthorized access attempt from {request.remote_addr}: {error}")
        if request.is_json:
            return jsonify({
                'success': False,
                'error': 'Unauthorized',
                'message': 'Authentication required.'
            }), 401
        return render_template('errors/401.html'), 401
    
    @app.errorhandler(403)
    def forbidden(error):
        logger.warning(f"Forbidden access attempt from {request.remote_addr}: {error}")
        if request.is_json:
            return jsonify({
                'success': False,
                'error': 'Forbidden',
                'message': 'You do not have permission to access this resource.'
            }), 403
        return render_template('errors/403.html'), 403
    
    @app.errorhandler(404)
    def not_found(error):
        logger.info(f"404 error from {request.remote_addr}: {request.url}")
        if request.is_json:
            return jsonify({
                'success': False,
                'error': 'Not Found',
                'message': 'The requested resource was not found.'
            }), 404
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(405)
    def method_not_allowed(error):
        logger.warning(f"Method not allowed from {request.remote_addr}: {request.method} {request.url}")
        if request.is_json:
            return jsonify({
                'success': False,
                'error': 'Method Not Allowed',
                'message': 'The method is not allowed for the requested URL.'
            }), 405
        return render_template('errors/405.html'), 405
    
    @app.errorhandler(413)
    def request_entity_too_large(error):
        logger.warning(f"Request too large from {request.remote_addr}")
        if request.is_json:
            return jsonify({
                'success': False,
                'error': 'Request Too Large',
                'message': 'The uploaded file is too large.'
            }), 413
        return render_template('errors/413.html'), 413
    
    @app.errorhandler(429)
    def ratelimit_handler(error):
        logger.warning(f"Rate limit exceeded from {request.remote_addr}")
        if request.is_json:
            return jsonify({
                'success': False,
                'error': 'Too Many Requests',
                'message': 'Rate limit exceeded. Please try again later.'
            }), 429
        return render_template('errors/429.html'), 429
    
    @app.errorhandler(500)
    def internal_server_error(error):
        logger.error(f"Internal server error: {error}", exc_info=True)
        if request.is_json:
            return jsonify({
                'success': False,
                'error': 'Internal Server Error',
                'message': 'An internal server error occurred.'
            }), 500
        return render_template('errors/500.html'), 500
    
    @app.errorhandler(Exception)
    def handle_exception(error):
        """Handle unexpected exceptions"""
        if isinstance(error, HTTPException):
            return error
        
        logger.error(f"Unhandled exception: {error}", exc_info=True)
        
        if request.is_json:
            return jsonify({
                'success': False,
                'error': 'Internal Server Error',
                'message': 'An unexpected error occurred.'
            }), 500
        
        return render_template('errors/500.html'), 500