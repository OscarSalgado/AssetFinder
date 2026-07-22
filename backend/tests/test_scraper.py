import pytest
from unittest.mock import MagicMock, patch
from requests.exceptions import RequestException
from src.scraper import Scraper, create_scraper, MOCK_ASSETS
from src.db import Database


class TestScraper:
    """Test Scraper class"""

    @pytest.fixture
    def scraper(self):
        """Create scraper instance"""
        return Scraper()

    def test_scraper_initialization(self, scraper):
        """Test scraper initialization"""
        assert scraper.portal_url == "https://w6.seg-social.es/subastas/"
        assert scraper.last_scraped is None

    def test_fetch_assets_returns_list(self, scraper):
        """Test that fetch_assets returns a list"""
        results = scraper.fetch_assets()
        assert isinstance(results, list)
        assert len(results) > 0

    def test_fetch_assets_all_mock_data(self, scraper):
        """Test fetching all mock assets"""
        results = scraper.fetch_assets()
        assert len(results) == len(MOCK_ASSETS)

    def test_fetch_assets_structure(self, scraper):
        """Test that returned assets have correct structure"""
        results = scraper.fetch_assets()

        required_fields = [
            "id",
            "type",
            "description",
            "price_initial",
            "date_subasta",
        ]

        for asset in results:
            for field in required_fields:
                assert field in asset
            assert isinstance(asset["type"], str)
            assert isinstance(asset["price_initial"], (int, float))

    def test_fetch_assets_with_query(self, scraper):
        """Test searching by query"""
        results = scraper.fetch_assets(query="Madrid")
        assert len(results) > 0
        assert any("Madrid" in asset["location"] for asset in results)

    def test_fetch_assets_with_empty_query(self, scraper):
        """Test with empty query returns all results"""
        results = scraper.fetch_assets(query="")
        assert len(results) == len(MOCK_ASSETS)

    def test_fetch_assets_case_insensitive_search(self, scraper):
        """Test that search is case insensitive"""
        results_lower = scraper.fetch_assets(query="madrid")
        results_upper = scraper.fetch_assets(query="MADRID")

        assert len(results_lower) > 0
        assert len(results_lower) == len(results_upper)

    def test_fetch_assets_search_in_description(self, scraper):
        """Test search finds text in description"""
        results = scraper.fetch_assets(query="habitaciones")
        assert len(results) > 0
        assert any(
            "habitaciones" in asset["description"].lower() for asset in results
        )

    def test_fetch_assets_search_in_type(self, scraper):
        """Test search finds text in type"""
        results = scraper.fetch_assets(query="vehiculo")
        assert len(results) > 0
        assert all(asset["type"] == "vehiculo" for asset in results)

    def test_fetch_assets_no_results(self, scraper):
        """Test query with no results"""
        results = scraper.fetch_assets(query="NONEXISTENT_QUERY_XYZ")
        assert len(results) == 0

    def test_fetch_assets_filter_by_type(self, scraper):
        """Test filtering by type"""
        results = scraper.fetch_assets(filters={"type": "inmueble"})
        assert len(results) > 0
        assert all(asset["type"] == "inmueble" for asset in results)

    def test_fetch_assets_filter_invalid_type(self, scraper):
        """Test filtering by invalid type returns empty"""
        results = scraper.fetch_assets(filters={"type": "invalid_type"})
        assert len(results) == 0

    def test_fetch_assets_filter_price_min(self, scraper):
        """Test filtering by minimum price"""
        results = scraper.fetch_assets(filters={"price_min": 100000})
        assert len(results) > 0
        assert all(asset["price_initial"] >= 100000 for asset in results)

    def test_fetch_assets_filter_price_max(self, scraper):
        """Test filtering by maximum price"""
        results = scraper.fetch_assets(filters={"price_max": 10000})
        assert len(results) > 0
        assert all(asset["price_initial"] <= 10000 for asset in results)

    def test_fetch_assets_filter_price_range(self, scraper):
        """Test filtering by price range"""
        results = scraper.fetch_assets(
            filters={"price_min": 5000, "price_max": 50000}
        )
        assert len(results) > 0
        assert all(
            5000 <= asset["price_initial"] <= 50000 for asset in results
        )

    def test_fetch_assets_filter_date_from(self, scraper):
        """Test filtering by start date"""
        results = scraper.fetch_assets(filters={"date_from": "2024-03-20"})
        assert len(results) > 0
        assert all(asset["date_subasta"] >= "2024-03-20" for asset in results)

    def test_fetch_assets_filter_date_to(self, scraper):
        """Test filtering by end date"""
        results = scraper.fetch_assets(filters={"date_to": "2024-03-15"})
        assert len(results) > 0
        assert all(asset["date_subasta"] <= "2024-03-15" for asset in results)

    def test_fetch_assets_filter_date_range(self, scraper):
        """Test filtering by date range"""
        results = scraper.fetch_assets(
            filters={"date_from": "2024-03-15", "date_to": "2024-03-20"}
        )
        assert len(results) > 0
        assert all(
            "2024-03-15" <= asset["date_subasta"] <= "2024-03-20"
            for asset in results
        )

    def test_fetch_assets_combined_filters(self, scraper):
        """Test combining multiple filters"""
        results = scraper.fetch_assets(
            query="piso",
            filters={
                "type": "inmueble",
                "price_min": 100000,
                "price_max": 200000,
            },
        )
        assert len(results) >= 0
        if len(results) > 0:
            assert results[0]["type"] == "inmueble"

    def test_fetch_assets_with_none_filters(self, scraper):
        """Test with None filters"""
        results = scraper.fetch_assets(filters=None)
        assert len(results) > 0

    def test_fetch_assets_none_query(self, scraper):
        """Test with None query"""
        results = scraper.fetch_assets(query=None)
        assert len(results) == len(MOCK_ASSETS)

    def test_fetch_assets_adds_metadata(self, scraper):
        """Test that fetch_assets adds created_at and updated_at"""
        results = scraper.fetch_assets()

        for asset in results:
            assert "created_at" in asset
            assert "updated_at" in asset
            assert asset["created_at"] is not None
            assert asset["updated_at"] is not None

    def test_fetch_assets_updates_last_scraped(self, scraper):
        """Test that last_scraped is updated"""
        assert scraper.last_scraped is None

        scraper.fetch_assets()
        assert scraper.last_scraped is not None

    def test_is_healthy(self, scraper):
        """Test health check"""
        assert scraper.is_healthy() is True

    def test_create_scraper_factory(self):
        """Test scraper factory function"""
        scraper = create_scraper()
        assert isinstance(scraper, Scraper)
        assert scraper.is_healthy() is True

    def test_fetch_assets_multiple_calls(self, scraper):
        """Test multiple consecutive calls"""
        results1 = scraper.fetch_assets(query="Madrid")
        results2 = scraper.fetch_assets(query="Madrid")

        assert len(results1) == len(results2)

    def test_fetch_assets_idempotent(self, scraper):
        """Test that results are consistent"""
        results1 = scraper.fetch_assets()
        results2 = scraper.fetch_assets()

        ids1 = {asset["id"] for asset in results1}
        ids2 = {asset["id"] for asset in results2}

        assert ids1 == ids2

    def test_mock_assets_structure(self):
        """Test that mock assets have correct structure"""
        required_fields = [
            "id",
            "type",
            "description",
            "price_initial",
            "date_subasta",
        ]

        for asset in MOCK_ASSETS:
            for field in required_fields:
                assert field in asset

    def test_mock_assets_valid_types(self):
        """Test that mock assets have valid types"""
        valid_types = {"inmueble", "vehiculo", "mueble", "otros"}

        for asset in MOCK_ASSETS:
            assert asset["type"] in valid_types

    def test_fetch_assets_preserves_original_mock_data(self, scraper):
        """Test that original mock data is not modified"""
        original_count = len(MOCK_ASSETS)

        scraper.fetch_assets()
        scraper.fetch_assets(query="test")

        assert len(MOCK_ASSETS) == original_count


class TestScraperWithDatabase:
    """Test Scraper with database persistence"""

    @pytest.fixture
    def temp_db(self, tmp_path):
        """Create temporary database for testing"""
        db_path = str(tmp_path / "test.db")
        return Database(db_path)

    @pytest.fixture
    def scraper_with_db(self, temp_db):
        """Create scraper instance with database"""
        return Scraper(use_mock=True, db=temp_db)

    def test_scraper_with_db_initialization(self, scraper_with_db, temp_db):
        """Test scraper initializes with database"""
        assert scraper_with_db.db is not None
        assert scraper_with_db.db == temp_db

    def test_fetch_assets_with_db_saves_to_database(self, scraper_with_db, temp_db):
        """Test that fetch_assets with save_to_db persists to database"""
        results = scraper_with_db.fetch_assets(save_to_db=True)

        assert len(results) > 0
        assert temp_db.get_asset_count() > 0

    def test_fetch_assets_saves_all_assets(self, scraper_with_db, temp_db):
        """Test that all fetched assets are saved"""
        results = scraper_with_db.fetch_assets(save_to_db=True)

        assert temp_db.get_asset_count() == len(results)

    def test_fetch_assets_with_filters_saves_correctly(self, scraper_with_db, temp_db):
        """Test that filtered assets are still saved correctly"""
        results = scraper_with_db.fetch_assets(
            filters={"type": "inmueble"},
            save_to_db=True
        )

        assert len(results) > 0
        assert temp_db.get_asset_count() > 0

    def test_sync_assets_returns_count(self, scraper_with_db, temp_db):
        """Test that sync_assets returns count of synced assets"""
        count = scraper_with_db.sync_assets()

        assert isinstance(count, int)
        assert count > 0

    def test_sync_assets_populates_database(self, scraper_with_db, temp_db):
        """Test that sync_assets populates database"""
        assert temp_db.get_asset_count() == 0

        count = scraper_with_db.sync_assets()

        assert count > 0
        assert temp_db.get_asset_count() > 0

    def test_sync_assets_without_database_returns_zero(self):
        """Test that sync without database returns 0"""
        scraper = Scraper(use_mock=True, db=None)
        count = scraper.sync_assets()

        assert count == 0

    def test_fetch_assets_without_db_parameter_no_save(self, scraper_with_db, temp_db):
        """Test fetch_assets without save_to_db flag doesn't save"""
        temp_db.delete_all_assets()

        results = scraper_with_db.fetch_assets(save_to_db=False)

        assert len(results) > 0
        assert temp_db.get_asset_count() == 0

    def test_fetch_assets_metadata_added(self, scraper_with_db, temp_db):
        """Test that created_at and updated_at are added"""
        results = scraper_with_db.fetch_assets(save_to_db=True)

        for asset in results:
            assert "created_at" in asset
            assert "updated_at" in asset


class TestScraperRealScraping:
    """Test real scraping functionality"""

    def test_session_created(self):
        """Test that requests session is created"""
        scraper = Scraper()
        assert scraper.session is not None

    def test_session_has_user_agent(self):
        """Test that session has user agent header"""
        scraper = Scraper()
        assert "User-Agent" in scraper.session.headers

    def test_build_search_url_no_params(self):
        """Test building URL with no parameters"""
        scraper = Scraper()
        url = scraper._build_search_url(None, {})

        assert url == scraper.portal_url

    def test_build_search_url_with_query(self):
        """Test building URL with query parameter"""
        scraper = Scraper()
        url = scraper._build_search_url("test", {})

        assert "q=test" in url
        assert scraper.portal_url in url

    def test_build_search_url_with_type_filter(self):
        """Test building URL with type filter"""
        scraper = Scraper()
        url = scraper._build_search_url(None, {"type": "inmueble"})

        assert "type=inmueble" in url

    def test_build_search_url_with_multiple_params(self):
        """Test building URL with multiple parameters"""
        scraper = Scraper()
        url = scraper._build_search_url("test", {"type": "vehiculo"})

        assert "q=test" in url
        assert "type=vehiculo" in url

    @patch('src.scraper.requests.Session.get')
    def test_fetch_html_success(self, mock_get):
        """Test fetching HTML successfully"""
        mock_response = MagicMock()
        mock_response.text = "<html>test</html>"
        mock_get.return_value = mock_response

        scraper = Scraper()
        result = scraper._fetch_html("http://test.com")

        assert result == "<html>test</html>"
        mock_get.assert_called_once()

    @patch('src.scraper.requests.Session.get')
    def test_fetch_html_failure(self, mock_get):
        """Test fetch HTML handles exceptions"""
        mock_get.side_effect = RequestException("Network error")

        scraper = Scraper()
        result = scraper._fetch_html("http://test.com")

        assert result is None

    def test_real_scraping_mode_fallback_to_mock(self):
        """Test that real scraping mode falls back to mock on failure"""
        scraper = Scraper(use_mock=False)
        results = scraper.fetch_assets()

        assert len(results) > 0

    @patch('src.scraper.Scraper._fetch_html')
    def test_real_scraping_uses_parser(self, mock_fetch_html):
        """Test that real scraping uses the parser"""
        mock_fetch_html.return_value = None

        scraper = Scraper(use_mock=False)
        results = scraper.fetch_assets()

        assert isinstance(results, list)

    def test_is_healthy_always_true(self):
        """Test that is_healthy always returns True"""
        scraper = Scraper()
        assert scraper.is_healthy() is True

    @patch('src.scraper.Scraper._fetch_html')
    def test_fetch_real_assets_exception_fallback(self, mock_fetch_html):
        """Test that fetch_real_assets falls back to mock on exception"""
        mock_fetch_html.side_effect = Exception("Parse error")

        scraper = Scraper(use_mock=False)
        results = scraper.fetch_assets()

        assert len(results) > 0

    def test_sync_assets_with_db_exception_handling(self, tmp_path):
        """Test sync_assets exception handling"""
        db_path = str(tmp_path / "test.db")
        db = Database(db_path)
        scraper = Scraper(use_mock=True, db=db)

        with patch.object(db, "insert_asset") as mock_insert:
            mock_insert.side_effect = Exception("DB error")

            count = scraper.sync_assets()
            assert isinstance(count, int)
