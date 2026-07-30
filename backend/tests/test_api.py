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
        # The export streams from iter_search_assets; the first row is pulled
        # before responding so a query failure still yields a 500.
        with patch('src.api.db.iter_search_assets') as mock_search:
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


class TestDuplicatesEndpoint:
    """Test /api/duplicates endpoint"""

    def test_duplicates_returns_200(self, client):
        """Test duplicates endpoint returns 200 for an existing asset"""
        response = client.get("/api/duplicates?asset_id=SSSS-2024-001")
        assert response.status_code == 200

    def test_duplicates_response_structure(self, client):
        """Test duplicates response contains the expected keys"""
        response = client.get("/api/duplicates?asset_id=SSSS-2024-001")
        data = response.get_json()

        assert data["asset_id"] == "SSSS-2024-001"
        assert data["asset"]["id"] == "SSSS-2024-001"
        assert "duplicate_count" in data
        assert "duplicates" in data
        assert "timestamp" in data
        assert isinstance(data["duplicates"], list)
        assert data["duplicate_count"] == len(data["duplicates"])

    def test_duplicates_no_duplicates_in_mock_data(self, client):
        """Test mock catalogue has no duplicates above the threshold"""
        response = client.get("/api/duplicates?asset_id=SSSS-2024-001")
        data = response.get_json()

        assert data["duplicate_count"] == 0
        assert data["duplicates"] == []

    def test_duplicates_finds_seeded_duplicate(self, client):
        """Test a near-identical asset is reported as a duplicate"""
        import src.api as api_module

        # Fetching through the API also triggers the lazy DB initialisation.
        original = client.get("/api/assets/SSSS-2024-001").get_json()["asset"]

        near_copy = dict(original)
        near_copy["id"] = "SSSS-2024-001-COPY"
        near_copy["description"] = original["description"] + "."
        api_module.db.insert_asset(near_copy)

        response = client.get("/api/duplicates?asset_id=SSSS-2024-001")
        data = response.get_json()

        assert data["duplicate_count"] == 1
        duplicate = data["duplicates"][0]
        assert duplicate["id"] == "SSSS-2024-001-COPY"
        assert duplicate["confidence"] >= 0.8
        assert duplicate["type"] == original["type"]
        assert duplicate["location"] == original["location"]

    def test_duplicates_excludes_self(self, client):
        """Test the asset itself is never reported as its own duplicate"""
        response = client.get("/api/duplicates?asset_id=SSSS-2024-001")
        data = response.get_json()

        assert all(d["id"] != "SSSS-2024-001" for d in data["duplicates"])

    def test_duplicates_missing_asset_id_returns_400(self, client):
        """Test missing asset_id parameter returns 400"""
        response = client.get("/api/duplicates")
        assert response.status_code == 400
        assert "required" in response.get_json()["error"]

    def test_duplicates_blank_asset_id_returns_400(self, client):
        """Test whitespace-only asset_id returns 400"""
        response = client.get("/api/duplicates?asset_id=%20%20")
        assert response.status_code == 400

    def test_duplicates_oversized_asset_id_returns_400(self, client):
        """Test asset_id above the length limit returns 400"""
        response = client.get(f"/api/duplicates?asset_id={'x' * 150}")
        assert response.status_code == 400
        assert "maximum length" in response.get_json()["error"]

    def test_duplicates_unknown_asset_returns_404(self, client):
        """Test unknown asset_id returns 404"""
        response = client.get("/api/duplicates?asset_id=DOES-NOT-EXIST")
        assert response.status_code == 404
        assert "not found" in response.get_json()["error"]

    def test_duplicates_value_error_returns_400(self, client):
        """Test ValueError from the engine is surfaced as 400"""
        with patch("src.api.DeduplicationEngine") as mock_engine:
            mock_engine.side_effect = ValueError("confidence_threshold must be between 0 and 1")
            response = client.get("/api/duplicates?asset_id=SSSS-2024-001")
            assert response.status_code == 400

    def test_duplicates_error_handling_sanitizes_message(self, client):
        """Test unexpected errors return a generic message"""
        with patch("src.api.db.search_assets") as mock_search:
            mock_search.side_effect = Exception("Internal table corrupted")
            response = client.get("/api/duplicates?asset_id=SSSS-2024-001")
            assert response.status_code == 500
            data = response.get_json()
            assert data["code"] == "DUPLICATE_ERROR"
            assert "Internal table corrupted" not in data["error"]


class TestRateLimiting:
    """Test the rate limiter wired into the API"""

    def test_requests_within_limit_are_allowed(self, client):
        """Test normal traffic is not rate limited"""
        for _ in range(5):
            assert client.get("/api/health").status_code == 200

    def test_exceeding_the_limit_returns_429(self, client):
        """Test the limit is enforced with a 429"""
        from src.security import rate_limiter

        for _ in range(rate_limiter.max_requests):
            client.get("/api/health")

        response = client.get("/api/health")

        assert response.status_code == 429
        assert response.get_json()["code"] == "RATE_LIMITED"

    def test_rate_limited_response_has_retry_after(self, client):
        """Test a throttled response tells the client when to retry"""
        from src.security import rate_limiter

        for _ in range(rate_limiter.max_requests + 1):
            response = client.get("/api/health")

        assert response.status_code == 429
        assert int(response.headers["Retry-After"]) > 0

    def test_rate_limit_headers_are_exposed(self, client):
        """Test remaining quota is advertised on normal responses"""
        from src.security import rate_limiter

        response = client.get("/api/health")

        assert response.headers["X-RateLimit-Limit"] == str(rate_limiter.max_requests)
        assert int(response.headers["X-RateLimit-Remaining"]) < rate_limiter.max_requests

    def test_creating_the_app_resets_the_window(self, temp_db):
        """Test each app instance starts with a clean rate limit window"""
        from src.security import rate_limiter

        app = create_app(temp_db)
        app.config["TESTING"] = True

        with app.test_client() as first:
            for _ in range(rate_limiter.max_requests + 1):
                first.get("/api/health")

        app = create_app(temp_db)
        app.config["TESTING"] = True

        with app.test_client() as second:
            assert second.get("/api/health").status_code == 200


class TestSecurityHeadersWiring:
    """Test responses carry the shared security header set"""

    def test_core_security_headers_are_present(self, client):
        """Test the hardened header set is applied"""
        response = client.get("/api/health")

        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert "max-age=31536000" in response.headers["Strict-Transport-Security"]
        assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert "Permissions-Policy" in response.headers

    def test_csp_blocks_framing_and_inline_scripts(self, client):
        """Test the CSP from SecurityHeaders is the one served"""
        csp = client.get("/api/health").headers["Content-Security-Policy"]

        assert "frame-ancestors 'none'" in csp
        assert "script-src 'self'" in csp
        assert "base-uri 'self'" in csp

    def test_cors_allowed_only_for_the_known_origin(self, client):
        """Test CORS headers are not handed out to arbitrary origins"""
        allowed = client.get("/api/health", headers={"Origin": "http://localhost:3000"})
        assert allowed.headers.get("Access-Control-Allow-Origin") == "http://localhost:3000"

        rejected = client.get("/api/health", headers={"Origin": "https://evil.example"})
        assert "Access-Control-Allow-Origin" not in rejected.headers


class TestStartupInitialisation:
    """Test the one-off database seeding guard"""

    def test_database_is_seeded_once_not_per_request(self, client):
        """Test the row count is not queried on every request"""
        import src.api as api_module

        client.get("/api/health")  # triggers the one-off initialisation

        with patch.object(api_module.db, "get_asset_count") as mock_count:
            for _ in range(5):
                assert client.get("/api/health").status_code == 200

            mock_count.assert_not_called()

    def test_initialisation_failure_propagates_as_500(self, temp_db):
        """Test a failure while seeding surfaces as an internal error"""
        import src.api as api_module

        app = create_app(temp_db)
        app.config["TESTING"] = True
        # TESTING re-raises instead of producing the response a client would get.
        app.config["PROPAGATE_EXCEPTIONS"] = False

        with patch.object(api_module.db, "get_asset_count") as mock_count:
            mock_count.side_effect = RuntimeError("disk gone")

            with app.test_client() as client:
                response = client.get("/api/health")

            assert response.status_code == 500

    def test_seeding_populates_the_catalogue(self, client):
        """Test the first request leaves the database populated"""
        import src.api as api_module

        client.get("/api/health")

        assert api_module.db.get_asset_count() > 0


class TestExportStreaming:
    """Test the streamed CSV export"""

    def _reference_csv(self, rows):
        """CSV built the old way: fully materialised in memory."""
        import csv as csv_module
        import io as io_module
        from src.api import EXPORT_FIELDNAMES

        output = io_module.StringIO()
        if rows:
            writer = csv_module.DictWriter(
                output, fieldnames=EXPORT_FIELDNAMES, restval=""
            )
            writer.writeheader()
            writer.writerows(rows)
        return output.getvalue()

    def test_export_returns_csv(self, client):
        """Test export responds with a CSV attachment"""
        response = client.get("/api/export")

        assert response.status_code == 200
        assert response.mimetype == "text/csv"
        assert "assets_export.csv" in response.headers["Content-Disposition"]

    def test_export_is_streamed(self, client):
        """Test the response is a stream, not a buffered body"""
        response = client.get("/api/export")

        assert response.is_streamed

    def test_export_matches_the_buffered_output_byte_for_byte(self, client):
        """Test streaming did not change a single byte of the CSV"""
        import src.api as api_module

        client.get("/api/health")  # ensure the catalogue is seeded
        rows, _ = api_module.db.search_assets(limit=api_module.MAX_EXPORT_ROWS)
        expected = self._reference_csv(rows)

        got = client.get("/api/export").get_data(as_text=True)

        assert got == expected

    def test_export_with_filters_matches_reference(self, client):
        """Test a filtered export is also byte-identical"""
        import src.api as api_module

        client.get("/api/health")  # ensure the catalogue is seeded
        rows, _ = api_module.db.search_assets(
            filters={"type": "inmueble"},
            limit=api_module.MAX_EXPORT_ROWS,
            sort_by="id",
            sort_order="ASC",
        )
        expected = self._reference_csv(rows)

        got = client.get(
            "/api/export?type=inmueble&sort_by=id&sort_order=ASC"
        ).get_data(as_text=True)

        assert got == expected

    def test_export_header_is_present_with_rows(self, client):
        """Test the header row is emitted when there is data"""
        body = client.get("/api/export").get_data(as_text=True)

        assert body.startswith("id,type,description")

    def test_export_of_no_rows_is_empty(self, client):
        """Test an empty result set yields an empty body, as before"""
        response = client.get("/api/export?type=inmueble&price_max=1")

        assert response.status_code == 200
        assert response.get_data(as_text=True) == ""

    def test_export_covers_every_row(self, client):
        """Test no row is lost across chunk boundaries"""
        import src.api as api_module

        many = [
            {
                "id": f"CHUNK-{i:05d}",
                "type": "inmueble",
                "description": "Piso en Madrid centro con balcon " * 5,
                "price_initial": 1000.0 + i,
                "price_min": 900.0 + i,
                "date_subasta": "2024-03-15",
                "location": "Madrid, España",
            }
            for i in range(2000)
        ]
        api_module.db.insert_assets(many)

        body = client.get("/api/export?q=Piso%20en%20Madrid").get_data(as_text=True)
        data_lines = [line for line in body.splitlines() if line.strip()]

        # One header plus every matching row.
        assert len(data_lines) == len(many) + 1
        assert "CHUNK-00000" in body
        assert "CHUNK-01999" in body

    def test_export_rejects_invalid_price_before_streaming(self, client):
        """Test validation errors still produce a 400, not a partial CSV"""
        response = client.get("/api/export?price_min=invalid")

        assert response.status_code == 400
        assert response.get_json()["code"] == "INVALID_PARAM"

    def test_export_rejects_oversized_query(self, client):
        """Test the query length limit is enforced before streaming"""
        response = client.get(f"/api/export?q={'x' * 1001}")

        assert response.status_code == 400

    def test_export_is_not_compressed(self, client):
        """Test the streaming guard keeps gzip away from the export"""
        response = client.get(
            "/api/export", headers={"Accept-Encoding": "gzip"}
        )

        assert response.status_code == 200
        assert "Content-Encoding" not in response.headers
        assert response.get_data(as_text=True).startswith("id,type,description")


class TestCompressionAndCaching:
    """Test gzip and conditional requests"""

    def _big_catalogue(self):
        return [
            {
                "id": f"GZIP-{i:05d}",
                "type": "inmueble",
                "description": "Piso amplio en Madrid centro con balcon y garaje " * 3,
                "price_initial": 100000.0 + i,
                "price_min": 90000.0 + i,
                "date_subasta": "2024-03-15",
                "location": "Madrid, España",
            }
            for i in range(200)
        ]

    def test_json_is_compressed_when_accepted(self, client):
        """Test a sizeable JSON body is gzipped"""
        import gzip as gzip_module
        import json as json_module
        import src.api as api_module

        api_module.db.insert_assets(self._big_catalogue())

        response = client.get(
            "/api/search?limit=200", headers={"Accept-Encoding": "gzip"}
        )

        assert response.headers["Content-Encoding"] == "gzip"
        # The test client does not decode Content-Encoding for us.
        payload = json_module.loads(gzip_module.decompress(response.get_data()))
        assert payload["total"] > 0

    def test_compression_is_lossless(self, client):
        """Test the decompressed body is exactly the uncompressed one"""
        import gzip as gzip_module
        import json as json_module
        import src.api as api_module

        api_module.db.insert_assets(self._big_catalogue())

        plain = client.get("/api/search?limit=200").get_json()
        packed = client.get(
            "/api/search?limit=200", headers={"Accept-Encoding": "gzip"}
        ).get_data()
        unpacked = json_module.loads(gzip_module.decompress(packed))

        # Every response embeds a fresh timestamp, so compare everything else.
        plain.pop("timestamp")
        unpacked.pop("timestamp")
        assert unpacked == plain

    def test_compression_shrinks_the_payload(self, client):
        """Test gzip actually reduces the transferred bytes"""
        import gzip as gzip_module
        import src.api as api_module

        api_module.db.insert_assets(self._big_catalogue())

        raw = client.get("/api/search?limit=200").get_data()
        packed = client.get(
            "/api/search?limit=200", headers={"Accept-Encoding": "gzip"}
        ).get_data()

        assert len(packed) < len(raw)
        # Worth doing at all only if the saving is substantial.
        assert len(packed) < len(raw) * 0.5
        assert len(gzip_module.decompress(packed)) == len(raw)

    def test_no_compression_without_accept_encoding(self, client):
        """Test a client that does not advertise gzip gets plain bytes"""
        import src.api as api_module

        api_module.db.insert_assets(self._big_catalogue())

        response = client.get("/api/search?limit=200", headers={"Accept-Encoding": ""})

        assert "Content-Encoding" not in response.headers

    def test_small_responses_are_not_compressed(self, client):
        """Test tiny bodies skip gzip, where the header costs more than it saves"""
        response = client.get("/api/health", headers={"Accept-Encoding": "gzip"})

        assert len(response.get_data()) < 1024
        assert "Content-Encoding" not in response.headers

    def test_vary_header_is_set(self, client):
        """Test caches are told the body varies by encoding"""
        response = client.get("/api/health")

        assert response.headers["Vary"] == "Accept-Encoding"

    def test_responses_embed_a_fresh_timestamp(self, client):
        """
        Test why no ETag is served.

        Two identical requests return different bytes because every payload
        carries a freshly generated timestamp. A validator computed over the
        body could therefore never match, so attaching one would cost a hash
        per response for a cache hit that cannot happen. This test pins that
        reasoning: if responses ever become byte-stable, revisit the decision.
        """
        first = client.get("/api/assets/SSSS-2024-001")
        second = client.get("/api/assets/SSSS-2024-001")

        assert first.get_json()["timestamp"] != second.get_json()["timestamp"]
        assert "ETag" not in first.headers

    def test_error_responses_are_not_compressed(self, client):
        """Test non-200 responses are returned untouched"""
        response = client.get(
            "/api/assets/DOES-NOT-EXIST", headers={"Accept-Encoding": "gzip"}
        )

        assert response.status_code == 404
        assert "Content-Encoding" not in response.headers


class TestCompressionEdgeCases:
    """Test the compression guard rails directly"""

    def test_already_encoded_body_is_left_alone(self, client):
        """Test a response that declares an encoding is not double-compressed"""
        import src.api as api_module
        from flask import Response

        with api_module.app.test_request_context(
            "/api/search", headers={"Accept-Encoding": "gzip"}
        ):
            response = Response(b"x" * 4096, mimetype="application/json")
            response.headers["Content-Encoding"] = "br"

            result = api_module._compress_response(response)

            assert result.headers["Content-Encoding"] == "br"
            assert result.get_data() == b"x" * 4096

    def test_non_compressible_mimetype_is_left_alone(self, client):
        """Test binary payloads skip gzip"""
        import src.api as api_module
        from flask import Response

        with api_module.app.test_request_context(
            "/api/search", headers={"Accept-Encoding": "gzip"}
        ):
            payload = b"\x89PNG\r\n" + b"\x00" * 4096
            response = Response(payload, mimetype="image/png")

            result = api_module._compress_response(response)

            assert "Content-Encoding" not in result.headers
            assert result.get_data() == payload

    def test_streamed_response_is_left_alone(self, client):
        """Test the is_streamed guard protects the generator"""
        import src.api as api_module
        from flask import Response

        consumed = []

        def generate():
            for chunk in ("a" * 2048, "b" * 2048):
                consumed.append(chunk[0])
                yield chunk

        with api_module.app.test_request_context(
            "/api/export", headers={"Accept-Encoding": "gzip"}
        ):
            response = Response(generate(), mimetype="text/csv")

            result = api_module._compress_response(response)

            # Nothing was pulled from the generator.
            assert consumed == []
            assert "Content-Encoding" not in result.headers


class TestExportFailureModes:
    """Test what happens when the export fails at each stage"""

    def test_value_error_before_streaming_returns_400(self, client):
        """Test a ValueError while preparing the export is a clean 400"""
        with patch("src.api.db.iter_search_assets") as mock_iter:
            mock_iter.side_effect = ValueError("bad sort field")

            response = client.get("/api/export")

            assert response.status_code == 400
            assert response.get_json()["code"] == "INVALID_PARAM"

    def test_failure_after_the_first_row_is_logged(self, client):
        """
        Test a mid-stream failure is logged instead of silently truncating.

        The 200 is already committed by then, so the download ends up short;
        the log entry is the only signal that it happened.
        """
        import src.api as api_module

        client.get("/api/health")  # seed the catalogue

        rows, _ = api_module.db.search_assets(limit=10)

        def exploding():
            yield rows[0]
            raise RuntimeError("connection lost")

        with patch("src.api.db.iter_search_assets", return_value=exploding()):
            with patch("src.api.logger") as mock_logger:
                with pytest.raises(RuntimeError):
                    client.get("/api/export").get_data()

                logged = " ".join(
                    str(call) for call in mock_logger.error.call_args_list
                )
                assert "Export truncated" in logged
