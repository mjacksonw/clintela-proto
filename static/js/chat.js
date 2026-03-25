/**
 * Clintela Chat — interaction logic for HTMX chat sidebar.
 *
 * Provides: optimistic UI, auto-scroll, suggestion chips, inline errors,
 * escalation banner, offline detection, notification sound,
 * markdown rendering (marked.js + DOMPurify), progressive timeout.
 */
const clintelaChat = (() => {
    // --- State ---
    let timeoutTimer = null;
    let timeoutStage = 0;
    const TIMEOUT_STAGES = [
        { at: 0, text: 'Your care team is thinking...' },
        { at: 15000, text: 'Still working on your question...' },
        { at: 45000, text: 'This is taking longer than usual...' },
    ];
    const TIMEOUT_ERROR_MS = 90000;

    // --- Helpers ---
    function qs(sel, root) { return (root || document).querySelector(sel); }
    function messagesEl() { return qs('#messages'); }
    function typingEl() { return qs('#typing-indicator'); }
    function chipsEl() { return qs('#suggestion-chips'); }

    function scrollToBottom(el) {
        if (!el) return;
        const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 100;
        if (nearBottom) {
            el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
        }
    }

    // Markdown rendering delegated to shared markdown-render.js (clintelaMarkdown)
    function renderMarkdown(text) {
        if (window.clintelaMarkdown) return window.clintelaMarkdown.render(text);
        // Fallback if shared lib not loaded yet
        var d = document.createElement('div');
        d.textContent = text;
        return d.innerHTML;
    }

    // --- Typing indicator ---
    function showTyping() {
        const el = typingEl();
        if (!el) return;
        const data = Alpine.$data(el);
        if (data) {
            data.visible = true;
            data.text = TIMEOUT_STAGES[0].text;
        } else {
            el.style.display = '';
            el.removeAttribute('x-cloak');
        }
        startProgressiveTimeout();
    }

    function hideTyping() {
        const el = typingEl();
        if (!el) return;
        const data = Alpine.$data(el);
        if (data) {
            data.visible = false;
        } else {
            el.style.display = 'none';
        }
        clearProgressiveTimeout();
    }

    function startProgressiveTimeout() {
        clearProgressiveTimeout();
        timeoutStage = 0;
        const el = typingEl();

        // Schedule text updates
        for (let i = 1; i < TIMEOUT_STAGES.length; i++) {
            const stage = TIMEOUT_STAGES[i];
            setTimeout(() => {
                if (!el) return;
                const data = Alpine.$data(el);
                if (data) data.text = stage.text;
            }, stage.at);
        }

        // Schedule error at 45s
        timeoutTimer = setTimeout(() => {
            hideTyping();
            appendErrorBubble('This is taking too long. Please try again.');

            // Reset inflight state so user can type again
            const form = document.getElementById('chat-form');
            if (form) {
                const alpineData = Alpine.$data(form);
                if (alpineData) alpineData.inflight = false;
            }
            setChipsDisabled(false);
        }, TIMEOUT_ERROR_MS);
    }

    function clearProgressiveTimeout() {
        if (timeoutTimer) {
            clearTimeout(timeoutTimer);
            timeoutTimer = null;
        }
    }

    // --- Optimistic UI ---
    function appendUserBubble(text) {
        const container = messagesEl();
        if (!container) return;

        // Remove empty chat state if present
        const empty = container.querySelector('.flex.flex-col.items-center');
        if (empty) empty.remove();

        const bubble = document.createElement('div');
        bubble.className = 'flex justify-end';
        bubble.innerHTML = `
            <div class="max-w-[85%]">
                <div class="px-4 py-2.5 text-white text-lg leading-relaxed"
                     style="background-color: var(--color-primary);
                            border-radius: 16px 16px 4px 16px;">
                    ${clintelaMarkdown.escapeHtml(text)}
                </div>
                <div class="text-xs mt-1 text-right" style="color: var(--color-text-secondary);">
                    just now
                </div>
            </div>
        `;
        container.appendChild(bubble);
        container.scrollTo({ top: container.scrollHeight, behavior: 'smooth' });
    }

    function appendIncomingBubble(message) {
        const container = messagesEl();
        if (!container) return;

        // Remove empty chat state if present
        const empty = container.querySelector('.flex.flex-col.items-center');
        if (empty) empty.remove();

        const name = message.clinician_name || 'Your Care Team';
        const bubble = document.createElement('div');
        bubble.className = 'flex justify-start';
        bubble.innerHTML = `
            <div class="max-w-[85%]">
                <div class="text-xs mb-1 flex items-center gap-1" style="color: var(--color-text-secondary);">
                    <span>\u2695 ${clintelaMarkdown.escapeHtml(name)}</span>
                </div>
                <div class="agent-message-content px-4 py-2.5 text-lg leading-relaxed"
                     style="background-color: var(--color-surface);
                            border: 1px solid var(--color-border);
                            border-radius: 16px 16px 16px 4px;"
                     data-raw-content="${clintelaMarkdown.escapeHtml(message.content)}">
                    ${clintelaMarkdown.escapeHtml(message.content)}
                </div>
                <div class="text-xs mt-1" style="color: var(--color-text-secondary);">
                    just now
                </div>
            </div>
        `;
        container.appendChild(bubble);
        renderAgentMessages(bubble);
        container.scrollTo({ top: container.scrollHeight, behavior: 'smooth' });
        playNotifySound();
    }

    function appendErrorBubble(text) {
        const container = messagesEl();
        if (!container) return;

        const bubble = document.createElement('div');
        bubble.className = 'flex justify-start';
        bubble.innerHTML = `
            <div class="max-w-[85%]">
                <div class="px-4 py-2.5 text-lg leading-relaxed"
                     style="background-color: #FEE2E2; color: #991B1B;
                            border-radius: 16px 16px 16px 4px;">
                    ${clintelaMarkdown.escapeHtml(text)}
                    <button onclick="clintelaChat.retry()" class="block mt-2 text-sm underline hover:no-underline">
                        Try again
                    </button>
                </div>
            </div>
        `;
        container.appendChild(bubble);
        container.scrollTo({ top: container.scrollHeight, behavior: 'smooth' });
    }

    // --- Markdown in agent messages ---
    // Delegates to shared clintelaMarkdown.renderAgentMessages() with local fallback
    function renderAgentMessages(root) {
        if (window.clintelaMarkdown) {
            window.clintelaMarkdown.renderAgentMessages(root);
            return;
        }
        // Fallback: inline rendering if shared lib not loaded
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

    // --- Notification sound ---
    let soundEnabled = localStorage.getItem('clintela-sound') === 'true';
    let audioCtx = null;

    function playNotifySound() {
        if (!soundEnabled) return;
        try {
            if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            const osc = audioCtx.createOscillator();
            const gain = audioCtx.createGain();
            osc.connect(gain);
            gain.connect(audioCtx.destination);
            osc.type = 'sine';
            osc.frequency.setValueAtTime(880, audioCtx.currentTime);
            osc.frequency.setValueAtTime(1100, audioCtx.currentTime + 0.08);
            gain.gain.setValueAtTime(0.08, audioCtx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.2);
            osc.start(audioCtx.currentTime);
            osc.stop(audioCtx.currentTime + 0.2);
        } catch (_) { /* silent fail */ }
    }

    function toggleSound() {
        soundEnabled = !soundEnabled;
        localStorage.setItem('clintela-sound', soundEnabled);
        // Update icon
        const icon = document.getElementById('sound-icon');
        if (icon) {
            icon.setAttribute('data-lucide', soundEnabled ? 'volume-2' : 'volume-x');
            if (typeof lucide !== 'undefined') lucide.createIcons();
        }
    }

    // --- Escalation banner ---
    function checkEscalation(fragment) {
        const esc = fragment && fragment.querySelector('[data-escalation]');
        if (esc) {
            const banner = document.getElementById('escalation-banner');
            if (banner) banner.classList.remove('hidden');
        }
    }

    // --- Offline detection ---
    function initOffline() {
        function update() {
            const banner = document.getElementById('offline-banner');
            const textarea = document.getElementById('chat-textarea');
            if (!navigator.onLine) {
                if (banner) banner.classList.remove('hidden');
                if (textarea) textarea.disabled = true;
            } else {
                if (banner) banner.classList.add('hidden');
                if (textarea) textarea.disabled = false;
            }
        }
        window.addEventListener('online', update);
        window.addEventListener('offline', update);
        update();
    }

    // --- Suggestion chip ---
    function sendChip(text) {
        const textarea = document.getElementById('chat-textarea');
        const form = document.getElementById('chat-form');
        if (!textarea || !form) return;

        // Set value via Alpine
        textarea.value = text;
        textarea.dispatchEvent(new Event('input', { bubbles: true }));

        // Small delay to let Alpine sync, then submit
        requestAnimationFrame(() => {
            form.requestSubmit();
        });
    }

    // --- Retry last message ---
    let lastMessage = '';

    function retry() {
        if (!lastMessage) return;
        sendChip(lastMessage);
    }

    // --- Disable/enable chips during flight ---
    function setChipsDisabled(disabled) {
        const chips = document.querySelectorAll('.suggestion-chip');
        chips.forEach(c => {
            c.disabled = disabled;
        });
    }

    // --- HTMX event handlers (called from template attributes) ---

    function onBeforeRequest(event) {
        const form = event.target;
        const textarea = form.querySelector('textarea[name="message"]');
        const text = textarea ? textarea.value.trim() : '';

        if (!text) {
            event.preventDefault();
            return;
        }

        lastMessage = text;

        // Optimistic UI
        appendUserBubble(text);

        // Clear textarea via Alpine
        textarea.value = '';
        textarea.dispatchEvent(new Event('input', { bubbles: true }));
        textarea.style.height = 'auto';

        // Set inflight via Alpine
        const alpineData = Alpine.$data(form);
        if (alpineData) {
            alpineData.message = '';
            alpineData.inflight = true;
        }

        showTyping();
        setChipsDisabled(true);
    }

    function onAfterRequest(event) {
        // Fires on the form element after any response (success or error).
        // Cleans up typing indicator and inflight state reliably.
        hideTyping();

        const form = event.target;
        const alpineData = Alpine.$data(form);
        if (alpineData) {
            alpineData.inflight = false;
        }

        setChipsDisabled(false);
    }

    function onError(event) {
        hideTyping();

        const form = event.target;
        const alpineData = Alpine.$data(form);
        if (alpineData) {
            alpineData.inflight = false;
        }

        setChipsDisabled(false);
        appendErrorBubble('Something went wrong. Please try again.');
    }

    // --- Init ---
    function init() {
        initOffline();
        renderAgentMessages();

        // Scroll to bottom on load
        const container = messagesEl();
        if (container) {
            container.scrollTop = container.scrollHeight;
        }

        // Post-swap work: render markdown, scroll, play sound.
        // afterSettle fires on the swap target (#messages), so check elt.id
        // matches the messages container. Typing/inflight cleanup is handled
        // by onAfterRequest (fires on the form).
        document.body.addEventListener('htmx:afterSettle', (event) => {
            if (event.detail.elt?.id !== 'messages') return;
            const xhr = event.detail.xhr;
            if (!xhr || xhr.status !== 200) return;

            // If non-empty response (AI message was swapped in), do post-swap work
            if (xhr.responseText.trim()) {
                renderAgentMessages();
                if (typeof lucide !== 'undefined') lucide.createIcons();
                const container = messagesEl();
                if (container) {
                    checkEscalation(container);
                    container.scrollTo({ top: container.scrollHeight, behavior: 'smooth' });
                }
                playNotifySound();
                const textarea = document.getElementById('chat-textarea');
                if (textarea) textarea.focus();
            }
        });

        // Expose sound toggle
        window.clintelaSoundToggle = toggleSound;
    }

    // Run init when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Public API
    return {
        sendChip,
        retry,
        toggleSound,
        onBeforeRequest,
        onAfterRequest,
        onError,
        appendIncomingBubble,
    };
})();
