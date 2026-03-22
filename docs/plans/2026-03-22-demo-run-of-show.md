# Clintela Demo Run-of-Show

## Context

Demo in ~2 days. Internal team presentation to decide go/no-go on pursuing Clintela as a business. Product is at v0.2.10.0 with 6 phases shipped: patient interface, multi-agent AI, SMS/voice/WebSocket, clinical knowledge RAG, clinician dashboard, surveys/ePRO + admin KPI dashboard.

**Audience**: Teammates evaluating the opportunity. The demo must answer:
1. Is the market real? (CMS penalties, $26B readmissions)
2. Is the product useful? (show all three interfaces working)
3. Can we execute? (depth of what's built, vision for what's next)

**Target duration**: 10-12 minutes + open discussion.

---

## Part 1: Run-of-Show Script (10-12 min)

### Pre-Demo Setup

**Seed the database:**
```bash
manage.py reset_demo
```
This single command runs: flush, seed_pathways, seed_cardiac_pathways, seed_instruments, create_test_clinician, create_test_admin, create_cardiology_service, seed_demo_data.

**Browser setup:**
- **Window 1 (left half)**: Patient dashboard, pre-authed as demo patient (clean conversation)
- **Window 2 (right half)**: Clinician dashboard at `/clinician/login/` — credentials: `dr_smith` / `testpass123`
- **Window 3 (hidden)**: Admin dashboard at `/admin-dashboard/login/` — credentials: `admin_test` / `testpass123`
- Clinician in **dark mode**, patient in **light mode**
- Chrome maximized, bookmarks bar hidden
- Display must be at least **1280px wide** (projectors and TVs may need adjustment — the clinician three-panel layout needs the space)

**Pre-flight check:**
- LLM backend running + test one chat message
- Redis running (`redis-cli ping` → PONG)
- Celery running (`celery -A config inspect active` → shows worker)
- WebSocket connection working (open clinician dashboard, check browser console for WS connect)
- If any service is down: `make services` or restart individually before proceeding

---

### Act 1: Why This Matters (2 min)

**SHOW**: Clintela landing page at `/`

**Scripted framing** (speak over the landing page):

> "Hospital readmissions cost $26 billion a year in the US. CMS penalizes hospitals whose readmission rates exceed the national average — the Hospital Readmissions Reduction Program. The core problem: the moment a patient leaves the hospital after surgery, they enter a black box. No one is watching. They have questions at 2am, they miss warning signs, they forget medication instructions. By the time something goes wrong, they're back in the ER.
>
> We built Clintela to be the 24/7 care team that fills that gap. AI agents that know the patient, know the surgery, know the clinical protocols — and seamlessly hand off to human clinicians when it matters. Let me show you what it does."

---

### Act 2: The Cold Open — Dual Screen (2-3 min)

**SHOW**: Patient window (left) + Clinician login window (right), side by side.

**Step 1**: Log in as clinician (`dr_smith` / `testpass123`). Point out: "45 cardiac surgery patients, sorted by clinical severity. Green is recovering well, red needs attention. This is the clinician's home base."

**Step 2**: On the patient side, type a critical symptom:

> *"I'm having severe chest pain, about 8 out of 10, and it's radiating to my left arm."*

**While waiting** (5-10 seconds): "The AI has a nurse triage agent with clinical pattern matching for critical symptoms — chest pain, breathing difficulty, high fever, severe pain. Plus the LLM itself does clinical reasoning. Belt and suspenders."

**When response arrives**: Point out on BOTH screens simultaneously:
- **Patient side**: Immediate, clear response — "I'm connecting you with your care team right now." Escalation banner appears.
- **Clinician side**: Real-time WebSocket alert — the patient jumps to the top of the list with a red indicator. Notification bell lights up.

**Talk**: "That happened in real-time. No page refresh, no polling. The moment the AI detects a critical symptom, the clinician knows. Now let me show you the less dramatic side — the 99% of interactions that prevent that emergency from ever happening."

---

### Act 3: The Patient Experience (2-3 min)

**SHOW**: Switch patient window to the demo patient Margaret Torres (navigate to her dashboard URL printed by `create_cardiology_service`, or use the red DEV toolbar at the bottom of the patient page → patient switcher dropdown → "Margaret Torres").

**Scene 1 — Dashboard (30s)**:
- Point out: Day 8 hero counter, recovery status, "What to Expect" section
- "The patient wakes up, checks their phone. They know exactly where they are in recovery."

**Scene 2 — Warm Chat (1 min)**:
- Type: *"I'm having trouble sleeping on my back, is that normal after bypass surgery?"*
- When response arrives: "The AI knows this patient had CABG, knows they're Day 8, and pulls from clinical cardiac surgery protocols. It doesn't say 'contact your doctor.' It provides real guidance — and asks a follow-up question to keep the conversation going."
- Point out suggestion chips: "For patients who aren't comfortable typing."

**Scene 3 — Survey (1 min)**:
- Show the survey card on the patient dashboard (KCCQ-12 pending)
- Click to open survey, show 2-3 questions: "This is the Kansas City Cardiomyopathy Questionnaire — a validated clinical instrument. The patient takes it on their phone, the scores flow to the clinician automatically."
- (Don't complete the full survey — just show the UX, then switch to clinician view)

---

### Act 4: The Clinician Workflow (2-3 min)

**SHOW**: Clinician dashboard (right window, already logged in, dark mode)

**Scene 1 — Patient Detail (1 min)**:
- Click a patient (Robert Chen, red, Day 2 CABG)
- **Details tab**: Point out escalation badges, timeline, notes
- **Surveys tab**: Show KCCQ-12 score history with sparkline trends, color-coded scores
- "The clinician sees structured outcomes data alongside the conversational AI — both channels feeding into one view."

**Scene 2 — Research (30s)**:
- Click Research tab, type: *"What are the key risk factors for Robert's recovery?"*
- "Private AI for the clinician — patient context is pre-loaded, backed by RAG from clinical protocols. They can route to specialists: Cardiology, Pharmacy, Nutrition."

**Scene 3 — Take Control (30s)**:
- Send a message to the patient: *"Robert, this is Dr. Smith. I want you at the ER. I'm calling ahead."*
- Point out: "The AI steps aside, the clinician steps in. The patient sees a named human, not 'AI.' When the clinician releases control, the AI resumes."

---

### Act 5: The Leadership View (1 min)

**SHOW**: Switch to Window 3, log in as admin (`admin_test` / `testpass123`)

- "This is what clinical leadership sees. Not the conversations — the outcomes."
- Point out: **Readmission rate** hero card with sparkline trend, **census** triage distribution, **engagement** metrics, **pathway performance**
- Click through time periods: 120d (4.9%) → 30d (3.0%) → 7d (0%). "When the program started, 4.9%. Last 30 days, 3%. Last 7 days, zero. The program is working."
- "This replaces the monthly EHR-to-Excel ritual. Real-time readmission tracking, live quality metrics, exportable to CSV for board presentations."
- If the "Functional Improvement" card shows "No data yet": "This card will be powered by the survey scores you just saw — that integration is the bridge between ePRO data and outcome tracking."
- Flash the pathway admin page: "Pathways are editable — clinical leadership can tune milestones, see per-milestone completion rates."

---

### Act 6: The Opportunity (1-2 min)

**Talk** (no screen changes needed — stay on admin dashboard or return to landing page):

> "What you just saw: three interfaces for three audiences — patient, clinician, administrator. Multi-agent AI with clinical knowledge, real-time escalation, validated survey instruments, and outcome tracking.
>
> Where this goes: **EHR integration** — Epic, Cerner. Patient records flow in, care notes flow back. **Predictive risk scoring** — identify high-risk patients before discharge, not after. **A native mobile app** with push notifications and offline access. **A specialist marketplace** — an AMC's cardiology department builds a specialist agent, every community hospital in their network gets access.
>
> The market is real — CMS penalties, $26B in readmission costs, and every hospital system is looking for this. The product works — you just saw it. And we built this in **[FILL IN: e.g., "two weeks" / "10 days"]**. That's the team's capability."

---

### Timing Summary

| Section | Duration |
|---------|----------|
| Act 1: Why This Matters | ~2 min |
| Act 2: Cold Open (dual-screen escalation) | ~2-3 min |
| Act 3: Patient Experience + Survey | ~2-3 min |
| Act 4: Clinician Workflow | ~2-3 min |
| Act 5: Admin Dashboard | ~1 min |
| Act 6: The Opportunity | ~1-2 min |
| **Total** | **~10-12 min** |

---

### Risk Mitigation

| Risk | Fallback |
|------|----------|
| LLM slow/down | Navigate pre-seeded conversations (Robert Chen has rich multi-turn threads). "Here's a conversation from earlier today." |
| WebSocket fails | Refresh clinician dashboard — escalation is in DB. "In production this is real-time; let me refresh." |
| Survey empty state | Seed data should populate; if not, skip to clinician Surveys tab which has historical scores |
| Admin dashboard empty | DailyMetrics seed data should populate; if not, narrate over empty cards: "In production, these fill from nightly aggregation." |
| Redis/Celery down | Pre-flight catches this. If missed: escalation still creates in DB, refresh clinician dashboard. Restart with `celery -A config worker -l info` |
| Compliance questions | AgentAuditLog, ConsentRecord, `docs/security.md`, TODO-008 (HIPAA BAA provider plan) |

---

## Part 2: Code Changes

### 1. Fix hardcoded version on home page
- **File**: `templates/home.html:38`
- **Change**: Replace `Version 0.1.0` with current version from `VERSION` file
- **Why**: Stale version looks unprofessional

### 2. Friendly agent type labels in clinician chat
- **File**: `templates/clinicians/components/_patient_chat.html:37`
- **Change**: Replace `{{ msg.agent_type|title }}` with a template filter mapping `nurse_triage` → "Nurse Triage", `care_coordinator` → "Care Coordinator", `cardiology` → "Cardiology Specialist", etc.
- **Why**: Raw snake_case labels look unpolished

### 3. Live notification bell with pending escalation count
- **File**: `templates/clinicians/components/_header.html:28` — init Alpine `unreadCount` from `{{ pending_escalation_count }}` context variable
- **File**: `apps/clinicians/views.py` — add `pending_escalation_count` to dashboard view context (`Escalation.objects.filter(status="pending", patient__hospital__in=...).count()`)
- **File**: `static/js/clinician_dashboard.js` (or inline in header template) — on WebSocket `escalation_alert` event, increment `unreadCount` and show the badge. This makes the bell light up in real-time during the dual-screen cold open.
- **Why**: Dead bell undermines the "real-time" narrative; WS increment makes the cold open moment land

### 4. Survey section loading skeleton on patient dashboard
- **File**: `templates/patients/dashboard.html:50-55`
- **Change**: Add a skeleton card inside the `#survey-section` div (matching the admin dashboard's skeleton pattern) so there's no empty flash while the HTMX fetch loads
- **Why**: On a projector with any latency, the empty div is visible before the survey card appears

### 5. Suggestion chip touch targets (TODO-014)
- **File**: `templates/components/_chat_sidebar.html:78-106`
- **Change**: `py-2` → `py-2.5` on suggestion chip buttons (38px → 44px WCAG minimum)

### 6. Demo reset management command
- **File**: New `apps/patients/management/commands/reset_demo.py`
- **Change**: Single command that runs flush + all seed commands in order
- **Why**: One command for demo prep/rehearsal instead of six

### 7. Hand-crafted demo fixture data: surveys + DailyMetrics
- **File**: New `apps/patients/management/commands/seed_demo_data.py` (or extend `create_cardiology_service.py`)
- **Approach**: Write fixture data BY HAND — not generated programmatically. Each data point should feel realistic and serve the demo narrative.
- **Survey data to craft**:
  - KCCQ-12 assignments for ~8-10 key patients (not all 45)
  - Hand-written completed survey instances with specific, realistic scores that tell stories:
    - Robert Chen (red, Day 2): low KCCQ-12 score (35/100) — severely limited post-op, declining trend
    - Linda Rodriguez (yellow, Day 8): moderate scores (55→60→65) — steady improvement
    - Margaret Torres (demo patient): one completed score (58), one pending instance for live demo
    - A "success story" patient: scores climbing from 40→55→72→80 over 4 weeks
    - A "concern" patient: scores plateauing or dipping (65→62→58) — subtle decline
  - Each score should have realistic domain_scores (physical limitation, symptom frequency, quality of life, social limitation)
- **DailyMetrics to craft**:
  - Hand-write ~90 rows with a compelling narrative arc:
    - Early days: higher readmission rate (~12%), fewer patients, fewer messages
    - Mid period: rate drops as engagement increases (~8%), message volume grows
    - Recent: rate approaching target (~5.5%), high engagement, good check-in completion
    - Include realistic variability (not a smooth line — some days spike, weekends dip)
  - Per-hospital rows (SJMC) + aggregate (hospital=NULL) for each day
- **Why**: Programmatically generated data feels fake. Hand-crafted data with narrative intent makes the admin dashboard sparklines and clinician survey trends tell a compelling story during the demo.

### 8. Demo-ready patient with empty conversation
- **File**: Same as item 6 (or `create_cardiology_service.py`)
- **Change**: Add "Margaret Torres, 66, Day 8 CABG, yellow, lifecycle=recovering" with:
  - Empty conversation (for live typing in Act 3)
  - One completed KCCQ-12 instance (score: 58, from 3 days ago)
  - One pending KCCQ-12 instance due today (for live survey walkthrough in Act 3)
  - Print her dashboard URL in command output
- **Why**: Need a clean-slate patient for live typing + live survey during demo

---

## Verification

1. `manage.py reset_demo` loads all seed data successfully
2. Open patient dashboard → survey card with pending KCCQ-12 visible
3. Send a chat message → agent responds
4. Send critical symptom → escalation appears on clinician dashboard via WebSocket
5. Clinician Surveys tab → KCCQ-12 scores with sparklines
6. Admin dashboard → all 9 metric cards populated with data, sparkline trends visible
7. Take-control mode works
8. Notification bell shows pending escalation count
9. Agent type labels display friendly names
10. Home page shows current version
11. `make test` passes — no regressions

## Engineering Notes (from /plan-eng-review)

### Tests to add
- Template filter: `agent_type_display` — test all known agent types + unknown fallback
- View context: `pending_escalation_count` present in clinician dashboard context
- Seed data: `create_cardiology_service` creates SurveyAssignment + SurveyInstance + DailyMetrics rows
- Seed data: Margaret Torres patient exists with empty conversation and pending KCCQ-12
- Reset command: `reset_demo` runs without errors on clean DB

### Implementation notes
- Demo fixture data: write all survey scores and DailyMetrics rows by hand with specific values — do NOT use random generation. Each data point should serve the demo narrative.
- DailyMetrics: use `bulk_create` for the 90 days of hand-crafted rows
- Survey instances: use `bulk_create` for completed instances. Respect `uq_surveys_instance_one_active` constraint (only one pending/available/in_progress instance per patient+instrument)
- Agent type filter: handle unknown types gracefully (fall back to `title()` case)
- Notification bell WS: the `ClinicianDashboardConsumer` already broadcasts `escalation_alert` — just listen for it in the header Alpine component and increment

## NOT in scope (cut for time or deferred)
- Pre-recorded video fallbacks
- Scheduling deep dive
- Keyboard shortcuts demo
- Voice input demo
- Dark mode toggle during demo
- SMS live demo (mention in talking points only)
- Care Plan tab deep dive (flash briefly if time allows)
