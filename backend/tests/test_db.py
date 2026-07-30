import pytest
import tempfile
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock
from src.db import Database, ASSET_COLUMNS, HISTORY_COLUMNS


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

    def test_search_with_sort_by_price_asc(self, db):
        """Test searching with ascending price sort"""
        assets_data = [
            {
                "id": "ASSET-1",
                "type": "inmueble",
                "description": "Expensive property",
                "price_initial": 500000,
                "price_min": 400000,
                "date_subasta": "2024-03-15",
                "location": "Madrid",
            },
            {
                "id": "ASSET-2",
                "type": "inmueble",
                "description": "Cheap property",
                "price_initial": 100000,
                "price_min": 80000,
                "date_subasta": "2024-03-20",
                "location": "Barcelona",
            },
        ]
        for asset in assets_data:
            db.insert_asset(asset)

        results, _ = db.search_assets(sort_by="price_initial", sort_order="ASC")
        assert len(results) == 2
        assert results[0]["price_initial"] < results[1]["price_initial"]

    def test_search_with_sort_by_price_desc(self, db):
        """Test searching with descending price sort"""
        assets_data = [
            {
                "id": "ASSET-1",
                "type": "inmueble",
                "description": "Expensive property",
                "price_initial": 500000,
                "price_min": 400000,
                "date_subasta": "2024-03-15",
                "location": "Madrid",
            },
            {
                "id": "ASSET-2",
                "type": "inmueble",
                "description": "Cheap property",
                "price_initial": 100000,
                "price_min": 80000,
                "date_subasta": "2024-03-20",
                "location": "Barcelona",
            },
        ]
        for asset in assets_data:
            db.insert_asset(asset)

        results, _ = db.search_assets(sort_by="price_initial", sort_order="DESC")
        assert len(results) == 2
        assert results[0]["price_initial"] > results[1]["price_initial"]

    def test_search_with_sort_by_date(self, db):
        """Test searching with date sort"""
        assets_data = [
            {
                "id": "ASSET-1",
                "type": "inmueble",
                "description": "Early date",
                "price_initial": 100000,
                "price_min": 80000,
                "date_subasta": "2024-01-15",
                "location": "Madrid",
            },
            {
                "id": "ASSET-2",
                "type": "inmueble",
                "description": "Late date",
                "price_initial": 200000,
                "price_min": 160000,
                "date_subasta": "2024-12-15",
                "location": "Barcelona",
            },
        ]
        for asset in assets_data:
            db.insert_asset(asset)

        results, _ = db.search_assets(sort_by="date_subasta", sort_order="DESC")
        assert len(results) == 2
        assert results[0]["date_subasta"] > results[1]["date_subasta"]

    def test_search_with_invalid_sort_field_defaults_to_date(self, db):
        """Test that invalid sort fields default to date_subasta"""
        asset = {
            "id": "ASSET-1",
            "type": "inmueble",
            "description": "Test property",
            "price_initial": 100000,
            "price_min": 80000,
            "date_subasta": "2024-03-15",
            "location": "Madrid",
        }
        db.insert_asset(asset)

        results, _ = db.search_assets(sort_by="invalid_field")
        assert len(results) == 1

    def test_search_with_invalid_sort_order_defaults_to_desc(self, db):
        """Test that invalid sort order defaults to DESC"""
        asset = {
            "id": "ASSET-1",
            "type": "inmueble",
            "description": "Test property",
            "price_initial": 100000,
            "price_min": 80000,
            "date_subasta": "2024-03-15",
            "location": "Madrid",
        }
        db.insert_asset(asset)

        results, _ = db.search_assets(sort_order="invalid_order")
        assert len(results) == 1

    def test_search_with_sort_preserves_filters(self, db):
        """Test that sorting works correctly with filters"""
        assets_data = [
            {
                "id": "ASSET-1",
                "type": "inmueble",
                "description": "Property 1",
                "price_initial": 300000,
                "price_min": 240000,
                "date_subasta": "2024-03-15",
                "location": "Madrid",
            },
            {
                "id": "ASSET-2",
                "type": "vehiculo",
                "description": "Car 1",
                "price_initial": 25000,
                "price_min": 20000,
                "date_subasta": "2024-03-20",
                "location": "Barcelona",
            },
            {
                "id": "ASSET-3",
                "type": "inmueble",
                "description": "Property 2",
                "price_initial": 150000,
                "price_min": 120000,
                "date_subasta": "2024-03-25",
                "location": "Valencia",
            },
        ]
        for asset in assets_data:
            db.insert_asset(asset)

        filters = {"type": "inmueble"}
        results, total = db.search_assets(
            filters=filters, sort_by="price_initial", sort_order="ASC"
        )
        assert total == 2
        assert len(results) == 2
        assert all(r["type"] == "inmueble" for r in results)
        assert results[0]["price_initial"] < results[1]["price_initial"]


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
        with patch.object(db, "_shared_connection") as mock_shared_conn:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()

            mock_shared_conn.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.execute.side_effect = sqlite3.Error("Insert error")

            with pytest.raises(RuntimeError, match="Failed to insert asset"):
                db.insert_asset({"id": "1", "type": "test", "description": "test", "price_initial": 1.0, "date_subasta": "2024-01-01"})

    def test_get_asset_sqlite_error(self, tmp_path):
        """Test that sqlite3.Error in get_asset raises RuntimeError"""
        db_path = str(tmp_path / "test.db")
        db = Database(db_path)

        with patch.object(db, "_shared_connection") as mock_shared_conn:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()

            mock_shared_conn.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.execute.side_effect = sqlite3.Error("Get error")

            with pytest.raises(RuntimeError, match="Failed to get asset"):
                db.get_asset("TEST")

    def test_search_assets_sqlite_error(self, tmp_path):
        """Test that sqlite3.Error in search_assets raises RuntimeError"""
        db_path = str(tmp_path / "test.db")
        db = Database(db_path)

        with patch.object(db, "_shared_connection") as mock_shared_conn:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()

            mock_shared_conn.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.execute.side_effect = sqlite3.Error("Search error")

            with pytest.raises(RuntimeError, match="Failed to search assets"):
                db.search_assets()

    def test_add_search_history_sqlite_error(self, tmp_path):
        """Test that sqlite3.Error in add_search_history raises RuntimeError"""
        db_path = str(tmp_path / "test.db")
        db = Database(db_path)

        with patch.object(db, "_shared_connection") as mock_shared_conn:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()

            mock_shared_conn.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.execute.side_effect = sqlite3.Error("History error")

            with pytest.raises(RuntimeError, match="Failed to add search history"):
                db.add_search_history("test", {}, 1)

    def test_get_search_history_sqlite_error(self, tmp_path):
        """Test that sqlite3.Error in get_search_history raises RuntimeError"""
        db_path = str(tmp_path / "test.db")
        db = Database(db_path)

        with patch.object(db, "_shared_connection") as mock_shared_conn:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()

            mock_shared_conn.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.execute.side_effect = sqlite3.Error("History error")

            with pytest.raises(RuntimeError, match="Failed to get search history"):
                db.get_search_history()

    def test_delete_all_assets_sqlite_error(self, tmp_path):
        """Test that sqlite3.Error in delete_all_assets raises RuntimeError"""
        db_path = str(tmp_path / "test.db")
        db = Database(db_path)

        with patch.object(db, "_shared_connection") as mock_shared_conn:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()

            mock_shared_conn.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.execute.side_effect = sqlite3.Error("Delete error")

            with pytest.raises(RuntimeError, match="Failed to delete assets"):
                db.delete_all_assets()

    def test_get_asset_count_sqlite_error(self, tmp_path):
        """Test that sqlite3.Error in get_asset_count raises RuntimeError"""
        db_path = str(tmp_path / "test.db")
        db = Database(db_path)

        with patch.object(db, "_shared_connection") as mock_shared_conn:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()

            mock_shared_conn.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.execute.side_effect = sqlite3.Error("Count error")

            with pytest.raises(RuntimeError, match="Failed to get asset count"):
                db.get_asset_count()


class TestBatchInsert:
    """Test insert_assets batch writes"""

    @pytest.fixture
    def db(self, tmp_path):
        """Create test database"""
        return Database(str(tmp_path / "test.db"))

    def test_insert_assets_writes_all_rows(self, db, mock_assets):
        """Test batch insert persists every asset"""
        written = db.insert_assets(mock_assets)

        assert written == len(mock_assets)
        assert db.get_asset_count() == len(mock_assets)

    def test_insert_assets_empty_list_returns_zero(self, db):
        """Test batch insert of nothing is a no-op"""
        assert db.insert_assets([]) == 0
        assert db.get_asset_count() == 0

    def test_insert_assets_is_equivalent_to_insert_asset(self, tmp_path, mock_assets):
        """Test batch and per-row inserts produce the same rows"""
        per_row = Database(str(tmp_path / "rows.db"))
        for asset in mock_assets:
            per_row.insert_asset(asset)

        batch = Database(str(tmp_path / "batch.db"))
        batch.insert_assets(mock_assets)

        rows_a, total_a = per_row.search_assets(sort_by="id", sort_order="ASC")
        rows_b, total_b = batch.search_assets(sort_by="id", sort_order="ASC")

        assert total_a == total_b
        # created_at/updated_at are generated, so compare the payload columns.
        payload = ("id", "type", "description", "price_initial", "price_min",
                   "date_subasta", "location")
        assert [{k: r[k] for k in payload} for r in rows_a] == \
               [{k: r[k] for k in payload} for r in rows_b]

    def test_insert_assets_replaces_existing(self, db, mock_asset):
        """Test batch insert upserts on conflicting id"""
        db.insert_asset(mock_asset)
        updated = dict(mock_asset)
        updated["description"] = "Descripcion actualizada"

        db.insert_assets([updated])

        assert db.get_asset_count() == 1
        assert db.get_asset("TEST-001")["description"] == "Descripcion actualizada"

    def test_insert_assets_missing_field_raises_value_error(self, db):
        """Test batch insert validates required fields"""
        with pytest.raises(ValueError, match="Missing required field"):
            db.insert_assets([{"id": "X", "type": "otros"}])

    def test_insert_assets_rejects_batch_atomically(self, db, mock_asset):
        """Test a malformed asset aborts the whole batch"""
        with pytest.raises(ValueError):
            db.insert_assets([mock_asset, {"id": "BAD"}])

        # Validation happens before any write, so nothing was persisted.
        assert db.get_asset_count() == 0

    def test_insert_assets_sqlite_error(self, tmp_path, mock_assets):
        """Test that sqlite3.Error in insert_assets raises RuntimeError"""
        db = Database(str(tmp_path / "test.db"))

        with patch.object(db, "_shared_connection") as mock_shared_conn:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()

            mock_shared_conn.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.executemany.side_effect = sqlite3.Error("Batch error")

            with pytest.raises(RuntimeError, match="Failed to insert assets"):
                db.insert_assets(mock_assets)


class TestConnectionReuse:
    """Test the pooled connection introduced for efficiency"""

    @pytest.fixture
    def db(self, tmp_path):
        """Create test database"""
        return Database(str(tmp_path / "test.db"))

    def test_shared_connection_is_reused(self, db):
        """Test repeated calls return the same connection object"""
        assert db._shared_connection() is db._shared_connection()

    def test_get_connection_returns_a_fresh_connection(self, db):
        """Test the public accessor still hands out caller-owned connections"""
        first = db.get_connection()
        second = db.get_connection()

        assert first is not second
        first.close()
        second.close()

    def test_get_connection_is_independent_of_the_pool(self, db, mock_asset):
        """Test closing a caller-owned connection does not break the pool"""
        conn = db.get_connection()
        conn.close()

        db.insert_asset(mock_asset)
        assert db.get_asset_count() == 1

    def test_wal_mode_is_enabled(self, db):
        """Test the pooled connection runs in WAL journal mode"""
        mode = db._shared_connection().execute("PRAGMA journal_mode").fetchone()[0]

        assert mode.lower() == "wal"

    def test_queries_do_not_open_new_connections(self, db, mock_assets):
        """Test the hot path stops paying a connect() per query"""
        db.insert_assets(mock_assets)
        db._shared_connection()  # warm the pool

        original_connect = sqlite3.connect
        opened = []

        def counting_connect(*args, **kwargs):
            opened.append(args)
            return original_connect(*args, **kwargs)

        with patch("src.db.sqlite3.connect", side_effect=counting_connect):
            db.search_assets(query="Madrid")
            db.get_asset("TEST-001")
            db.get_asset_count()
            db.add_search_history("Madrid", None, 1)

        assert opened == []

    def test_close_releases_the_pooled_connection(self, db, mock_asset):
        """Test close() drops the cached connection and it can be reopened"""
        first = db._shared_connection()
        db.close()

        second = db._shared_connection()
        assert second is not first

        db.insert_asset(mock_asset)
        assert db.get_asset_count() == 1

    def test_close_is_idempotent(self, db):
        """Test closing twice does not raise"""
        db.close()
        db.close()


class TestSearchHistoryRetention:
    """Test the rolling window that bounds search_history"""

    @pytest.fixture
    def db(self, tmp_path):
        """Create test database"""
        return Database(str(tmp_path / "test.db"))

    def test_prune_keeps_the_newest_entries(self, db):
        """Test pruning retains the most recent rows"""
        for i in range(50):
            db.add_search_history(f"consulta {i}", None, i)

        db.prune_search_history(keep=10)

        history, total = db.get_search_history(limit=100)
        assert total == 10
        queries = {item["query"] for item in history}
        assert "consulta 49" in queries
        assert "consulta 0" not in queries

    def test_prune_on_empty_table_is_a_noop(self, db):
        """Test pruning nothing does not fail"""
        assert db.prune_search_history(keep=10) == 0

    def test_prune_below_the_limit_removes_nothing(self, db):
        """Test a table under the limit is left alone"""
        for i in range(5):
            db.add_search_history(f"consulta {i}", None, i)

        assert db.prune_search_history(keep=100) == 0
        assert db.get_search_history()[1] == 5

    def test_prune_reports_rows_removed(self, db):
        """Test the number of deleted rows is returned"""
        for i in range(30):
            db.add_search_history(f"consulta {i}", None, i)

        assert db.prune_search_history(keep=10) == 20

    def test_prune_is_stable_across_repeated_calls(self, db):
        """Test pruning twice does not keep shrinking the window"""
        for i in range(30):
            db.add_search_history(f"consulta {i}", None, i)

        db.prune_search_history(keep=10)
        assert db.prune_search_history(keep=10) == 0
        assert db.get_search_history()[1] == 10

    def test_history_is_pruned_automatically(self, tmp_path):
        """Test the table stabilises without an explicit prune call"""
        db = Database(str(tmp_path / "auto.db"))
        db.SEARCH_HISTORY_LIMIT = 20
        db.HISTORY_PRUNE_INTERVAL = 10

        for i in range(60):
            db.add_search_history(f"consulta {i}", None, i)

        # Bounded by the limit plus at most one un-pruned interval.
        total = db.get_search_history(limit=1)[1]
        assert total <= db.SEARCH_HISTORY_LIMIT + db.HISTORY_PRUNE_INTERVAL
        assert total < 60

    def test_add_search_history_still_returns_the_row_id(self, db):
        """Test pruning does not disturb the returned id"""
        first = db.add_search_history("uno", None, 1)
        second = db.add_search_history("dos", None, 2)

        assert isinstance(first, int)
        assert second > first

    def test_prune_sqlite_error(self, tmp_path):
        """Test that sqlite3.Error in prune raises RuntimeError"""
        db = Database(str(tmp_path / "test.db"))

        with patch.object(db, "_shared_connection") as mock_shared_conn:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_shared_conn.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.execute.side_effect = sqlite3.Error("Prune error")

            with pytest.raises(RuntimeError, match="Failed to prune search history"):
                db.prune_search_history()


class TestSchemaIndexes:
    """Test the indexes that keep queries off full scans"""

    @pytest.fixture
    def db(self, tmp_path):
        """Create test database"""
        return Database(str(tmp_path / "test.db"))

    def _index_names(self, db):
        rows = db._shared_connection().execute(
            "SELECT name FROM sqlite_master WHERE type = 'index'"
        ).fetchall()
        return {row[0] for row in rows}

    def test_expected_indexes_exist(self, db):
        """Test every index the queries rely on is created"""
        names = self._index_names(db)

        for expected in (
            "idx_assets_type",
            "idx_assets_price",
            "idx_assets_date",
            "idx_assets_type_date",
            "idx_history_created",
        ):
            assert expected in names

    def test_history_ordering_uses_the_index(self, db):
        """Test the history query no longer sorts the whole table"""
        for i in range(20):
            db.add_search_history(f"consulta {i}", None, i)

        plan = db._shared_connection().execute(
            "EXPLAIN QUERY PLAN SELECT id, query, filters, result_count, created_at "
            "FROM search_history ORDER BY created_at DESC LIMIT 50 OFFSET 0"
        ).fetchall()
        detail = " ".join(str(row[-1]) for row in plan)

        assert "idx_history_created" in detail
        assert "TEMP B-TREE" not in detail.upper()

    def test_type_filter_with_date_order_uses_the_composite_index(self, db, mock_assets):
        """Test filter-plus-order is served by one index"""
        db.insert_assets(mock_assets)

        plan = db._shared_connection().execute(
            "EXPLAIN QUERY PLAN SELECT id FROM assets WHERE type = ? "
            "ORDER BY date_subasta DESC LIMIT 50",
            ("inmueble",),
        ).fetchall()
        detail = " ".join(str(row[-1]) for row in plan)

        assert "idx_assets_type_date" in detail


class TestExplicitColumns:
    """Test queries select named columns instead of *"""

    @pytest.fixture
    def db(self, tmp_path):
        """Create test database"""
        return Database(str(tmp_path / "test.db"))

    def test_get_asset_returns_every_column(self, db, mock_asset):
        """Test the asset shape is unchanged by the explicit column list"""
        db.insert_asset(mock_asset)

        asset = db.get_asset("TEST-001")

        assert set(asset) == set(ASSET_COLUMNS)

    def test_search_returns_every_column(self, db, mock_assets):
        """Test searching returns the same shape as before"""
        db.insert_assets(mock_assets)

        rows, _ = db.search_assets()

        assert rows
        for row in rows:
            assert set(row) == set(ASSET_COLUMNS)

    def test_history_returns_every_column(self, db):
        """Test history rows keep their shape"""
        db.add_search_history("madrid", {"type": "inmueble"}, 3)

        history, _ = db.get_search_history()

        assert set(history[0]) == set(HISTORY_COLUMNS)
        assert history[0]["filters"] == {"type": "inmueble"}


class TestTimestampFormat:
    """Test the deprecated utcnow replacement keeps the stored format"""

    @pytest.fixture
    def db(self, tmp_path):
        """Create test database"""
        return Database(str(tmp_path / "test.db"))

    def test_timestamps_are_naive_utc(self, db, mock_asset):
        """Test stored timestamps carry no timezone suffix"""
        db.insert_asset(mock_asset)

        created = db.get_asset("TEST-001")["created_at"]

        assert "+" not in created
        assert not created.endswith("Z")
        datetime.fromisoformat(created)  # parses as a naive timestamp

    def test_history_timestamps_are_naive_utc(self, db):
        """Test history timestamps use the same format"""
        db.add_search_history("madrid", None, 1)

        created = db.get_search_history()[0][0]["created_at"]

        assert "+" not in created
        datetime.fromisoformat(created)

    def test_timestamps_are_close_to_utc_now(self, db, mock_asset):
        """Test the value is actually UTC, not local time"""
        db.insert_asset(mock_asset)

        created = datetime.fromisoformat(db.get_asset("TEST-001")["created_at"])
        delta = abs((datetime.now(timezone.utc).replace(tzinfo=None) - created).total_seconds())

        assert delta < 60


class TestIterSearchAssets:
    """Test the lazy row iterator used by the streaming export"""

    @pytest.fixture
    def db(self, tmp_path):
        """Create test database"""
        return Database(str(tmp_path / "test.db"))

    def test_yields_the_same_rows_as_search_assets(self, db, mock_assets):
        """Test the iterator matches the list-returning search"""
        db.insert_assets(mock_assets)

        listed, _ = db.search_assets(sort_by="id", sort_order="ASC")
        streamed = list(db.iter_search_assets(sort_by="id", sort_order="ASC"))

        assert streamed == listed

    def test_applies_the_same_filters(self, db, mock_assets):
        """Test filters behave identically on both paths"""
        db.insert_assets(mock_assets)

        listed, _ = db.search_assets(query="Madrid", filters={"type": "inmueble"})
        streamed = list(
            db.iter_search_assets(query="Madrid", filters={"type": "inmueble"})
        )

        assert streamed == listed

    def test_honours_the_limit(self, db, mock_assets):
        """Test the row cap is enforced"""
        db.insert_assets(mock_assets)

        assert len(list(db.iter_search_assets(limit=2))) == 2

    def test_invalid_sort_falls_back_to_the_default(self, db, mock_assets):
        """Test an unknown sort field cannot be injected"""
        db.insert_assets(mock_assets)

        rows = list(db.iter_search_assets(sort_by="; DROP TABLE assets", limit=10))

        assert len(rows) == len(mock_assets)

    def test_sqlite_error(self, tmp_path):
        """Test that sqlite3.Error while iterating raises RuntimeError"""
        db = Database(str(tmp_path / "test.db"))

        with patch.object(db, "_shared_connection") as mock_shared_conn:
            mock_conn = MagicMock()
            mock_conn.cursor.side_effect = sqlite3.Error("Iter error")
            mock_shared_conn.return_value = mock_conn

            with pytest.raises(RuntimeError, match="Failed to search assets"):
                list(db.iter_search_assets())
