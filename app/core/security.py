"""
Security utilities for input validation and sanitization
"""
import re
import html
import logging
from typing import Optional, Union
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

def sanitize_input(value: str, max_length: int = 255, allow_html: bool = False) -> str:
    """Sanitize user input to prevent XSS and other attacks"""
    if not isinstance(value, str):
        return ""
    
    # Trim whitespace
    value = value.strip()
    
    # Limit length
    if len(value) > max_length:
        value = value[:max_length]
    
    # HTML escape if not allowing HTML
    if not allow_html:
        value = html.escape(value)
    
    return value

def validate_email(email: str) -> bool:
    """Validate email format with comprehensive checks"""
    if not email or not isinstance(email, str):
        return False
    
    # Basic length check
    if len(email) > 254 or len(email) < 5:
        return False
    
    # RFC 5322 compliant regex (simplified)
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    if not re.match(pattern, email):
        return False
    
    # Additional checks
    local, domain = email.rsplit('@', 1)
    
    # Local part checks
    if len(local) > 64 or len(local) < 1:
        return False
    
    # Domain part checks
    if len(domain) > 253 or len(domain) < 4:
        return False
    
    # No consecutive dots
    if '..' in email:
        return False
    
    return True

def validate_username(username: str) -> tuple[bool, str]:
    """Validate username with detailed error messages"""
    if not username or not isinstance(username, str):
        return False, "Username is required"
    
    username = username.strip()
    
    if len(username) < 3:
        return False, "Username must be at least 3 characters long"
    
    if len(username) > 50:
        return False, "Username must be less than 50 characters"
    
    # Allow alphanumeric, underscore, hyphen, and dot
    if not re.match(r'^[a-zA-Z0-9._-]+$', username):
        return False, "Username can only contain letters, numbers, dots, hyphens, and underscores"
    
    # Must start with alphanumeric
    if not username[0].isalnum():
        return False, "Username must start with a letter or number"
    
    # Reserved usernames (only block system-level names, not 'admin')
    reserved = ['root', 'system', 'api', 'www', 'mail', 'ftp']
    if username.lower() in reserved:
        return False, "This username is reserved"
    
    return True, ""

def validate_vehicle_plate(plate: str) -> tuple[bool, str]:
    """Validate vehicle plate number"""
    if not plate:
        return True, ""  # Plate is optional
    
    if not isinstance(plate, str):
        return False, "Invalid plate format"
    
    plate = plate.strip().upper()
    
    if len(plate) < 4 or len(plate) > 20:
        return False, "Plate number must be between 4-20 characters"
    
    # Allow only alphanumeric characters
    if not re.match(r'^[A-Z0-9]+$', plate):
        return False, "Plate number can only contain letters and numbers"
    
    return True, ""

def validate_duration(duration: Union[str, int]) -> tuple[bool, int, str]:
    """Validate parking duration"""
    try:
        duration_int = int(duration)
        if duration_int < 1:
            return False, 1, "Duration must be at least 1 hour"
        if duration_int > 24:
            return False, 24, "Duration cannot exceed 24 hours"
        return True, duration_int, ""
    except (ValueError, TypeError):
        return False, 1, "Invalid duration format"

def validate_vehicle_type(vehicle_type: str, allowed_types: list) -> tuple[bool, str]:
    """Validate vehicle type against allowed types"""
    if not vehicle_type or not isinstance(vehicle_type, str):
        return False, "Vehicle type is required"
    
    vehicle_type = vehicle_type.strip()
    
    if vehicle_type not in allowed_types:
        return False, f"Vehicle type must be one of: {', '.join(allowed_types)}"
    
    return True, ""

def validate_slot_id(slot_id: str) -> tuple[bool, str]:
    """Validate parking slot ID format"""
    if not slot_id or not isinstance(slot_id, str):
        return False, "Slot ID is required"
    
    slot_id = slot_id.strip().upper()
    
    # Expected format: A1, B2, etc.
    if not re.match(r'^([A-E][1-9]|[A-E]10)$', slot_id):
        return False, "Invalid slot ID format (expected: A1-E10)"
    
    return True, ""

def validate_payment_method(method: str) -> tuple[bool, str]:
    """Validate payment method"""
    allowed_methods = ['Cash', 'UPI', 'Card', 'Wallet']
    
    if not method or not isinstance(method, str):
        return False, "Payment method is required"
    
    method = method.strip()
    
    if method not in allowed_methods:
        return False, f"Payment method must be one of: {', '.join(allowed_methods)}"
    
    return True, ""

def sanitize_sql_input(value: str) -> str:
    """Additional SQL injection protection (though we use parameterized queries)"""
    if not isinstance(value, str):
        return ""
    
    # Remove potentially dangerous SQL keywords and characters
    dangerous_patterns = [
        r'(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|UNION)\b)',
        r'(--|/\*|\*/)',
        r'(\bOR\b.*=.*=)',
        r'(\bAND\b.*=.*=)',
        r'[;\'"]'
    ]
    
    cleaned = value
    for pattern in dangerous_patterns:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
    
    return cleaned.strip()

def validate_url(url: str) -> bool:
    """Validate URL format"""
    if not url or not isinstance(url, str):
        return False
    
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False

def rate_limit_key(request, endpoint: str) -> str:
    """Generate rate limiting key"""
    # Use IP address and endpoint for rate limiting
    return f"{request.remote_addr}:{endpoint}"

def log_security_event(event_type: str, details: dict, severity: str = "INFO"):
    """Log security-related events"""
    logger.log(
        getattr(logging, severity.upper(), logging.INFO),
        f"SECURITY_EVENT: {event_type} - {details}"
    )