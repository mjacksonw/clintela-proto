# Clintela

**AI-powered post-surgical patient recovery support**

Clintela helps patients experience their best possible recovery after hospital discharge. By combining expert AI agents, clinical knowledge, and seamless patient interaction, we provide 24/7 care coordination that helps prevent readmissions and keeps recovery on track.

---

## The Problem

Hospital 30-day readmission rates are a critical quality metric. Many readmissions are preventable—patients miss warning signs, have questions that go unanswered, or struggle to follow discharge instructions. Traditional care models can't provide continuous monitoring and support.

## Our Approach

Clintela deploys a multi-agent system that augments clinical teams with intelligent, always-available support:

- **Care Coordinator Agent**: The primary patient-facing interface, accessible via text, voice, web chat, email, and app. Translates clinical guidance into patient-friendly language, asks follow-up questions, and delivers reminders, surveys, and instructions.

- **Care Supervisor/Orchestrator**: The central brain that routes requests, evaluates symptoms, determines escalation needs, and coordinates specialist involvement.

- **Nurse Triage Agent**: Interprets recovery progress against clinical pathways, classifies symptoms, answers post-op questions, and recommends appropriate interventions.

- **Documentation Agent**: Creates structured summaries for clinicians, handoff notes, and chart-ready drafts.

- **Specialist Agents**: RAG-backed domain experts in Cardiology, Pharmacy, Nutrition, PT/Rehab, Social Work, and Palliative Care — each retrieves evidence from the clinical knowledge base before responding, falling back to human escalation only when confidence is low.

## Three Interfaces

### 1. Patient Interface

Multi-modal access to care coordination:
- Conversational AI that meets patients where they are
- Proactive check-ins and symptom monitoring
- Medication reminders and care plan guidance
- Seamless escalation to human clinicians when needed

### 2. Clinician Interface

Three-panel dashboard for nurses and physicians:
- **Patient list**: Severity-sorted with triage color dots, unread badges, and search/sort
- **Patient detail**: Four tabs — Details (timeline, escalations, notes), Care Plan (pathway milestones), Research (LLM chat with specialist routing), Tools (lifecycle transitions, consent, caregivers)
- **Patient chat**: Read conversation history, inject clinician messages, take control of the AI thread
- **Take-control mode**: Clinician takes over patient chat — AI pauses, patient sees messages from named clinician, race-safe locking with automatic timeout release
- **Scheduling**: Weekly calendar with availability management and appointment CRUD
- **Shift handoff**: Summary of changes since last login — new escalations, status changes, missed check-ins
- **Keyboard shortcuts**: j/k navigate, 1-4 switch tabs, e acknowledge escalation, / search, ? help
- **Real-time**: WebSocket escalation alerts, desktop notifications for critical events
- **Dark mode**: Full support across all clinician views

### 3. Administrator Interface

KPI scorecard for clinical leadership — live metrics replacing manual EHR-to-Excel workflows:
- **Hero metric**: CMS cohort-based readmission rate with period tabs (7/30/60/90/120 days) and sparkline trend
- **Outcome cards**: Discharge to community rate, follow-up completion (on-time milestone tracking), functional improvement (pending ePRO)
- **Engagement cards**: Program engagement (multi-horizon 7/14/30/90d), message volume, check-in completion rate
- **Operations cards**: Escalation response time with SLA compliance, census with triage color distribution, pathway performance
- **Operational alerts bar**: SLA breaches, stale escalations, inactive patients
- **Pathway administration**: Effectiveness stats, per-milestone check-in rates, inline edit, active/inactive toggle
- **Global filters**: Hospital filter and time range (30/60/90/120 days) scoping all cards
- **CSV export**: Formula injection protection for board presentations
- **Print-friendly**: CSS stylesheet for browser "Save as PDF"
- **Dark mode**: Full support across all admin views

---

## Technical Architecture

### Core Stack

- **Web Framework**: Django (request-based, idiomatic Python)
- **Database**: PostgreSQL + pgvector (relational data, vector embeddings for RAG, key-value caching)
- **AI/ML**: LangChain / LangGraph for multi-agent orchestration
- **Real-time**: WebSockets (Django Channels) for chat and live notifications
- **Task Queue**: Celery + Redis for async notification delivery and scheduled reminders
- **Communications**: Twilio SMS with signature validation, MediaRecorder voice input with Whisper transcription

### Agent Architecture

We use a `supervisor + subagents-as-tools` pattern:
- **Auditability**: Clear decision chains with human-readable reasoning
- **Safety**: Permission enforcement at the workflow level
- **Control**: Human approval gates for critical actions
- **Defensibility**: Bounded agent capabilities with explicit action authorization

Non-LLM workflows handle: permissions, thresholds, escalation rules, retries, time windows, task tracking, audit logging, and human signoff.

### Data & Events

- **Inbound Events**: Webhook endpoints and polling mechanisms for external data (wearables, EHR changes)
- **Event Injection**: Administrative interface for demonstration and testing
- **Future**: Event bus integration for production data pipelines

---

## Engineering Principles

### Security & Privacy

- HITRUST, ISO 27001, and SOC 2 Type 2 aligned
- OWASP security practices
- Defense against unintentional data exfiltration
- Privacy-by-design architecture

### Quality

- **Test Coverage**: >90% code coverage required
- **CI/CD**: 100% test pass rate required for deployment
- **External Services**: LLMs, telephony, and third-party services are mocked in tests
- **Documentation**: Four audiences—users, clinicians, administrators, and teammates

### Design

- Clear, beautiful, engaging, and performant UI
- Deliberate attention to microcopy, typography, and information design
- Accessibility as table stakes
- Multi-modal patient interaction design

---

## Project Status

This repository contains the prototype implementation of Clintela's user interfaces and core systems.

**Current Phase**: Phase 6 complete — administrator KPI dashboard with 9 metric cards, operational alerts, pathway administration, DailyMetrics pipeline, CSV export, and 91%+ test coverage (1222 tests)

---

## Documentation

- [Design System](./DESIGN.md) — **Start here** — Visual design, typography, colors, components
- [Product Vision](./docs/vision.md)
- [Clintela Foundation Design](./docs/designs/clintela-foundation.md) — Scope expansion plan from CEO review
- [Engineering Review](./docs/engineering-review.md) — Architecture, diagrams, and implementation guide
- [Architecture Overview](./docs/architecture.md)
- [Agent System Design](./docs/agents.md)
- [API Documentation](./docs/api.md)
- [Development Setup](./docs/development.md)
- [Security & Compliance](./docs/security.md)
- [Testing Guide](./docs/testing.md)
- [Phase 3 Acceptance Testing](./docs/ACCEPTANCE-TESTING-PHASE3.md) — Manual QA guide for SMS, voice, notifications, and WebSocket features
- [Phase 4 Plan](./docs/plans/2026-03-20-phase4-clinical-knowledge-rag.md) — Clinical knowledge RAG design and implementation notes
- [Phase 5 Plan](./docs/plans/2026-03-20-phase5-clinician-dashboard.md) — Clinician dashboard design and implementation notes
- [Implementation Handoff](./IMPLEMENTATION_HANDOFF.md) — Session handoff with architecture, environment, and testing details
- [TODOs](./TODOS.md) — Deferred work and future phases

---

## License

[License TBD]

---

*Clintela is a prototype project focused on improving post-surgical patient outcomes through intelligent care coordination.*
