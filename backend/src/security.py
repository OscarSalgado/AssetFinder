"""
Security module for AssetFinder API
Provides rate limiting, input validation, and security utilities
"""

import hashlib
import logging
import re
import time
from collections import defaultdict, deque
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# Rate limiting configuration
class RateLimiter:
    """
    In-memory rate limiter using a sliding window.

    Timestamps are held in a deque per identifier so expiring them is O(1) per
    dropped entry instead of rebuilding the whole list on every check. Silent
    identifiers are swept periodically, otherwise the table would grow without
    bound for the lifetime of the process.
    """

    # Requests between two sweeps of fully-expired identifiers.
    SWEEP_INTERVAL = 1000

    def __init__(self, max_requests: int = 100, window_seconds: int = 3600):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: dict[str, deque] = defaultdict(deque)
        self._checks_since_sweep = 0

    def _drop_expired(self, timestamps: deque, now: float) -> None:
        """Discard timestamps that fell out of the window."""
        window_start = now - self.window_seconds
        while timestamps and timestamps[0] <= window_start:
            timestamps.popleft()

    def is_rate_limited(self, identifier: str) -> bool:
        """Check if an identifier has exceeded rate limit"""
        now = time.time()

        self._checks_since_sweep += 1
        if self._checks_since_sweep >= self.SWEEP_INTERVAL:
            self.purge_expired()

        timestamps = self.requests[identifier]
        self._drop_expired(timestamps, now)

        # Check if limit exceeded
        if len(timestamps) >= self.max_requests:
            logger.warning(f"Rate limit exceeded for {identifier}")
            return True

        # Record this request
        timestamps.append(now)
        return False

    def get_remaining(self, identifier: str) -> int:
        """Get remaining requests for an identifier"""
        timestamps = self.requests.get(identifier)

        # Unknown identifiers are not tracked, so no entry is created for them.
        if not timestamps:
            return self.max_requests

        self._drop_expired(timestamps, time.time())

        if not timestamps:
            del self.requests[identifier]
            return self.max_requests

        return max(0, self.max_requests - len(timestamps))

    def retry_after(self, identifier: str) -> int:
        """Seconds until the oldest request in the window expires."""
        timestamps = self.requests.get(identifier)
        if not timestamps:
            return 0

        elapsed = time.time() - timestamps[0]
        return max(1, int(self.window_seconds - elapsed))

    def purge_expired(self) -> int:
        """
        Forget identifiers with no requests left in the window.

        Returns:
            Number of identifiers dropped
        """
        now = time.time()
        self._checks_since_sweep = 0

        stale = []
        for identifier, timestamps in self.requests.items():
            self._drop_expired(timestamps, now)
            if not timestamps:
                stale.append(identifier)

        for identifier in stale:
            del self.requests[identifier]

        return len(stale)

    def reset(self) -> None:
        """Drop all tracked state (used when rebuilding the app for tests)."""
        self.requests.clear()
        self._checks_since_sweep = 0


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
    def validate_query(query: str) -> tuple[bool, str | None]:
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
    def validate_asset_id(asset_id: str) -> tuple[bool, str | None]:
        """Validate asset ID"""
        if not asset_id:
            return False, "Asset ID is required"

        if len(asset_id) > InputValidator.MAX_ID_LENGTH:
            return False, f"Asset ID exceeds max length of {InputValidator.MAX_ID_LENGTH}"

        if not InputValidator.SAFE_ID_PATTERN.match(asset_id):
            return False, "Asset ID contains invalid characters"

        return True, asset_id

    @staticmethod
    def validate_type(asset_type: str) -> tuple[bool, str | None]:
        """Validate asset type"""
        valid_types = ["inmueble", "vehiculo", "mueble", "otros"]

        if asset_type not in valid_types:
            return False, f"Invalid type. Must be one of: {', '.join(valid_types)}"

        return True, asset_type

    @staticmethod
    def validate_price(price: float) -> tuple[bool, str | None]:
        """Validate price value"""
        try:
            price_float = float(price)
            if price_float < 0:
                return False, "Price must be non-negative"
            return True, price_float
        except (ValueError, TypeError):
            return False, "Invalid price value"

    @staticmethod
    def validate_date(date_str: str) -> tuple[bool, str | None]:
        """Validate date string (YYYY-MM-DD format)"""
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
            return True, date_str
        except ValueError:
            return False, "Invalid date format. Use YYYY-MM-DD"

    @staticmethod
    def validate_sort_params(sort_by: str, sort_order: str) -> tuple[bool, str, str]:
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
    def validate_pagination(limit: int, offset: int) -> tuple[int, int]:
        """Validate and normalize pagination parameters"""
        limit = max(1, min(int(limit or 50), InputValidator.MAX_LIMIT))
        offset = max(0, min(int(offset or 0), InputValidator.MAX_OFFSET))
        return limit, offset


class SecurityHeaders:
    """Security headers configuration"""

    @staticmethod
    def get_security_headers(origin: str | None = None) -> dict[str, str]:
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


def log_security_event(event_type: str, details: dict[str, Any], level: str = "INFO"):
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
