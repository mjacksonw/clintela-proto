# TODOS

*Deferred items from CEO Review (2026-03-17)*

---

## Phase 2 (Near-Term: Post-V1 Launch)

### TODO-001: EHR Integration (Epic/Cerner)
**What:** Direct integration with major EHR systems for real-time patient data sync and bidirectional communication.

**Why:** Eliminates manual data entry, ensures data freshness, enables writing care notes back to EHR. Critical for production deployment at partner AMC.

**Pros:**
- Seamless workflow for clinicians
- Real-time data without manual imports
- Establishes integration patterns for other hospitals

**Cons:**
- Complex OAuth/SAML implementation
- Requires compliance review and Business Associate Agreements
- Epic/Cerner have different APIs and approval processes

**Context:**
Webhook simulation is in place for V1. This replaces simulated data with live EHR feeds. SAML infrastructure for clinician auth will be built as part of this.

**Effort:** Large (2-3 months per EHR)
**Priority:** P1
**Blocked by:** Production readiness, HIPAA BAA in place

---

### TODO-002: Patient Mobile App (Native iOS/Android)
**What:** Dedicated native mobile applications for patients with offline support, push notifications, and camera integration.

**Why:** Native apps enable better UX for elderly patients, offline access to critical info, push notifications for medication reminders, and camera for medication verification.

**Pros:**
- Better engagement rates
- Push notification reliability
- Offline access to care instructions
- Camera integration for medication photos

**Cons:**
- Significant development effort (iOS + Android)
- App store approval processes
- Maintenance overhead for two platforms

**Context:**
Web-first approach validates core experience. Mobile app becomes compelling once patient engagement is proven and EHR integration is live.

**Effort:** Large (2-3 months)
**Priority:** P2
**Blocked by:** V1 validation, EHR integration

---

## Phase 3 (Mid-Term: Scale & Intelligence)

### TODO-003: Predictive Risk Scoring (Pre-Discharge)
**What:** ML models that predict readmission risk before patient discharge, enabling customized post-discharge protocols.

**Why:** Intervene earlier—identify high-risk patients during hospital stay. The holy grail of readmission prevention with AMC partner data.

**Pros:**
- Prevent readmissions before they happen
- Personalized care protocols based on risk
- Data-driven clinical decision support

**Cons:**
- Requires substantial historical data (years of patient records)
- Model training, validation, and regulatory considerations
- Integration with clinical workflow for risk scores

**Context:**
AMC partnership provides access to full patient charts. Focus initially on cardiology patients with Harlan Krumholz guidance. Reactive monitoring delivers value while this is built.

**Effort:** Large (3-4 months)
**Priority:** P2
**Blocked by:** AMC data access, data science resources

---

### TODO-004: Medication Photo Verification
**What:** Patients photograph medication labels/pills; system uses OCR + AI to verify correct medication at the right time.

**Why:** Medication errors are a leading cause of readmissions. Photo verification adds safety layer and catches mix-ups.

**Pros:**
- Catches medication errors visually
- Accessible for patients who struggle with text
- Audit trail of medication verification

**Cons:**
- HIPAA-compliant image storage requirements
- OCR accuracy challenges with poor lighting/handwriting
- Additional infrastructure for image processing

**Context:**
Text-based medication confirmation is sufficient for V1. This becomes compelling with native mobile app (TODO-002) where camera access is seamless.

**Effort:** Medium (2-3 weeks)
**Priority:** P2
**Blocked by:** Patient mobile app, image storage infrastructure

---

### TODO-005: Marketplace of Specialist Agents
**What:** Plugin architecture where third parties build specialist agents (diabetes management, wound care) that plug into the supervisor.

**Why:** Scales expertise beyond in-house capabilities. Enables ecosystem and AMC-to-community-hospital specialist sharing.

**Pros:**
- Unlimited specialist coverage
- Community hospitals access AMC expertise
- Revenue opportunity (marketplace fees)

**Cons:**
- Complex sandboxing and security model
- API contracts and backward compatibility
- Developer documentation and support

**Context:**
Placeholder specialists in V1 (Cardiology, Social Work, Nutrition, PT/Rehab, Palliative, Pharmacy). Design agent interfaces to support this from day one.

**Effort:** Large (1-2 months)
**Priority:** P2
**Blocked by:** V1 agent architecture validation, partner interest

---

### TODO-006: Patient Portal SSO
**What:** Single sign-on with existing hospital patient portals (MyChart, etc.) so patients don't need new credentials.

**Why:** Reduces friction, leverages existing authentication, increases trust through familiar entry point.

**Pros:**
- Seamless patient experience
- Trust through familiar portal
- No password management for patients

**Cons:**
- OAuth/SAML integration with each portal
- Partnership and compliance review for each hospital
- Fallback auth required for direct access

**Context:**
Standalone auth with magic links/SMS for V1. SAML infrastructure for clinician auth (TODO-001) enables this later. Most valuable after EHR integration is proven.

**Effort:** Medium (1-2 weeks per portal)
**Priority:** P2
**Blocked by:** EHR integration, patient portal partnerships

---

## Phase 4+ (Future Considerations)

### TODO-007: Offline Mode
**What:** Critical patient information available without internet connectivity via service workers and local storage.

**Why:** Patients may have spotty connectivity at home, especially rural or lower-income populations. Emergency info shouldn't depend on connection.

**Pros:**
- Accessibility for underserved populations
- Emergency access to care instructions
- Resilience against network failures

**Cons:**
- Service worker complexity
- Sync conflict resolution
- Limited offline functionality (can't reach agents)

**Context:**
Keep architecture open—design data layer with offline in mind. Native mobile app (TODO-002) makes this more viable than web-only.

**Effort:** Medium (1-2 weeks)
**Priority:** P3
**Blocked by:** Patient mobile app, service worker architecture

---

## Infrastructure & Platform TODOs

### TODO-008: Production LLM Migration
**What:** Replace Ollama Cloud with HIPAA-compliant LLM provider (AWS Bedrock with Claude, Azure OpenAI, or self-hosted).

**Why:** Ollama Cloud is for prototyping only. Production requires HIPAA Business Associate Agreement.

**Pros:**
- Compliance with healthcare regulations
- Better performance and reliability
- Audit trails and access controls

**Cons:**
- Cost increase
- Integration changes
- Latency considerations

**Context:**
Decision needed before any production patient data. Evaluate providers: Anthropic via AWS Bedrock (Claude), Azure OpenAI (GPT-4), or self-hosted Llama.

**Effort:** Medium (1 week)
**Priority:** P0 (Blocker for production)
**Blocked by:** Vendor selection, security review

---

### TODO-009: Comprehensive Audit Logging
**What:** Complete audit trail for all patient data access, agent decisions, and clinical actions.

**Why:** HIPAA requires audit trails. Critical for incident response, clinical review, and model improvement.

**Pros:**
- Compliance with regulations
- Debugging and incident response
- Model performance analysis

**Cons:**
- Storage costs for high-volume logs
- Performance impact on writes
- Log retention policies

**Context:**
Build logging infrastructure from day one. This TODO represents the comprehensive audit dashboard and long-term retention strategy.

**Effort:** Medium (1-2 weeks)
**Priority:** P1
**Blocked by:** None—can start immediately

---

### TODO-010: Load Testing & Performance Benchmarks
**What:** Establish performance baselines and load testing for agent response times, concurrent patients, and dashboard scalability.

**Why:** Ensure system performs under realistic load. Identify bottlenecks before they impact patients.

**Pros:**
- Confidence in production scaling
- Capacity planning data
- Performance regression detection

**Cons:**
- Requires realistic test data
- Infrastructure for load generation
- Ongoing maintenance of test suites

**Context:**
Start with basic load testing once core features are stable. Essential before production launch.

**Effort:** Small (3-5 days)
**Priority:** P1
**Blocked by:** Core features stable

---

## Phase 4 Deferred Items

### TODO-011: OCR for Scanned PDFs
**What:** Add OCR capability (Tesseract or cloud OCR) to the PDF parser so scanned/image-based PDFs can be ingested into the knowledge base.

**Why:** Some hospital protocols are scanned PDFs with no extractable text. Currently these are skipped with a warning during ingestion.

**Pros:**
- Broader coverage of hospital protocol documents
- Reduces manual re-typing of scanned content

**Cons:**
- OCR accuracy varies with scan quality
- Additional dependency (Tesseract) or cloud API costs
- HIPAA considerations for cloud OCR providers

**Context:**
The PDF parser (`apps/knowledge/parsers.py`) currently uses pdfplumber for text extraction. Scanned PDFs with no extractable text are skipped with a logged warning. This TODO adds OCR as a fallback path.

**Effort:** Small (human: ~1 week / CC: ~30 min)
**Priority:** P2
**Blocked by:** None — ingestion pipeline shipped in v0.2.7.0

---

### TODO-012: Embedding Cache for RAG Queries
**What:** Cache query embeddings in Redis to avoid re-embedding identical or near-identical patient questions.

**Why:** Patients often ask similar questions ("when can I shower?", "can I take a shower?"). Caching embeddings reduces Ollama API calls and improves response latency.

**Pros:**
- Faster RAG response times for repeated questions
- Reduced load on embedding service
- Simple Redis-based implementation

**Cons:**
- Cache invalidation complexity (embedding model changes)
- Memory usage for cached vectors
- Marginal benefit if embedding calls are already fast

**Context:**
The `KnowledgeRetrievalService.search()` method embeds the query on every call. A TTL-based Redis cache keyed on normalized query text would avoid redundant embedding calls. Start with a 1-hour TTL and tune based on hit rates.

**Effort:** Small (human: ~3 days / CC: ~15 min)
**Priority:** P3
**Blocked by:** None — retrieval service shipped in v0.2.7.0

---

### TODO-013: Caregiver Read-Only Dashboard Design
**What:** Design and implement the caregiver dashboard — the view caregivers see after accepting an invitation and verifying with the leaflet code.

**Why:** The caregiver invitation flow (Phase 4 Step 7) creates the relationship, but the caregiver needs a dedicated read-only view of the patient's recovery status, progress, and escalation alerts.

**Pros:**
- Completes the caregiver user journey
- Reduces anxiety for family members
- Decreases inbound calls to clinical teams

**Cons:**
- New template and view to maintain
- Careful access control (read-only, respects consent)
- Needs real-time updates when patient status changes

**Context:**
After a caregiver accepts an invitation and verifies with the patient's leaflet code, they should see a simplified view of: patient status (lifecycle + triage), recent agent interactions (summary, not full chat), and any active escalations. This is read-only — caregivers cannot interact with agents or modify patient data. Access is gated by `CaregiverRelationship.is_active` and `ConsentRecord` for `data_sharing_caregiver`.

**Effort:** Medium (human: ~1 week / CC: ~30 min)
**Priority:** P2
**Blocked by:** None — caregiver flow + consent shipped in v0.2.7.0

---

### TODO-015: Server-Side Pagination for Patient List
**What:** Add server-side pagination to the clinician patient list instead of loading all patients at once.

**Why:** The current implementation loads all patients from the clinician's hospitals in a single queryset. This works for the prototype (~50 patients) but won't scale beyond ~300 patients.

**Pros:**
- Supports clinicians with large patient loads
- Reduces initial page load time
- Enables infinite scroll or paged navigation

**Cons:**
- More complex frontend interaction (HTMX pagination)
- Sort/search needs to work with pagination

**Context:**
The patient list in `apps/clinicians/views.py:patient_list_fragment` uses Django ORM annotations (Subquery/Count/Max) for a single queryset. Adding `.paginate_by` and HTMX `hx-trigger="revealed"` for infinite scroll is the recommended approach.

**Effort:** Small (human: ~3 days / CC: ~15 min)
**Priority:** P2
**Blocked by:** None — clinician dashboard shipped in Phase 5

---

### TODO-016: Migrate Async Wrappers to Django 5.1 Native Async ORM
**What:** Replace 8+ `sync_to_async` / `database_sync_to_async` boilerplate functions in `apps/agents/api.py` with Django 5.1 native async ORM methods (`aget`, `acreate`, `aiterator`).

**Why:** Django 5.1 supports native async ORM. The current wrappers are verbose and add unnecessary indirection.

**Pros:**
- Cleaner code, less boilerplate
- Better performance (no thread pool overhead)
- Uses framework-standard patterns

**Cons:**
- Minor migration effort
- Need to verify all async ORM methods are available for the queries used

**Context:**
`apps/agents/api.py` has ~8 `sync_to_async` wrapper functions that can be replaced with `await Model.objects.aget()`, `await Model.objects.acreate()`, etc. Low risk, high code quality improvement.

**Effort:** Small (human: ~2 days / CC: ~15 min)
**Priority:** P3
**Blocked by:** None

---

### TODO-017: Anomaly Detection & Weekly Digest Emails
**What:** Automated anomaly detection on KPI metrics with weekly digest emails for administrators showing trends, outliers, and actionable insights.

**Why:** Administrators shouldn't have to log in every day to catch problems. Proactive alerts for metric anomalies (sudden readmission spikes, engagement drops) enable faster intervention.

**Pros:**
- Proactive problem detection without manual dashboard monitoring
- Weekly digest keeps leadership informed with minimal effort
- Establishes patterns for future alerting infrastructure

**Cons:**
- Email delivery infrastructure needed
- Threshold tuning to avoid alert fatigue
- Anomaly detection algorithm complexity

**Context:**
The admin KPI dashboard (Phase 6) provides live metrics. This TODO adds passive monitoring: background analysis of DailyMetrics trends, anomaly detection (statistical outliers vs rolling average), and a weekly HTML email digest summarizing key metric movements. Start simple (z-score based) and iterate.

**Effort:** Medium (human: ~1-2 weeks / CC: ~30 min)
**Priority:** P2
**Blocked by:** DailyMetrics pipeline (shipped in v0.2.10.0)

---

### TODO-018: Multi-Site Anonymized Benchmarking
**What:** Cross-hospital benchmarking allowing administrators to compare their metrics against anonymized aggregate data from other Clintela-using hospitals.

**Why:** Hospitals want to know how they compare to peers. Anonymized benchmarks provide context without revealing individual hospital data.

**Pros:**
- Contextualizes metrics ("is our 8% readmission rate good or bad?")
- Drives competitive improvement
- Network effect — more hospitals = better benchmarks

**Cons:**
- Data privacy and anonymization complexity
- Requires multiple hospital deployments
- Statistical validity concerns with small N

**Context:**
The admin dashboard (Phase 6) currently shows hospital-specific metrics only. The user explicitly noted "you are your own benchmark" as the right V1 framing — continuous improvement vs. prior period. Multi-site benchmarking is a future network effect once multiple hospitals are live.

**Effort:** Large (human: ~2-3 weeks / CC: ~1 hour)
**Priority:** P3
**Blocked by:** Multiple hospital deployments, data sharing agreements

---

### TODO-014: Chat Sidebar Suggestion Chips Touch Target
**What:** Increase suggestion chip height from 38px to 44px minimum WCAG touch target in `_chat_sidebar.html`.

**Why:** Design review (2026-03-20) found chips below 44px minimum. Deferred because the chips are pre-existing code not changed in the Phase 4 branch.

**Effort:** Tiny (human: ~5 min / CC: ~2 min)
**Priority:** P3
**Blocked by:** None

---

## Deferred Scope (Explicitly Not in Scope)

The following were considered during CEO Review and explicitly deferred:

1. **Patient Mobile App** — See TODO-002
2. **Predictive Risk Scoring** — See TODO-003
3. **EHR Integration** — See TODO-001
4. **Medication Photo Verification** — See TODO-004
5. **Offline Mode** — See TODO-007
6. **Marketplace of Specialist Agents** — See TODO-005
7. **Patient Portal SSO** — See TODO-006

---

## Completed TODOs

*Phase 3 shipped in v0.2.6.0 (2026-03-19): SMS via Twilio, voice input with Whisper transcription, WebSocket real-time notifications, Celery task queue, notification preference model, and dev toolbar. See CHANGELOG.md for full details.*

---

## How to Update This Document

When completing a TODO:
1. Move it to "Completed TODOs" section
2. Add completion date and PR/commit reference
3. Update any dependent TODOs' "Blocked by" fields

When deferring new work:
1. Add to appropriate phase section
2. Use TODO-00X numbering (increment from last)
3. Include all fields: What, Why, Pros, Cons, Context, Effort, Priority, Blocked by

---

*Last updated: 2026-03-21*
*Source: CEO Review Scope Expansion + Phase 3 completion (v0.2.6.0) + Phase 4 completion (v0.2.7.0) + Phase 5 completion (v0.2.8.0) + Phase 6 completion (v0.2.10.0) + Design review deferrals*
