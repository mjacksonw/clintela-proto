# Changelog

All notable changes to this project will be documented in this file.

## [0.2.5.0] - 2026-03-19

### Added
- Playwright E2E test suite (27 tests) covering dashboard structure, accessibility attributes, and chat sidebar DOM
- WCAG 2.1 AA accessibility improvements: `aria-modal` on mobile dialog, `id="main-content"` on main element, `<label>` for chat textarea
- Playwright and pytest-playwright as dev dependencies
- E2E tests excluded from xdist parallel runs via `--ignore=tests/e2e` in pytest addopts

### Changed
- Patient dashboard template rewritten with cleaner recovery status hero, phase-based "What to Expect" guidance, and simplified care team card
- Patient views refactored: lazy imports for agent services, improved error handling with inline HTML error response, `settings.DEBUG` for debug flag
- Suggestion chips now fall back to sensible defaults when no pathway data is available
- Chat send view mock path fixed from `apps.patients.views.get_workflow` to `apps.agents.workflow.get_workflow`
- Django Debug Toolbar defaults to collapsed in development settings

### Fixed
- E2E tests use `.first` for elements duplicated across desktop sidebar and mobile dialog (strict mode violations)
- E2E form test scoped to `[role='complementary']` sidebar to avoid ambiguity
