"""
Timestamp helpers for AssetFinder.

datetime.utcnow() is deprecated from Python 3.12 onwards. The timezone-aware
replacement serialises with a "+00:00" suffix, which would change every value
this project stores and returns, so the helpers below produce the same naive
UTC representation the schema and the API already use.
"""

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Current UTC time as a naive datetime, matching the stored convention."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def utc_now_isoformat() -> str:
    """Current UTC time as the naive ISO string used by the schema and the API."""
    return utc_now().isoformat()
