/**
 * Alpine.js component for check-in widget state management.
 *
 * Handles: tap → loading → success/error states
 * Submits via HTMX to the REST API endpoint.
 * Respects reduced-motion preference.
 */
function checkinWidget(sessionId, questionCode, initialAnswered, initialValue) {
    return {
        sessionId,
        questionCode,
        answered: initialAnswered || false,
        selectedValue: initialValue || null,
        loading: false,
        pendingValue: null,
        freeTextValue: '',
        statusMessage: '',
        error: false,

        async submitResponse(value) {
            if (this.answered || this.loading) return;

            this.loading = true;
            this.pendingValue = value;
            this.error = false;

            try {
                const response = await fetch(
                    `/api/widgets/respond/${this.sessionId}/${this.questionCode}/`,
                    {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': this._getCSRFToken(),
                        },
                        body: JSON.stringify({ value }),
                    }
                );

                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }

                const data = await response.json();

                if (data.success) {
                    this.answered = true;
                    this.selectedValue = value;
                    this.statusMessage = `Saved: ${value}`;

                    // Check if session is complete
                    if (data.updated_widget_state?.session_complete) {
                        // Session complete — follow-ups will appear via WebSocket or page refresh
                        this.statusMessage = 'All questions answered. Thanks!';
                    }
                } else {
                    throw new Error(data.error || 'Unknown error');
                }
            } catch (err) {
                console.error('Widget response failed:', err);
                this.error = true;
                this.pendingValue = null;

                // Brief red flash on the button (handled via CSS)
                this.$el.classList.add('widget-error-flash');
                setTimeout(() => this.$el.classList.remove('widget-error-flash'), 200);

                // Toast notification
                if (window.clintelaChat?.showToast) {
                    window.clintelaChat.showToast("Couldn't save your answer. Tap to try again.");
                }
            } finally {
                this.loading = false;
            }
        },

        _getCSRFToken() {
            const cookie = document.cookie
                .split('; ')
                .find(row => row.startsWith('csrftoken='));
            return cookie ? cookie.split('=')[1] : '';
        },
    };
}
