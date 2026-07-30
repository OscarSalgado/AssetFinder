"""
WSGI entrypoint for production.

Run with a real WSGI server instead of Flask's development server:

    gunicorn --config gunicorn.conf.py wsgi:application

The database path comes from ASSETFINDER_DB so the process can write to a
mounted volume rather than the repository directory.
"""

from src.api import app as application

# Alias for servers that look for `app`.
app = application

__all__ = ["app", "application"]
