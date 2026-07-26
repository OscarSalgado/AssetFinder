"""Security tests for AssetFinder API"""

import pytest
from src.security import (
    RateLimiter,
    InputValidator,
    SecurityHeaders,
    sanitize_error_message,
    hash_sensitive_data,
)


class TestRateLimiter:
    """Test rate limiting functionality"""

    def test_rate_limiter_initialization(self):
        """Test rate limiter can be initialized"""
        limiter = RateLimiter(max_requests=10, window_seconds=60)
        assert limiter.max_requests == 10
        assert limiter.window_seconds == 60

    def test_rate_limiter_allows_requests_within_limit(self):
        """Test rate limiter allows requests within limit"""
        limiter = RateLimiter(max_requests=3, window_seconds=60)

        assert not limiter.is_rate_limited("user1")
        assert not limiter.is_rate_limited("user1")
        assert not limiter.is_rate_limited("user1")

    def test_rate_limiter_blocks_requests_exceeding_limit(self):
        """Test rate limiter blocks requests exceeding limit"""
        limiter = RateLimiter(max_requests=2, window_seconds=60)

        assert not limiter.is_rate_limited("user1")
        assert not limiter.is_rate_limited("user1")
        assert limiter.is_rate_limited("user1")

    def test_rate_limiter_tracks_different_users(self):
        """Test rate limiter tracks different users independently"""
        limiter = RateLimiter(max_requests=2, window_seconds=60)

        assert not limiter.is_rate_limited("user1")
        assert not limiter.is_rate_limited("user1")
        assert not limiter.is_rate_limited("user2")
        assert not limiter.is_rate_limited("user2")
        assert limiter.is_rate_limited("user1")
        assert limiter.is_rate_limited("user2")

    def test_rate_limiter_remaining_count(self):
        """Test rate limiter returns correct remaining count"""
        limiter = RateLimiter(max_requests=5, window_seconds=60)

        assert limiter.get_remaining("user1") == 5
        limiter.is_rate_limited("user1")
        assert limiter.get_remaining("user1") == 4
        limiter.is_rate_limited("user1")
        assert limiter.get_remaining("user1") == 3


class TestInputValidator:
    """Test input validation functionality"""

    def test_validate_query_accepts_valid_input(self):
        """Test validator accepts valid queries"""
        valid, result = InputValidator.validate_query("Madrid piso")
        assert valid
        assert result == "Madrid piso"

    def test_validate_query_rejects_empty_input(self):
        """Test validator handles empty queries"""
        valid, result = InputValidator.validate_query("")
        assert valid
        assert result == ""

    def test_validate_query_rejects_too_long(self):
        """Test validator rejects overly long queries"""
        long_query = "a" * (InputValidator.MAX_QUERY_LENGTH + 1)
        valid, error = InputValidator.validate_query(long_query)
        assert not valid
        assert "exceeds max length" in error

    def test_validate_query_rejects_sql_injection(self):
        """Test validator rejects SQL injection attempts"""
        sql_injection = "test' OR '1'='1"
        valid, error = InputValidator.validate_query(sql_injection)
        assert not valid

    def test_validate_query_rejects_dangerous_keywords(self):
        """Test validator rejects SQL keywords"""
        dangerous = "madrid; DROP TABLE assets"
        valid, error = InputValidator.validate_query(dangerous)
        assert not valid

    def test_validate_asset_id_accepts_valid_id(self):
        """Test validator accepts valid asset IDs"""
        valid, result = InputValidator.validate_asset_id("SSSS-2024-001")
        assert valid
        assert result == "SSSS-2024-001"

    def test_validate_asset_id_rejects_empty(self):
        """Test validator rejects empty asset ID"""
        valid, error = InputValidator.validate_asset_id("")
        assert not valid

    def test_validate_asset_id_rejects_special_chars(self):
        """Test validator rejects special characters in ID"""
        valid, error = InputValidator.validate_asset_id("SSSS-2024-001<script>")
        assert not valid

    def test_validate_type_accepts_valid_types(self):
        """Test validator accepts valid asset types"""
        for asset_type in ["inmueble", "vehiculo", "mueble", "otros"]:
            valid, result = InputValidator.validate_type(asset_type)
            assert valid
            assert result == asset_type

    def test_validate_type_rejects_invalid_types(self):
        """Test validator rejects invalid types"""
        valid, error = InputValidator.validate_type("unknown")
        assert not valid

    def test_validate_price_accepts_valid_prices(self):
        """Test validator accepts valid prices"""
        valid, result = InputValidator.validate_price(100000.50)
        assert valid
        assert result == 100000.50

    def test_validate_price_rejects_negative(self):
        """Test validator rejects negative prices"""
        valid, error = InputValidator.validate_price(-100)
        assert not valid

    def test_validate_price_rejects_invalid(self):
        """Test validator rejects invalid price values"""
        valid, error = InputValidator.validate_price("not a number")
        assert not valid

    def test_validate_date_accepts_valid_date(self):
        """Test validator accepts valid dates"""
        valid, result = InputValidator.validate_date("2024-01-15")
        assert valid
        assert result == "2024-01-15"

    def test_validate_date_rejects_invalid_format(self):
        """Test validator rejects invalid date format"""
        valid, error = InputValidator.validate_date("01/15/2024")
        assert not valid

    def test_validate_sort_params_defaults(self):
        """Test sort params validation with defaults"""
        valid, sort_by, sort_order = InputValidator.validate_sort_params("", "")
        assert valid
        assert sort_by == "date_subasta"
        assert sort_order == "DESC"

    def test_validate_sort_params_valid_values(self):
        """Test sort params validation with valid values"""
        valid, sort_by, sort_order = InputValidator.validate_sort_params("price_initial", "ASC")
        assert valid
        assert sort_by == "price_initial"
        assert sort_order == "ASC"

    def test_validate_sort_params_invalid_defaults_to_safe(self):
        """Test sort params validation reverts invalid to defaults"""
        valid, sort_by, sort_order = InputValidator.validate_sort_params("invalid_field", "invalid_order")
        assert valid
        assert sort_by == "date_subasta"
        assert sort_order == "DESC"

    def test_validate_pagination_normalizes_values(self):
        """Test pagination normalization"""
        limit, offset = InputValidator.validate_pagination(1000, 50)
        assert limit == 1000
        assert offset == 50

    def test_validate_pagination_clamps_excessive_values(self):
        """Test pagination clamps excessive values"""
        limit, offset = InputValidator.validate_pagination(100000, 10000000)
        assert limit <= InputValidator.MAX_LIMIT
        assert offset <= InputValidator.MAX_OFFSET

    def test_validate_pagination_ensures_positive(self):
        """Test pagination ensures positive values"""
        limit, offset = InputValidator.validate_pagination(-10, -50)
        assert limit > 0
        assert offset >= 0


class TestSecurityHeaders:
    """Test security headers functionality"""

    def test_get_security_headers_returns_dict(self):
        """Test security headers returns dictionary"""
        headers = SecurityHeaders.get_security_headers()
        assert isinstance(headers, dict)

    def test_security_headers_has_xss_protection(self):
        """Test headers include XSS protection"""
        headers = SecurityHeaders.get_security_headers()
        assert 'X-XSS-Protection' in headers
        assert headers['X-XSS-Protection'] == '1; mode=block'

    def test_security_headers_has_content_type_options(self):
        """Test headers include Content-Type-Options"""
        headers = SecurityHeaders.get_security_headers()
        assert 'X-Content-Type-Options' in headers
        assert headers['X-Content-Type-Options'] == 'nosniff'

    def test_security_headers_has_frame_options(self):
        """Test headers include Frame-Options"""
        headers = SecurityHeaders.get_security_headers()
        assert 'X-Frame-Options' in headers
        assert headers['X-Frame-Options'] == 'DENY'

    def test_security_headers_has_csp(self):
        """Test headers include Content Security Policy"""
        headers = SecurityHeaders.get_security_headers()
        assert 'Content-Security-Policy' in headers
        assert "default-src 'self'" in headers['Content-Security-Policy']

    def test_security_headers_has_hsts(self):
        """Test headers include HSTS"""
        headers = SecurityHeaders.get_security_headers()
        assert 'Strict-Transport-Security' in headers

    def test_security_headers_has_referrer_policy(self):
        """Test headers include Referrer-Policy"""
        headers = SecurityHeaders.get_security_headers()
        assert 'Referrer-Policy' in headers

    def test_security_headers_has_permissions_policy(self):
        """Test headers include Permissions-Policy"""
        headers = SecurityHeaders.get_security_headers()
        assert 'Permissions-Policy' in headers

    def test_security_headers_with_valid_cors_origin(self):
        """Test CORS headers with valid origin"""
        headers = SecurityHeaders.get_security_headers('http://localhost:3000')
        assert 'Access-Control-Allow-Origin' in headers
        assert headers['Access-Control-Allow-Origin'] == 'http://localhost:3000'

    def test_security_headers_with_invalid_cors_origin(self):
        """Test CORS headers with invalid origin"""
        headers = SecurityHeaders.get_security_headers('http://evil.com')
        assert 'Access-Control-Allow-Origin' not in headers


class TestErrorSanitization:
    """Test error message sanitization"""

    def test_sanitize_valueerror(self):
        """Test sanitizing ValueError"""
        error = ValueError("Some internal error")
        sanitized = sanitize_error_message(error)
        assert "Invalid request parameter" in sanitized

    def test_sanitize_keyerror(self):
        """Test sanitizing KeyError"""
        error = KeyError("Some missing key")
        sanitized = sanitize_error_message(error)
        assert "Missing required field" in sanitized

    def test_sanitize_typeerror(self):
        """Test sanitizing TypeError"""
        error = TypeError("Type mismatch")
        sanitized = sanitize_error_message(error)
        assert "Invalid data type" in sanitized

    def test_sanitize_generic_error(self):
        """Test sanitizing generic error"""
        error = Exception("Generic error")
        sanitized = sanitize_error_message(error)
        assert "error occurred" in sanitized


class TestDataHashing:
    """Test sensitive data hashing"""

    def test_hash_sensitive_data_produces_hash(self):
        """Test hashing produces hash"""
        hashed = hash_sensitive_data("sensitive_value")
        assert len(hashed) == 16
        assert hashed != "sensitive_value"

    def test_hash_sensitive_data_consistent(self):
        """Test hashing is consistent"""
        hash1 = hash_sensitive_data("value")
        hash2 = hash_sensitive_data("value")
        assert hash1 == hash2

    def test_hash_sensitive_data_different_input(self):
        """Test different inputs produce different hashes"""
        hash1 = hash_sensitive_data("value1")
        hash2 = hash_sensitive_data("value2")
        assert hash1 != hash2
