"""
Security module for AssetFinder API
Provides rate limiting, input validation, and security utilities
"""

import time
import logging
import re
import hashlib
from typing import Dict, Tuple, Optional, Any
from functools import wraps
from collections import defaultdict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Rate limiting configuration
class RateLimiter:
    """Simple in-memory rate limiter using sliding window"""

    def __init__(self, max_requests: int = 100, window_seconds: int = 3600):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, list] = defaultdict(list)

    def is_rate_limited(self, identifier: str) -> bool:
        """Check if an identifier has exceeded rate limit"""
        now = time.time()
        window_start = now - self.window_seconds

        # Clean old requests outside the window
        self.requests[identifier] = [
            req_time for req_time in self.requests[identifier]
            if req_time > window_start
        ]

        # Check if limit exceeded
        if len(self.requests[identifier]) >= self.max_requests:
            logger.warning(f"Rate limit exceeded for {identifier}")
            return True

        # Record this request
        self.requests[identifier].append(now)
        return False

    def get_remaining(self, identifier: str) -> int:
        """Get remaining requests for an identifier"""
        now = time.time()
        window_start = now - self.window_seconds

        # Clean old requests
        self.requests[identifier] = [
            req_time for req_time in self.requests[identifier]
            if req_time > window_start
        ]

        return max(0, self.max_requests - len(self.requests[identifier]))


# Global rate limiter instance
rate_limiter = RateLimiter(max_requests=100, window_seconds=3600)


class InputValidator:
    """Validates and sanitizes user input"""

    # Safe characters for various fields
    SAFE_QUERY_PATTERN = re.compile(r'^[a-zA-Z0-9\s\-.,áéíóúñ]+$', re.UNICODE)
    SAFE_ID_PATTERN = re.compile(r'^[a-zA-Z0-9\-_]+$')
    SAFE_TYPE_PATTERN = re.compile(r'^[a-zA-Z]+$')
    SAFE_SORT_PATTERN = re.compile(r'^[a-zA-Z_]+$')

    # Max lengths for fields
    MAX_QUERY_LENGTH = 1000
    MAX_ID_LENGTH = 100
    MAX_TYPE_LENGTH = 50
    MAX_SORT_LENGTH = 50
    MAX_OFFSET = 1000000
    MAX_LIMIT = 10000

    @staticmethod
    def validate_query(query: str) -> Tuple[bool, Optional[str]]:
        """Validate search query"""
        if not query:
            return True, query.strip()

        if len(query) > InputValidator.MAX_QUERY_LENGTH:
            return False, f"Query exceeds max length of {InputValidator.MAX_QUERY_LENGTH}"

        # Basic sanitization: remove leading/trailing whitespace
        sanitized = query.strip()

        # Check for SQL injection patterns (basic check)
        dangerous_patterns = [
            r"(\bOR\b.*=.*|AND.*=.*)",  # OR/AND with equals
            r"['\"](.*?)['\"](;|--)",  # SQL statement injection
            r"(\bUNION\b|\bSELECT\b|\bDROP\b|\bDELETE\b|\bINSERT\b)",  # SQL keywords
            r"(--|;)",  # SQL comment or statement terminator in query
        ]

        for pattern in dangerous_patterns:
            if re.search(pattern, sanitized, re.IGNORECASE):
                logger.warning(f"Suspicious query pattern detected: {sanitized[:50]}")
                return False, "Invalid query characters"

        return True, sanitized

    @staticmethod
    def validate_asset_id(asset_id: str) -> Tuple[bool, Optional[str]]:
        """Validate asset ID"""
        if not asset_id:
            return False, "Asset ID is required"

        if len(asset_id) > InputValidator.MAX_ID_LENGTH:
            return False, f"Asset ID exceeds max length of {InputValidator.MAX_ID_LENGTH}"

        if not InputValidator.SAFE_ID_PATTERN.match(asset_id):
            return False, "Asset ID contains invalid characters"

        return True, asset_id

    @staticmethod
    def validate_type(asset_type: str) -> Tuple[bool, Optional[str]]:
        """Validate asset type"""
        valid_types = ["inmueble", "vehiculo", "mueble", "otros"]

        if asset_type not in valid_types:
            return False, f"Invalid type. Must be one of: {', '.join(valid_types)}"

        return True, asset_type

    @staticmethod
    def validate_price(price: float) -> Tuple[bool, Optional[str]]:
        """Validate price value"""
        try:
            price_float = float(price)
            if price_float < 0:
                return False, "Price must be non-negative"
            return True, price_float
        except (ValueError, TypeError):
            return False, "Invalid price value"

    @staticmethod
    def validate_date(date_str: str) -> Tuple[bool, Optional[str]]:
        """Validate date string (YYYY-MM-DD format)"""
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
            return True, date_str
        except ValueError:
            return False, "Invalid date format. Use YYYY-MM-DD"

    @staticmethod
    def validate_sort_params(sort_by: str, sort_order: str) -> Tuple[bool, str, str]:
        """Validate sort parameters"""
        valid_sorts = ["price_initial", "date_subasta", "id", "type"]
        valid_orders = ["ASC", "DESC"]

        sort_by = sort_by.lower() if sort_by else "date_subasta"
        sort_order = sort_order.upper() if sort_order else "DESC"

        if sort_by not in valid_sorts:
            sort_by = "date_subasta"

        if sort_order not in valid_orders:
            sort_order = "DESC"

        return True, sort_by, sort_order

    @staticmethod
    def validate_pagination(limit: int, offset: int) -> Tuple[int, int]:
        """Validate and normalize pagination parameters"""
        limit = max(1, min(int(limit or 50), InputValidator.MAX_LIMIT))
        offset = max(0, min(int(offset or 0), InputValidator.MAX_OFFSET))
        return limit, offset


class SecurityHeaders:
    """Security headers configuration"""

    @staticmethod
    def get_security_headers(origin: Optional[str] = None) -> Dict[str, str]:
        """Get security headers for responses"""
        headers = {
            # Prevent MIME type sniffing
            'X-Content-Type-Options': 'nosniff',

            # Clickjacking protection
            'X-Frame-Options': 'DENY',

            # XSS protection
            'X-XSS-Protection': '1; mode=block',

            # HSTS - Force HTTPS (for production)
            'Strict-Transport-Security': 'max-age=31536000; includeSubDomains; preload',

            # Content Security Policy - strict
            'Content-Security-Policy': (
                "default-src 'self'; "
                "script-src 'self'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data:; "
                "font-src 'self'; "
                "connect-src 'self'; "
                "frame-ancestors 'none'; "
                "base-uri 'self'; "
                "form-action 'self'"
            ),

            # Referrer policy
            'Referrer-Policy': 'strict-origin-when-cross-origin',

            # Feature policy
            'Permissions-Policy': (
                'accelerometer=(), '
                'ambient-light-sensor=(), '
                'autoplay=(), '
                'camera=(), '
                'encrypted-media=(), '
                'fullscreen=(), '
                'geolocation=(), '
                'gyroscope=(), '
                'magnetometer=(), '
                'microphone=(), '
                'midi=(), '
                'payment=(), '
                'usb=()'
            ),
        }

        # CORS headers (if origin specified)
        if origin and origin == 'http://localhost:3000':
            headers['Access-Control-Allow-Origin'] = origin
            headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
            headers['Access-Control-Allow-Headers'] = 'Content-Type'
            headers['Access-Control-Max-Age'] = '3600'

        return headers


def require_api_key(f):
    """Decorator to require API key validation"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = None

        # Try to get from header
        if 'X-API-Key' in request.headers:
            api_key = request.headers.get('X-API-Key')

        # For development, allow without key
        # In production, this should validate against a real key store
        if not api_key:
            logger.warning("Request without API key")
            # For now, allow all - this should be enforced in production

        return f(*args, **kwargs)

    return decorated_function


def log_security_event(event_type: str, details: Dict[str, Any], level: str = "INFO"):
    """Log security-related events"""
    message = f"SECURITY[{event_type}] {details}"

    if level == "WARNING":
        logger.warning(message)
    elif level == "ERROR":
        logger.error(message)
    else:
        logger.info(message)


def sanitize_error_message(error: Exception) -> str:
    """Sanitize error messages to prevent information disclosure"""
    # Map internal errors to safe messages
    error_type = type(error).__name__

    safe_messages = {
        "ValueError": "Invalid request parameter",
        "KeyError": "Missing required field",
        "TypeError": "Invalid data type",
        "DatabaseError": "Database operation failed",
    }

    return safe_messages.get(error_type, "An error occurred")


def hash_sensitive_data(data: str) -> str:
    """Hash sensitive data for logging (one-way)"""
    return hashlib.sha256(data.encode()).hexdigest()[:16]
