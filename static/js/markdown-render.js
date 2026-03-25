/**
 * Shared markdown rendering for chat messages.
 *
 * Used by both the patient chat sidebar (chat.js) and the clinician
 * dashboard so that agent-generated markdown (bold, lists, code, etc.)
 * renders identically everywhere.
 *
 * Requires marked.js and DOMPurify to be loaded first (via base.html CDN).
 */
(function (root) {
    'use strict';

    function escapeHtml(text) {
        var d = document.createElement('div');
        d.textContent = text;
        return d.innerHTML;
    }

    function dedent(text) {
        // Strip common leading whitespace that comes from Django template indentation.
        // Without this, marked.js treats indented lines as code blocks.
        var lines = text.split('\n');
        var minIndent = Infinity;
        for (var i = 0; i < lines.length; i++) {
            if (lines[i].trim().length === 0) continue;
            var indent = lines[i].match(/^(\s*)/)[1].length;
            if (indent < minIndent) minIndent = indent;
        }
        if (minIndent > 0 && minIndent < Infinity) {
            lines = lines.map(function (line) { return line.slice(minIndent); });
        }
        return lines.join('\n').trim();
    }

    /**
     * Convert markdown text to sanitised HTML.
     * Falls back to escaped plain text if libraries are missing.
     */
    function renderMarkdown(text) {
        if (typeof marked !== 'undefined' && typeof DOMPurify !== 'undefined') {
            return DOMPurify.sanitize(marked.parse(dedent(text)));
        }
        return escapeHtml(text);
    }

    /**
     * Find all `.agent-message-content` elements within *root* (default: document)
     * and convert their raw content to rendered markdown.
     *
     * Each element is processed at most once (guarded by `data-rendered`).
     * Raw content is read from `data-raw-content` (preferred, preserves newlines)
     * or falls back to `textContent`.
     */
    function renderAgentMessages(root) {
        var els = (root || document).querySelectorAll('.agent-message-content');
        els.forEach(function (el) {
            if (el.dataset.rendered) return;
            var raw = el.dataset.rawContent || el.textContent;
            if (raw && raw.trim()) {
                el.innerHTML = renderMarkdown(raw);
            }
            el.dataset.rendered = 'true';
        });
    }

    // Expose globally
    root.clintelaMarkdown = {
        escapeHtml: escapeHtml,
        render: renderMarkdown,
        renderAgentMessages: renderAgentMessages,
    };
})(window);
