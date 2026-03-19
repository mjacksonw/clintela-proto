/**
 * Clintela dark mode management.
 *
 * Reads/writes localStorage('clintela-theme') — 'light', 'dark', or 'system'.
 * Listens for prefers-color-scheme changes when in 'system' mode.
 */
(function () {
  var STORAGE_KEY = 'clintela-theme';

  function getStoredTheme() {
    try {
      return localStorage.getItem(STORAGE_KEY) || 'system';
    } catch (e) {
      return 'system';
    }
  }

  function getEffectiveTheme(preference) {
    if (preference === 'system') {
      return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }
    return preference;
  }

  function applyTheme(preference) {
    var effective = getEffectiveTheme(preference);
    document.documentElement.setAttribute('data-theme', effective);
  }

  function setTheme(preference) {
    try {
      localStorage.setItem(STORAGE_KEY, preference);
    } catch (e) {
      // localStorage unavailable — theme still works for this session
    }
    applyTheme(preference);
  }

  // Toggle cycles: light → dark → system → light
  function toggleTheme() {
    var current = getStoredTheme();
    var next = current === 'light' ? 'dark' : current === 'dark' ? 'system' : 'light';
    setTheme(next);
    return next;
  }

  // Listen for system theme changes
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function () {
    if (getStoredTheme() === 'system') {
      applyTheme('system');
    }
  });

  // Expose globally for Alpine.js
  window.clintelaTheme = {
    get: getStoredTheme,
    set: setTheme,
    toggle: toggleTheme,
    effective: function () {
      return getEffectiveTheme(getStoredTheme());
    },
  };
})();
