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

    # --- users table: each person who signs in with Google ---
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            google_id     TEXT NOT NULL UNIQUE,    -- Google's unique user ID
            email         TEXT NOT NULL,
            name          TEXT,                    -- Display name from Google
            picture       TEXT,                    -- Profile picture URL from Google
            created_date  TEXT NOT NULL
        )
    """)

    # --- items table: each movie/show on a user's watchlist ---
    # The user_id column links each item to the user who added it.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER NOT NULL,        -- Which user owns this item
            tmdb_id       INTEGER NOT NULL,
            media_type    TEXT NOT NULL,            -- 'movie' or 'tv'
            title         TEXT NOT NULL,
            year          TEXT,                     -- Release year
            poster_path   TEXT,                     -- Path to poster image on TMDB
            overview      TEXT,                     -- Plot summary
            status        TEXT NOT NULL DEFAULT 'want',  -- 'want', 'progress', or 'watched'
            rating        INTEGER,                  -- Your rating 1-10 (optional)
            notes         TEXT,                     -- Your personal notes (optional)
            added_date    TEXT NOT NULL,
            updated_date  TEXT NOT NULL,
            UNIQUE(user_id, tmdb_id, media_type),  -- Same user can't add the same title twice
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # --- providers table: cached streaming availability ---
    # This data is shared (not per-user) since streaming info is the same for everyone.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS providers (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            tmdb_id        INTEGER NOT NULL,
            media_type     TEXT NOT NULL,
            provider_name  TEXT NOT NULL,
            provider_logo  TEXT,                    -- Path to logo image on TMDB
            provider_type  TEXT NOT NULL,            -- 'flatrate' (stream), 'rent', or 'buy'
            country        TEXT NOT NULL DEFAULT 'GB',
            fetched_date   TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


# -----------------------------------------------------------------------
# User operations
# -----------------------------------------------------------------------

def get_or_create_user(google_id, email, name, picture):
    """
    Find a user by their Google ID, or create a new one if they're signing
    in for the first time.

    Returns a dict with the user's database row.
    """
    conn = get_db()

    # Check if this Google account already has a user record
    row = conn.execute(
        "SELECT * FROM users WHERE google_id = ?", (google_id,)
    ).fetchone()

    if row:
        # User exists — update their name/picture in case they changed it on Google
        conn.execute(
            "UPDATE users SET name = ?, picture = ?, email = ? WHERE google_id = ?",
            (name, picture, email, google_id)
        )
        conn.commit()
        # Re-fetch to get updated data
        row = conn.execute(
            "SELECT * FROM users WHERE google_id = ?", (google_id,)
        ).fetchone()
    else:
        # First time signing in — create a new user
        now = datetime.now().isoformat()
        conn.execute(
            """INSERT INTO users (google_id, email, name, picture, created_date)
               VALUES (?, ?, ?, ?, ?)""",
            (google_id, email, name, picture, now)
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM users WHERE google_id = ?", (google_id,)
        ).fetchone()

    user = dict(row)
    conn.close()
    return user


def get_user(user_id):
    """Get a user by their database ID."""
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


# -----------------------------------------------------------------------
# CRUD operations (Create, Read, Update, Delete)
# -----------------------------------------------------------------------

def add_item(user_id, tmdb_id, media_type, title, year, poster_path, overview):
    """Add a movie/show to a user's watchlist with status 'want'."""
    now = datetime.now().isoformat()
    conn = get_db()
    try:
        conn.execute(
            """INSERT INTO items (user_id, tmdb_id, media_type, title, year, poster_path, overview, status, added_date, updated_date)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'want', ?, ?)""",
            (user_id, tmdb_id, media_type, title, year, poster_path, overview, now, now)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        # UNIQUE constraint failed — this title is already on the user's list
        return False
    finally:
        conn.close()


def get_all_items(user_id):
    """Get all watchlist items for a specific user, grouped by status."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM items WHERE user_id = ? ORDER BY updated_date DESC",
        (user_id,)
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


def get_item_by_tmdb(user_id, tmdb_id, media_type):
    """Check if a title is already on a specific user's watchlist."""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM items WHERE user_id = ? AND tmdb_id = ? AND media_type = ?",
        (user_id, tmdb_id, media_type)
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
