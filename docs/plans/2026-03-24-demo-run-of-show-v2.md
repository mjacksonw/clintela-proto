# Clintela Demo Run-of-Show v2

## Context

Demo day. Internal team presentation to decide go/no-go on pursuing Clintela as a business. Product is at v0.2.12+ with 7 phases shipped: patient interface, multi-agent AI, SMS/voice/WebSocket, clinical knowledge RAG, clinician dashboard, surveys/ePRO + admin KPI dashboard, and the Clinical Intelligence Layer with vitals monitoring, rules-based alerts, and OMOP bridge. Plus Spanish i18n.

**Audience**: Teammates evaluating the opportunity. The demo must answer:
1. Is the market real? (CMS penalties, $26B readmissions)
2. Is the product useful? (show all three interfaces working — with clinical intelligence as the differentiator)
3. Can we execute? (depth of what's built, speed of iteration, vision for what's next)

**Target duration**: 12-15 minutes + open discussion.

---

## Pre-Demo Setup

**Seed the database:**
```bash
ENABLE_CLINICAL_DATA=True manage.py reset_demo
```
This single command runs: flush, seed_pathways, seed_cardiac_pathways, seed_instruments, create_test_clinician, create_test_admin, create_cardiology_service, seed_demo_data, seed_clinical_data (4 cardiac scenarios with 30 days of vitals).

**Environment:**
```bash
# .env must include:
ENABLE_CLINICAL_DATA=True
```

**Browser setup:**
- **Window 1 (left half)**: Patient dashboard, pre-authed as demo patient (clean conversation)
- **Window 2 (right half)**: Clinician dashboard at `/clinician/login/` — credentials: `dr_smith` / `testpass123`
- **Window 3 (hidden)**: Admin dashboard at `/admin-dashboard/login/` — credentials: `admin_test` / `testpass123`
- Clinician in **dark mode**, patient in **light mode**
- Chrome maximized, bookmarks bar hidden
- Display must be at least **1280px wide**

**Pre-flight check:**
- LLM backend running + test one chat message
- Redis running (`redis-cli ping` → PONG)
- Celery running (`celery -A config inspect active` → shows worker)
- WebSocket connection working (open clinician dashboard, check browser console for WS connect)
- Vitals tab shows charts for Gordon Bryant (the CHF scenario patient)

---

## Act 1: Why This Matters (2 min)

**SHOW**: Clintela landing page at `/`

**Scripted framing** (speak over the landing page):

> "Hospital readmissions cost $26 billion a year in the US. CMS penalizes hospitals whose readmission rates exceed the national average — the Hospital Readmissions Reduction Program. The core problem: the moment a patient leaves the hospital after surgery, they enter a black box. No one is watching. They have questions at 2am, they miss warning signs, they forget medication instructions. By the time something goes wrong, they're back in the ER.
>
> We built Clintela to be the 24/7 care team that fills that gap. AI agents that know the patient, know the surgery, know the clinical protocols — and seamlessly hand off to human clinicians when it matters. And as of this week, Clintela also knows what's happening to the patient medically — wearable data, vitals, lab trends — not just what they're saying in chat. Let me show you."

---

## Act 2: The Cold Open — Dual Screen (2-3 min)

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

## Act 3: The Patient Experience (2-3 min)

**SHOW**: Switch patient window to Margaret Torres (use the red DEV toolbar → patient switcher dropdown → "Margaret Torres").

**Scene 1 — Dashboard (30s)**:
- Point out: Day 8 hero counter, recovery status, "What to Expect" section
- If My Health card visible: "She can see her own vitals trending — heart rate, weight, blood pressure. Presented in warm, non-clinical language."
- "The patient wakes up, checks their phone. They know exactly where they are in recovery."

**Scene 2 — Warm Chat (1 min)**:
- Type: *"I'm having trouble sleeping on my back, is that normal after bypass surgery?"*
- When response arrives: "The AI knows this patient had CABG, knows they're Day 8, and pulls from clinical cardiac surgery protocols. It doesn't say 'contact your doctor.' It provides real guidance."

**Scene 3 — Survey (30s)**:
- Show the survey card on the patient dashboard (KCCQ-12 pending)
- Click to open, show 2-3 questions: "This is the Kansas City Cardiomyopathy Questionnaire — a validated clinical instrument. Scores flow to the clinician automatically."

**Scene 4 — Spanish (30s)** *(Optional — nice "one more thing" if time allows)*:
- Use the language selector to switch to Spanish
- "Full Spanish translation, not machine-translated strings. Every patient-facing surface — chat, surveys, dashboard, error messages."
- Switch back to English

---

## Act 4: The Clinician Workflow (3-4 min)

**SHOW**: Clinician dashboard (right window, already logged in, dark mode)

**Scene 1 — Patient Detail (1 min)**:
- Click a patient (Robert Chen, red, Day 2 CABG)
- **Details tab**: Point out escalation badges, timeline, notes
- **Surveys tab**: Show KCCQ-12 score history with sparkline trends, color-coded scores
- "The clinician sees structured outcomes data alongside the conversational AI — both channels feeding into one view."

**Scene 2 — Vitals Tab (1-1.5 min)** *(This is the new centerpiece)*:
- Switch to Gordon Bryant (the CHF decompensation patient) in the patient list
- Click the **Vitals** tab (or press `6`)
- Point out:
  - **Snapshot bar**: trajectory badge (likely "concerning" or "deteriorating"), risk score, data completeness, active alerts
  - **Charts**: Heart rate, systolic BP, body weight with normal range bands (teal shading). "30 days of data from Apple Watch and Withings Scale. Look at the weight chart — trending up over the last few days."
  - **Active alerts**: Expand one to show the rule rationale. "This alert says: 'Weight gain of 2.5 kg over 3 days combined with elevated heart rate — pattern consistent with CHF decompensation.' That's not AI hallucination — that's a deterministic rules engine with FDA-compliance-ready rationale."
- "In the old world, this patient sees the cardiologist at the 4-week follow-up. The weight gain started on day 10. Clintela caught it on day 12. That's the difference between an office visit adjustment and an ER readmission."

**Scene 3 — Research (30s)**:
- Click Research tab, type: *"What are the key risk factors for this patient's recovery?"*
- "Private AI for the clinician — patient context is pre-loaded, backed by RAG from clinical protocols."

**Scene 4 — Take Control (30s)**:
- Send a message to the patient: *"Gordon, this is Dr. Smith. I want to adjust your diuretic dose. Can you come in tomorrow?"*
- "The AI steps aside, the clinician steps in. The patient sees a named human. When the clinician releases, the AI resumes."

---

## Act 5: The Leadership View (1-1.5 min)

**SHOW**: Switch to Window 3, log in as admin (`admin_test` / `testpass123`)

- "This is what clinical leadership sees. Not the conversations — the outcomes."
- Point out: **Readmission rate** hero card with sparkline, **census** triage distribution, **escalation response time** (15 min avg), **pathway performance**
- Click through time periods: 120d → 30d → 7d. "When the program started, readmission rate was higher. Last 30 days, 3.1%. The trend is down. The program is working."
- Point out **engagement**: "67% at 7 days — patients still onboarding. 91% at 90 days — established patients are highly engaged."
- "This replaces the monthly EHR-to-Excel ritual. Real-time quality metrics, exportable to CSV for board presentations."

---

## Act 6: The Vision (2 min)

**Talk** (stay on admin dashboard or return to landing page):

> "What you just saw: three interfaces for three audiences — patient, clinician, administrator. Multi-agent AI with clinical knowledge. Real-time escalation. Validated survey instruments. Clinical intelligence with vitals monitoring, trend detection, and rules-based alerts. And it works in Spanish.
>
> The clinical intelligence layer is the moat. The rules engine uses OMOP concept IDs — the same vocabulary as Epic's OMOP pipeline. When a health system connects their EHR, the data maps directly to our observation model. No translation layer. We built the bridge before the highway exists.
>
> Where this goes next:
> - **EHR integration** — Epic FHIR, Cerner. Patient records flow in, care notes flow back.
> - **Predictive risk scoring** — move from rules-based alerts to ML models trained on our observation data.
> - **Proactive outreach** — the system detects missing weight data and sends a gentle nudge: 'Hey Margaret, we haven't seen a weight reading in a couple days. Everything okay?'
> - **Native mobile app** with push notifications and offline access.
> - **A specialist marketplace** — an AMC's cardiology department builds a specialist agent, every community hospital in their network gets access.
>
> The market is real — CMS penalties, $26B in readmission costs. The product works. And we built this in **[X days]**. That's the team's capability."

---

## Timing Summary

| Section | Duration |
|---------|----------|
| Act 1: Why This Matters | ~2 min |
| Act 2: Cold Open (dual-screen escalation) | ~2-3 min |
| Act 3: Patient Experience (chat + survey + optional i18n) | ~2-3 min |
| Act 4: Clinician Workflow (vitals is centerpiece) | ~3-4 min |
| Act 5: Admin Dashboard | ~1-1.5 min |
| Act 6: The Vision | ~2 min |
| **Total** | **~12-15 min** |

---

## Key Demo Patients

| Patient | Status | Scenario | Used In |
|---------|--------|----------|---------|
| **Margaret Torres** | Yellow, Day 8, CABG | Demo patient — clean conversation, pending survey | Act 3 (patient experience) |
| **Robert Chen** | Red, Day 2, CABG | Critical escalation, rich conversation history | Act 2 (cold open), Act 4 Scene 1 |
| **Gordon Bryant** | Varies, CHF scenario | 30 days vitals, weight gain trend, active alerts | Act 4 Scene 2 (vitals centerpiece) |
| Any patient | — | — | Act 4 Scene 4 (take control) |

---

## Risk Mitigation

| Risk | Fallback |
|------|----------|
| LLM slow/down | Navigate pre-seeded conversations (Robert Chen has rich threads). "Here's a conversation from earlier today." |
| WebSocket fails | Refresh clinician dashboard — escalation is in DB. "In production this is real-time; let me refresh." |
| Vitals tab empty | `ENABLE_CLINICAL_DATA=True` must be set. If forgotten: "This is feature-flagged; let me enable it." (flip .env, restart) |
| Clinical seed data missing | Run `python manage.py seed_clinical_data` separately. Takes ~10 seconds. |
| Survey empty state | Seed data should populate; if not, skip to clinician Surveys tab |
| Admin dashboard empty | DailyMetrics seed data should populate; if not, narrate over empty cards |
| Spanish not loading | Check `locale/es/` exists and `LANGUAGE_CODE` in settings. Non-critical — skip this beat. |
| Redis/Celery down | Pre-flight catches this. Escalation still creates in DB; refresh clinician dashboard. |
| Compliance questions | AgentAuditLog, ConsentRecord, `docs/security.md`, OMOP concept IDs, FDA-compliant rule rationale |

---

## What Changed from v1

1. **Added**: Act 4 Scene 2 — Vitals tab is now the clinician centerpiece (was Research + Take Control only)
2. **Added**: Act 3 Scene 4 — Spanish i18n optional beat
3. **Added**: Act 3 Scene 1 — My Health card mention on patient dashboard
4. **Updated**: Act 6 — Vision section now leads with clinical intelligence as the moat, OMOP bridge, and proactive outreach
5. **Updated**: Pre-demo setup — `ENABLE_CLINICAL_DATA=True` required, `seed_clinical_data` added to `reset_demo`
6. **Updated**: Key patients table — Gordon Bryant added for vitals demo
7. **Timing**: Extended to 12-15 min (was 10-12) to accommodate vitals walkthrough
