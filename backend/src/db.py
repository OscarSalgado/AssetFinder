import json
import sqlite3
import threading
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .timeutils import utc_now_isoformat

# Columns of the assets table in the order used by INSERT statements.
ASSET_COLUMNS = (
    "id",
    "type",
    "description",
    "price_initial",
    "price_min",
    "date_subasta",
    "location",
    "created_at",
    "updated_at",
)

REQUIRED_ASSET_FIELDS = ("id", "type", "description", "price_initial", "date_subasta")

HISTORY_COLUMNS = ("id", "query", "filters", "result_count", "created_at")

# Explicit column lists: SELECT * returns whatever the schema happens to hold and
# forces SQLite to read every column even when only some are used.
ASSET_SELECT = ", ".join(ASSET_COLUMNS)
HISTORY_SELECT = ", ".join(HISTORY_COLUMNS)


class Database:
    """SQLite database interface for AssetFinder"""

    # Every search appends a history row and nothing ever removed them, so the
    # table grew without bound. Keep a rolling window instead.
    SEARCH_HISTORY_LIMIT = 10000

    # Inserts between two prunes: pruning on every insert would pay a DELETE per
    # search for nothing.
    HISTORY_PRUNE_INTERVAL = 500

    def __init__(self, db_path: str = "data/assetfinder.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # Connections are cached per thread: sqlite3 connections are not meant to
        # be shared across threads, and opening one per query was costing a
        # connect() on every single database call.
        self._local = threading.local()
        self._history_inserts_since_prune = 0
        self.create_tables()

    def get_connection(self) -> sqlite3.Connection:
        """
        Open a new connection owned by the caller.

        The caller is responsible for closing it. Internal methods use the
        pooled connection instead (see _shared_connection).
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _shared_connection(self) -> sqlite3.Connection:
        """
        Return this thread's long-lived connection, opening it on first use.

        WAL lets readers run concurrently with a writer, and synchronous=NORMAL
        avoids an fsync per transaction, which dominated batch inserts.
        """
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA cache_size=-8000")  # ~8 MB page cache
            self._local.conn = conn
        return conn

    def close(self) -> None:
        """Close this thread's pooled connection, if it is open."""
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None

    def create_tables(self) -> bool:
        """Create database schema if not exists"""
        conn = self._shared_connection()
        try:
            cursor = conn.cursor()

            # Assets table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS assets (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    description TEXT NOT NULL,
                    price_initial REAL NOT NULL,
                    price_min REAL,
                    date_subasta TEXT NOT NULL,
                    location TEXT,
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL
                )
                """
            )

            # Search history table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS search_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query TEXT NOT NULL,
                    filters TEXT,
                    result_count INTEGER NOT NULL,
                    created_at TIMESTAMP NOT NULL
                )
                """
            )

            # Create indexes for better search performance
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_assets_type
                ON assets(type)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_assets_price
                ON assets(price_initial)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_assets_date
                ON assets(date_subasta)
                """
            )
            # Filter by type plus order by date is the most common search shape;
            # a composite index serves both without a sort step.
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_assets_type_date
                ON assets(type, date_subasta)
                """
            )
            # Without this, reading the history scans and sorts the whole table,
            # which grows with every single search.
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_history_created
                ON search_history(created_at DESC)
                """
            )

            conn.commit()
            return True
        except sqlite3.Error as e:
            raise RuntimeError(f"Failed to create tables: {e}") from e

    @staticmethod
    def _asset_row(asset: dict[str, Any], now: str) -> tuple:
        """Build the INSERT parameter tuple for an asset, validating it first."""
        for field in REQUIRED_ASSET_FIELDS:
            if field not in asset:
                raise ValueError(f"Missing required field: {field}")

        return (
            asset.get("id"),
            asset.get("type"),
            asset.get("description"),
            asset.get("price_initial"),
            asset.get("price_min"),
            asset.get("date_subasta"),
            asset.get("location"),
            asset.get("created_at", now),
            now,
        )

    def insert_asset(self, asset: dict[str, Any]) -> str:
        """Insert or replace asset in database"""
        conn = self._shared_connection()
        try:
            cursor = conn.cursor()
            now = utc_now_isoformat()
            row = self._asset_row(asset, now)

            cursor.execute(
                """
                INSERT OR REPLACE INTO assets
                (id, type, description, price_initial, price_min, date_subasta, location, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                row,
            )

            conn.commit()
            return asset.get("id")
        except sqlite3.Error as e:
            raise RuntimeError(f"Failed to insert asset: {e}") from e

    def insert_assets(self, assets: Iterable[dict[str, Any]]) -> int:
        """
        Insert or replace many assets in a single transaction.

        One executemany plus one commit instead of a commit (and an fsync) per
        row, which is what made syncing a catalogue slow.

        Returns:
            Number of assets written
        """
        conn = self._shared_connection()
        try:
            cursor = conn.cursor()
            now = utc_now_isoformat()
            rows = [self._asset_row(asset, now) for asset in assets]

            if not rows:
                return 0

            cursor.executemany(
                """
                INSERT OR REPLACE INTO assets
                (id, type, description, price_initial, price_min, date_subasta, location, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

            conn.commit()
            return len(rows)
        except sqlite3.Error as e:
            raise RuntimeError(f"Failed to insert assets: {e}") from e

    def get_asset(self, asset_id: str) -> dict[str, Any] | None:
        """Get asset by ID"""
        conn = self._shared_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(f"SELECT {ASSET_SELECT} FROM assets WHERE id = ?", (asset_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        except sqlite3.Error as e:
            raise RuntimeError(f"Failed to get asset: {e}") from e

    def search_assets(
        self,
        query: str | None = None,
        filters: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
        sort_by: str = "date_subasta",
        sort_order: str = "DESC",
    ) -> tuple[list[dict[str, Any]], int]:
        """Search assets with optional filters, pagination, and sorting"""
        conn = self._shared_connection()
        try:
            cursor = conn.cursor()

            sort_by, sort_order = self._validate_sort(sort_by, sort_order)
            where_sql, params = self._build_search_where(query, filters)

            # Count total results
            count_query = f"SELECT COUNT(*) FROM assets WHERE {where_sql}"
            cursor.execute(count_query, params)
            total = cursor.fetchone()[0]

            # Fetch paginated results with sorting
            data_query = f"""
                SELECT {ASSET_SELECT} FROM assets
                WHERE {where_sql}
                ORDER BY {sort_by} {sort_order}
                LIMIT ? OFFSET ?
            """
            cursor.execute(data_query, params + [limit, offset])
            rows = cursor.fetchall()

            return [dict(row) for row in rows], total
        except sqlite3.Error as e:
            raise RuntimeError(f"Failed to search assets: {e}") from e

    @staticmethod
    def _validate_sort(sort_by: str, sort_order: str) -> tuple[str, str]:
        """Clamp sort parameters to the allow-list before interpolating them."""
        valid_sort_fields = ["price_initial", "date_subasta", "id", "type"]
        if sort_by not in valid_sort_fields:
            sort_by = "date_subasta"

        valid_sort_orders = ["ASC", "DESC"]
        if sort_order.upper() not in valid_sort_orders:
            sort_order = "DESC"

        return sort_by, sort_order

    @staticmethod
    def _build_search_where(
        query: str | None, filters: dict[str, Any] | None
    ) -> tuple[str, list]:
        """
        Build the WHERE clause and parameters shared by search and export.

        Kept in one place so the streaming export cannot drift from the
        paginated search and silently apply different filters.
        """
        filters = filters or {}
        where_clauses = []
        params: list = []

        # Text search in description
        if query:
            where_clauses.append("description LIKE ?")
            params.append(f"%{query}%")

        # Type filter
        if "type" in filters and filters["type"]:
            where_clauses.append("type = ?")
            params.append(filters["type"])

        # Price range filter
        if "price_min" in filters and filters["price_min"] is not None:
            where_clauses.append("price_initial >= ?")
            params.append(filters["price_min"])

        if "price_max" in filters and filters["price_max"] is not None:
            where_clauses.append("price_initial <= ?")
            params.append(filters["price_max"])

        # Date range filter
        if "date_from" in filters and filters["date_from"]:
            where_clauses.append("date_subasta >= ?")
            params.append(filters["date_from"])

        if "date_to" in filters and filters["date_to"]:
            where_clauses.append("date_subasta <= ?")
            params.append(filters["date_to"])

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
        return where_sql, params

    def iter_search_assets(
        self,
        query: str | None = None,
        filters: dict[str, Any] | None = None,
        limit: int = 100,
        sort_by: str = "date_subasta",
        sort_order: str = "DESC",
    ) -> Iterable[dict[str, Any]]:
        """
        Yield matching assets one at a time instead of building a list.

        Used by the CSV export: materialising up to MAX_EXPORT_ROWS rows made
        peak memory grow with the size of the result set.
        """
        conn = self._shared_connection()
        try:
            sort_by, sort_order = self._validate_sort(sort_by, sort_order)
            where_sql, params = self._build_search_where(query, filters)

            cursor = conn.cursor()
            cursor.execute(
                f"""
                SELECT {ASSET_SELECT} FROM assets
                WHERE {where_sql}
                ORDER BY {sort_by} {sort_order}
                LIMIT ?
                """,
                params + [limit],
            )

            for row in cursor:
                yield dict(row)
        except sqlite3.Error as e:
            raise RuntimeError(f"Failed to search assets: {e}") from e

    def add_search_history(
        self, query: str, filters: dict[str, Any] | None, result_count: int
    ) -> int:
        """Log search query to history"""
        conn = self._shared_connection()
        try:
            cursor = conn.cursor()
            now = utc_now_isoformat()
            filters_json = json.dumps(filters) if filters else None

            cursor.execute(
                """
                INSERT INTO search_history (query, filters, result_count, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (query, filters_json, result_count, now),
            )

            conn.commit()
            row_id = cursor.lastrowid
        except sqlite3.Error as e:
            raise RuntimeError(f"Failed to add search history: {e}") from e

        # Amortised: one prune every HISTORY_PRUNE_INTERVAL inserts.
        self._history_inserts_since_prune += 1
        if self._history_inserts_since_prune >= self.HISTORY_PRUNE_INTERVAL:
            self.prune_search_history()

        return row_id

    def prune_search_history(self, keep: int | None = None) -> int:
        """
        Drop the oldest history rows, keeping a rolling window.

        Deletes by primary key range rather than by timestamp: id is
        INTEGER PRIMARY KEY AUTOINCREMENT, so it is monotonic and never reused,
        and the delete walks the primary key index at O(rows removed).

        Args:
            keep: Rows to retain (defaults to SEARCH_HISTORY_LIMIT)

        Returns:
            Number of rows removed
        """
        keep = self.SEARCH_HISTORY_LIMIT if keep is None else keep
        conn = self._shared_connection()

        try:
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(id) FROM search_history")
            max_id = cursor.fetchone()[0]

            self._history_inserts_since_prune = 0

            if max_id is None:
                return 0

            cutoff = max_id - keep
            if cutoff <= 0:
                return 0

            cursor.execute("DELETE FROM search_history WHERE id <= ?", (cutoff,))
            conn.commit()
            return cursor.rowcount
        except sqlite3.Error as e:
            raise RuntimeError(f"Failed to prune search history: {e}") from e

    def get_search_history(
        self, limit: int = 50, offset: int = 0
    ) -> tuple[list[dict[str, Any]], int]:
        """Get search history with pagination"""
        conn = self._shared_connection()
        try:
            cursor = conn.cursor()

            # Count
            cursor.execute("SELECT COUNT(*) FROM search_history")
            total = cursor.fetchone()[0]

            # Fetch
            cursor.execute(
                f"""
                SELECT {HISTORY_SELECT} FROM search_history
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            )
            rows = cursor.fetchall()

            results = []
            for row in rows:
                result = dict(row)
                if result["filters"]:
                    result["filters"] = json.loads(result["filters"])
                results.append(result)

            return results, total
        except sqlite3.Error as e:
            raise RuntimeError(f"Failed to get search history: {e}") from e

    def delete_all_assets(self) -> bool:
        """Delete all assets (for testing only)"""
        conn = self._shared_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM assets")
            conn.commit()
            return True
        except sqlite3.Error as e:
            raise RuntimeError(f"Failed to delete assets: {e}") from e

    def get_asset_count(self) -> int:
        """Get total number of assets"""
        conn = self._shared_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM assets")
            return cursor.fetchone()[0]
        except sqlite3.Error as e:
            raise RuntimeError(f"Failed to get asset count: {e}") from e
