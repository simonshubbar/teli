"""
TMDB API wrapper for the Teli app.

TMDB (The Movie Database) is a free API that provides:
- Movie/TV show search results with posters
- Streaming availability by country (who has it: Netflix, Disney+, etc.)

Authentication uses the v3 API key, passed as a query parameter
(?api_key=...) on every request.  This is the shorter key you get
from TMDB's API settings page.
"""

import requests
from config import TMDB_BASE_URL, TMDB_API_KEY, TMDB_IMAGE_BASE, PROVIDER_COUNTRY


def _base_params():
    """
    Base query parameters included in every TMDB request.

    The api_key parameter authenticates us with TMDB's v3 API.
    """
    return {"api_key": TMDB_API_KEY}


def search_multi(query):
    """
    Search for movies AND TV shows in one call.

    Returns a list of results, each with:
    - tmdb_id, media_type, title, year, poster_url, overview

    We filter out results that aren't movies or TV shows
    (TMDB also returns "person" results which we don't need).
    """
    if not query or not query.strip():
        return []

    url = f"{TMDB_BASE_URL}/search/multi"
    params = {
        **_base_params(),       # Includes the api_key
        "query": query,
        "include_adult": False,
        "language": "en-GB",    # Prefer British English titles
        "page": 1
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()  # Raise an error if the request failed
        data = response.json()
    except requests.RequestException:
        return []  # Return empty list if API is down or key is invalid

    results = []
    for item in data.get("results", []):
        media_type = item.get("media_type")

        # Skip anything that isn't a movie or TV show
        if media_type not in ("movie", "tv"):
            continue

        # Movies use "title" and "release_date", TV shows use "name" and "first_air_date"
        if media_type == "movie":
            title = item.get("title", "Unknown Title")
            date_str = item.get("release_date", "")
        else:
            title = item.get("name", "Unknown Title")
            date_str = item.get("first_air_date", "")

        # Extract just the year from the date (e.g., "2010-07-16" → "2010")
        year = date_str[:4] if date_str else ""

        # Build the full poster URL (or None if no poster)
        poster_path = item.get("poster_path")
        poster_url = f"{TMDB_IMAGE_BASE}{poster_path}" if poster_path else None

        results.append({
            "tmdb_id": item["id"],
            "media_type": media_type,
            "title": title,
            "year": year,
            "poster_url": poster_url,
            "poster_path": poster_path,  # Store the path for the database
            "overview": item.get("overview", ""),
        })

    return results


def get_providers(tmdb_id, media_type):
    """
    Get streaming/rent/buy availability for a title in the UK.

    TMDB's "watch providers" endpoint tells us which services carry
    each title, broken down by country and type (stream, rent, buy).

    Returns a list of dicts with: name, logo, type, country
    """
    url = f"{TMDB_BASE_URL}/{media_type}/{tmdb_id}/watch/providers"

    try:
        response = requests.get(url, params=_base_params(), timeout=10)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException:
        return []

    # The results are nested by country code
    country_data = data.get("results", {}).get(PROVIDER_COUNTRY, {})
    if not country_data:
        return []

    providers = []

    # TMDB uses different keys for different types of availability:
    # "flatrate" = streaming subscription (Netflix, Disney+, etc.)
    # "rent"     = pay-per-view rental (Amazon, Apple TV, etc.)
    # "buy"      = digital purchase
    type_mapping = {
        "flatrate": "stream",
        "rent": "rent",
        "buy": "buy"
    }

    for tmdb_key, display_type in type_mapping.items():
        for provider in country_data.get(tmdb_key, []):
            logo_path = provider.get("logo_path")
            providers.append({
                "name": provider.get("provider_name", "Unknown"),
                "logo": f"{TMDB_IMAGE_BASE}{logo_path}" if logo_path else None,
                "type": display_type,
                "country": PROVIDER_COUNTRY
            })

    return providers


def search_single(query):
    """
    Search for a single best match — used during batch import.

    Returns the top result or None if nothing matches.
    """
    results = search_multi(query)
    return results[0] if results else None
