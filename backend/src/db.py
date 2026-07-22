import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any


class Database:
    """SQLite database interface for AssetFinder"""

    def __init__(self, db_path: str = "data/assetfinder.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.create_tables()

    def get_connection(self) -> sqlite3.Connection:
        """Get database connection with row factory"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def create_tables(self) -> bool:
        """Create database schema if not exists"""
        conn = self.get_connection()
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

            conn.commit()
            return True
        except sqlite3.Error as e:
            raise RuntimeError(f"Failed to create tables: {e}")
        finally:
            conn.close()

    def insert_asset(self, asset: Dict[str, Any]) -> str:
        """Insert or replace asset in database"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            now = datetime.utcnow().isoformat()

            # Validate required fields
            required = ["id", "type", "description", "price_initial", "date_subasta"]
            for field in required:
                if field not in asset:
                    raise ValueError(f"Missing required field: {field}")

            cursor.execute(
                """
                INSERT OR REPLACE INTO assets
                (id, type, description, price_initial, price_min, date_subasta, location, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    asset.get("id"),
                    asset.get("type"),
                    asset.get("description"),
                    asset.get("price_initial"),
                    asset.get("price_min"),
                    asset.get("date_subasta"),
                    asset.get("location"),
                    asset.get("created_at", now),
                    now,
                ),
            )

            conn.commit()
            return asset.get("id")
        except sqlite3.Error as e:
            raise RuntimeError(f"Failed to insert asset: {e}")
        finally:
            conn.close()

    def get_asset(self, asset_id: str) -> Optional[Dict[str, Any]]:
        """Get asset by ID"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM assets WHERE id = ?", (asset_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        except sqlite3.Error as e:
            raise RuntimeError(f"Failed to get asset: {e}")
        finally:
            conn.close()

    def search_assets(
        self,
        query: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 100,
        offset: int = 0,
        sort_by: str = "date_subasta",
        sort_order: str = "DESC",
    ) -> tuple[List[Dict[str, Any]], int]:
        """Search assets with optional filters, pagination, and sorting"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            filters = filters or {}

            valid_sort_fields = ["price_initial", "date_subasta", "id", "type"]
            if sort_by not in valid_sort_fields:
                sort_by = "date_subasta"

            valid_sort_orders = ["ASC", "DESC"]
            if sort_order.upper() not in valid_sort_orders:
                sort_order = "DESC"

            # Base query
            where_clauses = []
            params = []

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

            # Count total results
            count_query = f"SELECT COUNT(*) FROM assets WHERE {where_sql}"
            cursor.execute(count_query, params)
            total = cursor.fetchone()[0]

            # Fetch paginated results with sorting
            data_query = f"""
                SELECT * FROM assets
                WHERE {where_sql}
                ORDER BY {sort_by} {sort_order}
                LIMIT ? OFFSET ?
            """
            cursor.execute(data_query, params + [limit, offset])
            rows = cursor.fetchall()

            return [dict(row) for row in rows], total
        except sqlite3.Error as e:
            raise RuntimeError(f"Failed to search assets: {e}")
        finally:
            conn.close()

    def add_search_history(
        self, query: str, filters: Optional[Dict[str, Any]], result_count: int
    ) -> int:
        """Log search query to history"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            now = datetime.utcnow().isoformat()
            filters_json = json.dumps(filters) if filters else None

            cursor.execute(
                """
                INSERT INTO search_history (query, filters, result_count, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (query, filters_json, result_count, now),
            )

            conn.commit()
            return cursor.lastrowid
        except sqlite3.Error as e:
            raise RuntimeError(f"Failed to add search history: {e}")
        finally:
            conn.close()

    def get_search_history(
        self, limit: int = 50, offset: int = 0
    ) -> tuple[List[Dict[str, Any]], int]:
        """Get search history with pagination"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()

            # Count
            cursor.execute("SELECT COUNT(*) FROM search_history")
            total = cursor.fetchone()[0]

            # Fetch
            cursor.execute(
                """
                SELECT * FROM search_history
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
            raise RuntimeError(f"Failed to get search history: {e}")
        finally:
            conn.close()

    def delete_all_assets(self) -> bool:
        """Delete all assets (for testing only)"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM assets")
            conn.commit()
            return True
        except sqlite3.Error as e:
            raise RuntimeError(f"Failed to delete assets: {e}")
        finally:
            conn.close()

    def get_asset_count(self) -> int:
        """Get total number of assets"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM assets")
            return cursor.fetchone()[0]
        except sqlite3.Error as e:
            raise RuntimeError(f"Failed to get asset count: {e}")
        finally:
            conn.close()
