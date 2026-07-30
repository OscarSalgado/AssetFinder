from flask import Flask, request, jsonify, Response, stream_with_context
from typing import Tuple
import csv
import gzip
import io
import logging

from .db import Database
from .scraper import create_scraper
from .deduplication import DeduplicationEngine
from .security import SecurityHeaders, rate_limiter
from .timeutils import utc_now_isoformat

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
MAX_ASSET_ID_LENGTH = 100

# Response compression
COMPRESSION_MIN_BYTES = 1024
COMPRESSIBLE_MIMETYPES = frozenset(
    {"application/json", "application/javascript", "image/svg+xml"}
)

# CSV export is streamed: the buffer is flushed once it reaches this size, so
# peak memory does not grow with the number of exported rows.
EXPORT_CHUNK_BYTES = 64 * 1024
EXPORT_FIELDNAMES = [
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

# Deduplication configuration
MAX_DUPLICATE_CANDIDATES = 5000
DUPLICATE_CONFIDENCE_THRESHOLD = 0.8

# Initialize database and scraper
db = Database()
scraper = create_scraper(use_mock=True, db=db)


# Seeding is a one-off startup concern, so it is guarded by a flag instead of
# counting rows on every single request.
_db_initialized = False


def _initialize_database():
    """Populate database with initial assets if empty"""
    global _db_initialized
    if db.get_asset_count() == 0:
        scraper.fetch_assets(save_to_db=True)
    _db_initialized = True


@app.before_request
def before_request():
    """Rate limit, then ensure database and scraper are initialized"""
    logger.info(f"{request.method} {request.path} from {request.remote_addr}")

    identifier = request.remote_addr or "unknown"
    if rate_limiter.is_rate_limited(identifier):
        retry_after = rate_limiter.retry_after(identifier)
        response = jsonify(
            {
                "error": "Rate limit exceeded",
                "code": "RATE_LIMITED",
            }
        )
        response.headers["Retry-After"] = str(retry_after)
        return response, 429

    if _db_initialized:
        return

    try:
        _initialize_database()
    except Exception as e:
        logger.error(f"Error initializing database in before_request: {type(e).__name__}")
        # Re-raise to trigger error handlers
        raise


@app.after_request
def add_security_headers(response):
    """Add security headers to all responses"""
    # SecurityHeaders is the single source of truth for the header set.
    for header, value in SecurityHeaders.get_security_headers(
        origin=request.headers.get("Origin")
    ).items():
        response.headers[header] = value

    remaining = rate_limiter.get_remaining(request.remote_addr or "unknown")
    response.headers["X-RateLimit-Limit"] = str(rate_limiter.max_requests)
    response.headers["X-RateLimit-Remaining"] = str(remaining)

    return _compress_response(response)


def _compress_response(response):
    """
    Compress the response body when the client accepts gzip.

    Streamed responses are left untouched: reading their body would consume the
    generator and defeat the streaming export entirely. The check is
    `is_streamed`, not `direct_passthrough` — a Response built from a generator
    has direct_passthrough set to False, so that guard would never fire.

    No ETag is attached: every payload embeds a freshly generated `timestamp`,
    so the validator would differ on every request and a 304 could never
    happen. Hashing each body for an unreachable cache hit is pure overhead.
    """
    if response.is_streamed or response.direct_passthrough:
        return response

    response.headers["Vary"] = "Accept-Encoding"

    if response.status_code != 200:
        return response

    if "gzip" not in request.headers.get("Accept-Encoding", ""):
        return response

    if response.headers.get("Content-Encoding"):
        return response

    mimetype = (response.mimetype or "").lower()
    if not (mimetype.startswith("text/") or mimetype in COMPRESSIBLE_MIMETYPES):
        return response

    body = response.get_data()
    # Below roughly one packet the gzip header costs more than it saves.
    if len(body) < COMPRESSION_MIN_BYTES:
        return response

    response.set_data(gzip.compress(body, compresslevel=6))
    response.headers["Content-Encoding"] = "gzip"
    response.headers["Content-Length"] = str(len(response.get_data()))
    return response


@app.route("/api/health", methods=["GET"])
def health_check() -> Tuple[dict, int]:
    """Health check endpoint"""
    try:
        return (
            {
                "status": "ok",
                "timestamp": utc_now_isoformat(),
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
                "timestamp": utc_now_isoformat(),
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
                "timestamp": utc_now_isoformat(),
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
                "timestamp": utc_now_isoformat(),
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
                "timestamp": utc_now_isoformat(),
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

        # Every parameter is validated above: once the first byte is on the wire
        # the status code is fixed, so nothing that can fail may happen later.
        rows = iter(
            db.iter_search_assets(
                query=query or None,
                filters=filters or None,
                limit=MAX_EXPORT_ROWS,
                sort_by=sort_by,
                sort_order=sort_order,
            )
        )

        # Pull the first row eagerly. iter_search_assets is a generator, so the
        # query does not even run until the first next(): without this, a failing
        # query would surface mid-stream, once the 200 is already committed, and
        # the client would receive a truncated CSV that looks successful.
        try:
            first_row = next(rows)
        except StopIteration:
            first_row = None

        def generate():
            """
            Serialise the CSV in chunks.

            Rows arrive lazily from SQLite and the buffer is drained every
            EXPORT_CHUNK_BYTES, so peak memory is bounded by the chunk size
            rather than by the size of the result set.
            """
            buffer = io.StringIO()
            writer = csv.DictWriter(buffer, fieldnames=EXPORT_FIELDNAMES, restval="")
            exported = 0

            try:
                # The header is only emitted when there is at least one row,
                # matching the previous behaviour of returning an empty body.
                if first_row is not None:
                    writer.writeheader()
                    writer.writerow(first_row)
                    exported = 1

                for row in rows:
                    writer.writerow(row)
                    exported += 1

                    if buffer.tell() >= EXPORT_CHUNK_BYTES:
                        yield buffer.getvalue()
                        buffer.seek(0)
                        buffer.truncate(0)

                if buffer.tell():
                    yield buffer.getvalue()
            except Exception as e:
                # The status code is already sent, so the download ends up
                # truncated. Log it loudly rather than failing silently.
                logger.error(
                    f"Export truncated after {exported} rows: {type(e).__name__}"
                )
                raise

            logger.info(f"Export completed: {exported} rows, query='{query[:50]}'")

        response = Response(
            stream_with_context(generate()), mimetype="text/csv"
        )
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

        if len(asset_id) > MAX_ASSET_ID_LENGTH:
            return jsonify({"error": "asset_id exceeds maximum length"}), 400

        # Get the target asset
        asset = db.get_asset(asset_id)
        if not asset:
            return jsonify({"error": f"Asset {asset_id} not found"}), 404

        # Get candidate assets to compare against. search_assets returns a
        # (rows, total) tuple, so the list has to be unpacked explicitly.
        candidates, _ = db.search_assets(
            query=None,
            filters=None,
            limit=MAX_DUPLICATE_CANDIDATES,
            offset=0,
        )

        # Find duplicates using deduplication engine
        engine = DeduplicationEngine(confidence_threshold=DUPLICATE_CONFIDENCE_THRESHOLD)
        duplicates = engine.find_duplicates(asset, candidates)

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
                    "timestamp": utc_now_isoformat() + "Z",
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
    global db, scraper, _db_initialized
    db = Database(db_path)
    scraper = create_scraper(use_mock=True, db=db)
    # A fresh database has to be seeded again, so drop the one-off init flag.
    _db_initialized = False
    # The limiter is process-global; rebuilding the app starts a clean window.
    rate_limiter.reset()
    return app


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
