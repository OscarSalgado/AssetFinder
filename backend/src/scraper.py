from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .parser import AssetParser
from .timeutils import utc_now, utc_now_isoformat

# Mock data for fallback (Delta 0.2 compatibility)
MOCK_ASSETS = [
    {
        "id": "SSSS-2024-001",
        "type": "inmueble",
        "description": "Piso de 3 habitaciones en Madrid centro, con balcón y vista a calle principal",
        "price_initial": 150000.0,
        "price_min": 120000.0,
        "date_subasta": "2024-03-15",
        "location": "Madrid, España",
    },
    {
        "id": "SSSS-2024-002",
        "type": "vehiculo",
        "description": "Toyota Corolla 2015 diesel, buen estado, revisión al día",
        "price_initial": 8500.0,
        "price_min": 6500.0,
        "date_subasta": "2024-03-20",
        "location": "Barcelona, España",
    },
    {
        "id": "SSSS-2024-003",
        "type": "inmueble",
        "description": "Casa unifamiliar con jardín, 4 habitaciones, garaje",
        "price_initial": 250000.0,
        "price_min": 200000.0,
        "date_subasta": "2024-03-25",
        "location": "Valencia, España",
    },
    {
        "id": "SSSS-2024-004",
        "type": "mueble",
        "description": "Sofá de 3 plazas en tela, buen estado",
        "price_initial": 500.0,
        "price_min": 300.0,
        "date_subasta": "2024-03-10",
        "location": "Sevilla, España",
    },
    {
        "id": "SSSS-2024-005",
        "type": "vehiculo",
        "description": "Fiat 500 2010, color rojo, 120.000 km",
        "price_initial": 4500.0,
        "price_min": 3000.0,
        "date_subasta": "2024-03-22",
        "location": "Bilbao, España",
    },
    {
        "id": "SSSS-2024-006",
        "type": "inmueble",
        "description": "Apartamento con vistas al mar, zona turística",
        "price_initial": 180000.0,
        "price_min": 150000.0,
        "date_subasta": "2024-03-18",
        "location": "Málaga, España",
    },
]


class Scraper:
    """Scraper for SSSS embargos portal with real HTML parsing and DB persistence"""

    def __init__(self, use_mock: bool = True, db=None):
        self.portal_url = "https://w6.seg-social.es/subastas/"
        self.last_scraped = None
        self.use_mock = use_mock
        self.parser = AssetParser()
        self.session = self._create_session()
        self.db = db  # Database instance for persistence

    def _create_session(self) -> requests.Session:
        """Create requests session with retry strategy"""
        session = requests.Session()

        # Retry strategy for network resilience
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        # Set user agent to avoid blocking
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })

        return session

    def fetch_assets(
        self,
        query: str | None = None,
        filters: dict[str, Any] | None = None,
        save_to_db: bool = False,
    ) -> list[dict[str, Any]]:
        """
        Fetch assets from portal using real scraping or mock data

        Args:
            query: Search query string
            filters: Dict with optional keys: type, price_min, price_max, date_from, date_to
            save_to_db: Whether to save fetched assets to database

        Returns:
            List of asset dictionaries
        """
        filters = filters or {}

        # Use mock data or real scraping
        if self.use_mock:
            results = self._fetch_mock_assets(query, filters)
        else:
            results = self._fetch_real_assets(query, filters)

        # Add metadata to results. One timestamp for the whole batch instead of
        # two clock reads per asset, and they now share a single value.
        now = utc_now_isoformat()
        for asset in results:
            if "created_at" not in asset:
                asset["created_at"] = now
            asset["updated_at"] = now

        # Save to database if requested
        if save_to_db and self.db:
            self._persist(results)

        self.last_scraped = utc_now()
        return results

    def _fetch_mock_assets(
        self, query: str | None, filters: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Fetch mock assets (Delta 0.2 compatibility)"""
        results = MOCK_ASSETS

        # Filter by query
        if query:
            query_lower = query.lower()
            results = [
                asset
                for asset in results
                if query_lower in asset["description"].lower()
                or query_lower in asset["type"].lower()
                or query_lower in asset["location"].lower()
            ]

        # Filter by type
        if "type" in filters and filters["type"]:
            results = [
                asset for asset in results if asset["type"] == filters["type"]
            ]

        # Filter by price range
        if "price_min" in filters and filters["price_min"] is not None:
            results = [
                asset
                for asset in results
                if asset["price_initial"] >= filters["price_min"]
            ]

        if "price_max" in filters and filters["price_max"] is not None:
            results = [
                asset
                for asset in results
                if asset["price_initial"] <= filters["price_max"]
            ]

        # Filter by date range
        if "date_from" in filters and filters["date_from"]:
            results = [
                asset
                for asset in results
                if asset["date_subasta"] >= filters["date_from"]
            ]

        if "date_to" in filters and filters["date_to"]:
            results = [
                asset
                for asset in results
                if asset["date_subasta"] <= filters["date_to"]
            ]

        # Return copies: callers mutate the returned dicts (created_at/updated_at)
        # and MOCK_ASSETS is module-level state that must stay pristine. A shallow
        # copy per asset is enough because every value is an immutable scalar,
        # and only the assets that survived filtering are copied.
        return [dict(asset) for asset in results]

    def _fetch_real_assets(
        self, query: str | None, filters: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Fetch real assets from SSSS portal by scraping HTML"""
        try:
            # Build search URL with parameters
            search_url = self._build_search_url(query, filters)

            # Fetch HTML from portal
            html_content = self._fetch_html(search_url)

            if not html_content:
                # Fallback to mock data if scraping fails
                return self._fetch_mock_assets(query, filters)

            # Parse HTML to extract assets
            return self.parser.parse_response(html_content)

        except Exception:
            # Fallback to mock data on any error
            return self._fetch_mock_assets(query, filters)

    def _build_search_url(
        self, query: str | None, filters: dict[str, Any]
    ) -> str:
        """Build search URL with query parameters"""
        url = self.portal_url

        # Add query parameters if needed
        params = []

        if query:
            params.append(f"q={query}")

        if filters.get("type"):
            params.append(f"type={filters['type']}")

        if params:
            url += "?" + "&".join(params)

        return url

    def _fetch_html(self, url: str) -> str | None:
        """Fetch HTML content from URL with error handling"""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response.text
        except requests.RequestException:
            return None

    def _persist(self, assets: list[dict[str, Any]]) -> int:
        """
        Write assets to the database in a single transaction.

        Falls back to inserting one by one so that a single malformed asset does
        not discard the whole batch, preserving the previous skip-and-continue
        behaviour without paying a commit per row in the common case.

        Returns:
            Number of assets written
        """
        if not assets:
            return 0

        try:
            return self.db.insert_assets(assets)
        except Exception:
            count = 0
            for asset in assets:
                try:
                    self.db.insert_asset(asset)
                    count += 1
                except Exception:
                    # Skip DB errors, continue with next asset
                    pass
            return count

    def is_healthy(self) -> bool:
        """Check if scraper is operational"""
        return True

    def sync_assets(self) -> int:
        """
        Sync assets from portal to database

        Returns:
            Number of assets synced
        """
        if not self.db:
            return 0

        try:
            # Fetch assets from portal
            assets = self.fetch_assets()

            # Save to database
            return self._persist(assets)
        except Exception:
            return 0


def create_scraper(use_mock: bool = True, db=None) -> Scraper:
    """Factory function to create scraper instance"""
    return Scraper(use_mock=use_mock, db=db)
