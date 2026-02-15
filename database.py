"""
Database helper functions for the Teli app.

Uses SQLite — a simple file-based database built into Python.
No server to install, no password to configure.  The entire database
lives in a single file called watchlist.db.

Key concept: We use a context manager (get_db) so the database
connection is automatically closed when we're done with it.
"""

import sqlite3
from datetime import datetime
from config import DATABASE


def get_db():
    """
    Open a connection to the SQLite database.

    row_factory = sqlite3.Row  lets us access columns by name
    instead of by number.  So instead of row[1] we can write row["title"].
    """
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row      # Access columns by name
    conn.execute("PRAGMA foreign_keys = ON")  # Enable foreign key support
    return conn


def init_db():
    """
    Create the database tables if they don't exist yet.

    This runs every time the app starts, but CREATE TABLE IF NOT EXISTS
    means it only actually creates the tables the very first time.
    """
    conn = get_db()

    # --- items table: each movie/show on your watchlist ---
    conn.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            tmdb_id       INTEGER NOT NULL,
            media_type    TEXT NOT NULL,          -- 'movie' or 'tv'
            title         TEXT NOT NULL,
            year          TEXT,                   -- Release year (text because some are ranges like "2020-2024")
            poster_path   TEXT,                   -- Path to poster image on TMDB
            overview      TEXT,                   -- Plot summary
            status        TEXT NOT NULL DEFAULT 'want',  -- 'want', 'progress', or 'watched'
            rating        INTEGER,                -- Your rating 1-10 (optional)
            notes         TEXT,                   -- Your personal notes (optional)
            added_date    TEXT NOT NULL,
            updated_date  TEXT NOT NULL,
            UNIQUE(tmdb_id, media_type)           -- Prevent adding the same title twice
        )
    """)

    # --- providers table: cached streaming availability ---
    conn.execute("""
        CREATE TABLE IF NOT EXISTS providers (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            tmdb_id        INTEGER NOT NULL,
            media_type     TEXT NOT NULL,
            provider_name  TEXT NOT NULL,
            provider_logo  TEXT,                  -- Path to logo image on TMDB
            provider_type  TEXT NOT NULL,          -- 'flatrate' (stream), 'rent', or 'buy'
            country        TEXT NOT NULL DEFAULT 'GB',
            fetched_date   TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


# -----------------------------------------------------------------------
# CRUD operations (Create, Read, Update, Delete)
# -----------------------------------------------------------------------

def add_item(tmdb_id, media_type, title, year, poster_path, overview):
    """Add a movie/show to the watchlist with status 'want'."""
    now = datetime.now().isoformat()
    conn = get_db()
    try:
        conn.execute(
            """INSERT INTO items (tmdb_id, media_type, title, year, poster_path, overview, status, added_date, updated_date)
               VALUES (?, ?, ?, ?, ?, ?, 'want', ?, ?)""",
            (tmdb_id, media_type, title, year, poster_path, overview, now, now)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        # UNIQUE constraint failed — this title is already on the list
        return False
    finally:
        conn.close()


def get_all_items():
    """Get all watchlist items, grouped by status."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM items ORDER BY updated_date DESC"
    ).fetchall()
    conn.close()

    # Group into three lists for the three sections on the main page
    grouped = {"want": [], "progress": [], "watched": []}
    for row in rows:
        grouped[row["status"]].append(dict(row))

    return grouped


def get_item(item_id):
    """Get a single item by its database ID."""
    conn = get_db()
    row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_item_by_tmdb(tmdb_id, media_type):
    """Check if a title is already on the watchlist."""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM items WHERE tmdb_id = ? AND media_type = ?",
        (tmdb_id, media_type)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def update_item_status(item_id, new_status):
    """Change an item's status (want / progress / watched)."""
    now = datetime.now().isoformat()
    conn = get_db()
    conn.execute(
        "UPDATE items SET status = ?, updated_date = ? WHERE id = ?",
        (new_status, now, item_id)
    )
    conn.commit()
    conn.close()


def update_item_details(item_id, rating=None, notes=None):
    """Update an item's rating and/or notes."""
    now = datetime.now().isoformat()
    conn = get_db()
    conn.execute(
        "UPDATE items SET rating = ?, notes = ?, updated_date = ? WHERE id = ?",
        (rating, notes, now, item_id)
    )
    conn.commit()
    conn.close()


def delete_item(item_id):
    """Remove an item from the watchlist entirely."""
    conn = get_db()
    # Also delete cached providers for this item
    item = get_item(item_id)
    if item:
        conn.execute(
            "DELETE FROM providers WHERE tmdb_id = ? AND media_type = ?",
            (item["tmdb_id"], item["media_type"])
        )
    conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()


# -----------------------------------------------------------------------
# Provider (streaming) cache operations
# -----------------------------------------------------------------------

def get_cached_providers(tmdb_id, media_type):
    """Get cached streaming providers for a title, if still fresh."""
    conn = get_db()
    rows = conn.execute(
        """SELECT * FROM providers
           WHERE tmdb_id = ? AND media_type = ?
           ORDER BY provider_type, provider_name""",
        (tmdb_id, media_type)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_providers(tmdb_id, media_type, providers_list):
    """
    Cache streaming providers for a title.

    First deletes any old data for this title, then inserts fresh data.
    """
    now = datetime.now().isoformat()
    conn = get_db()

    # Clear old data
    conn.execute(
        "DELETE FROM providers WHERE tmdb_id = ? AND media_type = ?",
        (tmdb_id, media_type)
    )

    # Insert new data
    for p in providers_list:
        conn.execute(
            """INSERT INTO providers (tmdb_id, media_type, provider_name, provider_logo, provider_type, country, fetched_date)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (tmdb_id, media_type, p["name"], p["logo"], p["type"], p["country"], now)
        )

    conn.commit()
    conn.close()


def is_provider_cache_fresh(tmdb_id, media_type, max_age_days=7):
    """Check if the cached provider data is still recent enough."""
    conn = get_db()
    row = conn.execute(
        "SELECT fetched_date FROM providers WHERE tmdb_id = ? AND media_type = ? LIMIT 1",
        (tmdb_id, media_type)
    ).fetchone()
    conn.close()

    if not row:
        return False  # No cache at all

    fetched = datetime.fromisoformat(row["fetched_date"])
    age = (datetime.now() - fetched).days
    return age < max_age_days
