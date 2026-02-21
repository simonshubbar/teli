/**
 * Teli — Client-side JavaScript
 *
 * Handles interactive features:
 * - Profile dropdown menu toggle
 * - Auto-dismiss flash messages
 * - Import page checkbox toggling + inline per-row search
 * - Live search overlay
 * - Service worker registration (PWA)
 */

// ===== Global helper: escape HTML to prevent XSS =====
function escapeHtml(str) {
    if (!str) return "";
    var div = document.createElement("div");
    div.appendChild(document.createTextNode(String(str)));
    return div.innerHTML;
}

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

// ===== Import: Inline per-row search =====
// Lets users search for a different match right inside the import review list.

var importSearchTimers = {};  // one debounce timer per row index

// Toggle the inline search panel open/closed for a given row
function toggleImportSearch(index, btn) {
    var panel = document.getElementById("import-search-panel-" + index);
    if (panel.classList.contains("open")) {
        closeImportSearch(index);
    } else {
        panel.classList.add("open");
        // Store original button label so we can restore it on close
        btn.dataset.originalLabel = btn.textContent;
        btn.textContent = "Cancel";
        // Pre-fill the search input with the original typed query
        var input = document.getElementById("import-search-input-" + index);
        input.value = btn.dataset.query || "";
        input.focus();
        // Kick off the initial search immediately
        if (input.value.trim()) {
            runImportSearch(index);
        }
    }
}

// Close the inline search panel and reset UI
function closeImportSearch(index) {
    var panel = document.getElementById("import-search-panel-" + index);
    panel.classList.remove("open");
    document.getElementById("import-search-results-" + index).innerHTML = "";
    // Restore the Change/Search button label
    var display = document.getElementById("import-display-" + index);
    if (display) {
        var btn = display.querySelector(".import-change-btn");
        if (btn && btn.dataset.originalLabel) {
            btn.textContent = btn.dataset.originalLabel;
        }
    }
}

// Debounce typing so we don't spam /api/search on every keystroke
function scheduleImportSearch(index) {
    clearTimeout(importSearchTimers[index]);
    importSearchTimers[index] = setTimeout(function () {
        runImportSearch(index);
    }, 400);
}

// Fetch results from /api/search and render them
function runImportSearch(index) {
    var input = document.getElementById("import-search-input-" + index);
    var resultsDiv = document.getElementById("import-search-results-" + index);
    var query = input.value.trim();

    if (!query) {
        resultsDiv.innerHTML = "";
        return;
    }

    resultsDiv.innerHTML = '<p class="import-search-hint">Searching...</p>';

    fetch("/api/search?q=" + encodeURIComponent(query))
        .then(function (res) { return res.json(); })
        .then(function (data) { renderImportSearchResults(index, data.results); })
        .catch(function () {
            resultsDiv.innerHTML = '<p class="import-search-hint">Something went wrong. Try again.</p>';
        });
}

// Render a compact list of TMDB results with a "Select" button on each
function renderImportSearchResults(index, results) {
    var resultsDiv = document.getElementById("import-search-results-" + index);

    if (!results || results.length === 0) {
        resultsDiv.innerHTML = '<p class="import-search-hint">No results found. Try a different search.</p>';
        return;
    }

    var html = "";
    results.forEach(function (r) {
        var posterHtml = r.poster_url
            ? '<img src="' + escapeHtml(r.poster_url) + '" alt="" class="import-poster">'
            : '<div class="no-poster small">?</div>';
        var badgeLabel = r.media_type === "movie" ? "Movie" : "TV Show";
        var yearHtml = r.year ? " (" + escapeHtml(r.year) + ")" : "";

        html += '<div class="import-search-result">'
            + '<div class="import-match-info">'
            + posterHtml
            + '<div><strong>' + escapeHtml(r.title) + '</strong>' + yearHtml
            + '<br><span class="media-badge ' + escapeHtml(r.media_type) + '">' + badgeLabel + '</span>'
            + '</div></div>'
            + '<button type="button" class="ios-btn btn-small btn-primary import-select-btn"'
            + ' data-tmdb-id="' + r.tmdb_id + '"'
            + ' data-media-type="' + escapeHtml(r.media_type) + '"'
            + ' data-title="' + escapeHtml(r.title) + '"'
            + ' data-year="' + escapeHtml(r.year || "") + '"'
            + ' data-poster-path="' + escapeHtml(r.poster_path || "") + '"'
            + ' data-poster-url="' + escapeHtml(r.poster_url || "") + '"'
            + ' data-overview="' + escapeHtml(r.overview || "") + '"'
            + '>Select</button>'
            + '</div>';
    });

    resultsDiv.innerHTML = html;

    // Attach click handlers to each Select button
    resultsDiv.querySelectorAll(".import-select-btn").forEach(function (btn) {
        btn.addEventListener("click", function () {
            selectImportMatch(index, {
                tmdb_id: btn.dataset.tmdbId,
                media_type: btn.dataset.mediaType,
                title: btn.dataset.title,
                year: btn.dataset.year,
                poster_path: btn.dataset.posterPath,
                poster_url: btn.dataset.posterUrl,
                overview: btn.dataset.overview
            });
        });
    });
}

// Called when the user picks a result — updates the row with the new match
function selectImportMatch(index, r) {
    // Enable and populate the hidden form fields for this row
    var fields = document.getElementById("import-fields-" + index);
    ["tmdb_id", "media_type", "title", "year", "poster_path", "overview"].forEach(function (name) {
        var input = fields.querySelector('[name="' + name + '"]');
        if (input) {
            input.disabled = false;
            input.value = r[name === "tmdb_id" ? "tmdb_id"
                          : name === "media_type" ? "media_type"
                          : name === "poster_path" ? "poster_path"
                          : name] || "";
        }
    });
    // Set each field value explicitly (data-* keys differ slightly from field names)
    fields.querySelector('[name="tmdb_id"]').value     = r.tmdb_id;
    fields.querySelector('[name="media_type"]').value  = r.media_type;
    fields.querySelector('[name="title"]').value       = r.title;
    fields.querySelector('[name="year"]').value        = r.year || "";
    fields.querySelector('[name="poster_path"]').value = r.poster_path || "";
    fields.querySelector('[name="overview"]').value    = r.overview || "";

    // Rebuild the visual match display for this row
    var posterHtml = r.poster_url
        ? '<img src="' + escapeHtml(r.poster_url) + '" alt="' + escapeHtml(r.title) + '" class="import-poster">'
        : '<div class="no-poster small">No Poster</div>';
    var badgeLabel = r.media_type === "movie" ? "Movie" : "TV Show";
    var yearHtml = r.year ? "(" + escapeHtml(r.year) + ")" : "";

    var display = document.getElementById("import-display-" + index);
    display.innerHTML =
        '<label class="import-checkbox">'
        + '<input type="checkbox" value="' + index + '" id="import-cb-' + index + '" checked'
        + ' onchange="toggleImportFields(this)">'
        + '<div class="import-match-info">'
        + posterHtml
        + '<div><strong>' + escapeHtml(r.title) + '</strong> ' + yearHtml
        + '<br><span class="media-badge ' + escapeHtml(r.media_type) + '">' + badgeLabel + '</span>'
        + '</div></div></label>'
        + '<button type="button" class="import-change-btn"'
        + ' onclick="toggleImportSearch(' + index + ', this)"'
        + ' data-query="' + escapeHtml(r.title) + '">Change</button>';

    // Close the search panel
    var panel = document.getElementById("import-search-panel-" + index);
    panel.classList.remove("open");
    document.getElementById("import-search-results-" + index).innerHTML = "";
}

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
    var itemsAdded = false; // track whether anything was added this session

    // --- Open the overlay when the floating bar is tapped ---
    trigger.addEventListener("focus", function () {
        openOverlay();
    });
    trigger.addEventListener("click", function () {
        openOverlay();
    });

    function openOverlay() {
        overlay.classList.add("open");
        itemsAdded = false; // reset for each new search session
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
        // If anything was added, reload so the list updates instantly
        if (itemsAdded) {
            location.reload();
        }
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

        // Wait 250ms after the user stops typing before fetching
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
            itemsAdded = true; // flag so closeOverlay reloads the list
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

});

// ===== PWA: Register Service Worker =====
if ("serviceWorker" in navigator) {
    window.addEventListener("load", function () {
        navigator.serviceWorker.register("/static/sw.js").catch(function () {});
    });
}
