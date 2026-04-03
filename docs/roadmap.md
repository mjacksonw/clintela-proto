# Clintela Product Roadmap

**AI-powered post-surgical patient recovery support**

*Last updated: 2026-04-01 | Version: 1.0*

> Audience guide: Sections marked `[All]` are for everyone. `[Partners + Team]` adds integration detail for clinical partners. `[Team]` adds internal tactical context. Read to your depth.

---

## 1. Executive Summary `[All]`

Clintela is an AI-powered post-surgical care coordination platform that helps patients recover after hospital discharge. We deploy a multi-agent system, not a chatbot, that provides 24/7 monitoring, clinical intelligence, and emotional support across three interfaces: patients, clinicians, and administrators.

**In ~10 calendar days of agentic development**, we built:
- 8 production phases shipped (v0.2.12.1)
- 3 complete interfaces (patient, clinician, administrator)
- 8 AI agent types with RAG-backed specialist knowledge
- 16 deterministic clinical rules with FDA-compliant rationale
- 6 validated clinical survey instruments (PHQ-2, KCCQ-12, SAQ-7, AFEQT, PROMIS, daily symptom check)
- 12 OMOP concept IDs mapped for cardiac vitals and labs
- 1,534 tests at 90%+ coverage across 15 Django apps
- Multi-channel access: web chat, SMS (Twilio), voice (Whisper)
- Internationalization: English + Spanish with real-time chat translation

**The next 20 weeks** focus on three horizons: production-ready HIPAA deployment readiness for our AMC partner (weeks 1-4), real clinical data integration from wearables and EHR (weeks 5-10), and scale through predictive intelligence and multi-site deployment (weeks 11-20).

---

## 2. Vision & Market `[All]`

### The Problem

Hospital 30-day readmission rates cost the U.S. healthcare system [over $26 billion annually](https://www.cms.gov/medicare/payment/prospective-payment-systems/acute-inpatient-pps/hospital-readmissions-reduction-program-hrrp). CMS penalizes hospitals with above-average readmission rates, creating ~$500M/year in penalties industry-wide. Yet [a median 27% of readmissions are preventable](https://pubmed.ncbi.nlm.nih.gov/21444623/). The gap: after discharge, patients enter a monitoring black box. They miss warning signs, have questions that go unanswered at 2am, struggle to follow discharge instructions, and face recovery alone.

Clinician capacity can't fill this gap. A nurse managing 30 post-discharge patients can't provide continuous monitoring and emotional support to each one. The result: patients feel processed, not known.

### Our Approach

Clintela deploys a **multi-agent AI system** that augments clinical teams with intelligent, always-available care coordination:

- **Care Coordinator** as the patient's primary conversational interface, translating clinical guidance into warm, plain language
- **Nurse Triage** for symptom assessment with severity classification and deterministic escalation rules
- **6 RAG-backed specialist agents** (Cardiology, Pharmacy, Nutrition, PT/Rehab, Social Work, Palliative) that retrieve clinical evidence before responding
- **Clinical Intelligence Layer** with 16 deterministic rules monitoring vitals, detecting trends, and generating alerts with plain-language rationale
- **Three interfaces** purpose-built for patients (conversational), clinicians (real-time dashboard), and administrators (KPI analytics)

Our care philosophy: **"Help the patient be known."** Every interaction should make the patient feel known, not processed. The system captures their preferences, values, goals, daily life, and concerns. It remembers them. A patient talking to Clintela should feel like talking to someone who knows them, not like filling out another form.

### Competitive Landscape

| Player | Approach | Strength | Gap |
|--------|----------|----------|-----|
| **CoPilotIQ / Biofourmis** | Wearable-first RPM | FDA breakthrough-designated biosensor algorithms, in-home care | Single-channel, no AI conversational support, no peer support |
| **Hippocratic AI (Polaris)** | Multi-agent clinical AI | Closest model for clinical agent orchestration | No patient-facing emotional support, no peer group |
| **UHC Avery** | Payer-side AI companion | 6.5M+ members, benefits navigation | Payer tool, not clinical. No care coordination |
| **Wysa / Woebot / Ash** | Mental health chatbots | Evidence-based therapeutic techniques | 1:1 chatbot model, not multi-persona. Mental health only, not post-surgical |
| **Microsoft Copilot Health** | Consumer health companion | Platform scale | General wellness, not clinical recovery |
| **Clintela** | **Multi-agent mediation + AI peer support + clinician dashboard** | **Only platform combining clinical AI, emotional peer support, and real-time clinician integration** | Pre-production, single-specialty (cardiac) |

**Our unique position:** Nobody else combines multi-agent clinical AI with specialist mediation, an AI peer support group, and a real-time clinician dashboard. The mental health chatbot wave (Wysa, Woebot, Ash) proves the 1:1 AI companion model works, but they're all single-agent. We're building a *team*.

### Four Headline Capabilities

Clintela isn't one feature — it's four capabilities that no other platform combines:

1. **Agent-augmented care team with diverse expertise.** Not a single chatbot, but a team of specialist agents that retrieve clinical evidence before responding and can be extended per institution. The patient experiences a care team, not a search engine. *(Details below.)*

2. **24/7 monitoring via ePROs and wearable data.** Six validated clinical instruments combined with wearable vitals flowing through a 16-rule deterministic engine. No monitoring gaps between clinic visits. *(Details below.)*

3. **Virtual support group.** 7 AI personas modeled as recovery alumni, providing emotional peer support grounded in [Yalom's therapeutic factors](https://en.wikipedia.org/wiki/Group_psychotherapy#Therapeutic_factors). Zero direct competitors in healthcare. *(Details below.)*

4. **Clinician and administrator visibility.** Real-time dashboards that surface what's happening — clinicians and administrators don't have to go looking for it. *(Details below.)*

### Agent-Augmented Care Team Deep-Dive

Post-discharge patients don't need a chatbot. They need a care team — one that remembers their surgery, understands their medications, and can answer questions at 2am that span cardiology, nutrition, and emotional well-being. Clintela provides this through a multi-agent system where each specialist retrieves clinical evidence before responding.

**How it works:** A [LangGraph](https://langchain-ai.github.io/langgraph/)-based supervisor routes patient messages to the right specialist. Each specialist queries a RAG knowledge base (ACC guidelines, clinical research, hospital protocols) via [pgvector](https://github.com/pgvector/pgvector) hybrid search before generating a response. Confidence scoring determines whether the response goes to the patient or escalates to a human clinician.

| Agent | Domain | What It Does |
|-------|--------|-------------|
| Care Coordinator | Holistic care | Primary patient interface — translates clinical guidance into warm, plain language |
| Nurse Triage | Clinical assessment | Symptom evaluation, severity classification, deterministic escalation |
| Cardiology | Cardiac risk | Post-surgical cardiac recovery, medication effects, activity guidance |
| Pharmacy | Medications | Reconciliation, interactions, adherence support, side effect education |
| Nutrition | Diet | Post-surgical dietary restrictions, meal planning, fluid management |
| PT/Rehab | Mobility | Exercise progression, activity restrictions, rehabilitation milestones |
| Social Work | SDOH | Resource navigation, transportation, insurance, caregiver support |
| Palliative Care | Symptom management | Pain management, goals of care, quality of life |
| Documentation | Clinical records | Structured summaries, handoff notes, chart-ready drafts |

**Why it matters:**
- **Evidence-grounded, not hallucinated.** Every specialist response is backed by RAG retrieval from clinical knowledge bases. Hybrid search (0.7 semantic + 0.3 keyword) with pgvector HNSW indexing. Each cited document tracked with similarity score
- **Confidence-gated safety.** Responses below 0.70 confidence auto-escalate to human clinicians. Confidence scoring accounts for LLM completion quality, RAG evidence strength, and clinical keyword detection
- **Extensible per institution.** Knowledge sources are tenant-scoped — hospitals can add their own protocols alongside global ACC guidelines. The specialist registry is a simple mapping; adding a new specialist is configuration, not architecture
- **Full audit trail.** Every agent interaction logged with HIPAA-compliant audit records: agent type, routing decision, confidence score, cited documents, escalation triggers. Required for [CMS quality reporting](https://www.cms.gov/medicare/quality) and institutional compliance
- **Multi-channel, multi-language.** Same agent team accessible via web chat, SMS (Twilio with signature validation), and voice (Whisper transcription). Real-time translation between English and Spanish with original content preserved

### 24/7 Monitoring Deep-Dive

Between clinic visits, patients are invisible to their care team. A weight gain of 3kg over 3 days — a classic CHF decompensation signal — goes unnoticed until the patient is back in the ER. Clintela closes this gap with two complementary monitoring systems: patient-reported outcomes (ePROs) and a clinical intelligence engine that processes vitals in real time.

**Patient-reported outcomes:** Six validated clinical instruments, each with deterministic scoring and automatic escalation thresholds:

| Instrument | Domain | Questions | Escalation Trigger |
|-----------|--------|-----------|-------------------|
| [PHQ-2](https://www.apa.org/pi/about/publications/caregivers/practice-settings/assessment/tools/patient-health) | Depression screening | 2 | Score ≥ 3 |
| [KCCQ-12](https://cvoutcomes.org/pages/kccq-12) | Heart failure quality of life | 12 | Domain score decline |
| [SAQ-7](https://cvoutcomes.org/pages/saq-7) | Angina frequency/stability | 7 | Frequency worsening |
| AFEQT | Atrial fibrillation quality of life | 18 | Symptom/concern escalation |
| [PROMIS](https://www.healthmeasures.net/explore-measurement-systems/promis) | General functional status | Adaptive | Below population norms |
| Daily Symptom Check | Post-surgical symptom tracking | 5-8 | Any red-flag symptom |

**Clinical intelligence engine:** 16 deterministic rules organized in four categories — no ML black box, every alert includes a plain-language rationale explaining why it fired:

| Category | Rules | Example |
|----------|-------|---------|
| **Threshold** (critical + warning) | 7 | HR > 120 or < 50 → RED alert, SpO2 < 90% → RED alert |
| **Trend** | 4 | Weight gain > 2kg in 3 days (fluid retention), activity drop > 30% in 7 days |
| **Missing data** | 2 | No weight in 3+ days, no heart rate in 2+ days |
| **Combination** | 3 | CHF decompensation: weight gain + elevated HR + elevated RR + shortness of breath → ORANGE |

**How the pipeline works:**
1. **Ingest:** ClinicalObservation records arrive from wearables, manual entry, or EHR — each tagged with [OMOP concept IDs](https://ohdsi.github.io/CommonDataModel/) (12 cardiac concepts mapped)
2. **Compute:** PatientClinicalSnapshot aggregates latest vitals, computes trajectory via linear regression slope analysis, calculates risk score (0-100)
3. **Detect:** 16 rules evaluate against snapshot — threshold checks, 3-day and 7-day trend windows, cross-vital combinations
4. **Alert:** ClinicalAlert created with severity color, rule rationale ([FDA CDS-compliant](https://www.fda.gov/regulatory-information/search-fda-guidance-documents/clinical-decision-support-software)), and trigger data. Broadcast to clinician dashboard via WebSocket
5. **Act:** Proactive patient messaging triggered for actionable alerts. Clinician notification for clinical alerts

**Why it matters:**
- **No monitoring gaps.** Continuous data flow from ePROs + wearables means the care team sees deterioration in hours, not days
- **Deterministic and auditable.** Every alert has a rule_rationale field with algorithmic logic, input sources, clinical evidence, and patient-specific context — designed for FDA 2026 CDS compliance
- **Patient-facing too.** The My Health card shows patients their own vitals with sparkline charts and warm trajectory messaging ("Your heart rate has been steady this week"). Patients become partners in their recovery, not passive subjects
- **ePRO-clinical correlation.** Rule 16 cross-references declining activity levels with worsening ePRO symptom scores — catching patterns that neither data source reveals alone

### Virtual Support Group Deep-Dive

Post-surgical cardiac patients face isolation and uncertainty during recovery. Clinical AI provides medical support, but patients lack the emotional validation that comes from peers who've been there. Real peer support groups are logistically hard — scheduling, facilitation, patient matching. Our virtual support group solves this.

**What it is:** 7 AI personas modeled as recovery alumni (not concurrent patients) who've been through surgery and come out the other side. Each has a distinct therapeutic role grounded in Yalom's therapeutic factors:

| Persona | Role | Style |
|---------|------|-------|
| Maria, 62 | Encourager (instillation of hope) | Warm, optimistic, celebrates milestones |
| James, 58 | Straight Shooter (accountability) | Direct, humor, tough-but-caring |
| Linda, 67 | Researcher (information giving) | Detail-oriented, explains simply |
| Tony, 55 | Humorist (tension relief) | Self-deprecating humor, lightens mood |
| Priya, 45 | Storyteller (narrative therapy) | Shares narratives, reflective |
| Robert, 70 | Planner (task-oriented) | Practical advice, checklists, tips |
| Diane, 52 | Quiet Observer (gate-keeper) | Speaks rarely but deeply |

**Why it matters:**
- **Zero direct competitors** in healthcare multi-persona peer support
- Clinical evidence strong: peer support improves cardiac recovery outcomes ([Mended Hearts](https://mendedhearts.org/) visiting model, [AHA scientific statement on social isolation and CVD](https://www.ahajournals.org/doi/10.1161/JAHA.122.026493))
- **Regulatory path clear:** wellness/peer support classification, not SaMD (Software as a Medical Device) — no diagnostic or treatment claims
- Mood-adaptive routing selects which personas respond based on patient emotional state
- 3-layer crisis detection (keyword scan → router-level → per-persona guardrail) with automatic clinician escalation
- Clinicians see engagement summaries by default. Thread access only on escalation for clinical context
- AI transparency: onboarding discloses "AI companions inspired by real recovery journeys"

### Clinician & Administrator Visibility Deep-Dive

Clinical AI is only as valuable as the clinician's ability to see what it's doing. If a nurse has to dig through logs to find out which patients are deteriorating, the system has failed. Clintela's clinician and administrator interfaces are designed so that the most important information finds the right person — they don't have to go looking for it.

**Clinician dashboard — three-panel design:**

| Panel | Purpose | Key Features |
|-------|---------|-------------|
| **Patient list** | Severity-sorted overview | Triage color dots (red/orange/yellow/green), unread message badges, pending escalation count, search by name/MRN, sort by severity/alpha/last contact |
| **Patient detail** | Six-tab deep dive | Details (timeline, escalations), Care Plan (pathway milestones), Research (clinician-to-AI chat), Surveys (ePRO scores + trends), Tools (lifecycle, consent, caregivers), Vitals (Chart.js trends, active alerts with rule rationale) |
| **Chat** | Real-time communication | Read AI conversation history, inject clinician messages, take-control mode |

**Take-control mode:** When a clinician needs to speak directly to a patient, they take control of the chat thread. The AI pauses, the patient sees messages from a named clinician, and a [compare-and-swap](https://en.wikipedia.org/wiki/Compare-and-swap) lock prevents race conditions. Automatic 30-minute timeout releases stale locks (e.g., browser crash). This is the bridge between AI-assisted and human care.

**Keyboard-driven workflow:** Designed for nurses managing 20-30 patients per shift — `j`/`k` navigate the patient list, `1`-`6` switch tabs, `e` acknowledges an escalation, `/` searches, `?` shows help. Every common action is one keystroke away.

**Shift handoff:** At login, clinicians see a computed summary of everything that changed since their last session: new escalations, resolved escalations, status changes, missed check-ins. No more "what happened overnight?" guesswork.

**Administrator KPI dashboard:**

| Category | Cards | What It Measures |
|----------|-------|-----------------|
| **Hero metric** | CMS readmission rate | Cohort-based rate with period tabs (7/30/60/90/120 days), sparkline trend |
| **Outcomes** | Discharge to community, follow-up completion, functional improvement | Clinical effectiveness — are patients recovering? |
| **Engagement** | Program engagement, message volume, check-in completion | Patient participation — are patients using the system? |
| **Operations** | Escalation response time, census by triage color, pathway performance | Operational health — is the team keeping up? |

**Why it matters:**
- **Real-time, not batch.** WebSocket escalation alerts and desktop notifications mean critical events reach clinicians in seconds, not on the next dashboard refresh. The clinician dashboard subscribes to hospital-level event groups
- **Operational alerts.** SLA breaches, stale escalations, and inactive patients surface automatically in an alerts bar — the administrator doesn't need to query for problems
- **Pathway administration.** Administrators can view per-pathway effectiveness stats, per-milestone check-in rates, and toggle pathways active/inactive. This is the foundation for hospital-administered pathway building (Horizon 3)
- **Export and print.** CSV export with [formula injection protection](https://owasp.org/www-community/attacks/CSV_Injection) for board presentations. Print-friendly CSS stylesheet for browser "Save as PDF." Dark mode across all views for night-shift clinicians
- **Deep-linkable.** Every patient, tab, and subview has a stable URL. Clinicians can share specific views via link or bookmark their most critical patients

### Regulatory & Reimbursement Pathway

**CMS 2026 changes directly benefit us:**
- As of January 1, 2026, CMS reduced minimum RPM data collection to **2 days** (down from 16) and shortened management time requirements ([CMS Physician Fee Schedule](https://www.cms.gov/medicare/payment/fee-schedules/physician)). This makes shorter post-discharge monitoring episodes billable, expanding our addressable use cases.
- RPM and RTM billing codes (CPT 99453-99458, 98975-98981) now cover the exact workflow Clintela enables: continuous remote monitoring with clinical escalation.

**Our regulatory positioning:**
- **Clinical Intelligence Layer** = Clinical Decision Support (CDS). Our 16 deterministic rules with plain-language rationale are designed for [FDA CDS guidance](https://www.fda.gov/regulatory-information/search-fda-guidance-documents/clinical-decision-support-software) compliance — meeting all four criteria for non-device CDS. No ML black box.
- **Virtual Support Group** = wellness/peer support, not SaMD. No diagnostic or treatment claims. Clear of FDA device classification.
- **Agent system** = care coordination tool augmenting clinical teams, not replacing clinical judgment. All escalations route to human clinicians.

### Why Now

Three trends converging:
1. **LLM capability** has crossed the clinical utility threshold. Multi-agent orchestration, RAG-backed evidence retrieval, and natural language interaction are production-ready. See [Hippocratic AI's Polaris](https://www.hippocraticai.com/) and [Google's AMIE](https://research.google/blog/amie-a-research-ai-system-for-diagnostic-medical-reasoning-and-conversations/) for parallel evidence.
2. **[OMOP CDM](https://ohdsi.github.io/CommonDataModel/) standardization** enables interoperability. Our 12 OMOP concept IDs map directly to Epic-to-OMOP pipelines, eliminating ETL for the most common cardiac vitals and labs.
3. **CMS financial pressure** is increasing. The [Hospital Readmissions Reduction Program](https://www.cms.gov/medicare/payment/prospective-payment-systems/acute-inpatient-pps/hospital-readmissions-reduction-program-hrrp) penalizes hospitals, and the 2026 billing changes make continuous post-discharge monitoring immediately economically viable.

---

## 3. What We've Built `[All]`

### Development Timeline

| Phase | Date | Version | What Shipped |
|-------|------|---------|--------------|
| 1 | Mar 18 | — | Django 5.1 foundation, PostgreSQL 16 + pgvector, Docker, CI/CD, 10 core apps |
| 2 | Mar 19 | — | Multi-agent system: Supervisor + Care Coordinator + Nurse Triage + Documentation + 6 specialists. 641 tests, 92% coverage |
| 2.5 | Mar 19 | 0.2.5 | Patient chat UI: HTMX sidebar, dark mode, Satoshi design system, 27 E2E Playwright tests |
| 3 | Mar 19 | 0.2.6 | SMS (Twilio), voice input (Whisper), WebSocket notifications, Celery task queue, leaflet code auth |
| 4 | Mar 20 | 0.2.7 | Clinical Knowledge RAG (pgvector hybrid search), patient lifecycle state machine, caregiver invitations, consent management |
| 5 | Mar 20 | 0.2.8 | Clinician dashboard: 3-panel, 6 tabs, take-control mode, scheduling, shift handoff, keyboard shortcuts |
| 6 | Mar 21 | 0.2.10 | Admin KPI dashboard (9 cards, DailyMetrics pipeline, CSV export) + Survey/ePRO (6 clinical instruments, deterministic scoring) |
| 7 | Mar 23 | 0.2.11 | Clinical Intelligence Layer: 16-rule engine, OMOP concept IDs, ClinicalObservation → Snapshot → Alert, Vitals tab, My Health card |
| 8 | Mar 23+ | 0.2.12 | i18n (English + Spanish), appointment scheduling with iCal, proactive messaging infrastructure |

### Platform at a Glance

```
┌─────────────────────────────────────────────────────────────┐
│                    CLINTELA v0.2.12.1                        │
├─────────────────────────────────────────────────────────────┤
│  15 Django apps    │  1,534 tests    │  90%+ coverage       │
│  8 AI agent types  │  16 clinical rules  │  6 survey instruments  │
│  12 OMOP concepts  │  3 interfaces   │  2 languages         │
│  Web + SMS + Voice │  Real-time WS   │  Celery task queue   │
└─────────────────────────────────────────────────────────────┘
```

For full implementation details, see [IMPLEMENTATION_HANDOFF.md](../IMPLEMENTATION_HANDOFF.md).

---

## 4. Architecture `[Partners + Team]`

### Current System

The platform uses a **supervisor + subagents-as-tools** pattern built on LangGraph:

```
Patient message (web/SMS/voice)
    │
    ▼
┌─────────────────────────────────┐
│         Supervisor              │
│  (routes, evaluates urgency)    │
├─────────────────────────────────┤
│  Care Coordinator  │  Nurse Triage  │  Documentation  │
│  (patient-facing)  │  (clinical)    │  (summaries)    │
├─────────────────────────────────┤
│  Specialists (RAG-backed)                             │
│  Cardiology │ Pharmacy │ Nutrition │ PT/Rehab         │
│  Social Work │ Palliative Care                        │
├─────────────────────────────────┤
│  Clinical Intelligence Layer                          │
│  ClinicalObservation → Snapshot → ClinicalAlert       │
│  16 deterministic rules, OMOP CDM bridge              │
└─────────────────────────────────┘
    │
    ▼
Clinician dashboard (real-time WebSocket)
Admin KPI dashboard (DailyMetrics pipeline)
```

### Target Agent Architecture

The current system routes queries to the right specialist. The target architecture goes further: specialists can **disagree**, and the orchestration layer **mediates** consensus. This is the key architectural evolution.

```
Patient-Facing Layer
├── Patient Communicator
│   └── Rapport, empathy, health literacy adaptation
├── Recovery Coach (NEW — Horizon 2)
│   └── Motivational accountability, goal tracking, streaks
├── Support Group (IN DEVELOPMENT — Horizon 1)
│   └── 7 AI peer personas, mood-adaptive routing
│
Orchestration Layer
├── Care Coordinator
│   └── Routes queries AND mediates specialist disagreements
├── Checklist Specialist
│   └── Tracks care protocol state, discharge instruction todos
└── Privacy & Compliance Specialist
    └── Consent verification, data access audit
│
Clinical Specialist Agents (with debate capability)
├── Pharmacist — medication reconciliation, interactions, adherence
├── Nurse — symptom assessment, vitals interpretation, triage
├── Dietitian — nutrition guidance, meal planning, restrictions
├── Social Worker — SDOH assessment, resource navigation
├── Palliative Care — symptom management, goals of care
├── Cardiovascular Expert — cardiac risk, treatment optimization
├── Primary Care Expert — holistic assessment, preventive care
├── Health Educator — patient education, self-management
└── Physical Therapist — mobility, exercise, rehabilitation
│
Operational Agents
├── Administrative Assistant — scheduling, referrals, documentation
└── Cost Minimizer — insurance, formulary alternatives, prior auth
│
Safety & Verification Layer
├── Clinical Safety Verifier
│   └── Independent "fresh eyes" check on every clinical recommendation
└── Human Intervention Detector
    └── Escalation to real clinicians when confidence is low
│
Memory & State Management
├── Patient State Buffer
│   └── FHIR-shaped shared memory, writable by all agents
├── Care Plan Consolidator
│   └── Periodic background reconciliation of agent outputs
└── Longitudinal Memory
    └── Pruned patient history with contradiction detection
```

### Built vs. Target

| Layer | Built Today | Target | Gap |
|-------|------------|--------|-----|
| Patient-facing | Care Coordinator, Support Group (in dev) | + Coach, expanded communicator | Coach Agent (H2) |
| Orchestration | Supervisor (routes) | Coordinator (routes + mediates) | Mediation logic (H2 R&D) |
| Specialists | 6 RAG-backed (respond) | 9+ with debate capability | Debate protocol, new agents |
| Operational | — | Admin Assistant, Cost Minimizer | H2-3 |
| Safety | Dual-layer detection (regex + LLM) | + Independent safety verifier | Fresh-eyes pattern (H2) |
| Memory | Conversation context + clinical snapshot | 3-layer model | State Buffer (H2), Consolidator + Longitudinal (H3) |

### Production Readiness Signals

- **Feature flags:** `ENABLE_CLINICAL_DATA`, `ENABLE_RAG`, `ENABLE_SMS`, `ENABLE_SUPPORT_GROUP` gate all major subsystems
- **Consent management:** Append-only audit trail with 5 consent types
- **HIPAA patterns:** Role-based access, PHI-aware templates, audit logging
- **OMOP bridge:** 12 cardiac concepts mapped, ready for EHR data with zero ETL

---

## 5. Roadmap: Three Horizons `[All]`

### Horizon 1: Production Readiness (Weeks 1-4)

**Gate:** HIPAA-compliant deployment readiness for AMC partner. All critical-path tests green. <2s p95 response time.

| Item | Description | Status | Dependency |
|------|-------------|--------|------------|
| **HIPAA-compliant LLM** | Migrate from Ollama to AWS Bedrock or Azure OpenAI | P0 hard blocker | Vendor evaluation |
| **Virtual Support Group** | 7 AI peer personas, mood-adaptive routing, crisis detection, staggered delivery | In development | None |
| **Discharge Instructions** | Clinician uploads during onboarding → system extracts structured todos → agents reference → patient checklist on dashboard | Ready to build | RAG infrastructure exists |
| **Proactive Patient Messaging** | Wire existing 16-rule engine to patient chat delivery (alerts → auto-messages) | ~80% done | None |
| **Comprehensive Audit Logging** | Full access trails, long-term retention, audit dashboard | Ready to build | None |
| **Load Testing** | Performance baselines, capacity planning, p95 latency targets | Ready to build | None |
| **Production Infrastructure** | HIPAA hosting, monitoring, backups, disaster recovery | Ready to build | Vendor selection |

### Horizon 2: Clinical Integration (Weeks 5-10)

**Gate:** Real clinical data flowing through the rules engine, generating alerts visible to clinicians.

| Item | Description | Status | Dependency |
|------|-------------|--------|------------|
| **Wearable Device Integration** | HealthKit companion app or third-party aggregator → ClinicalObservation | Architecture done | Data team pipeline |
| **Patient Device Onboarding** | Device pairing flow, permissions, HealthKit auth, data sharing consent | Design needed | Mobile app or web bridge |
| **EHR FHIR Integration (Epic)** | Epic FHIR R4 via App Orchard or MyChart patient portal delegation (SMART on FHIR) | OMOP bridge ready | AMC partnership + Epic review (4-12 wk) |
| **Data Team Pipeline** | Databricks events → webhook → ClinicalObservation model | Interface designed | Data team deliverables |
| **Recovery Coach Agent** | Patient-facing motivational accountability: daily check-ins, goal tracking, celebrating streaks, exercise and medication nudges | Not started | Reuses agent framework |
| **Specialist Mediation (R&D)** | Phase A: weighted consensus with confidence scores. Phase B: structured debate with rationale. Phase C: clinician-adjudicated disagreements | Not started | Research (ref: Hippocratic AI/Polaris) |
| **Discharge Instructions (EHR)** | Pull from Epic via FHIR discharge summary / care plan resources → extraction pipeline | Depends on FHIR | EHR integration |
| **Additional Languages** | Mandarin, Vietnamese, Haitian Creole | i18n infrastructure exists | Translation review |
| **Caregiver Dashboard** | Read-only recovery view for family members | Models exist | None |
| **Patient State Buffer** | FHIR-shaped shared memory writable by all agents — foundational layer for memory architecture. Rule-based contradiction detection | Not started | Agent framework stable |
| **Clinical Pathway Review** | Clinical team reviews and validates care pathways. Structured feedback loop, pathway versioning, clinician sign-off workflow | Not started | Clinical team engagement |

### Horizon 3: Scale & Intelligence (Weeks 11-20)

**Gate:** Multi-site deployment capability. ML pipeline operational.

| Item | Description | Status | Dependency |
|------|-------------|--------|------------|
| **Predictive Risk Scoring** | Pre-discharge ML models for readmission risk prediction | Not started | 12+ months AMC historical data |
| **Native Mobile App** | iOS/Android with HealthKit integration, push notifications, offline mode | Not started | V1 clinical validation |
| **Memory Architecture (Phase 2)** | Care Plan Consolidator (periodic background reconciliation of agent outputs), Longitudinal Memory (pruned patient history, ML-augmented contradiction detection). Builds on Patient State Buffer from H2 | Not started | Patient State Buffer (H2) |
| **Pathway & ePRO Builder** | Hospital administrators build, deploy, and manage their own clinical pathways and associated ePRO instruments. Pathway effectiveness analytics, per-milestone check-in rates | Not started | Clinical pathway review (H2) |
| **Multi-Site Benchmarking** | Anonymized cross-hospital metrics comparison | Not started | Multiple deployments |
| **Agent Marketplace** | Plugin architecture for custom specialist agents | Interfaces designed | Partner interest |
| **Advanced Anomaly Detection** | ML-augmented pattern detection + weekly digest emails | Not started | Sufficient observation data |

---

## 6. Data Team Integration `[Partners + Team]`

### Interface Contract

Our internal data team is building a Databricks-style framework for ingesting and monitoring raw health and wearables data. Their pipeline produces structured patient events. Our platform consumes them.

```
Data Team Pipeline                    Clintela Platform
┌────────────────────┐               ┌────────────────────────────┐
│ Raw wearable data  │               │                            │
│ (Apple Watch,      │  webhook /    │  ClinicalObservation model │
│  Withings, Garmin) │──event bus──▶│  ├── source: "wearable"    │
│                    │               │  ├── source_device: "..."   │
│ Patient            │               │  ├── omop_concept_id: ...   │
│ representations    │               │  └── observed_at: timestamp │
│                    │               │           │                  │
│ Key event          │               │           ▼                  │
│ detection          │               │  16-Rule Engine → Alerts    │
└────────────────────┘               │           │                  │
                                     │           ▼                  │
                                     │  Clinician Dashboard        │
                                     │  Patient My Health Card     │
                                     └────────────────────────────────┘
```

**Integration surface already exists:** The `ClinicalObservation` model has `source`, `source_device`, and `omop_concept_id` fields. The 16-rule engine, alerting pipeline, clinician UI, and patient UI are all built and tested with simulated data via `seed_clinical_data`.

### Parallel Development

Both teams can work independently until the Horizon 2 integration point:
- **Platform team:** Builds and tests with simulated clinical data (4 cardiac scenarios, 30 days of vitals, 5 patients)
- **Data team:** Builds ingestion pipeline, patient representations, and key event detection independently

### What We Need from the Data Team

| Deliverable | Needed By | Purpose |
|-------------|-----------|---------|
| Event format specification | H2 start (week 5) | Define the webhook payload structure |
| Sample data payloads | H2 start (week 5) | Integration testing |
| Pipeline health endpoint | H2 mid (week 7) | Monitoring and alerting |
| Device onboarding documentation | H2 start (week 5) | Patient-facing setup flows |

### Dependency Matrix

| Roadmap Item | Platform Only | Needs Data Team |
|-------------|:---:|:---:|
| LLM Migration | x | |
| Virtual Support Group | x | |
| Discharge Instructions (upload) | x | |
| Proactive Messaging | x | |
| Coach Agent | x | |
| Wearable Integration | | x |
| EHR Integration | partial | partial |
| Predictive Risk Scoring | | x |
| Patient State Buffer (H2) | x | |
| Clinical Pathway Review (H2) | x | |
| Memory Architecture Phase 2 (H3) | x | |
| Pathway & ePRO Builder (H3) | x | |

---

## 7. Key Integration Deep-Dives `[Partners + Team]`

### Wearable / Device Integration

**What's built:** `ClinicalObservation` model supporting wearable data sources with `source='wearable'`, `source_device` (e.g., "Apple Watch", "Withings Scale"), and 12 OMOP cardiac concept IDs (heart rate, BP systolic/diastolic, weight, SpO2, temperature, respiratory rate, glucose, BNP, troponin, daily steps, sleep duration). The 16-rule engine already processes this data type.

**What's needed:** Real device connectivity. Three options under evaluation:

| Option | Pros | Cons | Timeline |
|--------|------|------|----------|
| (a) Companion mobile app with HealthKit / Google Health Connect | Deep integration, background sync, push notifications | Requires native app development (H3) | 6-8 weeks |
| (b) Third-party aggregator (Validic, Human API) | Fast integration, 400+ device types | Per-patient cost, dependency on vendor | 2-3 weeks |
| (c) Direct device APIs | No middleman cost | Limited devices, maintenance burden | 4-6 weeks per device |

**Division of labor:** The data team handles raw signal processing, noise filtering, and event surfacing from device data. Our platform handles event consumption, rules engine processing, alerting, and clinician/patient UI.

**Patient onboarding:** Patients will need a device pairing flow (connecting their wearable to Clintela), permissions management, and data sharing consent. This may require a companion mobile app (option a) or web-based OAuth flows (options b, c).

### EHR / Patient Record Integration (Epic-first)

**What's built:** OMOP concept ID bridge for 12 cardiac vitals/labs, `ClinicalObservation` ingestion pipeline, and feature-flagged clinical UI. The OMOP bridge means data from Epic-to-OMOP pipelines flows directly into our system with zero ETL.

**AMC partner is on Epic.** Three integration paths:

| Path | Institutional Buy-in | Patient Effort | Timeline |
|------|---------------------|----------------|----------|
| (a) Epic FHIR via App Orchard | High (requires Epic review) | None | 4-12 weeks for review |
| (b) MyChart patient portal delegation (SMART on FHIR) | Low | Patient authenticates via OAuth2 | 2-4 weeks to build |
| (c) Institution data feed via Epic Interconnect | High | None | Depends on IT |

**Recommended approach:** Start with (b) MyChart patient portal delegation. Less institutional IT buy-in needed, patient-controlled, can be built while waiting for Epic App Orchard review. Build (a) in parallel for the long-term integration path.

**What flows in:** Vitals, labs, medications, encounter history, discharge summaries, care plans. All mapped through OMOP concept IDs.

**Privacy:** Consent management already built with append-only audit trail supporting 5 consent types.

### Discharge Instructions

**What's built:** RAG knowledge base with PDF/Markdown/HTML/text parsers, pgvector hybrid search, and 6 specialist agents that can reference retrieved documents. Patient lifecycle state machine tracks `discharged → recovering → recovered`.

**Two-phase approach:**

**Phase 1 (Horizon 1):** Clinician uploads discharge instructions during patient onboarding. System extracts structured todos (medication schedules, activity restrictions, follow-up appointments, warning signs). Agents reference these in conversations. Patient sees an interactive checklist on their dashboard with progress tracking.

**Phase 2 (Horizon 2):** Pull discharge instructions from Epic via FHIR (discharge summary and care plan resources). Same extraction pipeline, automated instead of manual upload.

**Formats will vary wildly per institution:** PDF, scanned documents, free-text, structured HL7. Epic partner likely uses structured discharge summaries but may also have PDF attachments. Our existing parsers handle all common formats; OCR for scanned PDFs is deferred (TODO-011).

**Key insight:** Patients often lose or don't read paper discharge instructions. Making them interactive, searchable, and agent-referenced, so the patient's care team can remind them about specific items, is a core value proposition.

---

## 8. Dependencies & Risk Register `[Team]`

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| LLM vendor delay (BAA, integration) | Blocks all production deployment | Low | Multiple vendors evaluated (Bedrock, Azure); can switch |
| Epic App Orchard review timeline | Delays H2 EHR integration | Medium | MyChart patient portal approach as faster fallback |
| Data team pipeline delivery | Delays wearable integration | Medium | Platform continues with simulated data; seed commands exist |
| Regulatory review findings | Potential scope changes | Medium | CDS rules are deterministic (not ML); peer support is wellness classification |
| Clinical validation gaps | Feature rework | Low | 16 deterministic rules with auditable rationale, not ML black box |
| LLM hallucination in clinical context | Patient safety | Medium | RAG grounding, confidence thresholds, human escalation, dual-layer symptom detection |
| Specialist disagreement resolution complexity | R&D uncertainty | Medium | Phased approach (routing → consensus → mediation); Hippocratic AI as reference |

---

## 9. Development Velocity `[All]`

### Agentic Development

This project is built with AI-assisted development (Claude Code as a pair programmer with deep context retention across sessions). This isn't about replacing engineering judgment. It's about compressing implementation time so the team can iterate on product-market fit faster than competitors.

### Concrete Evidence

| Metric | Value |
|--------|-------|
| Phases shipped | 8 in ~10 calendar days |
| Tests written alongside features | 1,534 (not written after the fact) |
| Coverage maintained throughout | 90%+ at every phase |
| Dual effort estimates in backlog | e.g., "human: ~1 week / CC: ~30 min" |

### What It Multiplies

- **Implementation speed:** 3-5x compression on feature development
- **Test coverage thoroughness:** Tests generated alongside features, not as an afterthought
- **Documentation completeness:** Architecture docs, handoff docs, plan docs all maintained in real-time
- **Cross-cutting consistency:** Dark mode on every view, WCAG compliance everywhere, i18n from day one

### What It Does Not Replace

- **Clinical domain expertise** for defining the right rules, the right escalation thresholds, the right patient-facing language
- **Partnership development** for EHR access, AMC relationships, data sharing agreements
- **Regulatory and compliance review** for HIPAA, FDA CDS, billing code eligibility
- **User research** and clinical validation with real patients and clinicians
- **Data team domain knowledge** in health data ingestion, wearable signal processing, and patient representation

### What This Means for Investors

The team can iterate on product-market fit faster than competitors because the build cycle is compressed. A clinical insight on Monday can be a tested, deployed feature by Wednesday. The roadmap timelines in this document reflect agentic development velocity, not traditional engineering estimates.

---

## Appendix A: Detailed Backlog

See [TODOS.md](../TODOS.md) for the full prioritized backlog with 20 tracked items, effort estimates, dependencies, and blocking relationships.

Key items by priority:
- **P0:** Production LLM migration (hard blocker)
- **P1:** EHR integration, comprehensive audit logging, load testing
- **P2:** Mobile app, predictive risk scoring, caregiver dashboard, additional languages, real Zoom/Teams integration, medication photo verification
- **P3:** Offline mode, embedding cache, async ORM migration, multi-site benchmarking

## Appendix B: Glossary

| Term | Definition |
|------|-----------|
| **OMOP CDM** | Observational Medical Outcomes Partnership Common Data Model. A standardized vocabulary for clinical data that enables interoperability across health systems. |
| **FHIR** | Fast Healthcare Interoperability Resources. The HL7 standard for exchanging healthcare information electronically. |
| **SMART on FHIR** | An open standard for third-party app authorization with EHR systems. Enables patient-authorized data access. |
| **ePRO** | Electronic Patient-Reported Outcomes. Standardized surveys (PHQ-2, KCCQ-12, etc.) that patients complete to report symptoms and quality of life. |
| **RAG** | Retrieval-Augmented Generation. An AI technique where the model retrieves relevant documents before generating a response, grounding answers in evidence. |
| **CMS** | Centers for Medicare & Medicaid Services. The federal agency that administers Medicare and penalizes hospitals for high readmission rates. |
| **AMC** | Academic Medical Center. A hospital affiliated with a medical school, typically an early adopter of clinical technology. |
| **CDS** | Clinical Decision Support. Software that provides clinicians with knowledge and patient-specific information to enhance clinical decisions. |
| **SaMD** | Software as a Medical Device. Software intended for medical purposes that is subject to FDA regulation. |
| **RPM** | Remote Patient Monitoring. The use of technology to collect patient health data outside traditional healthcare settings. |
| **RTM** | Remote Therapeutic Monitoring. Similar to RPM but focused on monitoring therapeutic outcomes (e.g., medication adherence, respiratory therapy). |
| **HealthKit** | Apple's framework for health and fitness data on iOS. Enables apps to read and write health data with user permission. |
| **HIPAA BAA** | Business Associate Agreement. A contract required under HIPAA when a vendor handles protected health information on behalf of a covered entity. |

---

*This roadmap is a living document. For implementation details, see [IMPLEMENTATION_HANDOFF.md](../IMPLEMENTATION_HANDOFF.md). For the full backlog, see [TODOS.md](../TODOS.md). For the care philosophy that guides all patient-facing work, see [docs/philosophy.md](philosophy.md).*
