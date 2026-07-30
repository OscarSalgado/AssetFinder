"""
Gunicorn configuration for AssetFinder.

Sized for a small container (the free tiers of Render/Fly give a shared core and
512 MB), not for a large host.
"""

import os

bind = f"0.0.0.0:{os.environ.get('PORT', 5000)}"

# SQLite is the store and the connection pool is per thread, so scaling with
# threads inside one process keeps a single writer and avoids the
# "database is locked" contention that several worker processes would cause.
workers = 1
threads = int(os.environ.get("GUNICORN_THREADS", 4))
worker_class = "gthread"

# The seeding scrape runs on the first request; leave room for it.
timeout = 60
graceful_timeout = 30

# Recycle workers periodically: the rate limiter keeps in-memory state, and this
# bounds any slow leak without needing an external store.
max_requests = 2000
max_requests_jitter = 200

accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("LOG_LEVEL", "info")

# Behind a proxy (Render, Fly) the client address arrives in a header; without
# this the rate limiter would see the proxy address for every request and
# throttle all users as one.
forwarded_allow_ips = os.environ.get("FORWARDED_ALLOW_IPS", "*")
