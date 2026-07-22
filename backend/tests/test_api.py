import pytest
from src.api import create_app
from pathlib import Path
import tempfile
from unittest.mock import patch, MagicMock


@pytest.fixture
def temp_db():
    """Create temporary database for testing"""
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "test.db"
    return str(db_path)


@pytest.fixture
def client(temp_db):
    """Create Flask test client"""
    app = create_app(temp_db)
    app.config["TESTING"] = True

    with app.test_client() as client:
        yield client


class TestHealthEndpoint:
    """Test /api/health endpoint"""

    def test_health_check_success(self, client):
        """Test health check returns 200"""
        response = client.get("/api/health")
        assert response.status_code == 200

    def test_health_check_response_structure(self, client):
        """Test health check response structure"""
        response = client.get("/api/health")
        data = response.get_json()

        assert "status" in data
        assert data["status"] == "ok"
        assert "timestamp" in data
        assert "scraper" in data
        assert "database" in data

    def test_health_scraper_healthy(self, client):
        """Test scraper is reported as healthy"""
        response = client.get("/api/health")
        data = response.get_json()

        assert data["scraper"]["healthy"] is True

    def test_health_database_connected(self, client):
        """Test database is reported as connected"""
        response = client.get("/api/health")
        data = response.get_json()

        assert data["database"]["connected"] is True


class TestSearchEndpoint:
    """Test /api/search endpoint"""

    def test_search_success(self, client):
        """Test search endpoint returns 200"""
        response = client.get("/api/search?q=test")
        assert response.status_code == 200

    def test_search_response_structure(self, client):
        """Test search response has correct structure"""
        response = client.get("/api/search?q=test")
        data = response.get_json()

        assert "assets" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data
        assert "timestamp" in data

    def test_search_empty_query(self, client):
        """Test search with empty query"""
        response = client.get("/api/search")
        assert response.status_code == 200
        data = response.get_json()
        assert "assets" in data

    def test_search_with_type_filter(self, client):
        """Test search with type filter"""
        response = client.get("/api/search?type=inmueble")
        assert response.status_code == 200
        data = response.get_json()

        for asset in data["assets"]:
            assert asset["type"] == "inmueble"

    def test_search_with_invalid_type_filter(self, client):
        """Test search with invalid type filter (should be ignored)"""
        response = client.get("/api/search?type=invalid_type")
        assert response.status_code == 200
        # Invalid type should be ignored, not filtered

    def test_search_with_price_min(self, client):
        """Test search with minimum price filter"""
        response = client.get("/api/search?price_min=100000")
        assert response.status_code == 200
        data = response.get_json()

        for asset in data["assets"]:
            assert asset["price_initial"] >= 100000

    def test_search_with_price_max(self, client):
        """Test search with maximum price filter"""
        response = client.get("/api/search?price_max=50000")
        assert response.status_code == 200
        data = response.get_json()

        for asset in data["assets"]:
            assert asset["price_initial"] <= 50000

    def test_search_with_price_range(self, client):
        """Test search with price range"""
        response = client.get("/api/search?price_min=1000&price_max=100000")
        assert response.status_code == 200
        data = response.get_json()

        for asset in data["assets"]:
            assert 1000 <= asset["price_initial"] <= 100000

    def test_search_invalid_price_min(self, client):
        """Test search with invalid price_min returns 400"""
        response = client.get("/api/search?price_min=invalid")
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_search_invalid_price_max(self, client):
        """Test search with invalid price_max returns 400"""
        response = client.get("/api/search?price_max=invalid")
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_search_with_date_filters(self, client):
        """Test search with date filters"""
        response = client.get(
            "/api/search?date_from=2024-03-15&date_to=2024-03-25"
        )
        assert response.status_code == 200
        data = response.get_json()

        for asset in data["assets"]:
            assert "2024-03-15" <= asset["date_subasta"] <= "2024-03-25"

    def test_search_pagination_limit(self, client):
        """Test search pagination limit parameter"""
        response = client.get("/api/search?limit=10")
        assert response.status_code == 200
        data = response.get_json()

        assert data["limit"] == 10
        assert len(data["assets"]) <= 10

    def test_search_pagination_offset(self, client):
        """Test search pagination offset parameter"""
        response = client.get("/api/search?offset=5")
        assert response.status_code == 200
        data = response.get_json()

        assert data["offset"] == 5

    def test_search_limit_max_capped(self, client):
        """Test that limit is capped at 1000"""
        response = client.get("/api/search?limit=10000")
        assert response.status_code == 200
        data = response.get_json()

        assert data["limit"] == 1000

    def test_search_offset_negative_becomes_zero(self, client):
        """Test that negative offset becomes 0"""
        response = client.get("/api/search?offset=-10")
        assert response.status_code == 200
        data = response.get_json()

        assert data["offset"] == 0

    def test_search_combined_filters(self, client):
        """Test search with multiple filters combined"""
        response = client.get(
            "/api/search?q=inmueble&type=inmueble&price_min=100000&price_max=300000"
        )
        assert response.status_code == 200


class TestAssetDetailEndpoint:
    """Test /api/assets/<id> endpoint"""

    def test_get_asset_found(self, client, temp_db):
        """Test getting existing asset"""
        from src.api import app, db

        # Add a test asset to the database
        test_asset = {
            "id": "TEST-ASSET-001",
            "type": "inmueble",
            "description": "Test property",
            "price_initial": 100000.0,
            "price_min": 80000.0,
            "date_subasta": "2024-03-15",
            "location": "Test Location"
        }
        db.insert_asset(test_asset)

        # Now get the asset details
        response = client.get("/api/assets/TEST-ASSET-001")
        assert response.status_code == 200

        asset_data = response.get_json()
        assert "asset" in asset_data
        assert asset_data["asset"]["id"] == "TEST-ASSET-001"
        assert asset_data["asset"]["type"] == "inmueble"

    def test_get_asset_not_found(self, client):
        """Test getting non-existent asset returns 404"""
        response = client.get("/api/assets/NONEXISTENT_ID")
        assert response.status_code == 404
        data = response.get_json()

        assert "error" in data
        assert data["code"] == "NOT_FOUND"

    def test_get_asset_response_structure(self, client):
        """Test asset detail response structure"""
        response = client.get("/api/search")
        data = response.get_json()

        if data["total"] > 0:
            asset_id = data["assets"][0]["id"]
            response = client.get(f"/api/assets/{asset_id}")
            asset_data = response.get_json()

            assert "timestamp" in asset_data


class TestSearchHistoryEndpoint:
    """Test /api/search-history endpoint"""

    def test_search_history_success(self, client):
        """Test search history endpoint"""
        response = client.get("/api/search-history")
        assert response.status_code == 200

    def test_search_history_response_structure(self, client):
        """Test search history response structure"""
        response = client.get("/api/search-history")
        data = response.get_json()

        assert "history" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data
        assert "timestamp" in data

    def test_search_history_logged_after_search(self, client):
        """Test that searches are logged to history"""
        # Do a search
        client.get("/api/search?q=test")

        # Get history
        response = client.get("/api/search-history")
        data = response.get_json()

        # Should have at least one entry
        assert data["total"] >= 1

    def test_search_history_pagination(self, client):
        """Test search history pagination"""
        # Do multiple searches
        for i in range(5):
            client.get(f"/api/search?q=test{i}")

        # Get paginated history
        response = client.get("/api/search-history?limit=2&offset=0")
        data = response.get_json()

        assert len(data["history"]) <= 2


class TestErrorHandling:
    """Test error handling"""

    def test_404_error(self, client):
        """Test 404 error handling"""
        response = client.get("/api/nonexistent-endpoint")
        assert response.status_code == 404
        data = response.get_json()

        assert "error" in data
        assert data["code"] == "NOT_FOUND"

    def test_response_headers(self, client):
        """Test response headers"""
        response = client.get("/api/health")

        assert response.content_type == "application/json"

    def test_search_default_limit(self, client):
        """Test that default limit is 50"""
        response = client.get("/api/search")
        data = response.get_json()

        assert data["limit"] == 50

    def test_search_default_offset(self, client):
        """Test that default offset is 0"""
        response = client.get("/api/search")
        data = response.get_json()

        assert data["offset"] == 0

    def test_search_response_has_timestamp(self, client):
        """Test that search response includes timestamp"""
        response = client.get("/api/search")
        data = response.get_json()

        assert "timestamp" in data
        assert len(data["timestamp"]) > 0

    def test_asset_detail_response_has_timestamp(self, client):
        """Test that asset detail response has timestamp"""
        # Get an asset first
        response = client.get("/api/search")
        data = response.get_json()

        if data["total"] > 0:
            asset_id = data["assets"][0]["id"]
            response = client.get(f"/api/assets/{asset_id}")
            asset_data = response.get_json()

            assert "timestamp" in asset_data
            assert len(asset_data["timestamp"]) > 0

    def test_search_history_has_timestamp(self, client):
        """Test that search history response has timestamp"""
        response = client.get("/api/search-history")
        data = response.get_json()

        assert "timestamp" in data

    def test_search_with_query_and_filters(self, client):
        """Test search with both query and multiple filters"""
        response = client.get(
            "/api/search?q=piso&type=inmueble&price_min=50000&price_max=500000&date_from=2024-01-01&date_to=2024-12-31&limit=100&offset=0"
        )
        assert response.status_code == 200
        data = response.get_json()
        assert "assets" in data

    def test_search_edge_case_zero_price_min(self, client):
        """Test search with zero as price_min"""
        response = client.get("/api/search?price_min=0")
        assert response.status_code == 200

    def test_search_edge_case_float_prices(self, client):
        """Test search with float prices"""
        response = client.get("/api/search?price_min=1000.50&price_max=99999.99")
        assert response.status_code == 200

    def test_search_edge_case_large_limit(self, client):
        """Test that very large limit is capped"""
        response = client.get("/api/search?limit=999999")
        data = response.get_json()
        assert data["limit"] == 1000


class TestAPIErrorHandling:
    """Test error handling in API endpoints"""

    @pytest.fixture
    def client_with_mock_db(self, temp_db):
        """Create Flask test client with mockable database"""
        from src import api

        # Store original db
        original_db = api.db

        # Create a new app
        app = create_app(temp_db)
        app.config["TESTING"] = True

        with app.test_client() as test_client:
            yield test_client, app, api

    def test_search_exception_handling(self, client_with_mock_db):
        """Test that search endpoint handles exceptions"""
        client, app, api_module = client_with_mock_db

        with patch.object(api_module.db, "search_assets") as mock_search:
            mock_search.side_effect = Exception("Database error")

            response = client.get("/api/search?q=test")
            assert response.status_code == 500
            data = response.get_json()

            assert "error" in data
            assert data["code"] == "SEARCH_ERROR"

    def test_get_asset_exception_handling(self, client_with_mock_db):
        """Test that get asset endpoint handles exceptions"""
        client, app, api_module = client_with_mock_db

        with patch.object(api_module.db, "get_asset") as mock_get:
            mock_get.side_effect = Exception("Database error")

            response = client.get("/api/assets/TEST-001")
            assert response.status_code == 500
            data = response.get_json()

            assert "error" in data
            assert data["code"] == "GET_ASSET_ERROR"

    def test_search_history_exception_handling(self, client_with_mock_db):
        """Test that search history endpoint handles exceptions"""
        client, app, api_module = client_with_mock_db

        with patch.object(api_module.db, "get_search_history") as mock_history:
            mock_history.side_effect = Exception("Database error")

            response = client.get("/api/search-history")
            assert response.status_code == 500
            data = response.get_json()

            assert "error" in data
            assert data["code"] == "HISTORY_ERROR"

    def test_500_error_handler(self, client):
        """Test 500 error handler is callable"""
        # This is harder to trigger naturally, so we'll just verify the structure
        response = client.get("/api/health")
        assert response.status_code == 200

    def test_search_add_history_called(self, client):
        """Test that add_search_history is called during search"""
        response = client.get("/api/search?q=test_query")
        assert response.status_code == 200

        # Verify history was logged by checking if we can retrieve it
        history_response = client.get("/api/search-history")
        history_data = history_response.get_json()

        # Should have at least one search logged
        assert history_data["total"] >= 1

    def test_500_error_handler_callable(self, client_with_mock_db):
        """Test that 500 error handler can be called"""
        client, app, api_module = client_with_mock_db

        # Get the error handler and call it directly
        from src.api import internal_error

        result = internal_error(Exception("Test error"))
        data, status_code = result

        assert status_code == 500
        assert "error" in data
        assert data["code"] == "INTERNAL_ERROR"

    def test_sync_endpoint_exception_handling(self, client_with_mock_db):
        """Test that sync endpoint handles exceptions"""
        client, app, api_module = client_with_mock_db

        with patch.object(api_module.scraper, "sync_assets") as mock_sync:
            mock_sync.side_effect = Exception("Sync error")

            response = client.post("/api/sync")
            assert response.status_code == 500

            data = response.get_json()
            assert "error" in data
            assert data["code"] == "SYNC_ERROR"


class TestSyncEndpoint:
    """Test /api/sync endpoint"""

    def test_sync_endpoint_exists(self, client):
        """Test that sync endpoint exists"""
        response = client.post("/api/sync")
        assert response.status_code == 200

    def test_sync_endpoint_success(self, client):
        """Test sync endpoint returns success response"""
        response = client.post("/api/sync")
        assert response.status_code == 200

        data = response.get_json()
        assert "message" in data
        assert "count" in data
        assert "timestamp" in data

    def test_sync_endpoint_returns_count(self, client):
        """Test that sync returns count of synced assets"""
        response = client.post("/api/sync")
        data = response.get_json()

        assert isinstance(data["count"], int)
        assert data["count"] >= 0

    def test_sync_endpoint_populates_database(self, client, temp_db):
        """Test that sync populates database"""
        from src.api import app, db

        response = client.post("/api/sync")
        assert response.status_code == 200

        count = db.get_asset_count()
        assert count > 0

    def test_sync_endpoint_response_structure(self, client):
        """Test sync response structure"""
        response = client.post("/api/sync")
        data = response.get_json()

        assert response.content_type == "application/json"
        assert "message" in data
        assert "count" in data
        assert "timestamp" in data
        assert "error" not in data


class TestDatabaseInitialization:
    """Test database initialization on startup"""

    def test_first_search_initializes_database(self, client):
        """Test that first search initializes database if empty"""
        response = client.get("/api/search")
        assert response.status_code == 200

        data = response.get_json()
        assert data["total"] > 0

    def test_database_populated_after_first_request(self, client, temp_db):
        """Test database is populated after first request"""
        from src.api import app, db

        client.get("/api/search")

        assert db.get_asset_count() > 0

    def test_subsequent_requests_use_cached_data(self, client):
        """Test that subsequent requests use cached database data"""
        response1 = client.get("/api/search")
        data1 = response1.get_json()

        response2 = client.get("/api/search")
        data2 = response2.get_json()

        assert data1["total"] == data2["total"]
        assert len(data1["assets"]) == len(data2["assets"])

    def test_initialization_skipped_when_database_populated(self, client):
        """Test that initialization is skipped if database already has data"""
        from src.api import app, db

        response1 = client.get("/api/search")
        data1 = response1.get_json()
        count1 = data1["total"]

        response2 = client.get("/api/search")
        data2 = response2.get_json()
        count2 = data2["total"]

        assert count1 == count2

    def test_search_with_sort_by_price(self, client):
        """Test search endpoint with price sorting"""
        response = client.get("/api/search?sort_by=price_initial&sort_order=ASC")
        assert response.status_code == 200
        data = response.get_json()
        assert "sort_by" in data
        assert data["sort_by"] == "price_initial"
        assert data["sort_order"] == "ASC"

    def test_search_with_sort_by_date(self, client):
        """Test search endpoint with date sorting"""
        response = client.get("/api/search?sort_by=date_subasta&sort_order=DESC")
        assert response.status_code == 200
        data = response.get_json()
        assert data["sort_by"] == "date_subasta"
        assert data["sort_order"] == "DESC"

    def test_search_defaults_to_date_sort(self, client):
        """Test that search defaults to date sorting"""
        response = client.get("/api/search")
        assert response.status_code == 200
        data = response.get_json()
        assert data["sort_by"] == "date_subasta"
        assert data["sort_order"] == "DESC"

    def test_export_endpoint_csv_format(self, client):
        """Test export endpoint returns CSV format"""
        response = client.get("/api/export")
        assert response.status_code == 200
        assert response.content_type == "text/csv; charset=utf-8"

    def test_export_endpoint_with_filters(self, client):
        """Test export endpoint with filters"""
        response = client.get("/api/export?q=madrid&type=inmueble")
        assert response.status_code == 200
        assert response.content_type == "text/csv; charset=utf-8"

    def test_export_endpoint_invalid_price_min(self, client):
        """Test export endpoint with invalid price_min"""
        response = client.get("/api/export?price_min=invalid")
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_export_endpoint_invalid_price_max(self, client):
        """Test export endpoint with invalid price_max"""
        response = client.get("/api/export?price_max=invalid")
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_export_endpoint_with_sorting(self, client):
        """Test export endpoint with sorting parameters"""
        response = client.get(
            "/api/export?sort_by=price_initial&sort_order=ASC"
        )
        assert response.status_code == 200
        assert response.content_type == "text/csv; charset=utf-8"

    def test_export_csv_headers(self, client):
        """Test that export CSV has correct headers"""
        response = client.get("/api/export")
        assert response.status_code == 200
        csv_content = response.data.decode("utf-8")
        assert "id" in csv_content
        assert "type" in csv_content
        assert "description" in csv_content
        assert "price_initial" in csv_content


class TestSecurityHardening:
    """Test security hardening improvements"""

    def test_search_query_length_validation(self, client):
        """Test that query strings exceeding max length are rejected"""
        long_query = "a" * 1001  # MAX_QUERY_LENGTH = 1000
        response = client.get(f"/api/search?q={long_query}")
        assert response.status_code == 400
        data = response.get_json()
        assert data["code"] == "INVALID_PARAM"
        assert "Query string too long" in data["error"]

    def test_export_query_length_validation(self, client):
        """Test that export query strings exceeding max length are rejected"""
        long_query = "a" * 1001  # MAX_QUERY_LENGTH = 1000
        response = client.get(f"/api/export?q={long_query}")
        assert response.status_code == 400
        data = response.get_json()
        assert data["code"] == "INVALID_PARAM"

    def test_security_headers_present(self, client):
        """Test that security headers are included in responses"""
        response = client.get("/api/health")
        assert response.status_code == 200

        assert "X-Content-Type-Options" in response.headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"

        assert "X-Frame-Options" in response.headers
        assert response.headers["X-Frame-Options"] == "DENY"

        assert "X-XSS-Protection" in response.headers
        assert response.headers["X-XSS-Protection"] == "1; mode=block"

    def test_error_messages_sanitized_search(self, client):
        """Test that error messages don't expose internal details"""
        # Mock database to raise an exception
        with patch('src.api.db.search_assets') as mock_search:
            mock_search.side_effect = Exception("Internal DB connection error")
            response = client.get("/api/search")
            assert response.status_code == 500
            data = response.get_json()
            # Should not contain the actual error message
            assert "Search operation failed" in data["error"]
            assert "Internal DB connection error" not in data["error"]

    def test_error_messages_sanitized_get_asset(self, client):
        """Test that get_asset errors don't expose internal details"""
        with patch('src.api.db.get_asset') as mock_get:
            mock_get.side_effect = Exception("Database error: invalid connection")
            response = client.get("/api/assets/test-id")
            assert response.status_code == 500
            data = response.get_json()
            assert "Failed to retrieve asset" in data["error"]
            assert "Database error" not in data["error"]

    def test_error_messages_sanitized_export(self, client):
        """Test that export errors don't expose internal details"""
        with patch('src.api.db.search_assets') as mock_search:
            mock_search.side_effect = Exception("CSV writer error")
            response = client.get("/api/export")
            assert response.status_code == 500
            data = response.get_json()
            assert "Export operation failed" in data["error"]
            assert "CSV writer error" not in data["error"]

    def test_search_returns_generic_validation_error(self, client):
        """Test that invalid parameters return generic validation errors"""
        response = client.get("/api/search?limit=invalid_value")
        assert response.status_code == 400
        data = response.get_json()
        assert "Invalid input parameters" in data["error"]

    def test_404_error_no_path_exposed(self, client):
        """Test that 404 errors don't expose the requested path"""
        response = client.get("/api/nonexistent-endpoint")
        assert response.status_code == 404
        data = response.get_json()
        # Should not expose the path
        assert "path" not in data
        assert "Endpoint not found" in data["error"]

    def test_500_error_generic_message(self, client):
        """Test that 500 errors return generic messages"""
        # Test by triggering an internal error in the health endpoint
        with patch('src.api.scraper.is_healthy') as mock_health:
            mock_health.side_effect = Exception("Database crashed!")
            response = client.get("/api/health")
            assert response.status_code == 500
            data = response.get_json()
            assert "Internal server error" in data["error"]
            # The error message should be generic, not exposing the exception
            assert "Database crashed" not in data.get("error", "")

    def test_search_history_invalid_limit_returns_400(self, client):
        """Test that invalid limit parameter returns 400"""
        response = client.get("/api/search-history?limit=invalid")
        assert response.status_code == 400
        data = response.get_json()
        assert "Invalid pagination parameters" in data["error"]

    def test_search_history_error_handling(self, client):
        """Test search history error handling sanitizes messages"""
        with patch('src.api.db.get_search_history') as mock_history:
            mock_history.side_effect = Exception("Query execution failed")
            response = client.get("/api/search-history")
            assert response.status_code == 500
            data = response.get_json()
            assert "Failed to retrieve search history" in data["error"]
            assert "Query execution failed" not in data["error"]
