/**
 * Teli — Client-side JavaScript
 *
 * Handles interactive features:
 * - Profile dropdown menu toggle
 * - Auto-dismiss flash messages
 * - Import page checkbox toggling
 * - Service worker registration (PWA)
 */

// ===== Profile Dropdown Menu =====
// Clicking the avatar toggles the dropdown; clicking outside closes it.
document.addEventListener("DOMContentLoaded", function () {
    var toggle = document.getElementById("profileToggle");
    var dropdown = document.getElementById("profileDropdown");

    if (toggle && dropdown) {
        // Toggle dropdown open/closed when avatar is clicked
        toggle.addEventListener("click", function (e) {
            e.stopPropagation();
            dropdown.classList.toggle("open");
        });

        // Close the dropdown when clicking anywhere else on the page
        document.addEventListener("click", function () {
            dropdown.classList.remove("open");
        });

        // Prevent clicks inside the dropdown from closing it
        dropdown.addEventListener("click", function (e) {
            e.stopPropagation();
        });
    }
});

// ===== Auto-dismiss flash messages after 4 seconds =====
document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll(".flash-message").forEach(function (flash) {
        setTimeout(function () {
            flash.style.transition = "opacity 0.3s ease";
            flash.style.opacity = "0";
            setTimeout(function () { flash.remove(); }, 300);
        }, 4000);
    });
});

// ===== Import page: toggle hidden fields =====
function toggleImportFields(checkbox) {
    var index = checkbox.value;
    var fields = document.getElementById("import-fields-" + index);
    if (fields) {
        fields.querySelectorAll("input[type='hidden']").forEach(function (input) {
            input.disabled = !checkbox.checked;
        });
    }
}

// Initialize import checkboxes on page load
document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll(".import-checkbox input[type='checkbox']").forEach(function (cb) {
        toggleImportFields(cb);
    });
});

// ===== Search Overlay — Live Search =====
// Opens a full-screen overlay when the floating search bar is tapped.
// Fetches results from /api/search as you type (with debouncing).
document.addEventListener("DOMContentLoaded", function () {
    var trigger = document.getElementById("floatingSearchTrigger");
    var overlay = document.getElementById("searchOverlay");
    var overlayInput = document.getElementById("overlaySearchInput");
    var overlayResults = document.getElementById("overlayResults");
    var cancelBtn = document.getElementById("overlayCancel");

    // If not logged in, these elements won't exist — bail out
    if (!trigger || !overlay) return;

    var debounceTimer = null;

    // --- Open the overlay when the floating bar is tapped ---
    trigger.addEventListener("focus", function () {
        openOverlay();
    });
    trigger.addEventListener("click", function () {
        openOverlay();
    });

    function openOverlay() {
        overlay.classList.add("open");
        // Small delay so the slide-up animation finishes before focusing
        setTimeout(function () { overlayInput.focus(); }, 50);
        // Prevent the page behind from scrolling
        document.body.style.overflow = "hidden";
    }

    // --- Close the overlay ---
    function closeOverlay() {
        overlay.classList.remove("open");
        document.body.style.overflow = "";
        overlayInput.value = "";
        overlayResults.innerHTML = '<p class="overlay-hint">Type to search for movies and TV shows</p>';
        // Remove focus from the floating bar trigger so it doesn't re-open
        trigger.blur();
    }

    cancelBtn.addEventListener("click", closeOverlay);

    // Close on Escape key
    document.addEventListener("keydown", function (e) {
        if (e.key === "Escape" && overlay.classList.contains("open")) {
            closeOverlay();
        }
    });

    // --- Live search: fetch results as the user types ---
    overlayInput.addEventListener("input", function () {
        var query = overlayInput.value.trim();

        // Clear previous timer so we don't spam the API
        clearTimeout(debounceTimer);

        if (!query) {
            overlayResults.innerHTML = '<p class="overlay-hint">Type to search for movies and TV shows</p>';
            return;
        }

        // Show a loading indicator
        overlayResults.innerHTML = '<p class="overlay-hint">Searching...</p>';

        // Wait 400ms after the user stops typing before fetching
        debounceTimer = setTimeout(function () {
            fetch("/api/search?q=" + encodeURIComponent(query))
                .then(function (res) { return res.json(); })
                .then(function (data) {
                    renderResults(data.results);
                })
                .catch(function () {
                    overlayResults.innerHTML = '<p class="overlay-hint">Something went wrong. Try again.</p>';
                });
        }, 400);
    });

    // --- Render search results as HTML cards ---
    function renderResults(results) {
        if (!results || results.length === 0) {
            overlayResults.innerHTML = '<p class="overlay-hint">No results found. Try a different search.</p>';
            return;
        }

        // Build the same card layout used on the server-rendered search page
        var html = '<div class="search-results">';

        results.forEach(function (r) {
            // Poster: either an image or a "No Poster" placeholder
            var posterHtml;
            if (r.poster_url) {
                posterHtml = '<img src="' + escapeHtml(r.poster_url) + '" alt="' + escapeHtml(r.title) + ' poster" loading="lazy">';
            } else {
                posterHtml = '<div class="no-poster small">No Poster</div>';
            }

            // Year display
            var yearHtml = r.year ? ' <span class="result-year">(' + escapeHtml(r.year) + ')</span>' : '';

            // Media type badge (Movie or TV Show)
            var badgeLabel = r.media_type === "movie" ? "Movie" : "TV Show";
            var badgeHtml = '<span class="media-badge ' + r.media_type + '">' + badgeLabel + '</span>';

            // Overview (truncated to 150 chars)
            var overview = r.overview || "";
            if (overview.length > 150) overview = overview.substring(0, 150) + "...";

            // Action button: "On your list" link or "+ Add" button
            var actionHtml;
            if (r.on_list) {
                actionHtml = '<a href="/detail/' + r.list_id + '" class="btn-on-list">On your list &rarr;</a>';
            } else {
                // The button stores item data in data-* attributes so we can
                // send it to the server without a form submission
                actionHtml = '<button class="ios-btn btn-small btn-primary overlay-add-btn"'
                    + ' data-tmdb-id="' + r.tmdb_id + '"'
                    + ' data-media-type="' + escapeHtml(r.media_type) + '"'
                    + ' data-title="' + escapeHtml(r.title) + '"'
                    + ' data-year="' + escapeHtml(r.year || '') + '"'
                    + ' data-poster-path="' + escapeHtml(r.poster_path || '') + '"'
                    + ' data-overview="' + escapeHtml(r.overview || '') + '"'
                    + '>+ Add</button>';
            }

            html += '<article class="search-result">'
                + '<div class="result-poster">' + posterHtml + '</div>'
                + '<div class="result-info">'
                + '<h3 class="result-title">' + escapeHtml(r.title) + yearHtml + '</h3>'
                + badgeHtml
                + '<p class="result-overview">' + escapeHtml(overview) + '</p>'
                + actionHtml
                + '</div>'
                + '</article>';
        });

        html += '</div>';
        overlayResults.innerHTML = html;

        // --- Attach click handlers to all "+ Add" buttons ---
        overlayResults.querySelectorAll(".overlay-add-btn").forEach(function (btn) {
            btn.addEventListener("click", function () {
                addFromOverlay(btn);
            });
        });
    }

    // --- Add an item to the watchlist without leaving the overlay ---
    function addFromOverlay(btn) {
        // Disable the button to prevent double-clicks
        btn.disabled = true;
        btn.textContent = "Adding...";

        // Build form data from the button's data-* attributes
        var formData = new FormData();
        formData.append("tmdb_id", btn.dataset.tmdbId);
        formData.append("media_type", btn.dataset.mediaType);
        formData.append("title", btn.dataset.title);
        formData.append("year", btn.dataset.year);
        formData.append("poster_path", btn.dataset.posterPath);
        formData.append("overview", btn.dataset.overview);

        fetch("/add", {
            method: "POST",
            headers: { "X-Requested-With": "fetch" },
            body: formData
        })
        .then(function (res) { return res.json(); })
        .then(function () {
            // Swap the button for an "On your list" message
            var link = document.createElement("span");
            link.className = "btn-on-list";
            link.innerHTML = "On your list &#10003;";
            btn.replaceWith(link);
        })
        .catch(function () {
            btn.disabled = false;
            btn.textContent = "+ Add";
        });
    }

    // --- Helper: escape HTML to prevent XSS ---
    function escapeHtml(str) {
        if (!str) return "";
        var div = document.createElement("div");
        div.appendChild(document.createTextNode(str));
        return div.innerHTML;
    }
});

// ===== PWA: Register Service Worker =====
if ("serviceWorker" in navigator) {
    window.addEventListener("load", function () {
        navigator.serviceWorker.register("/static/sw.js").catch(function () {});
    });
}
