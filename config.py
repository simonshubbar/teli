"""
Configuration for the Teli app.

The TMDB API key is loaded from an environment variable so it never
appears in the source code.  On PythonAnywhere you'll set this in
the WSGI config or the "Environment variables" section.

Locally, you can export it in your terminal before running:
    export TMDB_API_KEY="your_key_here"
    python app.py
"""

import os

# --- TMDB API ----------------------------------------------------------
# The v3 API key from themoviedb.org (Settings → API)
TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "")

# Base URL for all TMDB API requests
TMDB_BASE_URL = "https://api.themoviedb.org/3"

# Base URL for poster images (w500 = 500px wide — good balance of quality/speed)
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"

# --- Google OAuth -------------------------------------------------------
# These come from the Google Cloud Console (APIs & Services → Credentials).
# Set them as environment variables so they never appear in source code.
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")

# --- Database -----------------------------------------------------------
# Path to the SQLite database file (sits next to app.py)
DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "watchlist.db")

# --- Streaming providers ------------------------------------------------
# Country code for streaming availability (GB = United Kingdom)
PROVIDER_COUNTRY = "GB"

# How many days before we re-fetch streaming data for a title
PROVIDER_CACHE_DAYS = 7
