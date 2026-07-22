import pytest
import json
from pathlib import Path


@pytest.fixture
def mock_asset():
    """Single mock asset for testing"""
    return {
        "id": "TEST-001",
        "type": "inmueble",
        "description": "Piso 3 habitaciones en Madrid centro",
        "price_initial": 150000.00,
        "price_min": 120000.00,
        "date_subasta": "2024-03-15",
        "location": "Madrid, España",
    }


@pytest.fixture
def mock_assets():
    """Multiple mock assets for testing"""
    return [
        {
            "id": "TEST-001",
            "type": "inmueble",
            "description": "Piso en Madrid",
            "price_initial": 150000.00,
            "price_min": 120000.00,
            "date_subasta": "2024-03-15",
            "location": "Madrid",
        },
        {
            "id": "TEST-002",
            "type": "vehiculo",
            "description": "Toyota Corolla 2015",
            "price_initial": 8000.00,
            "price_min": 6500.00,
            "date_subasta": "2024-03-20",
            "location": "Barcelona",
        },
        {
            "id": "TEST-003",
            "type": "mueble",
            "description": "Sofá de 3 plazas",
            "price_initial": 500.00,
            "price_min": 300.00,
            "date_subasta": "2024-03-10",
            "location": "Valencia",
        },
    ]


@pytest.fixture
def mock_search_filters():
    """Mock search filters"""
    return {
        "type": "inmueble",
        "price_min": 100000.00,
        "price_max": 200000.00,
        "date_from": "2024-03-01",
        "date_to": "2024-03-31",
    }


@pytest.fixture
def html_sample():
    """Sample HTML from SSSS portal (minimal mock)"""
    return """
    <html>
        <body>
            <div class="assets-list">
                <div class="asset-item">
                    <h3>Piso en Madrid</h3>
                    <span class="price">150.000€</span>
                    <span class="date">15/03/2024</span>
                </div>
            </div>
        </body>
    </html>
    """


@pytest.fixture
def temp_db_path(tmp_path):
    """Temporary database path for testing"""
    return tmp_path / "test_assetfinder.db"
