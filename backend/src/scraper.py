from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
import random


# Mock data for Delta 0.2 (without real scraping)
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
    """Scraper for SSSS embargos portal (mock version for Delta 0.2)"""

    def __init__(self):
        self.portal_url = "https://w6.seg-social.es/subastas/"
        self.last_scraped = None

    def fetch_assets(
        self,
        query: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch assets from portal (mock data for Delta 0.2)

        Args:
            query: Search query string
            filters: Dict with optional keys: type, price_min, price_max, date_from, date_to

        Returns:
            List of asset dictionaries
        """
        filters = filters or {}

        # Start with all mock assets
        results = MOCK_ASSETS.copy()

        # Filter by query (text search in description and type)
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

        # Add metadata to results
        for asset in results:
            asset["created_at"] = datetime.utcnow().isoformat()
            asset["updated_at"] = datetime.utcnow().isoformat()

        self.last_scraped = datetime.utcnow()
        return results

    def is_healthy(self) -> bool:
        """Check if scraper is operational"""
        return True


def create_scraper() -> Scraper:
    """Factory function to create scraper instance"""
    return Scraper()
