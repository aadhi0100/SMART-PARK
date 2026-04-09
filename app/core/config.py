"""
Secure configuration management for SmartPark
"""
import os
import secrets
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class Config:
    """Base configuration class"""
    
    # Security settings
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = 3600  # 1 hour
    
    # Database settings
    DB_PATH = os.environ.get('DB_PATH', 'database/parking.db')
    
    # Email settings
    SMTP_HOST = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
    SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
    SMTP_USER = os.environ.get('SMTP_USER', '')
    SMTP_PASS = os.environ.get('SMTP_PASS', '')
    
    # Application settings
    APP_BASE_URL = os.environ.get('APP_BASE_URL', 'http://localhost:5003')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file upload
    
    # Security settings
    BCRYPT_LOG_ROUNDS = 12
    PASSWORD_MIN_LENGTH = 8
    PASSWORD_MAX_LENGTH = 128
    USERNAME_MIN_LENGTH = 3
    USERNAME_MAX_LENGTH = 50
    
    # Rate limiting
    RATELIMIT_STORAGE_URL = "memory://"
    RATELIMIT_DEFAULT = "100 per hour"
    
    # OAuth settings
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')
    
    @staticmethod
    def validate_config():
        """Validate configuration settings"""
        issues = []
        
        # Check critical settings
        if not Config.SECRET_KEY:
            issues.append("SECRET_KEY is not set")
        
        if len(Config.SECRET_KEY) < 32:
            issues.append("SECRET_KEY should be at least 32 characters")
        
        # Check email configuration
        if Config.SMTP_USER and not Config.SMTP_PASS:
            issues.append("SMTP_PASS is required when SMTP_USER is set")
        
        # Check OAuth configuration
        if Config.GOOGLE_CLIENT_ID and not Config.GOOGLE_CLIENT_SECRET:
            issues.append("GOOGLE_CLIENT_SECRET is required when GOOGLE_CLIENT_ID is set")
        
        if issues:
            logger.warning("Configuration issues found: %s", "; ".join(issues))
        
        return len(issues) == 0

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    SESSION_COOKIE_SECURE = False  # Allow HTTP in development
    
class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    
    # Enhanced security for production
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Strict'
    
    # Stricter rate limiting
    RATELIMIT_DEFAULT = "50 per hour"

class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    DB_PATH = ':memory:'  # In-memory database for testing
    SECRET_KEY = 'test-secret-key-do-not-use-in-production'

def get_config() -> Config:
    """Get configuration based on environment"""
    env = os.environ.get('FLASK_ENV', 'development').lower()
    
    if env == 'production':
        return ProductionConfig()
    elif env == 'testing':
        return TestingConfig()
    else:
        return DevelopmentConfig()

def setup_logging():
    """Setup secure logging configuration"""
    log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()
    
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('smartpark.log', mode='a')
        ]
    )
    
    # Set specific log levels for different modules
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)

def check_environment():
    """Check if all required environment variables are set"""
    required_vars = []
    optional_vars = [
        'SMTP_USER', 'SMTP_PASS', 'GOOGLE_CLIENT_ID', 
        'GOOGLE_CLIENT_SECRET', 'APP_BASE_URL'
    ]
    
    missing_required = [var for var in required_vars if not os.environ.get(var)]
    missing_optional = [var for var in optional_vars if not os.environ.get(var)]
    
    if missing_required:
        logger.error("Missing required environment variables: %s", ", ".join(missing_required))
        return False
    
    if missing_optional:
        logger.info("Optional environment variables not set: %s", ", ".join(missing_optional))
    
    return True