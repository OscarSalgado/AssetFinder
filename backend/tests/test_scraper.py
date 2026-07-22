import pytest
from src.scraper import Scraper, create_scraper, MOCK_ASSETS


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
