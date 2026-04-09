import logging
import os
import secrets
from collections import defaultdict
from time import time
from datetime import timedelta

from dotenv import load_dotenv
load_dotenv()

from flask import Flask, jsonify, request, redirect, url_for, session
from .core.database import init_db
from .core.config import get_config, setup_logging, check_environment
from .core.error_handlers import register_error_handlers

logger = logging.getLogger(__name__)

_rate_store = defaultdict(list)

def create_app():
    # Setup logging first
    setup_logging()
    
    # Check environment
    check_environment()
    
    app = Flask(__name__)
    
    # Load configuration
    config = get_config()
    app.config.from_object(config)
    
    # Validate configuration
    config.validate_config()

    secret_key = os.environ.get('SECRET_KEY', '')
    if not secret_key or secret_key == 'replace-with-a-long-random-secret-key':
        secret_key = secrets.token_hex(32)
        logger.warning("SECRET_KEY not set — using a random key. Sessions will reset on restart.")
    app.secret_key = secret_key
    
    # Enhanced security configuration
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['SESSION_COOKIE_SECURE'] = os.environ.get('RENDER', False) or os.environ.get('SESSION_COOKIE_SECURE', False)
    app.permanent_session_lifetime = timedelta(hours=1)

    app.config['GOOGLE_CLIENT_ID'] = os.environ.get('GOOGLE_CLIENT_ID', '')
    app.config['GOOGLE_CLIENT_SECRET'] = os.environ.get('GOOGLE_CLIENT_SECRET', '')
    
    # Security headers
    @app.after_request
    def security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        if app.config.get('SESSION_COOKIE_SECURE'):
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline' cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' cdn.jsdelivr.net; img-src 'self' data: https:; font-src 'self' cdn.jsdelivr.net;"
        return response

    from .auth.routes import auth_bp
    from .auth.oauth import oauth_bp, init_oauth
    from .booking.routes import booking_bp
    from .admin.routes import admin_bp
    from .map.routes import map_bp
    from .core.routes import core_bp

    init_oauth(app)
    
    # Register error handlers
    register_error_handlers(app)

    app.register_blueprint(core_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(oauth_bp, url_prefix='/auth')
    app.register_blueprint(booking_bp, url_prefix='/booking')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(map_bp, url_prefix='/map')

    @app.before_request
    def rate_limit_bookings():
        """Enhanced rate limiting with security logging"""
        if request.method == 'POST' and '/booking/book/' in request.path:
            ip = request.remote_addr
            now = time()
            _rate_store[ip] = [t for t in _rate_store[ip] if now - t < 60]
            if len(_rate_store[ip]) >= 10:
                logger.warning(f"Rate limit exceeded for IP {ip} on booking endpoint")
                return jsonify({'error': 'Too many requests. Please wait a minute.'}), 429
            _rate_store[ip].append(now)
    
    # Root route with security check
    @app.route('/')
    def index():
        if 'username' in session:
            return redirect(url_for('core.dashboard', username=session['username']))
        return redirect(url_for('auth.login'))

    with app.app_context():
        init_db()

    return app
