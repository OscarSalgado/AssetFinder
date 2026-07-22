from flask import Flask, request, jsonify
from datetime import datetime
from typing import Tuple
import os

from .db import Database
from .scraper import create_scraper

# Initialize Flask app
app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False

# Initialize database and scraper
db = Database()
scraper = create_scraper()


@app.before_request
def before_request():
    """Ensure database and scraper are initialized"""
    pass


@app.route("/api/health", methods=["GET"])
def health_check() -> Tuple[dict, int]:
    """Health check endpoint"""
    return (
        {
            "status": "ok",
            "timestamp": datetime.utcnow().isoformat(),
            "scraper": {"healthy": scraper.is_healthy()},
            "database": {"connected": True},
        },
        200,
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
    - limit: Results per page (default: 50)
    - offset: Pagination offset (default: 0)
    """
    try:
        # Get query parameters
        query = request.args.get("q", "").strip()
        limit = min(int(request.args.get("limit", 50)), 1000)
        offset = max(int(request.args.get("offset", 0)), 0)

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

        # Search in database
        assets, total = db.search_assets(
            query=query or None, filters=filters or None, limit=limit, offset=offset
        )

        # Log search to history
        db.add_search_history(query or "", filters or {}, total)

        return (
            {
                "assets": assets,
                "total": total,
                "limit": limit,
                "offset": offset,
                "timestamp": datetime.utcnow().isoformat(),
            },
            200,
        )

    except Exception as e:
        return (
            {
                "error": str(e),
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
            return (
                {"error": "Asset not found", "code": "NOT_FOUND"},
                404,
            )

        return (
            {
                "asset": asset,
                "timestamp": datetime.utcnow().isoformat(),
            },
            200,
        )

    except Exception as e:
        return (
            {
                "error": str(e),
                "code": "GET_ASSET_ERROR",
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

    except Exception as e:
        return (
            {
                "error": str(e),
                "code": "HISTORY_ERROR",
            },
            500,
        )


@app.errorhandler(404)
def not_found(error):
    """404 error handler"""
    return (
        {
            "error": "Endpoint not found",
            "code": "NOT_FOUND",
            "path": request.path,
        },
        404,
    )


@app.errorhandler(500)
def internal_error(error):
    """500 error handler"""
    return (
        {
            "error": "Internal server error",
            "code": "INTERNAL_ERROR",
        },
        500,
    )


def create_app(db_path: str = "data/assetfinder.db"):
    """Factory function to create app with custom DB path (for testing)"""
    global db
    db = Database(db_path)
    return app


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
