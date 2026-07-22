import pytest
import tempfile
import sqlite3
from pathlib import Path
from unittest.mock import patch, MagicMock
from src.db import Database


class TestDatabase:
    """Test Database class"""

    @pytest.fixture
    def db_path(self, tmp_path):
        """Temporary database path"""
        return str(tmp_path / "test.db")

    @pytest.fixture
    def db(self, db_path):
        """Create test database"""
        database = Database(db_path)
        yield database
        # Cleanup is automatic with tmp_path

    def test_init_creates_database(self, db_path):
        """Test that __init__ creates database file"""
        db = Database(db_path)
        assert Path(db_path).exists()

    def test_init_creates_tables(self, db):
        """Test that tables are created"""
        conn = db.get_connection()
        cursor = conn.cursor()

        # Check assets table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='assets'"
        )
        assert cursor.fetchone() is not None

        # Check search_history table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='search_history'"
        )
        assert cursor.fetchone() is not None

        conn.close()

    def test_insert_asset_success(self, db, mock_asset):
        """Test successful asset insertion"""
        asset_id = db.insert_asset(mock_asset)
        assert asset_id == mock_asset["id"]

        # Verify asset was inserted
        retrieved = db.get_asset(asset_id)
        assert retrieved is not None
        assert retrieved["id"] == asset_id
        assert retrieved["type"] == "inmueble"

    def test_insert_asset_duplicate(self, db, mock_asset):
        """Test that inserting duplicate asset updates it"""
        db.insert_asset(mock_asset)

        # Update asset
        mock_asset["description"] = "Updated description"
        db.insert_asset(mock_asset)

        # Verify update
        retrieved = db.get_asset(mock_asset["id"])
        assert retrieved["description"] == "Updated description"

    def test_insert_asset_missing_required_field(self, db):
        """Test that missing required fields raise error"""
        incomplete_asset = {"id": "TEST-001", "type": "inmueble"}
        # Missing: description, price_initial, date_subasta

        with pytest.raises(ValueError, match="Missing required field"):
            db.insert_asset(incomplete_asset)

    def test_insert_asset_with_optional_fields(self, db):
        """Test insertion with all optional fields"""
        asset = {
            "id": "TEST-FULL",
            "type": "inmueble",
            "description": "Full asset",
            "price_initial": 100000.0,
            "price_min": 80000.0,
            "date_subasta": "2024-03-15",
            "location": "Madrid",
        }
        db.insert_asset(asset)
        retrieved = db.get_asset("TEST-FULL")
        assert retrieved["location"] == "Madrid"
        assert retrieved["price_min"] == 80000.0

    def test_get_asset_not_found(self, db):
        """Test getting non-existent asset"""
        result = db.get_asset("NONEXISTENT")
        assert result is None

    def test_search_assets_empty_database(self, db):
        """Test search on empty database"""
        results, total = db.search_assets()
        assert results == []
        assert total == 0

    def test_search_assets_all(self, db, mock_assets):
        """Test getting all assets"""
        for asset in mock_assets:
            db.insert_asset(asset)

        results, total = db.search_assets()
        assert len(results) == 3
        assert total == 3

    def test_search_assets_by_query(self, db, mock_assets):
        """Test text search"""
        for asset in mock_assets:
            db.insert_asset(asset)

        results, total = db.search_assets(query="Madrid")
        assert total == 1
        assert results[0]["id"] == "TEST-001"

    def test_search_assets_by_type_filter(self, db, mock_assets):
        """Test filtering by type"""
        for asset in mock_assets:
            db.insert_asset(asset)

        results, total = db.search_assets(filters={"type": "inmueble"})
        assert total == 1
        assert results[0]["type"] == "inmueble"

    def test_search_assets_by_price_range(self, db, mock_assets):
        """Test filtering by price range"""
        for asset in mock_assets:
            db.insert_asset(asset)

        results, total = db.search_assets(
            filters={"price_min": 100000, "price_max": 200000}
        )
        assert total == 1
        assert 100000 <= results[0]["price_initial"] <= 200000

    def test_search_assets_by_price_min_only(self, db, mock_assets):
        """Test filtering by minimum price only"""
        for asset in mock_assets:
            db.insert_asset(asset)

        results, total = db.search_assets(filters={"price_min": 150000})
        assert all(asset["price_initial"] >= 150000 for asset in results)

    def test_search_assets_by_price_max_only(self, db, mock_assets):
        """Test filtering by maximum price only"""
        for asset in mock_assets:
            db.insert_asset(asset)

        results, total = db.search_assets(filters={"price_max": 50000})
        assert all(asset["price_initial"] <= 50000 for asset in results)

    def test_search_assets_by_date_range(self, db, mock_assets):
        """Test filtering by date range"""
        for asset in mock_assets:
            db.insert_asset(asset)

        results, total = db.search_assets(
            filters={"date_from": "2024-03-15", "date_to": "2024-03-15"}
        )
        assert total == 1
        assert results[0]["date_subasta"] == "2024-03-15"

    def test_search_assets_by_date_from(self, db, mock_assets):
        """Test filtering by start date"""
        for asset in mock_assets:
            db.insert_asset(asset)

        results, total = db.search_assets(filters={"date_from": "2024-03-15"})
        assert all(asset["date_subasta"] >= "2024-03-15" for asset in results)

    def test_search_assets_combined_filters(self, db, mock_assets):
        """Test combining multiple filters"""
        for asset in mock_assets:
            db.insert_asset(asset)

        results, total = db.search_assets(
            query="Madrid",
            filters={
                "type": "inmueble",
                "price_min": 100000,
                "price_max": 200000,
            },
        )
        assert total == 1
        assert results[0]["id"] == "TEST-001"

    def test_search_assets_pagination(self, db, mock_assets):
        """Test pagination"""
        for asset in mock_assets:
            db.insert_asset(asset)

        # Get first page
        results1, total = db.search_assets(limit=2, offset=0)
        assert len(results1) == 2
        assert total == 3

        # Get second page
        results2, total = db.search_assets(limit=2, offset=2)
        assert len(results2) == 1
        assert total == 3

        # Verify no overlap
        ids1 = {r["id"] for r in results1}
        ids2 = {r["id"] for r in results2}
        assert len(ids1 & ids2) == 0

    def test_add_search_history(self, db):
        """Test adding search to history"""
        history_id = db.add_search_history("Madrid", {"type": "inmueble"}, 5)
        assert history_id > 0

    def test_add_search_history_without_filters(self, db):
        """Test adding search without filters"""
        history_id = db.add_search_history("Query", None, 10)
        assert history_id > 0

    def test_get_search_history(self, db):
        """Test retrieving search history"""
        db.add_search_history("Madrid", {"type": "inmueble"}, 5)
        db.add_search_history("Barcelona", None, 3)

        history, total = db.get_search_history()
        assert total == 2
        assert len(history) == 2
        assert history[0]["query"] in ["Madrid", "Barcelona"]

    def test_get_search_history_pagination(self, db):
        """Test search history pagination"""
        for i in range(5):
            db.add_search_history(f"Query {i}", None, i)

        # Get first page
        history1, total = db.get_search_history(limit=2, offset=0)
        assert len(history1) == 2
        assert total == 5

        # Get second page
        history2, total = db.get_search_history(limit=2, offset=2)
        assert len(history2) == 2

    def test_get_search_history_parses_filters(self, db):
        """Test that filters JSON is parsed"""
        db.add_search_history("Query", {"type": "inmueble", "price": 1000}, 5)

        history, _ = db.get_search_history()
        assert isinstance(history[0]["filters"], dict)
        assert history[0]["filters"]["type"] == "inmueble"

    def test_delete_all_assets(self, db, mock_assets):
        """Test deleting all assets"""
        for asset in mock_assets:
            db.insert_asset(asset)

        # Verify assets exist
        count = db.get_asset_count()
        assert count == 3

        # Delete all
        result = db.delete_all_assets()
        assert result is True

        # Verify deletion
        count = db.get_asset_count()
        assert count == 0

    def test_get_asset_count(self, db, mock_assets):
        """Test getting asset count"""
        assert db.get_asset_count() == 0

        for asset in mock_assets:
            db.insert_asset(asset)

        assert db.get_asset_count() == 3

    def test_get_connection(self, db):
        """Test getting database connection"""
        conn = db.get_connection()
        assert conn is not None
        assert hasattr(conn, "cursor")
        conn.close()

    def test_create_tables_idempotent(self, db_path):
        """Test that creating tables multiple times is safe"""
        db1 = Database(db_path)
        assert db1.create_tables() is True

        db2 = Database(db_path)
        assert db2.create_tables() is True

    def test_indexes_created(self, db):
        """Test that indexes are created"""
        conn = db.get_connection()
        cursor = conn.cursor()

        # Check indexes exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = {row[0] for row in cursor.fetchall()}

        assert "idx_assets_type" in indexes
        assert "idx_assets_price" in indexes
        assert "idx_assets_date" in indexes

        conn.close()

    def test_timestamps_set_on_insert(self, db, mock_asset):
        """Test that created_at and updated_at are set"""
        db.insert_asset(mock_asset)
        retrieved = db.get_asset(mock_asset["id"])

        assert "created_at" in retrieved
        assert "updated_at" in retrieved
        assert retrieved["created_at"] is not None
        assert retrieved["updated_at"] is not None

    def test_search_assets_returns_tuple(self, db):
        """Test that search_assets returns tuple of (results, total)"""
        result = db.search_assets()
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_search_assets_with_empty_filters(self, db, mock_assets):
        """Test search with empty filters dict"""
        for asset in mock_assets:
            db.insert_asset(asset)

        results, total = db.search_assets(filters={})
        assert len(results) == 3

    def test_get_search_history_returns_tuple(self, db):
        """Test that get_search_history returns tuple"""
        result = db.get_search_history()
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_asset_with_empty_string_location(self, db):
        """Test inserting asset with empty location"""
        asset = {
            "id": "TEST-EMPTY-LOC",
            "type": "mueble",
            "description": "Asset with no location",
            "price_initial": 100.0,
            "date_subasta": "2024-03-15",
            "location": "",
        }
        db.insert_asset(asset)
        retrieved = db.get_asset("TEST-EMPTY-LOC")
        assert retrieved["location"] == ""

    def test_search_with_special_characters(self, db):
        """Test search with special SQL characters"""
        asset = {
            "id": "TEST-SPECIAL",
            "type": "mueble",
            "description": "Asset with % and _",
            "price_initial": 100.0,
            "date_subasta": "2024-03-15",
        }
        db.insert_asset(asset)
        # Should not cause SQL injection or errors
        results, _ = db.search_assets(query="%")
        assert len(results) >= 0

    def test_search_empty_date_filter_ignored(self, db, mock_assets):
        """Test that empty date filters are ignored"""
        for asset in mock_assets:
            db.insert_asset(asset)

        results, total = db.search_assets(
            filters={"date_from": "", "date_to": ""}
        )
        assert total == 3

    def test_large_pagination_offset(self, db, mock_assets):
        """Test pagination with offset larger than total"""
        for asset in mock_assets:
            db.insert_asset(asset)

        results, total = db.search_assets(limit=10, offset=1000)
        assert len(results) == 0
        assert total == 3

    def test_price_filter_with_none_value(self, db, mock_assets):
        """Test that None price filters don't affect search"""
        for asset in mock_assets:
            db.insert_asset(asset)

        results1, _ = db.search_assets(
            filters={"price_min": None, "price_max": None}
        )
        results2, _ = db.search_assets()

        assert len(results1) == len(results2)


class TestDatabaseErrorHandling:
    """Test error handling in Database class"""

    def test_create_tables_sqlite_error(self, tmp_path):
        """Test that sqlite3.Error in create_tables raises RuntimeError"""
        db_path = str(tmp_path / "test.db")

        with patch("src.db.sqlite3.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()

            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.execute.side_effect = sqlite3.Error("Database error")

            with pytest.raises(RuntimeError, match="Failed to create tables"):
                Database(db_path)

    def test_insert_asset_sqlite_error(self, tmp_path):
        """Test that sqlite3.Error in insert_asset raises RuntimeError"""
        db_path = str(tmp_path / "test.db")
        db = Database(db_path)

        # Mock get_connection to return a connection that raises error
        with patch.object(db, "get_connection") as mock_get_conn:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()

            mock_get_conn.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.execute.side_effect = sqlite3.Error("Insert error")

            with pytest.raises(RuntimeError, match="Failed to insert asset"):
                db.insert_asset({"id": "1", "type": "test", "description": "test", "price_initial": 1.0, "date_subasta": "2024-01-01"})

    def test_get_asset_sqlite_error(self, tmp_path):
        """Test that sqlite3.Error in get_asset raises RuntimeError"""
        db_path = str(tmp_path / "test.db")
        db = Database(db_path)

        with patch.object(db, "get_connection") as mock_get_conn:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()

            mock_get_conn.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.execute.side_effect = sqlite3.Error("Get error")

            with pytest.raises(RuntimeError, match="Failed to get asset"):
                db.get_asset("TEST")

    def test_search_assets_sqlite_error(self, tmp_path):
        """Test that sqlite3.Error in search_assets raises RuntimeError"""
        db_path = str(tmp_path / "test.db")
        db = Database(db_path)

        with patch.object(db, "get_connection") as mock_get_conn:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()

            mock_get_conn.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.execute.side_effect = sqlite3.Error("Search error")

            with pytest.raises(RuntimeError, match="Failed to search assets"):
                db.search_assets()

    def test_add_search_history_sqlite_error(self, tmp_path):
        """Test that sqlite3.Error in add_search_history raises RuntimeError"""
        db_path = str(tmp_path / "test.db")
        db = Database(db_path)

        with patch.object(db, "get_connection") as mock_get_conn:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()

            mock_get_conn.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.execute.side_effect = sqlite3.Error("History error")

            with pytest.raises(RuntimeError, match="Failed to add search history"):
                db.add_search_history("test", {}, 1)

    def test_get_search_history_sqlite_error(self, tmp_path):
        """Test that sqlite3.Error in get_search_history raises RuntimeError"""
        db_path = str(tmp_path / "test.db")
        db = Database(db_path)

        with patch.object(db, "get_connection") as mock_get_conn:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()

            mock_get_conn.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.execute.side_effect = sqlite3.Error("History error")

            with pytest.raises(RuntimeError, match="Failed to get search history"):
                db.get_search_history()

    def test_delete_all_assets_sqlite_error(self, tmp_path):
        """Test that sqlite3.Error in delete_all_assets raises RuntimeError"""
        db_path = str(tmp_path / "test.db")
        db = Database(db_path)

        with patch.object(db, "get_connection") as mock_get_conn:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()

            mock_get_conn.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.execute.side_effect = sqlite3.Error("Delete error")

            with pytest.raises(RuntimeError, match="Failed to delete assets"):
                db.delete_all_assets()

    def test_get_asset_count_sqlite_error(self, tmp_path):
        """Test that sqlite3.Error in get_asset_count raises RuntimeError"""
        db_path = str(tmp_path / "test.db")
        db = Database(db_path)

        with patch.object(db, "get_connection") as mock_get_conn:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()

            mock_get_conn.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.execute.side_effect = sqlite3.Error("Count error")

            with pytest.raises(RuntimeError, match="Failed to get asset count"):
                db.get_asset_count()
