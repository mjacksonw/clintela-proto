/**
 * Clinician Dashboard — Alpine.js component
 *
 * Manages: patient selection, tab switching, keyboard shortcuts,
 * WebSocket connections, desktop notifications, take-control inactivity timer.
 */

/* global Alpine */

function clinicianDashboard() {
    return {
        // State
        selectedPatientId: null,
        activeTab: 'details',
        showKeyboardHelp: false,
        chatDrawerOpen: false,
        mobilePanel: 'list',

        // Notification state
        notificationPermission: Notification.permission || 'default',

        // URL routing guard
        _restoringFromUrl: false,

        // Take-control inactivity timer (30 min)
        _takeControlTimer: null,
        TAKE_CONTROL_TIMEOUT_MS: 30 * 60 * 1000,

        // WebSocket
        _dashboardWs: null,
        _reconnectAttempts: 0,

        init() {
            // Request notification permission
            if (this.notificationPermission === 'default') {
                Notification.requestPermission().then(p => {
                    this.notificationPermission = p;
                });
            }

            // Connect to dashboard WebSocket if hospital data is available
            this._connectDashboardWs();

            // Restore state from URL path (deep link / bookmark / refresh)
            const el = this.$el;
            const initialPatient = el.dataset.initialPatient;
            const initialTab = el.dataset.initialTab || 'details';
            const initialSubview = el.dataset.initialSubview;

            if (initialPatient) {
                this.$nextTick(() => {
                    this._restoringFromUrl = true;
                    this.selectedPatientId = initialPatient;
                    this.activeTab = initialTab;
                    this._loadTab(initialPatient, initialTab);
                    this._loadChat(initialPatient);
                    if (initialSubview && initialTab === 'surveys') {
                        const url = `/patient/surveys/clinician/instance/${initialSubview}/results/`;
                        setTimeout(() => {
                            htmx.ajax('GET', url, {
                                target: document.getElementById('detail-panel'),
                                swap: 'innerHTML'
                            });
                        }, 100);
                    }
                    this._highlightPatientInList(initialPatient);
                    this._restoringFromUrl = false;
                });
            }

            // Handle browser back/forward
            window.addEventListener('popstate', () => {
                if (!this._restoreFromUrl()) {
                    this.selectedPatientId = null;
                    this.activeTab = 'details';
                }
            });
        },

        // ---------------------------------------------------------------
        // Patient selection
        // ---------------------------------------------------------------

        selectPatient(patientId) {
            this.selectedPatientId = patientId;
            this.activeTab = 'details';

            // Load detail panel (tab content)
            this._loadTab(patientId, 'details');

            // Load chat panel
            this._loadChat(patientId);

            // Update browser URL
            if (!this._restoringFromUrl) this._updateUrl();

            // Focus center panel
            this.$nextTick(() => {
                const main = document.getElementById('main-content');
                if (main) main.focus();
            });
        },

        // ---------------------------------------------------------------
        // Tab switching
        // ---------------------------------------------------------------

        switchTab(tab) {
            if (!this.selectedPatientId) return;
            this.activeTab = tab;
            this._loadTab(this.selectedPatientId, tab);
            if (!this._restoringFromUrl) this._updateUrl();
        },

        _loadTab(patientId, tab) {
            const tabUrls = {
                details: `/clinician/patients/${patientId}/detail/`,
                care_plan: `/clinician/patients/${patientId}/care-plan/`,
                research: `/clinician/patients/${patientId}/research/`,
                surveys: `/patient/surveys/clinician/${patientId}/`,
                tools: `/clinician/patients/${patientId}/tools/`,
                vitals: `/clinical/clinician/patient/${patientId}/vitals/`,
            };

            const url = tabUrls[tab];
            if (!url) return;

            const target = document.getElementById('detail-panel');
            if (!target) return;

            // Use HTMX to load
            htmx.ajax('GET', url, { target: target, swap: 'innerHTML' });
        },

        _loadChat(patientId) {
            const url = `/clinician/patients/${patientId}/chat/`;
            const target = document.getElementById('chat-panel');
            if (target) {
                htmx.ajax('GET', url, { target: target, swap: 'innerHTML' });
            }
        },

        // ---------------------------------------------------------------
        // Keyboard shortcuts
        // ---------------------------------------------------------------

        handleKeydown(event) {
            // Don't fire when typing in inputs
            const tag = event.target.tagName;
            if (tag === 'INPUT' || tag === 'TEXTAREA' || event.target.isContentEditable) return;

            switch (event.key) {
                case 'j':
                    event.preventDefault();
                    this._navigatePatient(1);
                    break;
                case 'k':
                    event.preventDefault();
                    this._navigatePatient(-1);
                    break;
                case '1':
                    event.preventDefault();
                    this.switchTab('details');
                    break;
                case '2':
                    event.preventDefault();
                    this.switchTab('care_plan');
                    break;
                case '3':
                    event.preventDefault();
                    this.switchTab('research');
                    break;
                case '4':
                    event.preventDefault();
                    this.switchTab('surveys');
                    break;
                case '5':
                    event.preventDefault();
                    this.switchTab('tools');
                    break;
                case '6':
                    event.preventDefault();
                    this.switchTab('vitals');
                    break;
                case 'e':
                    event.preventDefault();
                    this._acknowledgeFirstEscalation();
                    break;
                case '/':
                    event.preventDefault();
                    this._focusSearch();
                    break;
                case '?':
                    event.preventDefault();
                    this.showKeyboardHelp = !this.showKeyboardHelp;
                    break;
                case 'Escape':
                    if (this.showKeyboardHelp) {
                        this.showKeyboardHelp = false;
                    } else if (this.chatDrawerOpen) {
                        this.chatDrawerOpen = false;
                    } else {
                        this.selectedPatientId = null;
                        this._updateUrl();
                    }
                    break;
            }
        },

        _navigatePatient(direction) {
            const items = document.querySelectorAll('[role="option"]');
            if (!items.length) return;

            let currentIdx = -1;
            items.forEach((el, i) => {
                if (el.getAttribute('@click')?.includes(this.selectedPatientId)) {
                    currentIdx = i;
                }
            });

            const newIdx = Math.max(0, Math.min(items.length - 1, currentIdx + direction));
            items[newIdx]?.click();
        },

        _focusSearch() {
            const search = document.getElementById('patient-search');
            if (search) search.focus();
        },

        _acknowledgeFirstEscalation() {
            const ackBtn = document.querySelector('[hx-post*="acknowledge"]');
            if (ackBtn) ackBtn.click();
        },

        // ---------------------------------------------------------------
        // URL routing (pushState / popstate)
        // ---------------------------------------------------------------

        _buildPath(patientId, tab, subview) {
            if (!patientId) return '/clinician/dashboard/';
            let path = `/clinician/dashboard/patient/${patientId}/${tab || 'details'}/`;
            if (subview) path += `${subview}/`;
            return path;
        },

        _updateUrl(opts = {}) {
            const path = this._buildPath(
                this.selectedPatientId,
                this.activeTab,
                opts.subview
            );
            history.pushState({ patientId: this.selectedPatientId, tab: this.activeTab, subview: opts.subview || null }, '', path);
        },

        _restoreFromUrl() {
            const match = window.location.pathname.match(
                /^\/clinician\/dashboard\/patient\/(\d+)(?:\/(\w+))?(?:\/(.+?))?\/?$/
            );
            if (!match) return false;

            const [, patientId, tab, subview] = match;
            const validTabs = ['details', 'care_plan', 'research', 'surveys', 'tools', 'vitals'];
            const resolvedTab = (tab && validTabs.includes(tab)) ? tab : 'details';

            this._restoringFromUrl = true;
            this.selectedPatientId = patientId;
            this.activeTab = resolvedTab;
            this._loadTab(patientId, resolvedTab);
            this._loadChat(patientId);

            if (subview && resolvedTab === 'surveys') {
                const url = `/patient/surveys/clinician/instance/${subview}/results/`;
                setTimeout(() => {
                    htmx.ajax('GET', url, {
                        target: document.getElementById('detail-panel'),
                        swap: 'innerHTML'
                    });
                }, 100);
            }

            this._highlightPatientInList(patientId);
            this._restoringFromUrl = false;
            return true;
        },

        _highlightPatientInList(patientId) {
            const tryHighlight = () => {
                const item = document.querySelector(`[data-patient-id="${patientId}"]`);
                if (item) { item.scrollIntoView({ block: 'nearest' }); return true; }
                return false;
            };
            if (!tryHighlight()) {
                document.addEventListener('htmx:afterSettle', function handler() {
                    tryHighlight();
                    document.removeEventListener('htmx:afterSettle', handler);
                });
            }
        },

        navigateToSurveyResult(instanceId) {
            this._updateUrl({ subview: instanceId });
        },

        backToSurveys() {
            if (!this.selectedPatientId) return;
            this.activeTab = 'surveys';
            this._loadTab(this.selectedPatientId, 'surveys');
            this._updateUrl();
        },

        // ---------------------------------------------------------------
        // WebSocket (dashboard real-time)
        // ---------------------------------------------------------------

        _connectDashboardWs() {
            // Hospital ID is needed — look for data attribute on body or derive from context
            const hospitalEl = document.querySelector('[data-hospital-id]');
            if (!hospitalEl) return;

            const hospitalId = hospitalEl.dataset.hospitalId;
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const url = `${protocol}//${window.location.host}/ws/dashboard/${hospitalId}/`;

            try {
                this._dashboardWs = new WebSocket(url);

                this._dashboardWs.onmessage = (event) => {
                    const data = JSON.parse(event.data);
                    this._handleWsMessage(data);
                };

                this._dashboardWs.onclose = () => {
                    if (this._reconnectAttempts < 10) {
                        const delay = Math.min(1000 * Math.pow(2, this._reconnectAttempts), 30000);
                        this._reconnectAttempts++;
                        setTimeout(() => this._connectDashboardWs(), delay);
                    }
                };

                this._dashboardWs.onopen = () => {
                    this._reconnectAttempts = 0;
                };
            } catch (e) {
                // WebSocket unavailable — graceful degradation
            }
        },

        _handleWsMessage(data) {
            if (data.type === 'escalation_alert') {
                this._showDesktopNotification(
                    'Escalation Alert',
                    `${data.patient_name}: ${data.reason}`,
                );
                // Notify header bell component
                window.dispatchEvent(new CustomEvent('escalation-alert'));
                // Refresh patient list
                htmx.ajax('GET', '/clinician/patients/', {
                    target: '#patient-list-panel',
                    swap: 'innerHTML',
                });
            } else if (data.type === 'patient_status_update') {
                // Refresh patient list
                htmx.ajax('GET', '/clinician/patients/', {
                    target: '#patient-list-panel',
                    swap: 'innerHTML',
                });
            } else if (data.type === 'patient_message') {
                // New patient message — refresh chat if viewing that patient
                if (this.selectedPatientId && String(data.patient_id) === String(this.selectedPatientId)) {
                    this._loadChat(this.selectedPatientId);
                }
            }
        },

        _showDesktopNotification(title, body) {
            if (this.notificationPermission !== 'granted') return;

            try {
                const n = new Notification(title, {
                    body: body,
                    icon: '/static/images/favicon.svg',
                    tag: 'clintela-escalation',
                });

                // Auto-close after 10s
                setTimeout(() => n.close(), 10000);

                // Play alert sound
                this._playAlertSound();
            } catch (e) {
                // Notification API unavailable
            }
        },

        _playAlertSound() {
            try {
                const ctx = new (window.AudioContext || window.webkitAudioContext)();
                const osc = ctx.createOscillator();
                const gain = ctx.createGain();
                osc.connect(gain);
                gain.connect(ctx.destination);
                osc.frequency.value = 880;
                gain.gain.value = 0.1;
                osc.start();
                osc.stop(ctx.currentTime + 0.15);
            } catch (e) {
                // Audio unavailable
            }
        },

        // ---------------------------------------------------------------
        // Take-control inactivity timer
        // ---------------------------------------------------------------

        resetTakeControlTimer() {
            if (this._takeControlTimer) clearTimeout(this._takeControlTimer);

            this._takeControlTimer = setTimeout(() => {
                // Auto-release: fire POST to release endpoint
                if (this.selectedPatientId) {
                    fetch(`/clinician/patients/${this.selectedPatientId}/take-control/release/`, {
                        method: 'POST',
                        headers: {
                            'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content,
                        },
                    }).then(() => {
                        // Reload chat panel
                        this._loadChat(this.selectedPatientId);
                    });
                }
            }, this.TAKE_CONTROL_TIMEOUT_MS);
        },
    };
}

// Helper functions used in HTMX callbacks
function scrollChat() {
    const el = document.getElementById('chat-messages');
    if (el) el.scrollTop = el.scrollHeight;
}

function scrollResearch() {
    const el = document.getElementById('research-messages');
    if (el) el.scrollTop = el.scrollHeight;
}

function exportHandoff(patientId) {
    fetch(`/clinician/patients/${patientId}/export-handoff/`)
        .then(r => r.json())
        .then(data => {
            const text = JSON.stringify(data, null, 2);
            navigator.clipboard.writeText(text).then(() => {
                alert('Handoff notes copied to clipboard.');
            });
        })
        .catch(() => {
            alert('Failed to export handoff notes.');
        });
}

function researchChat() {
    return {
        init() {
            this.$nextTick(() => scrollResearch());
        },
    };
}
