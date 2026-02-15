/**
 * Teli — Client-side JavaScript
 *
 * Handles interactive features:
 * - Bottom tab highlighting based on current page
 * - Auto-dismiss flash messages
 * - Import page checkbox toggling
 * - Service worker registration (PWA)
 */

// ===== Tab Bar Highlighting =====
// Reads "data-page" from <body> and highlights the matching tab.
document.addEventListener("DOMContentLoaded", function () {
    var currentPage = document.body.getAttribute("data-page");
    if (currentPage) {
        document.querySelectorAll(".tab-item").forEach(function (tab) {
            if (tab.getAttribute("data-tab") === currentPage) {
                tab.classList.add("active");
            }
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

// ===== PWA: Register Service Worker =====
if ("serviceWorker" in navigator) {
    window.addEventListener("load", function () {
        navigator.serviceWorker.register("/static/sw.js").catch(function () {});
    });
}
