/**
 * Admin Dashboard Alpine.js component.
 *
 * Manages global filters (hospital, time range), dark mode toggle,
 * and HTMX refresh coordination for all KPI cards.
 */

/* global Chart */

function adminDashboard() {
    return {
        hospitalFilter: '',
        daysFilter: '30',
        isDark: document.documentElement.getAttribute('data-theme') === 'dark',

        init() {
            // Read initial filter values from select elements
            const hospitalSelect = this.$el.querySelector('select[x-model="hospitalFilter"]');
            const daysSelect = this.$el.querySelector('select[x-model="daysFilter"]');
            if (hospitalSelect) this.hospitalFilter = hospitalSelect.value;
            if (daysSelect) this.daysFilter = daysSelect.value;

            // Configure Chart.js defaults
            this.configureChartDefaults();

            // Watch for theme changes
            const observer = new MutationObserver(() => {
                this.isDark = document.documentElement.getAttribute('data-theme') === 'dark';
                this.configureChartDefaults();
            });
            observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
        },

        configureChartDefaults() {
            if (typeof Chart === 'undefined') return;

            const isDark = document.documentElement.getAttribute('data-theme') === 'dark';

            Chart.defaults.font.family = "'Satoshi', ui-sans-serif, system-ui, sans-serif";
            Chart.defaults.font.size = 13;
            Chart.defaults.color = isDark ? '#94A3B8' : '#A8A29E';
            Chart.defaults.borderColor = isDark ? '#334155' : '#E7E5E4';

            // Update all existing charts
            Chart.helpers.each(Chart.instances, (chart) => {
                chart.update('none');
            });
        },

        refreshAll() {
            // Reload the page with current filter values as query parameters.
            // The server-rendered page passes filters to each HTMX fragment via :hx-vals.
            const params = new URLSearchParams();
            if (this.hospitalFilter) params.set('hospital', this.hospitalFilter);
            if (this.daysFilter !== '30') params.set('days', this.daysFilter);
            const qs = params.toString();
            window.location.href = window.location.pathname + (qs ? '?' + qs : '');
        },

        toggleTheme() {
            const current = document.documentElement.getAttribute('data-theme');
            const next = current === 'dark' ? 'light' : 'dark';
            document.documentElement.setAttribute('data-theme', next);
            localStorage.setItem('clintela-theme', next);
            this.isDark = next === 'dark';
            this.configureChartDefaults();
        }
    };
}
