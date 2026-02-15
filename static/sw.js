/**
 * Service Worker for Teli PWA
 *
 * A service worker runs in the background and enables:
 * - "Add to Home Screen" on mobile (the main reason we have this)
 * - Basic offline caching of static assets
 *
 * This is a minimal service worker — it caches the CSS and JS files
 * so the app shell loads faster, but still needs the network for
 * TMDB API calls and database operations.
 */

const CACHE_NAME = "teli-v1";

// Files to cache for the app shell (layout, styles, scripts)
const STATIC_ASSETS = [
    "/static/css/style.css",
    "/static/js/app.js"
];

// When the service worker is installed, cache static assets
self.addEventListener("install", function (event) {
    event.waitUntil(
        caches.open(CACHE_NAME).then(function (cache) {
            return cache.addAll(STATIC_ASSETS);
        })
    );
    // Activate immediately instead of waiting
    self.skipWaiting();
});

// When a new version is activated, delete old caches
self.addEventListener("activate", function (event) {
    event.waitUntil(
        caches.keys().then(function (names) {
            return Promise.all(
                names.filter(function (name) { return name !== CACHE_NAME; })
                     .map(function (name) { return caches.delete(name); })
            );
        })
    );
});

// Network-first strategy: try the network, fall back to cache
self.addEventListener("fetch", function (event) {
    event.respondWith(
        fetch(event.request).catch(function () {
            return caches.match(event.request);
        })
    );
});
