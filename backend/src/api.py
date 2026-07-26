from flask import Flask, request, jsonify, Response
from datetime import datetime
from typing import Tuple
from functools import wraps
import os
import csv
import io
import logging

from .db import Database
from .scraper import create_scraper
from .deduplication import DeduplicationEngine

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False

# Security configuration
MAX_QUERY_LENGTH = 1000
MAX_EXPORT_ROWS = 50000
RATE_LIMIT_REQUESTS = 100
RATE_LIMIT_WINDOW = 3600  # 1 hour

# Initialize database and scraper
db = Database()
scraper = create_scraper(use_mock=True, db=db)


def _initialize_database():
    """Populate database with initial assets if empty"""
    if db.get_asset_count() == 0:
        scraper.fetch_assets(save_to_db=True)


@app.before_request
def before_request():
    """Ensure database and scraper are initialized and log requests"""
    logger.info(f"{request.method} {request.path} from {request.remote_addr}")
    try:
        if db.get_asset_count() == 0:
            _initialize_database()
    except Exception as e:
        logger.error(f"Error initializing database in before_request: {type(e).__name__}")
        # Re-raise to trigger error handlers
        raise


@app.after_request
def add_security_headers(response):
    """Add security headers to all responses"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline';"
    return response


@app.route("/api/health", methods=["GET"])
def health_check() -> Tuple[dict, int]:
    """Health check endpoint"""
    try:
        return (
            {
                "status": "ok",
                "timestamp": datetime.utcnow().isoformat(),
                "scraper": {"healthy": scraper.is_healthy()},
                "database": {"connected": True},
            },
            200,
        )
    except Exception as e:
        logger.error(f"Error in health check: {type(e).__name__}")
        return (
            {
                "error": "Internal server error",
                "code": "INTERNAL_ERROR",
            },
            500,
        )


@app.route("/api/search", methods=["GET"])
def search_assets() -> Tuple[dict, int]:
    """
    Search assets endpoint

    Query parameters:
    - q: Search query string
    - type: Filter by type (inmueble, vehiculo, mueble, otros)
    - price_min: Minimum price
    - price_max: Maximum price
    - date_from: Date range start (YYYY-MM-DD)
    - date_to: Date range end (YYYY-MM-DD)
    - sort_by: Sort field (price_initial, date_subasta, id, type) (default: date_subasta)
    - sort_order: Sort order (ASC, DESC) (default: DESC)
    - limit: Results per page (default: 50)
    - offset: Pagination offset (default: 0)
    """
    try:
        # Get query parameters
        query = request.args.get("q", "").strip()

        # Validate query length
        if len(query) > MAX_QUERY_LENGTH:
            logger.warning(f"Query string exceeds max length: {len(query)}")
            return (
                {"error": "Query string too long", "code": "INVALID_PARAM"},
                400,
            )

        limit = min(int(request.args.get("limit", 50)), 1000)
        offset = max(int(request.args.get("offset", 0)), 0)
        sort_by = request.args.get("sort_by", "date_subasta")
        sort_order = request.args.get("sort_order", "DESC").upper()

        # Build filters dict
        filters = {}

        if type_filter := request.args.get("type"):
            if type_filter in ["inmueble", "vehiculo", "mueble", "otros"]:
                filters["type"] = type_filter

        if price_min := request.args.get("price_min"):
            try:
                filters["price_min"] = float(price_min)
            except ValueError:
                return (
                    {"error": "Invalid price_min value", "code": "INVALID_PARAM"},
                    400,
                )

        if price_max := request.args.get("price_max"):
            try:
                filters["price_max"] = float(price_max)
            except ValueError:
                return (
                    {"error": "Invalid price_max value", "code": "INVALID_PARAM"},
                    400,
                )

        if date_from := request.args.get("date_from"):
            filters["date_from"] = date_from

        if date_to := request.args.get("date_to"):
            filters["date_to"] = date_to

        # Search in database with sorting
        assets, total = db.search_assets(
            query=query or None,
            filters=filters or None,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        # Log search to history
        db.add_search_history(query or "", filters or {}, total)

        logger.info(f"Search completed: query='{query[:50]}', filters={filters}, results={total}")

        return (
            {
                "assets": assets,
                "total": total,
                "limit": limit,
                "offset": offset,
                "sort_by": sort_by,
                "sort_order": sort_order,
                "timestamp": datetime.utcnow().isoformat(),
            },
            200,
        )

    except ValueError as e:
        logger.error(f"Validation error in search: {type(e).__name__}")
        return (
            {
                "error": "Invalid input parameters",
                "code": "INVALID_PARAM",
            },
            400,
        )
    except Exception as e:
        logger.error(f"Unexpected error in search: {type(e).__name__}")
        return (
            {
                "error": "Search operation failed",
                "code": "SEARCH_ERROR",
            },
            500,
        )


@app.route("/api/assets/<asset_id>", methods=["GET"])
def get_asset(asset_id: str) -> Tuple[dict, int]:
    """Get specific asset by ID"""
    try:
        asset = db.get_asset(asset_id)

        if not asset:
            logger.info(f"Asset not found: {asset_id}")
            return (
                {"error": "Asset not found", "code": "NOT_FOUND"},
                404,
            )

        logger.info(f"Asset retrieved: {asset_id}")
        return (
            {
                "asset": asset,
                "timestamp": datetime.utcnow().isoformat(),
            },
            200,
        )

    except Exception as e:
        logger.error(f"Error retrieving asset {asset_id}: {type(e).__name__}")
        return (
            {
                "error": "Failed to retrieve asset",
                "code": "GET_ASSET_ERROR",
            },
            500,
        )


@app.route("/api/sync", methods=["POST"])
def sync_assets() -> Tuple[dict, int]:
    """Sync assets from portal to database"""
    try:
        logger.info("Starting asset sync")
        count = scraper.sync_assets()
        logger.info(f"Asset sync completed: {count} assets synced")
        return (
            {
                "message": f"Synced {count} assets",
                "count": count,
                "timestamp": datetime.utcnow().isoformat(),
            },
            200,
        )
    except Exception as e:
        logger.error(f"Error during sync: {type(e).__name__}")
        return (
            {
                "error": "Sync operation failed",
                "code": "SYNC_ERROR",
            },
            500,
        )


@app.route("/api/search-history", methods=["GET"])
def get_search_history() -> Tuple[dict, int]:
    """Get search history"""
    try:
        limit = min(int(request.args.get("limit", 50)), 1000)
        offset = max(int(request.args.get("offset", 0)), 0)

        history, total = db.get_search_history(limit=limit, offset=offset)

        logger.info(f"Search history retrieved: {total} total items, returned {len(history)}")
        return (
            {
                "history": history,
                "total": total,
                "limit": limit,
                "offset": offset,
                "timestamp": datetime.utcnow().isoformat(),
            },
            200,
        )

    except ValueError as e:
        logger.error(f"Validation error in search history: {type(e).__name__}")
        return (
            {
                "error": "Invalid pagination parameters",
                "code": "INVALID_PARAM",
            },
            400,
        )
    except Exception as e:
        logger.error(f"Unexpected error in search history: {type(e).__name__}")
        return (
            {
                "error": "Failed to retrieve search history",
                "code": "HISTORY_ERROR",
            },
            500,
        )


@app.route("/api/export", methods=["GET"])
def export_assets() -> Tuple[Response, int]:
    """
    Export search results to CSV

    Query parameters:
    - q: Search query string
    - type: Filter by type
    - price_min: Minimum price
    - price_max: Maximum price
    - date_from: Date range start
    - date_to: Date range end
    - sort_by: Sort field
    - sort_order: Sort order
    """
    try:
        query = request.args.get("q", "").strip()

        # Validate query length
        if len(query) > MAX_QUERY_LENGTH:
            logger.warning(f"Export query exceeds max length: {len(query)}")
            return (
                jsonify({"error": "Query string too long", "code": "INVALID_PARAM"}),
                400,
            )

        sort_by = request.args.get("sort_by", "date_subasta")
        sort_order = request.args.get("sort_order", "DESC").upper()

        filters = {}
        if type_filter := request.args.get("type"):
            if type_filter in ["inmueble", "vehiculo", "mueble", "otros"]:
                filters["type"] = type_filter

        if price_min := request.args.get("price_min"):
            try:
                filters["price_min"] = float(price_min)
            except ValueError:
                return (
                    jsonify({"error": "Invalid price_min value", "code": "INVALID_PARAM"}),
                    400,
                )

        if price_max := request.args.get("price_max"):
            try:
                filters["price_max"] = float(price_max)
            except ValueError:
                return (
                    jsonify({"error": "Invalid price_max value", "code": "INVALID_PARAM"}),
                    400,
                )

        if date_from := request.args.get("date_from"):
            filters["date_from"] = date_from

        if date_to := request.args.get("date_to"):
            filters["date_to"] = date_to

        assets, total = db.search_assets(
            query=query or None,
            filters=filters or None,
            limit=MAX_EXPORT_ROWS,
            offset=0,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        # Validate export size
        if len(assets) > MAX_EXPORT_ROWS:
            logger.warning(f"Export request exceeds max rows: {len(assets)}")
            return (
                jsonify({"error": f"Export limited to {MAX_EXPORT_ROWS} rows", "code": "EXPORT_TOO_LARGE"}),
                413,
            )

        output = io.StringIO()
        if assets:
            fieldnames = [
                "id",
                "type",
                "description",
                "price_initial",
                "price_min",
                "date_subasta",
                "location",
                "created_at",
                "updated_at",
            ]
            writer = csv.DictWriter(output, fieldnames=fieldnames, restval="")
            writer.writeheader()
            writer.writerows(assets)

        logger.info(f"Export completed: {len(assets)} rows, query='{query[:50]}'")
        response = Response(output.getvalue(), mimetype="text/csv")
        response.headers["Content-Disposition"] = "attachment; filename=assets_export.csv"
        return response, 200

    except ValueError as e:
        logger.error(f"Validation error in export: {type(e).__name__}")
        return (
            jsonify(
                {
                    "error": "Invalid input parameters",
                    "code": "INVALID_PARAM",
                }
            ),
            400,
        )
    except Exception as e:
        logger.error(f"Unexpected error in export: {type(e).__name__}")
        return (
            jsonify(
                {
                    "error": "Export operation failed",
                    "code": "EXPORT_ERROR",
                }
            ),
            500,
        )


@app.route("/api/duplicates", methods=["GET"])
def find_duplicates() -> Tuple[dict, int]:
    """Find potential duplicates for an asset"""
    try:
        asset_id = request.args.get("asset_id", "").strip()

        # Validate asset_id
        if not asset_id:
            return jsonify({"error": "asset_id parameter is required"}), 400

        if len(asset_id) > 100:
            return jsonify({"error": "asset_id exceeds maximum length"}), 400

        # Get the target asset
        asset = db.get_asset(asset_id)
        if not asset:
            return jsonify({"error": f"Asset {asset_id} not found"}), 404

        # Get all assets to search for duplicates
        all_assets = db.search_assets("", {})

        # Find duplicates using deduplication engine
        engine = DeduplicationEngine(confidence_threshold=0.8)
        duplicates = engine.find_duplicates(asset, all_assets)

        # Format response
        return (
            jsonify(
                {
                    "asset_id": asset_id,
                    "asset": asset,
                    "duplicate_count": len(duplicates),
                    "duplicates": [
                        {
                            "id": dup[0].get("id"),
                            "description": dup[0].get("description"),
                            "type": dup[0].get("type"),
                            "price_initial": dup[0].get("price_initial"),
                            "location": dup[0].get("location"),
                            "confidence": round(dup[1], 3),
                        }
                        for dup in duplicates
                    ],
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                }
            ),
            200,
        )

    except ValueError as e:
        logger.error(f"Validation error in duplicates: {str(e)}")
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Unexpected error in duplicates: {type(e).__name__}: {str(e)}")
        return (
            jsonify(
                {
                    "error": "Duplicate detection failed",
                    "code": "DUPLICATE_ERROR",
                }
            ),
            500,
        )


@app.errorhandler(404)
def not_found(error):
    """404 error handler"""
    logger.warning(f"404 error: {request.path}")
    return (
        {
            "error": "Endpoint not found",
            "code": "NOT_FOUND",
        },
        404,
    )


@app.errorhandler(500)
def internal_error(error):
    """500 error handler"""
    logger.error(f"500 error: {type(error).__name__}")
    return (
        {
            "error": "Internal server error",
            "code": "INTERNAL_ERROR",
        },
        500,
    )


def create_app(db_path: str = "data/assetfinder.db"):
    """Factory function to create app with custom DB path (for testing)"""
    global db, scraper
    db = Database(db_path)
    scraper = create_scraper(use_mock=True, db=db)
    return app


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
