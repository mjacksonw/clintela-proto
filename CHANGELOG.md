# Changelog

All notable changes to this project will be documented in this file.

## [0.2.11.0] - 2026-03-23

### Added
- Clinical Intelligence Layer — three-layer architecture: ClinicalObservation → PatientClinicalSnapshot → ClinicalAlert
- OMOP CDM concept ID mapping for 12 cardiac-relevant vitals and labs (heart rate, blood pressure, SpO2, body weight, temperature, step count, BNP, troponin, etc.)
- Deterministic rules engine with 16 registered rules: threshold rules, trend rules, missing data detection, and combination rules (CHF decompensation, infection signal, ePRO-activity correlation)
- FDA 2026 CDS-compliant rule_rationale on every alert — auditable, transparent, deterministic
- Clinician Vitals tab (6th tab, keyboard shortcut `6`) with snapshot summary bar, expandable alerts, Chart.js vital sign charts with normal range bands, and lab results table with EHR/OMOP source badges
- Patient My Health card with sparkline charts (2×2 grid) and warm trajectory messaging
- Trajectory arrows (↗/→/↘/⬇) on patient list items with color-coded severity
- Clinical alerts auto-wire to existing triage color system (update_triage_color)
- Clinical data injection into AI agent context (trajectory, risk score, vital signs, active alerts)
- Clinical alert summary in administrator KPI dashboard (severity counts, avg acknowledgment time, top 5 triggering rules)
- Clinical alert context in clinician handoff summaries
- Feature flag `ENABLE_CLINICAL_DATA` (follows existing ENABLE_RAG, ENABLE_SMS pattern) — all UI gated
- Dark mode support for all clinical UI components
- Seed command (`seed_clinical_data`) with 4 clinical scenarios: progressing, CHF decompensation, infection, declining activity
- Management command (`compute_clinical_snapshots`) for nightly snapshot recomputation
- Celery tasks for nightly snapshot computation and 6-hourly missing data checks
- 118 clinical tests across 7 test files (models, rules, services, views, commands, tasks, coverage gaps)

### Fixed
- IDOR vulnerability in vitals tab — added clinician role + hospital access verification
- Race condition in alert deduplication — IntegrityError catch on UniqueConstraint
- Chart.js infinite height bug — canvas in position:relative div with fixed 160px height
- Chart visual density — pointRadius:0 (hover only), borderWidth:1.5, tension:0.4
- data_completeness display — stored as 0-1 decimal, now correctly displayed as percentage
- Patient sparklines not rendering — Chart.js CDN added to patient base template + vanilla JS canvas creation
- Sparkline data double-serialized — pass dict directly to json_script (not json.dumps)

## [0.2.10.0] - 2026-03-21

### Added
- Survey/ePRO system with 6 clinical instruments (PHQ-2, Daily Symptom Check, KCCQ-12, SAQ-7, AFEQT, PROMIS Global-10)
- Patient survey wizard with intro screen, progress bar, post-completion reassurance, and abandon/resume flow
- Clinician Surveys tab (5th tab) with scores-first layout, sparkline trends, and assignment management
- Survey dashboard card with color-coded urgency borders and warm "All caught up!" empty state
- Patient score history with CSS bars and accessible aria-labels
- System messages in chat for survey completions (green) and missed surveys (amber)
- Deterministic scoring engine with automatic escalation and score change alerts
- Automated survey scheduling: daily instance creation and 30-minute expiration with missed-survey notifications
- Surveys auto-assigned when a patient receives a care pathway
- Data Visualization design system section in DESIGN.md (sparklines, score bars, delta badges, trend indicators)
- Administrator KPI dashboard replacing manual EHR-to-Excel workflows — 9 live metric cards
- Operational alerts bar, global hospital/time filters, CSV export, pathway administration
- DailyMetrics pipeline for trend analysis with nightly pre-aggregation
- 113 survey tests + 117 admin dashboard tests

### Fixed
- Race condition in survey instance creation (catch IntegrityError from concurrent requests)
- Race condition in expire task (atomic queryset update prevents overwriting completed surveys)
- Alpine.js :style binding overwriting static width/height on survey buttons (numeric 44px, Likert 56px)
- Survey modal overlay rendering inline instead of full-viewport (container moved to body)
- Score bar width calculated as percentage of 100 instead of instrument max score

## [0.2.9.0] - 2026-03-21

### Added
- Cardiology service demo data management command with 45 patients, realistic conversations, escalations, and appointments
- Cardiac pathways seed command with post-operative milestone definitions
- Conversation history context — agents now receive last 10 messages for continuity

### Fixed
- WebSocket support: added daphne to INSTALLED_APPS for ASGI dev server
- Patient chat loaded wrong conversation when clinician had active research thread (added clinician__isnull=True filter)
- Clinician-to-patient real-time push: messages now route through notification WebSocket group instead of unused chat group
- Patient-to-clinician real-time push: messages route through hospital dashboard WebSocket group with patient_message handler
- Typing indicator never hiding after AI response: migrated Alpine v2 API (el.__x) to v3 (Alpine.$data), switched from hx-on::after-swap to htmx:afterSettle for reliable post-swap handling
- Empty response handling when clinician has chat control (no AI response generated)
- Chat scroll-to-bottom on clinician side (runs on each HTMX fragment swap)
- Escalation acknowledge/resolve not updating UI: views now refresh_from_db() after service call to return updated state
- Dashboard WebSocket not connecting: added data-hospital-id attribute to clinician template

## [0.2.8.0] - 2026-03-20

### Added
- Three-panel clinician dashboard — patient list (severity sort, search, triage dots), patient detail (4 tabs), and patient chat panel
- Details tab with patient timeline (collapsed by day, expandable), escalation management (acknowledge/resolve/bulk), clinician notes, and export handoff
- Care Plan tab showing pathway milestones with check-in status
- Research tab — private clinician LLM chat with specialist routing dropdown, patient context pre-loaded
- Tools tab — lifecycle transitions, send auth text, consent status, caregiver management, patient info
- Take-control mode: clinician takes over patient chat thread with race-safe locking (atomic DB update), AI pauses, patient sees named clinician, three release mechanisms (explicit, disconnect, 30-min timeout)
- Scheduling UI with weekly calendar grid (7am–7pm clinical hours), availability management, and appointment CRUD with conflict validation
- Shift handoff summary showing changes since last login (escalations, status changes, missed check-ins)
- Keyboard shortcuts: j/k navigate patients, 1-4 switch tabs, e acknowledge escalation, / search, ? help modal — suppressed in input fields
- Desktop notification permission + critical escalation alerts (Web Notification API + Web Audio)
- Clinician auth with `@clinician_required` decorator enforcing role + hospital-scoped IDOR prevention
- Clinician login/logout views with Django session auth
- New models: ClinicianNote, ClinicianAvailability, Appointment
- Agent model extensions: clinician FK, paused_by/paused_at on AgentConversation, clinician_research agent type
- `create_test_clinician` management command (hospital, clinician, 5 patients at varying triage levels)
- Responsive layouts: desktop three-panel, tablet two-panel + chat drawer, mobile single-panel + bottom nav
- Next appointment toast on dashboard footer
- 90%+ test coverage with 6 test files covering all clinician features

### Fixed
- WebSocket consumer auth: `ClinicianDashboardConsumer` now verifies authenticated clinician with hospital access instead of accepting all connections
- WebSocket consumer correctly returns without accepting when auth fails (was calling `self.close()` before `self.accept()`)
- Agent API escalation acknowledge uses session auth instead of clinician_id from request body
- Schedule week range display now shows correct start and end dates
- DOB field in Tools tab references `patient.date_of_birth` instead of `patient.user.date_of_birth`
- Three-panel layout fixed — aside tags had missing closing `>` after Alpine `:class` attribute

## [0.2.7.0] - 2026-03-20

### Added
- Clinical knowledge RAG system with pgvector hybrid search (vector similarity + full-text ranking) for evidence-backed agent responses
- Knowledge ingestion pipeline with PDF, Markdown, HTML, and text parsers, SHA-256 deduplication, and content sanitizer for prompt injection defense
- Embedding client (Ollama nomic-embed-text) with mock client for testing and batch embedding support
- Six RAG-backed specialist agents (Cardiology, Pharmacy, Nutrition, PT/Rehab, Social Work, Palliative) replacing placeholder escalation-only agents
- Patient-facing citation display with expandable source list on chat message bubbles (Alpine.js x-collapse)
- MessageCitation M2M through model linking agent messages to knowledge documents with similarity scores
- Knowledge gap tracking — logs unanswered patient questions for admin visibility
- Knowledge health admin dashboard with source freshness indicators, top knowledge gaps, and most-cited documents
- Patient lifecycle state machine (pre_surgery → admitted → in_surgery → post_op → discharged → recovering → recovered) with atomic transitions and audit trail
- Advanced escalation model with type classification, priority scoring, and SLA tracking
- Caregiver invitation flow with token-based acceptance, leaflet code verification, and concurrent-safe atomic claim
- Consent management with append-only audit trail (5 consent types: AI interaction, caregiver sharing, SMS, email, research)
- Patient dashboard quick-link cards for Caregivers and Privacy pages
- ACC guideline scraper and document ingestion management commands

### Changed
- Care Coordinator and Nurse Triage agents now use RAG evidence when ENABLE_RAG=True, with confidence bonus for strong matches
- Specialist agents answer with clinical evidence instead of unconditionally escalating — escalation now based on confidence threshold
- Agent error messages sanitized to prevent internal error details leaking to patients
- Docker Compose postgres image switched to pgvector/pgvector:pg16

### Fixed
- Hardened concurrency controls: atomic invitation acceptance, optimistic locking on lifecycle transitions
- Input validation strengthened across caregiver and consent endpoints
- Toggle switch and back-link touch targets increased to 44px WCAG minimum

## [0.2.6.2] - 2026-03-19

### Fixed
- Chat message font size reduced from 18px to 16px to match input textarea and DESIGN.md minimum
- Chat pane and main content pane now scroll independently (overscroll-behavior: contain prevents scroll chaining)
- Dev toolbar no longer overlaps chat input (CSS custom property for dynamic bottom padding in debug mode)

## [0.2.6.1] - 2026-03-19

### Changed
- Implementation handoff document updated with Phase 3 details: project structure, environment variables, key files, testing summary, and resolved open questions
- Contributing guide updated to reference Ruff instead of Black/isort

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
