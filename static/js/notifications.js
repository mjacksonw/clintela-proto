/**
 * Notification bell — WebSocket-powered real-time notifications.
 *
 * Alpine.js component: notificationBell()
 * Connects to ws/notifications/patient/<id>/ for live updates.
 * Falls back gracefully if WebSockets are unavailable.
 */
function notificationBell() {
    return {
        open: false,
        unreadCount: 0,
        notifications: [],
        _ws: null,
        _reconnectTimer: null,
        _reconnectDelay: 1000,

        init() {
            const el = this.$el;
            const patientId = el.dataset.patientId;
            if (!patientId) return;

            this._connect(patientId);

            // Close dropdown on outside click
            document.addEventListener('click', (e) => {
                if (this.open && !el.contains(e.target)) {
                    this.open = false;
                }
            });
        },

        _connect(patientId) {
            const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
            const url = `${protocol}//${location.host}/ws/notifications/patient/${patientId}/`;

            try {
                this._ws = new WebSocket(url);
            } catch (e) {
                return;
            }

            this._ws.onopen = () => {
                this._reconnectDelay = 1000;
            };

            this._ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                this._handleMessage(data);
            };

            this._ws.onclose = () => {
                this._scheduleReconnect(patientId);
            };

            this._ws.onerror = () => {
                // onclose will fire after onerror
            };
        },

        _scheduleReconnect(patientId) {
            if (this._reconnectTimer) return;
            this._reconnectTimer = setTimeout(() => {
                this._reconnectTimer = null;
                this._reconnectDelay = Math.min(this._reconnectDelay * 2, 30000);
                this._connect(patientId);
            }, this._reconnectDelay);
        },

        _handleMessage(data) {
            switch (data.type) {
                case 'unread_count':
                    this.unreadCount = data.count;
                    break;

                case 'notification.new':
                    this.unreadCount = data.unread_count || this.unreadCount + 1;
                    this.notifications.unshift(data.notification);
                    // Keep max 20
                    if (this.notifications.length > 20) {
                        this.notifications = this.notifications.slice(0, 20);
                    }
                    this._showToast(data.notification);
                    break;

                case 'notification.read':
                    this.unreadCount = data.unread_count ?? Math.max(0, this.unreadCount - 1);
                    const idx = this.notifications.findIndex(n => n.id === data.notification_id);
                    if (idx !== -1) {
                        this.notifications[idx].is_read = true;
                    }
                    break;
            }
        },

        markRead(notificationId) {
            if (this._ws && this._ws.readyState === WebSocket.OPEN) {
                this._ws.send(JSON.stringify({
                    action: 'mark_read',
                    notification_id: notificationId,
                }));
            }
        },

        markAllRead() {
            this.notifications.forEach(n => {
                if (!n.is_read) this.markRead(n.id);
            });
        },

        get badgeText() {
            if (this.unreadCount === 0) return '';
            return this.unreadCount > 9 ? '9+' : String(this.unreadCount);
        },

        get bellLabel() {
            if (this.unreadCount === 0) return 'Notifications';
            return `${this.unreadCount} unread notification${this.unreadCount !== 1 ? 's' : ''}`;
        },

        _showToast(notification) {
            if (window.clintelaChat && window.clintelaChat.showToast) {
                window.clintelaChat.showToast(notification.title, 'info');
            }
        },

        severityColor(severity) {
            switch (severity) {
                case 'critical': return 'var(--color-danger, #DC2626)';
                case 'warning': return 'var(--color-warning, #D97706)';
                default: return 'var(--color-primary, #0D9488)';
            }
        },

        timeAgo(isoString) {
            if (!isoString) return '';
            const d = new Date(isoString);
            const now = new Date();
            const diff = Math.floor((now - d) / 1000);
            if (diff < 60) return 'just now';
            if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
            if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
            return `${Math.floor(diff / 86400)}d ago`;
        },

        destroy() {
            if (this._ws) this._ws.close();
            if (this._reconnectTimer) clearTimeout(this._reconnectTimer);
        },
    };
}
