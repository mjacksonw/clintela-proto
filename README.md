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

Dashboard for nurses and physicians:
- **Triage view**: Patients color-coded by severity (red/orange/yellow/green)
- Patient summaries with recent developments
- Detailed interaction history and status tracking
- Configurable notifications (event-driven, escalations, scheduled summaries)
- Support for email, SMS, and phone alerts with escalation chains

### 3. Administrator Interface

Metrics and oversight for clinical leadership:
- 30-day readmission rates with trend analysis
- Patient population overview and engagement metrics
- Unscheduled escalation tracking
- Complication analytics
- Operational dashboards for quality improvement

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

**Current Phase**: Phase 4 complete — clinical knowledge RAG, pgvector hybrid search, 6 RAG-backed specialist agents, patient lifecycle state machine, caregiver invitation flow, consent management, and knowledge health admin dashboard

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
- [TODOs](./TODOS.md) — Deferred work and future phases

---

## License

[License TBD]

---

*Clintela is a prototype project focused on improving post-surgical patient outcomes through intelligent care coordination.*
