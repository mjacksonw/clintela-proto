/**
 * Clinician Research Chat — Alpine.js helper
 *
 * Minimal — most logic is handled by HTMX in _tab_research.html.
 * This file exists for any future JS-side research chat enhancements.
 */

// Auto-scroll research chat after HTMX swap
document.addEventListener('htmx:afterSwap', function(event) {
    if (event.target.id === 'research-messages' || event.target.closest('#research-messages')) {
        scrollResearch();
    }
});
