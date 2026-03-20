# Changelog

All notable changes to this project will be documented in this file.

## [0.2.6.0] - 2026-03-19

### Added
- Notification engine with multi-channel delivery (in-app, SMS, email) and pluggable backends (Console/LocMem for dev/test)
- Celery task queue integration with Redis broker for async notification delivery and scheduled reminders
- SMS integration with Twilio backend abstraction, console backend for development, opt-out (STOP/START), and rate limiting
- SMS webhook endpoints for inbound messages and delivery status callbacks with Twilio signature validation
- Voice input via MediaRecorder — record, transcribe, and process through AI workflow
- Three-tier transcription system: MockTranscriptionClient, LocalWhisperClient (faster-whisper), RemoteTranscriptionClient
- WebSocket notification consumers for real-time patient and clinician notifications
- Notification bell with unread badge, desktop dropdown, and mobile bottom sheet
- Channel indicator icons on message bubbles (voice/SMS/web) and delivery status indicators
- Audio playback widget for voice messages with authenticated file serving
- Dev toolbar with SMS simulator, patient switcher, conversation reset, and patient info display
- Notification preference model with per-channel quiet hours support
- Voice memo cleanup management command and Celery periodic task (24h retention)
- Shared `process_patient_message()` helper eliminating code triplication across chat/SMS/voice
- Phone number database index for SMS inbound lookup performance
- Comprehensive test suite: 15 new test files covering all Phase 3 modules
- Acceptance testing guide for manual QA of all Phase 3 features

### Fixed
- Chat input no longer stuck disabled after 45-second client-side timeout
- WebSocket reconnect capped at 10 attempts to prevent console spam in dev mode
- Focus-visible rings added to voice record, stop, and send buttons for keyboard accessibility
- Audio file extension validated against allowlist to prevent path traversal
- Clinician WebSocket auth correctly looks up Clinician model by user FK

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
