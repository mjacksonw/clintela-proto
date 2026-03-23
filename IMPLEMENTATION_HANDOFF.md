# Implementation Session Handoff

**Date:** 2026-03-23
**Branch:** claude/cool-archimedes (Phase 7), claude/vibrant-hopper (Phase 6), claude/brave-goldwasser (Phase 5), feature/phase4-clinical-knowledge-rag (Phase 4)
**Status:** Phase 7 COMPLETE (core) - Clinical Intelligence Layer with three-layer architecture, 16-rule deterministic engine, OMOP bridge, clinician Vitals tab, patient My Health card. Proactive patient messaging deferred.

---

## What We Built

### Phase 1: Foundation ✅ COMPLETE (2026-03-18)

✅ **Development Environment**
- UV package manager with `pyproject.toml` (132 dependencies)
- Docker Compose with pgvector/pgvector:pg16 + Redis 7
- Virtual environment auto-managed (`.venv/`)
- Makefile with 30+ commands (`make dev`, `make test`, `make docker-up`)
- Pre-commit hooks (Ruff, security checks, tests on push)
- GitHub Actions CI workflow
- `.env.example` with all configuration documented

✅ **Django Project Structure**
- Django 5.1.15 with Python 3.12
- Split settings: `base.py`, `development.py`, `production.py`, `test.py`
- 10 Django apps with models:
  - `accounts/` - Custom User model with roles
  - `patients/` - Patient, Hospital models
  - `clinicians/` - Healthcare provider profiles
  - `caregivers/` - Family/caregiver access
  - `agents/` - AI conversation logging
  - `messages_app/` - SMS/chat/voice messages
  - `pathways/` - Clinical pathways
  - `notifications/` - Alerts and escalations
  - `analytics/` - Metrics, DailyMetrics pipeline
  - `administrators/` - Admin KPI dashboard, pathway administration
- All migrations created and applied

### Phase 2: Agent System ✅ COMPLETE (2026-03-19)

✅ **Multi-Agent Architecture**
- LangGraph StateGraph workflow with async nodes
- Supervisor agent with intelligent routing
- Care Coordinator agent (warm, supportive responses)
- Nurse Triage agent (clinical assessment + severity classification)
- Documentation agent (structured summaries)
- 6 RAG-backed Specialist agents (Cardiology, Pharmacy, Nutrition, PT/Rehab, Social Work, Palliative)

✅ **LLM Integration**
- Ollama Cloud API support (`/api/chat` endpoint)
- Configurable model via `OLLAMA_MODEL` env var
- Retry logic with exponential backoff
- MockLLMClient for testing

✅ **Safety & Detection**
- Dual-layer critical symptom detection:
  - Flexible regex patterns (pain 8-10/10, fever 102°F+, bleeding, etc.)
  - LLM-based severity classification (red/orange/yellow/green)
- Agents refuse to diagnose or prescribe
- Automatic escalation to human clinicians
- Confidence scoring with low-confidence escalation

✅ **Conversation Management**
- Conversation persistence via ConversationService
- Context assembly with patient + pathway + history
- Escalation workflow (create → acknowledge → resolve)
- Audit logging for HIPAA compliance

✅ **Testing**
- 641+ tests across all apps (92% coverage)
- Live LLM acceptance testing completed
- Critical keyword detection verified (9/9 scenarios)
- Safety guardrails verified (2/2 scenarios)

---

## Quick Start

```bash
# 1. Start services (PostgreSQL + Redis)
make docker-up

# 2. Activate environment
source .venv/bin/activate

# 3. Run development server
make dev
# Access at http://localhost:8000

# 4. Run tests
POSTGRES_PORT=5434 pytest

# 5. Test with live LLM
python manage.py shell
>>> from apps.agents.workflow import get_workflow
>>> import asyncio
>>> workflow = get_workflow()
>>> result = asyncio.run(workflow.process_message(
...     "When can I shower after surgery?",
...     {"patient": {"name": "Sarah", "surgery_type": "General Surgery", "days_post_op": 5}}
... ))
>>> print(result)
```

---

## Key Architectural Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Package Manager** | UV | 10-100x faster than pip, auto-venv management |
| **Database** | pgvector/pgvector:pg16 | pgvector extension for vector search, port 5434 to avoid conflicts |
| **Cache/Message Broker** | Redis 7 | For Channels and caching, port 6380 |
| **Linting** | Ruff | Replaces black/isort/flake8; faster and simpler |
| **Dev Environment** | Docker-first | `make docker-up` for turn-key setup |
| **Pre-commit** | Yes | Ruff + Django checks + security |
| **WebSockets** | Django Channels | Real-time notifications for patients and clinicians |
| **LLM** | Ollama Cloud | Prototyping; migrate to HIPAA-compliant before production |
| **Agent Framework** | LangGraph | StateGraph for workflow orchestration |
| **Auth** | Leaflet codes + DOB | Two-factor for patients; SAML for clinicians (future) |
| **Task Queue** | Celery + Redis | Async notification delivery, scheduled reminders, voice cleanup |
| **SMS** | Twilio (console in dev) | Backend abstraction with opt-out, rate limiting |
| **Agent Architecture** | Supervisor + tools | Auditability, safety, control |

---

## Implementation Roadmap

### Phase 1: Foundation ✅ COMPLETE
- [x] Django project structure with PostgreSQL
- [x] Core models (Hospital, Patient, Clinician, Caregiver)
- [x] Database migrations and indexes
- [x] Docker Compose setup
- [x] Pre-commit hooks configured
- [x] GitHub Actions CI

### Phase 2: Agent System ✅ COMPLETE
- [x] LangGraph/LangChain integration
- [x] Supervisor agent with routing
- [x] Care Coordinator agent
- [x] Nurse Triage agent with severity classification
- [x] Documentation agent
- [x] 6 Specialist placeholders
- [x] Conversation state persistence
- [x] Agent message logging
- [x] Escalation workflows
- [x] Dual-layer critical symptom detection
- [x] Safety guardrails (no diagnose/prescribe)
- [x] 641+ tests passing (92% coverage)
- [x] Live LLM acceptance testing

### Phase 2.5: Patient UI ✅ COMPLETE
- [x] Base template with full design system (Satoshi font, Tailwind CDN, dark mode)
- [x] Patient chat sidebar (omnipresent, HTMX-powered)
- [x] Chat message bubbles with markdown rendering (marked.js + DOMPurify)
- [x] Patient dashboard (recovery status, care plan, care team cards)
- [x] Optimistic UI, progressive timeout, offline detection
- [x] Suggestion chips (contextual from pathway data)
- [x] Escalation banner and confidence indicators
- [x] Mobile responsive (FAB overlay, tablet collapsible sidebar)
- [x] Dark mode toggle with localStorage persistence
- [x] Django admin registration (Patient, Hospital, User, Conversations)
- [x] `create_test_patient` management command
- [x] Template tags (agent_display_name, agent_icon)
- [x] Auth page styling (DOB entry, token expired, rate limited)
- [x] Accessibility (WCAG 2.1 AA): ARIA landmarks, focus management, focus trap, labels, reduced motion
- [x] Playwright E2E tests (27 tests: DOM structure, a11y attributes, responsiveness)
- [x] Unit tests (chat_send view, templatetags, management command)
- [x] Notification sound (Web Audio API, mute toggle)

### Phase 3: Communication ✅ COMPLETE (2026-03-19)
- [x] Leaflet code + DOB authentication
- [x] Twilio SMS integration (with backend abstraction, STOP/START opt-out, rate limiting)
- [x] WebSocket notification consumers (real-time patient and clinician notifications)
- [x] Notification engine (multi-channel: in-app, SMS, email; pluggable backends)
- [x] Celery task queue with Redis broker for async delivery and scheduled reminders
- [x] Voice input via MediaRecorder with three-tier transcription (Mock/Whisper/Remote)
- [x] Voice memo cleanup management command and Celery periodic task (24h retention)
- [x] Notification bell with unread badge, desktop dropdown, mobile bottom sheet
- [x] Dev toolbar (SMS simulator, patient switcher, conversation reset)
- [x] Channel indicator icons on message bubbles (voice/SMS/web)
- [x] Comprehensive test suite: 15 new test files, 92% coverage

### Phase 4: Clinical Features ✅ COMPLETE (2026-03-20)
- [x] Clinical knowledge RAG with pgvector hybrid search (vector + full-text)
- [x] Knowledge ingestion pipeline (PDF, Markdown, HTML, text; SHA-256 dedup; content sanitizer)
- [x] Embedding client (nomic-embed-text via Ollama) with mock for tests
- [x] 6 RAG-backed specialist agents replacing placeholders
- [x] Patient lifecycle state machine (pre_surgery → admitted → in_surgery → post_op → discharged → recovering → recovered / readmitted)
- [x] Advanced escalation model with type classification, priority scoring, SLA tracking
- [x] Caregiver invitation flow (token-based, atomic acceptance, leaflet verification)
- [x] Consent management with append-only audit trail (5 consent types)
- [x] Patient-facing citation display on chat message bubbles
- [x] Knowledge gap tracking for admin visibility
- [x] Knowledge health admin dashboard
- [x] Management commands: `ingest_document`, `ingest_acc_guidelines`
- [x] Test coverage ≥ 90%

### Phase 5: Clinician Dashboard UI - COMPLETE (2026-03-20)

**Three-Panel Dashboard**
- Patient list (280px left) with severity sort, search, triage color dots, unread badges
- Patient detail (center flex-1) with 4 tabs: Details, Care Plan, Research, Tools
- Patient chat (360px right) with message history and clinician message injection
- Responsive: desktop three-panel, tablet two-panel + chat drawer, mobile single-panel + bottom nav
- Dark mode across all views

**Detail Tabs**
- Details: patient timeline (collapsed by day), escalation list with acknowledge/resolve/bulk, clinician notes, export handoff
- Care Plan: pathway milestones with check-in status
- Research: private clinician LLM chat with specialist routing dropdown
- Tools: lifecycle transitions, send auth text, consent status, caregiver management, patient info

**Take-Control Mode**
- Clinician takes over patient chat thread — AI pauses, patient sees "Dr. Smith"
- Race-safe locking with `select_for_update()` / atomic UPDATE WHERE
- Three release mechanisms: explicit button, WebSocket disconnect, 30-min inactivity timeout (JS + Celery)
- Other clinicians see lock indicator with clinician name

**Scheduling UI**
- Weekly calendar grid with Mon-Fri headers, 7am-7pm clinical shift hours
- Availability management (recurring weekly hours)
- Appointment CRUD with conflict validation
- Next appointment toast on dashboard

**Shift Handoff Summary**
- Changes since last login: new/resolved escalations, status changes, missed check-ins
- First login: "Welcome" card
- Dismissible card above patient list

**Keyboard Shortcuts and Notifications**
- j/k navigate patient list, 1-4 switch tabs, e acknowledge escalation, / search, ? help modal
- Desktop notifications + audio for critical escalations (Web Notification API + Web Audio)
- Shortcuts suppressed when typing in input fields

**Security Hardening**
- `@clinician_required` decorator with IDOR prevention (patient must belong to clinician's hospitals)
- WebSocket consumer auth: verify authenticated clinician with hospital access
- Session-based API auth replacing hacky clinician_id-from-body pattern
- Structured audit logging for HIPAA compliance

**Testing**
- 6 test files covering models, auth, views, services, management command, coverage gaps
- 90%+ test coverage (pre-push hook enforced)
- QA: 3 issues found and fixed, health score 64 to 100

### Phase 6: Administrator KPI Dashboard - COMPLETE (2026-03-21)

**KPI Scorecard Dashboard**
- Hero metric: CMS cohort-based readmission rate with period tabs (7/30/60/90/120d) and Chart.js sparkline trend
- 9 metric cards in 3-column grid: Outcomes (discharge to community, follow-up completion, functional improvement), Engagement (program engagement 7/14/30/90d, message volume, check-in completion), Operations (escalation response time, census + triage distribution, pathway performance)
- Operational alerts bar: SLA breaches, stale escalations (>24h), inactive patients (>7d)
- HTMX lazy-loaded card fragments with per-card graceful degradation on DB errors

**Global Filters and Export**
- Hospital filter dropdown scoping all KPI cards
- Time range filter (30/60/90/120 days)
- CSV export with StreamingHttpResponse and formula injection protection
- Print-friendly CSS stylesheet (force light mode, 2-column grid, hide nav)

**Pathway Administration**
- Pathway list with effectiveness stats (completion rate, patient count)
- Pathway detail with milestones, per-milestone check-in rates
- Inline edit for pathway metadata (name, description, duration)
- Active/inactive toggle

**DailyMetrics Pipeline**
- Hospital-scoped pre-aggregation: per-hospital rows + NULL-hospital aggregate
- `DailyMetricsService.compute_for_date()` computing 13 metric fields
- Celery Beat nightly task (2:07 AM daily) with retry logic
- `compute_daily_metrics` management command with `--date` and `--backfill N` flags
- `unique_together = [("date", "hospital")]` constraint on DailyMetrics

**Admin Auth and Security**
- `@admin_required` decorator (mirrors `@clinician_required` pattern)
- `create_test_admin` management command
- No PHI — services return aggregate dicts only, templates never render individual patient data
- `json_script` template tag for XSS-safe JSON rendering

**Testing**
- 117 new tests: auth (7), services (30+), views (20+), coverage gaps (40+)
- 91%+ test coverage (pre-push hook enforced)
- N+1 query elimination via pre-fetched lookup dict pattern

### Phase 7: Clinical Intelligence Layer - COMPLETE (core) (2026-03-23)

The clinical data backbone — Clintela knows how to talk to patients (Phases 1-6) but Phase 7 gives it the ability to know what is happening to them medically. Three-layer architecture: time-series observations, computed patient snapshots, and rules-based alerts. Designed for the demo to a top-tier AMC cardiology practice and ACC leadership.

**Data Models (apps/clinical/)**
- `ClinicalObservation` — time-series vitals and labs with OMOP CDM concept IDs, source attribution (wearable, EHR, patient-reported, manual), quality flags, and flexible JSONField metadata. Indexed on (patient, concept_id, observed_at) for efficient time-range queries. CheckConstraint ensures value_numeric or value_text is non-empty.
- `PatientClinicalSnapshot` — OneToOne computed summary of patient's current clinical state. Includes trajectory (improving/stable/concerning/deteriorating), risk score (0-100 composite formula), vital_signs JSONField with latest values, data_completeness ratio, and active_alerts_count. Recomputed on every observation ingest and nightly via Celery.
- `ClinicalAlert` — rules-based alerts with severity (info/yellow/orange/red), alert type (threshold/trend/missing_data/combination), rule_rationale for FDA 2026 CDS transparency compliance, trigger_data preserving the observations that fired the rule. UniqueConstraint on (patient, rule_name) WHERE status='active' prevents duplicate alert spam. IntegrityError catch handles race conditions on concurrent ingestion.

**OMOP Concept ID Mapping**
- 12 cardiac-relevant concepts: heart rate (3027018), systolic BP (3004249), diastolic BP (3012888), body weight (3025315), SpO2 (3016502), temperature (3020891), respiratory rate (3024171), blood glucose (3004501), BNP (3022217), troponin (3019550), daily steps (40762499), sleep duration (40762503)
- Normal ranges defined per concept for chart range bands and rule thresholds
- OMOP concept IDs serve as the bridge to the team's Epic-to-OMOP pipeline (being built separately) — when that pipeline delivers data, it maps directly to ClinicalObservation with matching concept vocabulary

**Deterministic Rules Engine (rules.py)**
- Registry pattern with `@register_rule(name)` decorator and `RULE_REGISTRY: dict[str, RuleFunction]`
- 16 registered rules across four categories:
  - Threshold rules (7): hr_critical, hr_warning, bp_critical, spo2_critical, spo2_warning, temp_critical, temp_warning
  - Trend rules (5): weight_gain_3day, hr_trend_3day, bp_trend_3day, steps_declining_7day (with manual linear regression, no numpy dependency)
  - Missing data rules (2): missing_weight (48h), missing_hr (24h)
  - Combination rules (3): chf_decompensation (weight + HR + steps), infection_signal (temp + HR), epro_activity_correlation (PHQ-2 + steps)
- Each rule returns a RuleResult dataclass with rule_rationale string for FDA compliance — every alert can explain why it fired in plain language
- `check_all_rules(patient)` iterates the registry with per-rule exception isolation — one broken rule does not block others

**Clinical Data Service (services.py)**
- `ingest_observation()` — validates concept_id against known mappings, stores observation, triggers post-processing via `transaction.on_commit()` so the observation persists even if rules engine fails
- `_process_observation(patient)` — atomic block: runs all rules, creates/updates alerts with dedup, escalates RED/ORANGE alerts via existing Escalation model, updates patient triage color, recomputes clinical snapshot
- `update_triage_color(patient)` — maps worst active alert severity to existing Patient.status field (red/orange/yellow/green), wiring clinical intelligence into the existing triage system
- `compute_snapshot(patient)` — update_or_create with vital_signs dict, trajectory via 7-day slope calculation (worst-wins precedence), risk score formula (+20 RED, +10 ORANGE, +5 YELLOW, +15 deteriorating, +10 concerning, +10 low completeness, cap 100), data completeness ratio
- `process_patient_batch(patient)` — wrapped in transaction.atomic() for seed command bulk use

**Clinician UI — Vitals Tab**
- 6th tab on clinician patient detail panel, accessible via keyboard shortcut `6`
- Snapshot summary bar: trajectory badge (teal/gray/orange/coral), risk score, data completeness percentage, active alert count
- Active alerts list with severity-colored left border (4px solid), expandable via Alpine.js x-data/x-collapse to reveal rule_rationale
- Chart.js vital sign charts in 2-column grid: Heart Rate, Systolic BP, Diastolic BP, Body Weight, SpO2, Temperature. Each chart shows normal range bands (teal shading with dashed borders), responsive canvas in position:relative div with 160px fixed height. Chart styling: borderWidth 1.5, pointRadius 0 (hover only), tension 0.4, dark background Satoshi font tooltips.
- Lab results table with tabular-nums, abnormal values highlighted in orange, EHR/OMOP source badge
- IDOR protection: verifies clinician_profile exists and has hospital-level access to the patient
- Empty state for patients without clinical data: teal chart icon with warm messaging

**Patient UI — My Health Card**
- HTMX-loaded card on patient dashboard (feature-flagged)
- 4 sparkline charts in 2x2 grid (Heart Rate, Body Weight, Systolic BP, SpO2): 120x40px, teal line, no axes, vanilla JS canvas creation
- Trajectory messages in warm, non-clinical language: improving = "Your recovery is looking great! Your readings are trending in the right direction." Stable = "Your readings are holding steady — that is a good sign." Concerning/deteriorating use gentle language that informs without alarming.
- Connects to PatientPreferences.recovery_goals when available
- Chart.js CDN loaded in base_patient.html (feature-flagged)

**Integration Points**
- Agent context: `_inject_clinical_data()` in ContextService injects snapshot trajectory, risk_score, active_alerts_count, data_completeness, and vital_signs into the Care Coordinator's context so it can reference clinical data in conversations
- Admin dashboard: `ClinicalAlertService.get_alert_summary()` provides severity counts, average acknowledgment time, and top 5 triggering rules for the KPI dashboard
- Clinician handoff: `HandoffService.get_handoff_summary()` includes active clinical alerts in shift handoff context
- Patient list: trajectory Subquery annotation from PatientClinicalSnapshot adds trajectory arrows to patient list items
- Escalation: RED/ORANGE alerts auto-create Escalation records (type="clinical") which flow into the existing clinician notification and WebSocket system

**Feature Flag**
- `ENABLE_CLINICAL_DATA = env.bool("ENABLE_CLINICAL_DATA", default=False)` in settings
- Context processor `clinical_data_flags` makes the flag available in all templates
- All clinical UI gated in 6 template locations: base_clinician.html (Chart.js CDN + Vitals tab button), _patient_detail.html (Vitals tab), _patient_list_item.html (trajectory arrows), patients/dashboard.html (My Health card), base_patient.html (Chart.js CDN)
- Views use `@_require_clinical_enabled` decorator returning 404 when flag is off

**Demo Data Seeding**
- `seed_clinical_data` management command generates 30 days of realistic data for 5 patients across 4 scenarios: progressing well, CHF decompensation (weight gain + HR elevation starting day 12), post-op infection (temperature spike + HR around day 5), declining activity (step count drops suggesting depression or pain)
- Circadian HR variation via sine wave, natural post-surgical recovery curves
- Lab values (BNP, troponin) seeded as EHR-sourced observations
- Production guard: `settings.DEBUG` check prevents accidental seeding
- `skip_processing=True` for bulk insert performance (10K+ observations in seconds), then `process_patient_batch()` once per patient at end

**Celery Tasks**
- `compute_all_snapshots()` — nightly recomputation for all active patients using `.iterator()` for memory efficiency
- `check_missing_data()` — every 6 hours, runs missing_weight and missing_hr rules only

**Testing**
- 118 tests across 7 test files: test_models.py, test_rules.py (one test per rule), test_services.py (ingest, snapshot, triage, trend, alerts, risk score, batch), test_views.py (feature flag, empty states, chart data, auth, trajectory messages), test_commands.py (all 4 scenarios, production guard, invalid patient), test_tasks.py (snapshot recomputation, missing data checks), test_coverage_gaps.py (process_observation pipeline, dedup, escalation, IDOR, labs)
- 1534 total tests passing, 90.10% overall coverage (meets 90% threshold)
- QA: 2 bugs found and fixed (patient sparkline rendering, data double-serialization), health score 82 to 95

**Deferred to Phase 7.5 (proactive patient messaging)**
- Missing weight data auto-message to patient ("Hey [name], we haven't seen a weight reading in a couple days...")
- Declining activity auto-message ("We noticed you've been a bit less active lately...")
- Weight gain trend auto-message + auto-escalate ("Your weight has been creeping up a bit...")
- The rules engine fires the alerts and the escalation system notifies clinicians, but the system does not yet send proactive chat messages directly to patients. The plumbing exists (missing data rules, existing `process_patient_message()` in agents) — what is missing is wiring alert creation to patient-facing message dispatch.

### Phase 8: Polish and Testing
- [ ] Multilingual support (i18n)
- [ ] Visual recovery timeline
- [ ] Smart scheduling
- [ ] Recovery milestone celebrations
- [ ] Load testing
- [ ] Security audit

---

## Project Structure

```
clintela/
├── config/                    # Django settings
│   ├── settings/
│   │   ├── base.py           # Core settings + SMS/notification/voice config
│   │   ├── development.py    # Console backends, debug tools
│   │   ├── production.py
│   │   └── test.py           # LocMem backends, CELERY_ALWAYS_EAGER
│   ├── urls.py               # Root URLs including SMS webhooks
│   ├── celery.py             # Celery app configuration
│   ├── wsgi.py
│   └── asgi.py               # WebSocket routing
├── apps/
│   ├── accounts/              # Custom User model (phone_number indexed)
│   ├── patients/              # Patient, Hospital, voice views
│   ├── caregivers/            # Caregiver relationships
│   ├── clinicians/            # Provider profiles + dashboard views/services/auth
│   ├── clinical/              # Clinical intelligence layer (Phase 7)
│   │   ├── models.py         # ClinicalObservation, PatientClinicalSnapshot, ClinicalAlert
│   │   ├── rules.py          # 16-rule deterministic engine with registry pattern
│   │   ├── services.py       # ClinicalDataService (ingest, snapshot, triage, alerts)
│   │   ├── constants.py      # OMOP concept ID mappings, normal ranges
│   │   ├── views.py          # HTMX fragment views (Vitals tab, My Health card)
│   │   ├── tasks.py          # Celery: nightly snapshot, 6-hourly missing data
│   │   ├── context_processors.py  # ENABLE_CLINICAL_DATA template flag
│   │   └── management/commands/
│   │       ├── seed_clinical_data.py          # Demo data (4 cardiac scenarios)
│   │       └── compute_clinical_snapshots.py  # Manual snapshot recompute
│   ├── agents/                # AI multi-agent system
│   │   ├── agents.py         # Agent implementations
│   │   ├── workflow.py       # LangGraph workflow
│   │   ├── llm_client.py     # Ollama Cloud client
│   │   ├── prompts.py        # Agent prompts
│   │   ├── services.py       # ConversationService, process_patient_message()
│   │   ├── routing.py        # WebSocket routing (chat + notifications)
│   │   ├── tasks.py          # Celery tasks (check-ins, summaries)
│   │   └── tests/            # Agent tests
│   ├── knowledge/             # Clinical knowledge RAG (Phase 4)
│   │   ├── models.py         # KnowledgeSource, KnowledgeDocument (pgvector), KnowledgeGap
│   │   ├── embeddings.py     # OllamaEmbeddingClient + MockEmbeddingClient
│   │   ├── retrieval.py      # KnowledgeRetrievalService (hybrid vector + FTS)
│   │   ├── ingestion.py      # KnowledgeIngestionService (chunk, embed, deduplicate)
│   │   ├── parsers.py        # PDF, Markdown, HTML, plain-text parsers
│   │   ├── sanitizer.py      # Content sanitizer (prompt injection defense)
│   │   ├── admin.py          # KnowledgeSourceAdmin + health dashboard
│   │   └── management/commands/
│   │       ├── ingest_document.py        # Ingest any local file
│   │       └── ingest_acc_guidelines.py  # Scrape + ingest ACC guidelines
│   ├── messages_app/          # SMS, chat, voice
│   │   ├── backends.py       # SMS backends (Twilio/Console/LocMem)
│   │   ├── services.py       # SMSService (send, inbound, opt-out)
│   │   ├── transcription.py  # Three-tier transcription (Mock/Whisper/Remote)
│   │   ├── views.py          # Twilio webhook endpoints
│   │   ├── urls.py           # SMS webhook routes
│   │   ├── tasks.py          # Voice cleanup periodic task
│   │   └── tests/            # SMS, transcription, webhook tests
│   ├── notifications/         # Multi-channel notification engine
│   │   ├── backends.py       # Notification backends (InApp/Console/SMS/Email/LocMem)
│   │   ├── services.py       # NotificationService (create, deliver, preferences)
│   │   ├── consumers.py      # WebSocket notification consumers
│   │   ├── tasks.py          # Async delivery + scheduled reminders
│   │   └── tests/            # Notification tests
│   ├── pathways/              # Clinical pathways
│   ├── analytics/             # DailyMetrics pipeline + nightly Celery task
│   └── administrators/        # Admin KPI dashboard + pathway administration
│       ├── auth.py            # @admin_required decorator
│       ├── services.py        # 7 service classes (Census, Readmission, Outcomes, Engagement, Escalation, Pathway, Alerts)
│       ├── views.py           # Dashboard, 11 HTMX KPI fragments, CSV export, pathway CRUD
│       ├── urls.py            # 24 URL patterns
│       └── management/commands/create_test_admin.py
├── templates/
│   ├── base_patient.html      # Patient layout with notification bell
│   ├── base_clinician.html    # Clinician three-panel layout shell
│   ├── base_admin.html        # Admin layout shell (max-w-1200px, Chart.js, print CSS)
│   ├── clinical/              # Clinical intelligence HTMX fragments
│   │   ├── vitals_tab.html   # Clinician Vitals tab (charts, alerts, labs)
│   │   └── health_card.html  # Patient My Health card (sparklines, trajectory)
│   ├── administrators/        # Admin KPI dashboard + pathway admin templates
│   │   ├── dashboard.html     # KPI scorecard with HTMX lazy-loaded cards
│   │   ├── login.html         # Admin login page
│   │   ├── pathways.html      # Pathway list with breadcrumbs
│   │   ├── pathway_detail.html # Pathway detail with milestones + edit forms
│   │   └── components/        # 11 HTMX card fragments + alerts bar + pathway list table
│   ├── clinicians/            # Clinician dashboard templates
│   │   ├── login.html         # Clinician login page
│   │   ├── dashboard.html     # Dashboard (extends base_clinician)
│   │   ├── schedule.html      # Weekly calendar + availability
│   │   └── components/        # ~20 HTMX fragment components
│   └── components/
│       ├── _chat_input.html   # Chat + voice recorder
│       ├── _message_bubble.html # Channel icons + delivery status
│       ├── _header.html       # Notification bell + sound toggle
│       └── _dev_toolbar.html  # SMS simulator, patient switcher
├── static/
│   └── js/
│       ├── admin-dashboard.js      # Alpine adminDashboard() with Chart.js, filters, dark mode
│       ├── clinician-dashboard.js  # Alpine clinicianDashboard() component
│       ├── clinician-research-chat.js # Research tab LLM chat
│       ├── notifications.js   # WebSocket notification client
│       └── voice-recorder.js  # MediaRecorder voice input
├── docs/
│   ├── ACCEPTANCE-TESTING-PHASE3.md  # Manual QA guide
│   ├── AGENT_SYSTEM_ACCEPTANCE.md
│   └── engineering-review.md
├── pyproject.toml
├── docker-compose.yml
├── Dockerfile
├── Makefile
├── .pre-commit-config.yaml
└── .github/workflows/
    └── ci.yml
```

---

## Environment Variables

```env
# Core
DEBUG=True
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=localhost,127.0.0.1

# Database (PostgreSQL on port 5434)
DATABASE_URL=postgres://clintela:clintela@localhost:5434/clintela
POSTGRES_USER=clintela
POSTGRES_PASSWORD=clintela
POSTGRES_DB=clintela

# Redis (port 6380) — used by Celery + Django Channels
REDIS_URL=redis://localhost:6380/0

# LLM (Ollama Cloud)
OLLAMA_API_KEY=your-key
OLLAMA_BASE_URL=https://ollama.com/api
OLLAMA_MODEL=kimi-k2.5:cloud  # or llama3.2, etc.

# External Services (optional for dev — console backends used by default)
TWILIO_ACCOUNT_SID=your-sid
TWILIO_AUTH_TOKEN=your-token
TWILIO_PHONE_NUMBER=+1234567890
ENABLE_SMS=False  # Gate for production SMS sending

# SMS/Voice/Notifications (dev defaults — no external services needed)
SMS_BACKEND=apps.messages_app.backends.ConsoleSMSBackend
TRANSCRIPTION_BACKEND=apps.messages_app.transcription.MockTranscriptionClient
SMS_RATE_LIMIT_PER_HOUR=10
VOICE_MEMO_RETENTION_HOURS=24

# RAG / Knowledge (Phase 4)
ENABLE_RAG=False                              # Set True to activate RAG in agent responses
EMBEDDING_MODEL=nomic-embed-text              # Ollama embedding model name
EMBEDDING_DIMENSIONS=768                      # Must match model output
EMBEDDING_BASE_URL=http://localhost:11434     # Ollama base URL (embeddings)
RAG_TOP_K=5                                   # Documents returned per query
RAG_SIMILARITY_THRESHOLD=0.7                  # Minimum cosine similarity to include
RAG_VECTOR_WEIGHT=0.7                         # Weight for vector similarity score
RAG_TEXT_WEIGHT=0.3                           # Weight for full-text search score

# Clinical Intelligence Layer (Phase 7)
ENABLE_CLINICAL_DATA=False                    # Set True to activate clinical data UI and rules engine
```

---

## Key Files Added/Modified

### Phase 2: Agent System
- `apps/agents/agents.py` - Agent implementations (Supervisor, Care Coordinator, Nurse Triage, etc.)
- `apps/agents/workflow.py` - LangGraph StateGraph workflow
- `apps/agents/llm_client.py` - Ollama Cloud LLM client with retry logic
- `apps/agents/prompts.py` - Agent prompt templates with safety guardrails
- `apps/agents/services.py` - ConversationService, EscalationService, `process_patient_message()`
- `apps/agents/models.py` - AgentConversation, AgentMessage, Escalation models

### Phase 4: Clinical Knowledge RAG
- `apps/knowledge/models.py` - KnowledgeSource, KnowledgeDocument (pgvector + FTS), KnowledgeGap
- `apps/knowledge/embeddings.py` - OllamaEmbeddingClient with MockEmbeddingClient for tests
- `apps/knowledge/retrieval.py` - KnowledgeRetrievalService (hybrid search: vector + BM25-style FTS)
- `apps/knowledge/ingestion.py` - KnowledgeIngestionService (chunk, embed, SHA-256 deduplicate)
- `apps/knowledge/parsers.py` - PDF (pdfplumber), Markdown, HTML, plain-text parsers
- `apps/knowledge/sanitizer.py` - Content sanitizer (strips prompt injection patterns)
- `apps/knowledge/admin.py` - Knowledge health dashboard (freshness, gaps, top-cited)
- `apps/agents/specialists.py` - 6 RAG-backed specialists via RAGSpecialistAgent base class
- `apps/agents/workflow.py` - RAG integration with citation tracking and MessageCitation M2M
- `apps/patients/models.py` - Patient lifecycle state machine + ConsentRecord (append-only)
- `apps/caregivers/models.py` - CaregiverInvitation (token-based, atomic claim)
- `templates/patients/caregivers.html` - Caregiver invitation management page
- `templates/patients/consent.html` - Consent management page

### Phase 5: Clinician Dashboard UI
- `apps/clinicians/auth.py` - `@clinician_required` decorator with IDOR prevention
- `apps/clinicians/urls.py` - All clinician URL routes (dashboard, schedule, HTMX fragments)
- `apps/clinicians/views.py` - 25+ views (dashboard, detail tabs, chat, scheduling, take-control)
- `apps/clinicians/services.py` - SchedulingService, ClinicianResearchService, TakeControlService
- `apps/clinicians/admin.py` - ClinicianNote, Appointment, ClinicianAvailability admin
- `apps/clinicians/models.py` - ClinicianNote, ClinicianAvailability, Appointment models
- `apps/clinicians/management/commands/create_test_clinician.py` - Test data with 5 patients
- `apps/agents/models.py` - Added clinician FK, paused_by/paused_at, clinician_research agent type
- `apps/agents/consumers.py` - Auth hardening on ClinicianDashboardConsumer
- `apps/agents/api.py` - Session-based auth replacing hacky clinician_id-from-body
- `templates/base_clinician.html` - Three-panel layout shell with Alpine.js
- `templates/clinicians/` - Dashboard, login, schedule pages + ~20 component templates
- `static/js/clinician-dashboard.js` - Alpine clinicianDashboard() with keyboard shortcuts
- `static/js/clinician-research-chat.js` - Research tab LLM chat interface

### Phase 6: Administrator KPI Dashboard
- `apps/administrators/auth.py` - `@admin_required` decorator with role check + hospital scoping
- `apps/administrators/services.py` - 7 service classes: Census, Readmission, Outcomes, Engagement, Escalation, Pathway, OperationalAlert
- `apps/administrators/views.py` - Dashboard, 11 HTMX KPI fragment views, CSV export, pathway CRUD (list, detail, toggle, edit)
- `apps/administrators/urls.py` - 24 URL patterns under `administrators` namespace
- `apps/administrators/management/commands/create_test_admin.py` - Test admin user creation
- `apps/analytics/models.py` - Extended DailyMetrics with hospital FK + 13 metric fields
- `apps/analytics/services.py` - `DailyMetricsService.compute_for_date()` with per-hospital aggregation
- `apps/analytics/tasks.py` - `compute_daily_metrics` Celery periodic task (nightly)
- `apps/analytics/management/commands/compute_daily_metrics.py` - Manual/backfill with `--date` and `--backfill N`
- `templates/base_admin.html` - Admin layout shell with Chart.js CDN, print CSS, dark mode, KPI card styles
- `templates/administrators/dashboard.html` - KPI scorecard with HTMX lazy-loaded cards in 3-column grid
- `templates/administrators/components/` - 11 HTMX card fragment templates + alerts bar + pathway list table
- `static/js/admin-dashboard.js` - Alpine.js component for filters, Chart.js config, dark mode

### Phase 7: Clinical Intelligence Layer
- `apps/clinical/models.py` - ClinicalObservation, PatientClinicalSnapshot, ClinicalAlert with OMOP concept IDs
- `apps/clinical/rules.py` - 16-rule deterministic engine with registry pattern and FDA-compliant rationale
- `apps/clinical/services.py` - ClinicalDataService (ingest, snapshot, triage, trend, alerts, batch processing)
- `apps/clinical/constants.py` - OMOP concept ID mappings, normal ranges, severity/trajectory choices
- `apps/clinical/views.py` - HTMX fragment views for Vitals tab and My Health card with IDOR protection
- `apps/clinical/tasks.py` - Celery tasks for nightly snapshot recomputation and missing data checks
- `apps/clinical/context_processors.py` - Template context processor for ENABLE_CLINICAL_DATA flag
- `apps/clinical/management/commands/seed_clinical_data.py` - Demo data seeder with 4 cardiac scenarios
- `apps/clinical/management/commands/compute_clinical_snapshots.py` - Manual snapshot recomputation
- `apps/agents/services.py` - Added `_inject_clinical_data()` for agent context assembly
- `apps/clinicians/services.py` - Added trajectory Subquery annotation and clinical alert handoff context
- `apps/clinicians/views.py` - Added trajectory to patient list data
- `apps/administrators/services.py` - Added ClinicalAlertService for admin KPI dashboard
- `templates/clinical/vitals_tab.html` - Clinician Vitals tab with charts, alerts, labs
- `templates/clinical/health_card.html` - Patient My Health card with sparklines
- `templates/base_clinician.html` - Added Chart.js CDN and Vitals tab button (feature-flagged)
- `templates/base_patient.html` - Added Chart.js CDN (feature-flagged)
- `templates/clinicians/components/_patient_detail.html` - Added Vitals tab button
- `templates/clinicians/components/_patient_list_item.html` - Added trajectory arrows
- `templates/patients/dashboard.html` - Added My Health card div (feature-flagged)
- `static/js/clinician-dashboard.js` - Added Vitals tab URL and keyboard shortcut `6`
- `config/settings/base.py` - Added ENABLE_CLINICAL_DATA flag and apps.clinical to INSTALLED_APPS

### Phase 3: Communication & Multi-modality
- `config/celery.py` - Celery app configuration with Redis broker
- `apps/messages_app/backends.py` - SMS backend abstraction (Twilio/Console/LocMem)
- `apps/messages_app/services.py` - SMSService (send, inbound, opt-out, rate limiting)
- `apps/messages_app/transcription.py` - Three-tier transcription (Mock/Whisper/Remote)
- `apps/messages_app/views.py` - Twilio webhook endpoints (inbound + status)
- `apps/messages_app/tasks.py` - Voice memo cleanup periodic task
- `apps/notifications/backends.py` - Notification backends (InApp/Console/SMS/Email/LocMem)
- `apps/notifications/services.py` - NotificationService (create, deliver, preferences, quiet hours)
- `apps/notifications/consumers.py` - WebSocket notification consumers (patient + clinician)
- `apps/notifications/tasks.py` - Async delivery + scheduled reminder tasks
- `apps/notifications/models.py` - NotificationDelivery, NotificationPreference models
- `static/js/notifications.js` - WebSocket notification client with auto-reconnect
- `static/js/voice-recorder.js` - MediaRecorder voice input with timer/cancel/auto-stop

---

## Testing Summary

### Full Test Suite
```bash
POSTGRES_PORT=5434 pytest
# 1534 tests, ≥90% coverage
```

### Test Coverage by App
- `apps/clinical/` - Models, rules (1 per rule), services, views, commands, tasks, coverage gaps — 118 tests
- `apps/administrators/` - Auth decorator, 7 service classes, views (20+ endpoints), management command — 117 tests
- `apps/analytics/` - DailyMetrics pipeline, services, Celery task, backfill management command
- `apps/clinicians/` - Models, auth decorator, views (25+ endpoints), services, management command, coverage tests
- `apps/knowledge/` - Embeddings, parsers, ingestion, retrieval, sanitizer, admin, management commands
- `apps/agents/` - Agent routing, LLM client, services, tasks, workflow, RAG integration, specialists, WebSocket consumers
- `apps/caregivers/` - Invitation flow, atomic acceptance, token verification
- `apps/patients/` - Lifecycle transitions, consent management, views
- `apps/messages_app/` - SMS backends, services, transcription, webhooks, cleanup
- `apps/notifications/` - Backends, services, consumers, tasks, integration
- `tests/e2e/` - Playwright E2E tests (27 tests, run separately with `-p no:xdist`)

### Live LLM Acceptance Testing
✅ **Agent Routing** - 4/4 scenarios passed
✅ **Critical Keywords** - 9/9 scenarios passed
✅ **Safety Guardrails** - 2/2 scenarios passed
✅ **Conversation Services** - All passed

See `docs/AGENT_SYSTEM_ACCEPTANCE.md` for agent testing and `docs/ACCEPTANCE-TESTING-PHASE3.md` for Phase 3 manual QA.

---

## Resolved Questions (from Prior Sessions)

1. **Authentication:** Leaflet code + DOB two-factor auth implemented. UUID-based leaflet codes with DOB verification flow and session management.
2. **Communication Layer:** Twilio SMS with console backend for dev, WebSocket notifications via Django Channels, Celery + Redis for async delivery and scheduled reminders.
3. **Notification Architecture:** Multi-channel (in-app, SMS, email) with pluggable backends, NotificationDelivery tracking, patient preferences with quiet hours.

## Open Questions for Next Session

1. **Phase 7.5 — Proactive Patient Messaging (deferred from Phase 7):**
   - Wire alert creation to patient-facing chat messages via existing `process_patient_message()`
   - Missing weight data → warm outreach message
   - Declining activity → gentle check-in message
   - Weight gain trend → informative message + auto-escalate
   - The rules engine and alert system are complete — this is a wiring task, not new architecture

2. **Phase 8 Polish:**
   - Multilingual support (i18n) for patient-facing content
   - Visual recovery timeline component
   - Smart scheduling (pathway-suggested appointments)
   - Recovery milestone celebrations

3. **Admin Dashboard Enhancements:**
   - Anomaly detection / automated weekly digest emails (see TODO-017)
   - Multi-site anonymized benchmarking (see TODO-018)
   - Extend `create_cardiology_service` with LLM-produced seed data for admin dashboard demo
   - Design review on live admin dashboard

4. **Infrastructure:**
   - Server-side pagination for patient list (see TODO-015)
   - Migrate async wrappers to Django 5.1 native async ORM (see TODO-016)
   - Load testing and performance benchmarks (see TODO-010)
   - Production LLM migration (see TODO-008)

5. **Deferred improvements:**
   - Embedding cache (Redis, TTL-based) — see TODO-012
   - OCR for scanned PDFs — see TODO-011
   - Caregiver read-only dashboard — see TODO-013

---

## What to Do in Next Session

1. **Seed clinical data:** `ENABLE_CLINICAL_DATA=True python manage.py seed_clinical_data` — creates 5 patients with 4 cardiac scenarios
2. **Test clinician Vitals tab:** Log in as clinician → select Gordon Bryant → Vitals tab (or press `6`) → verify charts, alerts, labs
3. **Test patient My Health card:** Log in as patient with clinical data → scroll to My Health card → verify sparklines and trajectory
4. **Practice demo narrative:** "Patient discharged 12 days ago. Day 10, weight started trending up. Day 12, Clintela detected the pattern and escalated to the care team. In the old world, this wouldn't be caught until the 4-week follow-up."
5. **Verify feature flag:** `ENABLE_CLINICAL_DATA=False` hides all clinical UI cleanly
6. **Consider implementing proactive patient messaging** (Phase 7.5) — wire alert creation to patient-facing chat messages for missing data, declining activity, and weight gain trends
7. **Run tests:** `POSTGRES_PORT=5434 pytest` for full suite (1534 tests, 90%+ coverage)
8. **Focus on:** Phase 8 — Polish, i18n, visual recovery timeline, load testing, security audit

---

## Resources Ready to Reference

- **Design decisions:** DESIGN.md
- **Architecture:** docs/engineering-review.md
- **Agent system:** docs/AGENT_SYSTEM_ACCEPTANCE.md
- **Phase 3 QA guide:** docs/ACCEPTANCE-TESTING-PHASE3.md
- **Security requirements:** docs/security.md
- **Dev workflow:** docs/development.md
- **Deferred work:** TODOS.md

---

## Recent Commits

- **Foundation setup** (2026-03-18) - UV, Docker, Django project structure
- **Phase 1 models** - All 9 apps with migrations
- **Dev environment** - Makefile, pre-commit, CI workflow
- **Agent system** (2026-03-19) - Multi-agent AI with LangGraph, live LLM testing
- **Patient UI** (2026-03-19) - HTMX chat, dashboard, dark mode, E2E tests
- **Phase 3 communication** (2026-03-19) - SMS, voice, notifications, Celery, dev toolbar
- **Phase 4 RAG** (2026-03-20) - pgvector, knowledge models, ingestion pipeline, specialists, lifecycle, caregiver flow, consent, admin dashboard
- **Phase 5 clinician dashboard** (2026-03-20) - Models, auth, views, services, templates, JS, scheduling, take-control, tests, QA fixes
- **Phase 6 admin dashboard** (2026-03-21) - KPI scorecard, 7 service classes, DailyMetrics pipeline, pathway admin, 117 tests
- **Phase 7 clinical intelligence** (2026-03-23) - Three-layer clinical architecture, 16-rule deterministic engine, OMOP bridge, clinician Vitals tab, patient My Health card, 118 tests, QA health score 95

---

*Phase 7 Complete (v0.2.11.0) — Clinical Intelligence Layer: three-layer architecture (observations, snapshots, alerts), 16-rule deterministic engine with FDA-compliant rationale, OMOP concept ID bridge, clinician Vitals tab with Chart.js charts, patient My Health card with sparklines, 4 demo scenarios, feature-flagged. 1534 tests at 90%+ coverage. Proactive patient messaging deferred to Phase 7.5. Ready for Phase 8: Polish and Testing.*
