"""
Teli — Movie & TV Show Tracker

This is the main Flask application.  Flask is a "micro web framework" —
it handles routing (which URL shows which page) and rendering templates
(turning HTML files + data into complete web pages).

Each function below is a "route" — it handles requests to a specific URL.
The @app.route decorator tells Flask which URL triggers which function.
"""

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from database import init_db, add_item, get_all_items, get_item, get_item_by_tmdb, \
    update_item_status, update_item_details, delete_item, \
    get_cached_providers, save_providers, is_provider_cache_fresh
from tmdb import search_multi, get_providers, search_single
from config import TMDB_IMAGE_BASE
from auth import init_auth

# Create the Flask app
app = Flask(__name__)

# Secret key for sessions and flash messages.
# In production (PythonAnywhere), set this as an environment variable.
# Locally, the fallback "dev-secret-key" is fine for development.
import os
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")

# Set up Google Sign-In and Flask-Login
# This registers the /login, /login/google, /auth/callback, and /logout routes
init_auth(app)


# -----------------------------------------------------------------------
# Routes — all require login (except auth routes handled by auth.py)
# -----------------------------------------------------------------------

@app.route("/")
@login_required  # Redirects to login page if not signed in
def index():
    """
    Main page — shows your personal watchlist in three sections:
    Want to Watch / In Progress / Watched

    Also supports filtering by streaming provider and media type.
    """
    # Pass current_user.id so we only get THIS user's items
    items = get_all_items(current_user.id)
    provider_filter = request.args.get("provider", "")
    media_filter = request.args.get("media", "")  # "movie", "tv", or "" (all)

    # Filter by media type if a tab is selected
    if media_filter in ("movie", "tv"):
        for status in items:
            items[status] = [i for i in items[status] if i["media_type"] == media_filter]

    if provider_filter:
        # Filter items to only show those available on a specific service
        for status in items:
            filtered = []
            for item in items[status]:
                providers = get_cached_providers(item["tmdb_id"], item["media_type"])
                provider_names = [p["provider_name"] for p in providers]
                if provider_filter in provider_names:
                    filtered.append(item)
            items[status] = filtered

    # Collect all unique streaming provider names for the filter dropdown
    all_providers = set()
    for status in items:
        for item in items[status]:
            providers = get_cached_providers(item["tmdb_id"], item["media_type"])
            for p in providers:
                if p["provider_type"] == "stream":
                    all_providers.add(p["provider_name"])

    return render_template(
        "index.html",
        items=items,
        provider_filter=provider_filter,
        media_filter=media_filter,
        all_providers=sorted(all_providers),
        image_base=TMDB_IMAGE_BASE
    )


@app.route("/search")
@login_required
def search():
    """
    Search page — user types a title, we call TMDB API,
    and show matching results with posters.
    """
    query = request.args.get("q", "").strip()
    results = []

    if query:
        results = search_multi(query)

        # Mark results that are already on THIS user's watchlist
        for r in results:
            existing = get_item_by_tmdb(current_user.id, r["tmdb_id"], r["media_type"])
            r["on_list"] = existing is not None
            r["list_id"] = existing["id"] if existing else None

    return render_template("search.html", query=query, results=results)


@app.route("/add", methods=["POST"])
@login_required
def add():
    """
    Add a movie/show to the current user's watchlist.

    This is a POST route — it receives data from a form submission.
    After adding, it redirects back to the main page.
    """
    tmdb_id = request.form.get("tmdb_id", type=int)
    media_type = request.form.get("media_type")
    title = request.form.get("title")
    year = request.form.get("year")
    poster_path = request.form.get("poster_path")
    overview = request.form.get("overview")

    if tmdb_id and media_type and title:
        # Pass current_user.id so the item is linked to this user
        success = add_item(current_user.id, tmdb_id, media_type, title, year, poster_path, overview)
        if success:
            # Fetch and cache streaming providers right away
            _refresh_providers(tmdb_id, media_type)
            flash(f"Added '{title}' to your list!", "success")
        else:
            flash(f"'{title}' is already on your list.", "info")

    return redirect(url_for("index"))


@app.route("/detail/<int:item_id>")
@login_required
def detail(item_id):
    """
    Detail page for a single movie/show.

    Shows full info, streaming providers, and buttons to
    change status, rate, add notes, or delete.
    """
    item = get_item(item_id)
    if not item:
        flash("Item not found.", "error")
        return redirect(url_for("index"))

    # Ownership check — make sure this item belongs to the current user
    if item["user_id"] != current_user.id:
        flash("Item not found.", "error")
        return redirect(url_for("index"))

    # Get streaming providers (from cache or fresh from TMDB)
    providers = _get_or_fetch_providers(item["tmdb_id"], item["media_type"])

    # Group providers by type for display
    grouped_providers = {"stream": [], "rent": [], "buy": []}
    for p in providers:
        ptype = p.get("provider_type", p.get("type", "stream"))
        if ptype in grouped_providers:
            grouped_providers[ptype].append(p)

    return render_template(
        "detail.html",
        item=item,
        providers=grouped_providers,
        image_base=TMDB_IMAGE_BASE
    )


@app.route("/update/<int:item_id>", methods=["POST"])
@login_required
def update(item_id):
    """Update an item's status (want / progress / watched)."""
    item = get_item(item_id)
    if not item or item["user_id"] != current_user.id:
        flash("Item not found.", "error")
        return redirect(url_for("index"))

    new_status = request.form.get("status")

    if new_status in ("want", "progress", "watched"):
        update_item_status(item_id, new_status)

        # Pretty labels for the flash message
        labels = {"want": "Want to Watch", "progress": "In Progress", "watched": "Watched"}
        flash(f"Moved to '{labels[new_status]}'.", "success")

    return redirect(url_for("detail", item_id=item_id))


@app.route("/update_details/<int:item_id>", methods=["POST"])
@login_required
def update_details(item_id):
    """Update an item's rating and notes."""
    item = get_item(item_id)
    if not item or item["user_id"] != current_user.id:
        flash("Item not found.", "error")
        return redirect(url_for("index"))

    rating = request.form.get("rating", type=int)
    notes = request.form.get("notes", "").strip()

    # Clamp rating to 1-10 range (or None if not provided)
    if rating is not None:
        rating = max(1, min(10, rating))

    update_item_details(item_id, rating=rating, notes=notes if notes else None)
    flash("Details updated.", "success")
    return redirect(url_for("detail", item_id=item_id))


@app.route("/delete/<int:item_id>", methods=["POST"])
@login_required
def delete(item_id):
    """Remove an item from the current user's watchlist."""
    item = get_item(item_id)
    if not item or item["user_id"] != current_user.id:
        flash("Item not found.", "error")
        return redirect(url_for("index"))

    delete_item(item_id)
    flash(f"Removed '{item['title']}' from your list.", "success")
    return redirect(url_for("index"))


# -----------------------------------------------------------------------
# Batch Import
# -----------------------------------------------------------------------

@app.route("/import", methods=["GET"])
@login_required
def import_page():
    """Show the import page with a text box for pasting titles."""
    return render_template("import.html")


@app.route("/import/search", methods=["POST"])
@login_required
def import_search():
    """
    Take a list of titles (one per line), search TMDB for each,
    and return the best match for confirmation.
    """
    raw_text = request.form.get("titles", "")
    titles = [line.strip() for line in raw_text.splitlines() if line.strip()]

    matches = []
    for title in titles:
        result = search_single(title)
        if result:
            existing = get_item_by_tmdb(current_user.id, result["tmdb_id"], result["media_type"])
            result["on_list"] = existing is not None
            matches.append({"query": title, "match": result})
        else:
            matches.append({"query": title, "match": None})

    return render_template("import.html", matches=matches, raw_text=raw_text)


@app.route("/import/add", methods=["POST"])
@login_required
def import_add():
    """Add all selected items from the import confirmation list."""
    # The form sends arrays of values for each checked item
    tmdb_ids = request.form.getlist("tmdb_id")
    media_types = request.form.getlist("media_type")
    titles = request.form.getlist("title")
    years = request.form.getlist("year")
    poster_paths = request.form.getlist("poster_path")
    overviews = request.form.getlist("overview")

    added_count = 0
    for i in range(len(tmdb_ids)):
        success = add_item(
            current_user.id, int(tmdb_ids[i]), media_types[i], titles[i],
            years[i], poster_paths[i], overviews[i]
        )
        if success:
            _refresh_providers(int(tmdb_ids[i]), media_types[i])
            added_count += 1

    flash(f"Added {added_count} item(s) to your list!", "success")
    return redirect(url_for("index"))


# -----------------------------------------------------------------------
# Helper functions
# -----------------------------------------------------------------------

def _get_or_fetch_providers(tmdb_id, media_type):
    """Get providers from cache, or fetch fresh from TMDB if stale."""
    if is_provider_cache_fresh(tmdb_id, media_type):
        return get_cached_providers(tmdb_id, media_type)

    return _refresh_providers(tmdb_id, media_type)


def _refresh_providers(tmdb_id, media_type):
    """Fetch fresh provider data from TMDB and cache it."""
    providers = get_providers(tmdb_id, media_type)
    if providers:
        save_providers(tmdb_id, media_type, providers)
    return get_cached_providers(tmdb_id, media_type)


# -----------------------------------------------------------------------
# Run the app
# -----------------------------------------------------------------------

if __name__ == "__main__":
    # Create database tables on first run
    init_db()

    # debug=True auto-reloads when you change code (development only!)
    # host='0.0.0.0' makes the app accessible from other devices on your Wi-Fi
    # port 5001 avoids conflict with macOS AirPlay on port 5000
    app.run(debug=True, host='0.0.0.0', port=5001)
