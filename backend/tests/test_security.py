"""Security tests for AssetFinder API"""

from unittest.mock import patch

from src.security import (
    InputValidator,
    RateLimiter,
    SecurityHeaders,
    hash_sensitive_data,
    log_security_event,
    sanitize_error_message,
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


class TestRateLimiterEfficiency:
    """Test the deque-based sliding window and its memory behaviour"""

    def test_expired_timestamps_are_dropped(self):
        """Test the window slides instead of growing forever"""
        limiter = RateLimiter(max_requests=3, window_seconds=60)

        with patch("src.security.time.time", return_value=1000.0):
            for _ in range(3):
                limiter.is_rate_limited("user1")
            assert limiter.is_rate_limited("user1") is True

        # Past the window: the old requests no longer count.
        with patch("src.security.time.time", return_value=1100.0):
            assert limiter.is_rate_limited("user1") is False
            assert len(limiter.requests["user1"]) == 1

    def test_unknown_identifier_is_not_tracked(self):
        """Test get_remaining does not create an entry for unseen callers"""
        limiter = RateLimiter(max_requests=10, window_seconds=60)

        assert limiter.get_remaining("never-seen") == 10
        assert "never-seen" not in limiter.requests

    def test_get_remaining_decreases_with_usage(self):
        """Test remaining quota reflects requests made"""
        limiter = RateLimiter(max_requests=5, window_seconds=60)

        limiter.is_rate_limited("user1")
        limiter.is_rate_limited("user1")

        assert limiter.get_remaining("user1") == 3

    def test_get_remaining_forgets_fully_expired_identifiers(self):
        """Test an identifier with nothing left in the window is dropped"""
        limiter = RateLimiter(max_requests=5, window_seconds=60)

        with patch("src.security.time.time", return_value=1000.0):
            limiter.is_rate_limited("user1")

        with patch("src.security.time.time", return_value=1100.0):
            assert limiter.get_remaining("user1") == 5

        assert "user1" not in limiter.requests

    def test_purge_expired_reclaims_silent_identifiers(self):
        """Test the sweep bounds memory for callers that went away"""
        limiter = RateLimiter(max_requests=5, window_seconds=60)

        with patch("src.security.time.time", return_value=1000.0):
            for i in range(50):
                limiter.is_rate_limited(f"user{i}")

        assert len(limiter.requests) == 50

        with patch("src.security.time.time", return_value=1100.0):
            dropped = limiter.purge_expired()

        assert dropped == 50
        assert len(limiter.requests) == 0

    def test_purge_keeps_identifiers_still_inside_the_window(self):
        """Test the sweep does not discard active callers"""
        limiter = RateLimiter(max_requests=5, window_seconds=60)

        with patch("src.security.time.time", return_value=1000.0):
            limiter.is_rate_limited("stale")

        with patch("src.security.time.time", return_value=1090.0):
            limiter.is_rate_limited("active")
            assert limiter.purge_expired() == 1

        assert "active" in limiter.requests
        assert "stale" not in limiter.requests

    def test_sweep_runs_automatically(self):
        """Test the limiter sweeps itself without an explicit call"""
        limiter = RateLimiter(max_requests=10_000, window_seconds=60)
        limiter.SWEEP_INTERVAL = 10

        with patch("src.security.time.time", return_value=1000.0):
            for i in range(9):
                limiter.is_rate_limited(f"user{i}")
            assert len(limiter.requests) == 9

        # The 10th check triggers a sweep, by which time the earlier ones expired.
        with patch("src.security.time.time", return_value=1100.0):
            limiter.is_rate_limited("newcomer")

        assert list(limiter.requests) == ["newcomer"]

    def test_retry_after_is_within_the_window(self):
        """Test retry_after reports when the oldest request expires"""
        limiter = RateLimiter(max_requests=1, window_seconds=60)

        with patch("src.security.time.time", return_value=1000.0):
            limiter.is_rate_limited("user1")

        with patch("src.security.time.time", return_value=1030.0):
            assert limiter.retry_after("user1") == 30

    def test_retry_after_is_zero_for_unknown_identifier(self):
        """Test retry_after on an untracked caller"""
        limiter = RateLimiter(max_requests=1, window_seconds=60)

        assert limiter.retry_after("never-seen") == 0

    def test_retry_after_is_at_least_one_second(self):
        """Test retry_after never tells the client to retry immediately"""
        limiter = RateLimiter(max_requests=1, window_seconds=60)

        with patch("src.security.time.time", return_value=1000.0):
            limiter.is_rate_limited("user1")

        with patch("src.security.time.time", return_value=1059.9):
            assert limiter.retry_after("user1") == 1

    def test_reset_clears_all_state(self):
        """Test reset drops every tracked identifier"""
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        limiter.is_rate_limited("user1")
        limiter.is_rate_limited("user2")

        limiter.reset()

        assert len(limiter.requests) == 0
        assert limiter.get_remaining("user1") == 5

    def test_timestamps_are_stored_in_a_deque(self):
        """Test the window uses a deque so expiry is O(1) per entry"""
        from collections import deque

        limiter = RateLimiter(max_requests=5, window_seconds=60)
        limiter.is_rate_limited("user1")

        assert isinstance(limiter.requests["user1"], deque)


class TestValidateAssetIdLimits:
    """Test asset id validation boundaries"""

    def test_oversized_asset_id_is_rejected(self):
        """Test an id above MAX_ID_LENGTH is refused"""
        valid, message = InputValidator.validate_asset_id("x" * 101)

        assert valid is False
        assert "exceeds max length" in message

    def test_asset_id_at_the_limit_is_accepted(self):
        """Test an id exactly at MAX_ID_LENGTH passes"""
        asset_id = "x" * 100
        valid, value = InputValidator.validate_asset_id(asset_id)

        assert valid is True
        assert value == asset_id


class TestLogSecurityEvent:
    """Test the security event logger"""

    def test_warning_level_is_logged_as_warning(self):
        """Test WARNING events go to logger.warning"""
        with patch("src.security.logger") as mock_logger:
            log_security_event("RATE_LIMIT", {"ip": "1.2.3.4"}, level="WARNING")

            mock_logger.warning.assert_called_once()

    def test_error_level_is_logged_as_error(self):
        """Test ERROR events go to logger.error"""
        with patch("src.security.logger") as mock_logger:
            log_security_event("INJECTION", {"query": "drop"}, level="ERROR")

            mock_logger.error.assert_called_once()

    def test_default_level_is_info(self):
        """Test unspecified level goes to logger.info"""
        with patch("src.security.logger") as mock_logger:
            log_security_event("LOGIN", {"user": "abc"})

            mock_logger.info.assert_called_once()

    def test_event_type_and_details_are_included(self):
        """Test the formatted message carries the event context"""
        with patch("src.security.logger") as mock_logger:
            log_security_event("SCAN", {"path": "/admin"})

            message = mock_logger.info.call_args[0][0]
            assert "SCAN" in message
            assert "/admin" in message
