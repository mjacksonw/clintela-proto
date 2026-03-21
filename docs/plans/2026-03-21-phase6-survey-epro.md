# Survey/ePRO System Implementation Plan

## Context

Clintela has completed Phase 5 (clinician dashboard) but lacks patient-reported outcome surveys (ePROs) — a critical feature for post-surgical recovery monitoring. Surveys like PHQ-2, KCCQ-12, and daily symptom checks let us capture structured patient data, score it deterministically, and automatically escalate when thresholds are crossed. This directly reduces readmissions by catching deterioration early.

---

## Architecture Overview

New Django app `apps/surveys/` with:
- **Code-defined instruments** (Python classes with scoring logic) seeded into the database via management command
- **Assignment + scheduling** model that creates time-windowed instances via Celery beat
- **One-active-per-type constraint** enforced at the database level
- **System messages** injected into the existing chat (new `role="system"` on AgentMessage)
- **Deterministic scoring engine** that triggers escalations via existing EscalationService

### Accepted Scope Expansions (from CEO Review)
1. **Pathway-driven auto-assignment** — assigning a pathway auto-assigns its default surveys (via `PathwaySurveyDefault` model or JSON on ClinicalPathway)
2. **Agent context integration** — include recent survey scores in AI agent context (ContextService.assemble_full_context)
3. **Survey suggestion chips** — chat sidebar shows "Complete Daily Symptom Check" chip when surveys are available
4. **Score change alerts** — WebSocket alert to clinician when score changes significantly (configurable per instrument via `get_change_alert_config()`)
5. **Patient-facing score history** — dashboard card showing last N completions with CSS-only trend bars

---

## Data Models

### `SurveyInstrument`
The survey template (e.g., "PHQ-2", "KCCQ-12").

| Field | Type | Notes |
|-------|------|-------|
| code | CharField(50, unique) | `"phq_2"`, `"kccq_12"`, `"daily_symptom"` |
| name | CharField(200) | Display name |
| version | CharField(20) | `"1.0"` |
| category | CharField(30) | cardiac / mental_health / general / symptom_check / custom |
| is_active | BooleanField | |
| is_standard | BooleanField | False for hospital-custom |
| hospital | FK(Hospital, null) | Non-null for custom instruments |
| estimated_minutes | IntegerField | |
| metadata | JSONField | Flexible config |

### `SurveyQuestion`
Individual question within an instrument.

| Field | Type | Notes |
|-------|------|-------|
| instrument | FK(SurveyInstrument) | |
| code | CharField(50) | `"q1"`, `"interest"` |
| domain | CharField(50, blank) | Scoring domain: `"physical_limitation"` |
| order | IntegerField | Display order |
| text | TextField | Question text |
| question_type | CharField(20) | likert / numeric / yes_no / multiple_choice / free_text |
| options | JSONField | For likert/MC: `[{"value": 1, "label": "Not at all"}, ...]` |
| min_value / max_value | IntegerField(null) | For numeric scales |
| min_label / max_label | CharField(100) | `"No pain"` / `"Worst pain"` |
| required | BooleanField | |
| help_text | TextField(blank) | |

Unique: `(instrument, code)`. Ordered by `order`.

### `SurveyAssignment`
Links instrument to patient with a schedule. The "subscription" that drives instance creation.

| Field | Type | Notes |
|-------|------|-------|
| patient | FK(Patient) | |
| instrument | FK(SurveyInstrument) | |
| pathway | FK(PatientPathway, null) | If assigned via pathway |
| assigned_by | FK(User, null) | Clinician who assigned |
| schedule_type | CharField(20) | daily / weekly / biweekly / monthly / one_time / on_demand |
| is_active | BooleanField | |
| start_date | DateField | |
| end_date | DateField(null) | Null = indefinite |
| escalation_config | JSONField | `{"total": {"threshold": 3, "severity": "urgent", "type": "clinical"}}` |

Constraint: unique active assignment per (patient, instrument).

### `SurveyInstance`
A single survey occurrence for a patient to complete. **Critical: only one active per patient per instrument.**

| Field | Type | Notes |
|-------|------|-------|
| id | UUIDField(PK) | |
| assignment | FK(SurveyAssignment) | |
| patient | FK(Patient) | Denormalized for queries |
| instrument | FK(SurveyInstrument) | Denormalized |
| status | CharField(20) | pending / available / in_progress / completed / expired / missed |
| due_date | DateField | Target date |
| window_start | DateTimeField | When it becomes available |
| window_end | DateTimeField | When it expires |
| started_at | DateTimeField(null) | |
| completed_at | DateTimeField(null) | |
| total_score | FloatField(null) | Populated on completion |
| domain_scores | JSONField | `{"physical_limitation": 75.0}` |
| raw_scores | JSONField | `{"q1": 3, "q2": 5}` |
| escalation_triggered | BooleanField | |
| escalation | FK(Escalation, null) | |
| scoring_error | BooleanField(default=False) | True if scoring failed — instance still marked completed, answers preserved |

**Database constraint**: `UniqueConstraint(fields=["patient", "instrument"], condition=Q(status__in=["available", "in_progress", "pending"]))` — enforces one-active-per-type at the DB level.

### `SurveyAnswer`
Individual answer within a completed instance.

| Field | Type | Notes |
|-------|------|-------|
| instance | FK(SurveyInstance) | |
| question | FK(SurveyQuestion) | |
| value | JSONField | Flexible: int, string, bool, list |
| raw_value | CharField(500) | Original text for display |

Unique: `(instance, question)`.

---

## Instrument Registry (Code-Defined)

Hybrid approach: Python classes define questions + scoring logic, management command seeds the DB.

```
apps/surveys/instruments/
    __init__.py       # InstrumentRegistry (class-based registry with @register decorator)
    base.py           # BaseInstrument ABC: get_questions(), score(), get_domains(), get_escalation_defaults()
    phq_2.py          # 2 questions, score 0-6, threshold >= 3
    daily_symptom.py  # ~5 questions: pain, swelling, fever, wound, mood
    kccq_12.py        # 12 questions, 4 domains, score 0-100
    saq_7.py          # 7 questions, 3 domains
    afeqt.py          # AF-specific quality of life
    promis.py         # PROMIS global health
```

Each instrument's `score()` method returns a `ScoringResult` dataclass:
```python
@dataclass
class ScoringResult:
    total_score: float
    domain_scores: dict[str, float]
    raw_scores: dict[str, Any]
    interpretation: str        # "Minimal depression", "Moderate limitation"
    escalation_needed: bool
    escalation_severity: str   # "urgent", "critical"
    escalation_reason: str
```

Management command: `python manage.py seed_instruments` — upserts instruments + questions from registry.

---

## System Messages in Chat

Add `"system"` to `AgentMessage.role` choices (line 95 of `apps/agents/models.py`). System messages carry typed payloads in the existing `metadata` JSONField:

**Completion message:**
```python
AgentMessage(
    conversation=patient_conversation,
    role="system",
    content="You completed the Patient Health Questionnaire. Score: 2/6 — Minimal concerns.",
    metadata={
        "type": "survey_completed",
        "survey_instance_id": "uuid",
        "instrument_code": "phq_2",
        "instrument_name": "Patient Health Questionnaire-2",
        "total_score": 2.0,
        "max_score": 6.0,
    },
)
```

**Missed message:**
```python
AgentMessage(
    conversation=patient_conversation,
    role="system",
    content="Your daily symptom check was not completed.",
    metadata={
        "type": "survey_missed",
        "survey_instance_id": "uuid",
        "instrument_code": "daily_symptom",
        "instrument_name": "Daily Symptom Check",
    },
)
```

**Template rendering** (`_message_bubble.html`): System messages render as centered, full-width cards with:
- **Completed**: Success Green (#059669) 4px left border, Lucide `circle-check` icon, score as bold number, interpretation as muted text, "View Details" link
- **Missed**: Warning Amber (#D97706) 4px left border, Lucide `alert-triangle` icon, instrument name, muted text — NOT red (reserve Danger Red for clinical escalations only)
- Screen reader: `role="status"`, text includes full context: "Survey completed: PHQ-2, score 2 of 6, minimal concerns"

---

## Celery Tasks

### `create_survey_instances` (daily at 6:03 AM)
1. Query all active `SurveyAssignment` records
2. For each, check if an active instance already exists (status in pending/available/in_progress)
3. If no active instance and schedule says one is due: create new `SurveyInstance` with appropriate window
   - Daily: window = today 6am → tomorrow 6am
   - Weekly: window = Monday 6am → Sunday midnight
   - Monthly: window = 1st 6am → last day midnight
4. If an old instance is still `available` (never started), transition it to `expired` first

### `expire_survey_instances` (every 30 minutes)
1. Find instances where status = `available` AND `window_end < now` → transition to `missed`
2. Find instances where status = `in_progress` AND `window_end + 2 hours < now` → transition to `missed` (2-hour grace period for patients mid-completion)
3. Inject missed system message into patient's active chat conversation
4. Send notification via NotificationService
5. If 3+ consecutive misses for same instrument: create routine escalation ("Patient has missed N consecutive {instrument_name} surveys")

---

## Patient-Facing UI

### Dashboard Survey Card
HTMX-loaded section on `templates/patients/dashboard.html`, placed prominently after the "Recovery Status Hero" card:

```html
<div hx-get="/patient/surveys/available/"
     hx-trigger="load, surveyCompleted from:body"
     hx-swap="innerHTML">
</div>
```

**Visual spec per card:** `.card` with 4px left border color-coded:
- Amber (#D97706) if due today
- Primary Blue (#2563EB) if in-progress (partially completed)
- Gray 300 (#D6D3D1) if upcoming (not yet due)

Each card: Lucide `clipboard-list` icon, instrument name (H4), subtitle "~2 min · Due today" or "~8 min · Due Monday". "Start Survey" button (Primary Blue). Cards use `.animate-in` with staggered delays.

**Ordering:** Multiple pending surveys sorted by `estimated_minutes` ascending (shortest first — quick wins build completion momentum).

**Loading state:** Skeleton card (matches `.card` dimensions, shimmer animation).

**Empty state — "All caught up!":**
- Lucide `clipboard-check` icon (40px, opacity-30, centered)
- Headline: "All caught up!" (H3)
- Subtext: "Your next check-in is **[day]**. Keep up the great work with your recovery." (Body, Gray 500)
- If no future surveys scheduled: "No check-ins scheduled right now."
- Uses existing empty state pattern (`color: var(--color-text-secondary)`)

### Survey Modal (Alpine.js Wizard)
Full-screen modal overlay following existing Alpine.js modal pattern (`_keyboard_help.html`):
- `role="dialog"`, `aria-modal="true"`, `aria-label="[Instrument name] survey"`
- Focus trapped within modal while open
- Escape key closes wizard (soft exit — see abandon flow below)

**Intro screen (before Question 1):**
- Instrument display name (H3, Satoshi 600)
- Estimated time badge: "~2 minutes" (Neutral badge, Gray 100 bg)
- Purpose statement: "This helps your care team track your recovery." (Body, Gray 600)
- "Begin" button (Primary Blue, full width)
- X button to close (returns to dashboard)

**Progress bar:**
- Teal (#0D9488) fill on Gray 200 track, 4px height, `rounded-full`
- Label above: "Question 2 of 5" (Body Small, Gray 500)
- `aria-live="polite"` region announces progress to screen readers
- Smooth width transition: `transition: width 300ms ease-out`
- For domain-grouped instruments: show domain name as section header

**Question display:**
- **Instrument decides grouping**: Each instrument defines a `display_mode` — short instruments (PHQ-2, daily symptom) show all questions on one screen; longer instruments (KCCQ-12, SAQ-7) group by domain with one domain per screen. Defined in `BaseInstrument.get_display_config()`.
- Question text (Body Large, 18px, Gray 700)
- Help text below question in muted color (Gray 500, 14px) when `help_text` field is populated
- On question advance: focus moves to question text (`tabindex="-1"` on question heading)

**Input patterns:**
- **Likert/multiple-choice:** Stacked full-width buttons, 56px height, full width, 16px padding. Default: White bg, Gray 200 border, Gray 700 text. Selected: Primary Blue (#2563EB) 2px border, Blue-50 (#EFF6FF) bg, Primary Blue text. ARIA: `role="radiogroup"` on container, `role="radio"` + `aria-checked` on each button. Keyboard: Arrow keys navigate, Space/Enter select.
- **Numeric scales (0-10):** Horizontal row of number buttons, 44px × 44px each, same selected state. Min/max labels at ends ("No pain" / "Worst pain").
- **Yes/No:** Two stacked full-width buttons (same pattern as Likert)
- **Free text:** Standard form input following `caregivers.html` styling (48px height, 6px radius, 16px font)
- Build as **reusable template include** `templates/components/_button_group.html` with params: `options`, `name`, `selected`, `columns`

**Navigation:**
- Back/Next buttons, bottom-anchored on mobile
- Each "Next" saves answers via HTMX POST (partial progress preserved)
- Final "Submit" triggers scoring + chat message injection

**Post-completion screen (after final submit):**
- Checkmark animation (Lucide `circle-check`, Success #059669, 48px)
- Score interpretation headline: "Minimal concerns" / "Your recovery is on track" (H3)
- Warm body text: "Thank you for completing this check-in. Your care team will review your responses."
- "Back to Dashboard" button (Primary Blue, full width on mobile) — appears after 2-3s intentional pause
- **If scoring fails** (`scoring_error=True`): Show "Your responses have been saved. Your care team will review your answers shortly." — no score displayed, no error language

**Abandon flow:**
- Tapping X closes wizard immediately (no confirmation dialog)
- Answers already saved via partial POST on each "Next"
- Reopening the survey resumes at the first unanswered question
- Dashboard card shows "In Progress" badge (Primary Blue) for partially completed surveys

**Responsive:**
- Mobile (0-639px): Full-screen overlay, no margin, bottom-anchored nav buttons, question fills viewport
- Tablet (640-1023px): Centered modal, max-width 560px, 24px margin
- Desktop (1024+): Centered modal, max-width 560px, vertically centered

`surveyWizard()` Alpine component manages state

### Chat Integration
- **Suggestion chips**: When surveys are available, add chips like "Complete Daily Symptom Check" to the chat sidebar (extends existing chip logic in `_chat_sidebar.html`)
- **AI context**: Include recent survey scores in agent context (add to `ContextService.assemble_full_context()` in `apps/agents/services.py`) so the agent can reference them naturally
- System messages appear inline in chat history (completed = Success Green, missed = Warning Amber)
- Clicking "View Details" on a completed survey system message links to results

### Patient Score History
HTMX-loaded section on patient dashboard (below survey card):
- Shows last 5 completions per instrument with CSS-only horizontal bars (height 8px, rounded, color-coded by interpretation)
- Color: Teal (#0D9488) for improving/stable, Warning Amber (#D97706) for worsening
- Each bar: `role="img"` with `aria-label` describing the score: "PHQ-2 score: 2 out of 6, minimal concerns, March 21"
- **Loading state:** Skeleton bars (shimmer animation)
- **Empty state:** Lucide `bar-chart-3` icon (40px, opacity-30), "No check-ins completed yet." (Body, Gray 500)

---

## Clinician-Facing UI

### Survey Results View
Accessible from:
- Chat system message "View Details" link
- Care Plan tab survey section

Shows:
- Header: instrument name, patient, date, total score with interpretation
- Domain scores as horizontal bars
- Individual answers table
- Score trend (sparkline comparing last N completions)

### Care Plan Tab — Survey Summary
Add a "Surveys" section to `_tab_care_plan.html` showing:
- Active assignments with last completion date and score
- Missed/overdue indicators (Warning Amber dot, not red — matches missed survey color decision)
- Mini trend indicator (sparkline)
- Link to full survey detail in dedicated tab

### Surveys Tab (5th Tab)
New dedicated tab in clinician dashboard. **Scores-first layout:**

- **Top section:** Score trend sparklines per instrument (one row per active instrument — inline CSS/SVG sparkline 60×20px + latest score + delta badge). Teal for improving, Amber for declining.
- **Middle section:** Recent completions table (date, instrument, score, interpretation, delta from previous). Compact 16px padding per DESIGN.md clinician specs.
- **Bottom section:** Assignment management (active assignments with schedule info, assign/deactivate controls)

**Loading state:** Skeleton table (shimmer). **Empty state:** "No surveys assigned for this patient." with "Assign Survey" button.

### Tools Tab Integration
Add "Manage Surveys →" link to `_tab_tools.html` that switches to Surveys tab (assignment controls live only in Surveys tab to avoid DRY violation)

### Score Change Alerts
When a patient completes a survey, compare score to previous completion of same instrument.
- Each instrument defines `get_change_alert_config()` returning `{"min_delta": 10, "direction": "decrease", "severity": "warning"}` (or similar)
- If delta exceeds threshold: send WebSocket alert to clinician dashboard via existing `ClinicianDashboardConsumer`
- Alert appears as a notification badge, not a full escalation

### Pathway Auto-Assignment
Add `PathwaySurveyDefault` model (or JSON field on `ClinicalPathway`):
- Maps pathway → list of default survey configs: `[{"instrument_code": "kccq_12", "schedule_type": "weekly", "escalation_config": {...}}]`
- **Django post_save signal** on PatientPathway (in surveys app's `apps.py` `ready()`) auto-creates `SurveyAssignment` records — keeps dependency unidirectional (surveys → pathways, not vice versa)
- Clinician can still modify/deactivate individual assignments after auto-creation

---

## Scoring & Escalation

`ScoringEngine.score_instance()`:
1. Looks up instrument in `InstrumentRegistry`
2. Builds answers dict from `SurveyAnswer` records
3. Calls instrument's `score()` method (pure Python, deterministic)
4. Persists scores on `SurveyInstance`

`ScoringEngine.check_escalation()`:
1. Reads `escalation_config` from assignment (falls back to instrument defaults)
2. Checks total score against threshold
3. Checks each domain score against domain thresholds
4. If exceeded: calls `EscalationService.create_escalation()` + `NotificationService.create_escalation_notification()`
5. Links escalation to instance

---

## File Structure

```
apps/surveys/
    __init__.py
    apps.py
    models.py                    # All 5 models
    admin.py                     # Admin registration
    urls.py                      # Patient-facing URLs
    views.py                     # Patient-facing views
    services.py                  # SurveyService (assignment, completion, chat injection)
    scoring.py                   # ScoringResult, ScoringEngine
    tasks.py                     # Celery tasks
    instruments/
        __init__.py              # InstrumentRegistry
        base.py                  # BaseInstrument ABC
        phq_2.py
        daily_symptom.py
        kccq_12.py
        saq_7.py
        afeqt.py
        promis.py
    management/commands/
        seed_instruments.py
    tests/
        __init__.py
        test_models.py
        test_scoring.py
        test_instruments.py
        test_services.py
        test_tasks.py
        test_views.py
```

---

## Implementation Phases

### Phase A: Foundation
1. Create `apps/surveys/` app, add to `LOCAL_APPS`
2. Write all models, run migrations
3. Add `role="system"` to AgentMessage choices, run migration
4. Create instrument registry + base class
5. Implement `ScoringResult` dataclass and `ScoringEngine`
6. Implement PHQ-2 + daily symptom instruments
7. Create `seed_instruments` management command
8. Unit tests for models, scoring, instruments

### Phase B: Services & Tasks
1. Write `SurveyService` (create_assignment, create_instance, start, answer, complete, inject_chat_message)
2. Write Celery tasks (create_instances, expire_instances)
3. Add Celery Beat schedule entries
4. Integration tests for tasks and services

### Phase C: Patient UI
1. `templates/components/_button_group.html` — reusable button-group component (Likert, MC, yes/no, numeric)
2. Patient views + URLs
3. `_survey_card.html` — dashboard card with empty state, loading skeleton, ordering logic
4. `_survey_modal.html` — Alpine.js wizard modal with intro screen, progress bar, post-completion screen, abandon flow
5. `_survey_system_message.html` — chat system message rendering (Success Green completed, Warning Amber missed)
6. Update `_message_bubble.html` for `role="system"` rendering
7. `_score_history.html` — patient score history with CSS bars and a11y labels
8. Add survey card + score history sections to patient dashboard
9. View tests

### Phase D: Clinician UI
1. Clinician survey views (results, trend, assign/deactivate)
2. `_tab_surveys.html` — Surveys tab with scores-first layout (sparklines top, completions middle, assignments bottom)
3. `_survey_results.html` — results detail view
4. Integrate survey section into Care Plan tab (with Warning Amber missed indicators)
5. Add "Manage Surveys →" link to Tools tab
6. View tests

### Phase E: All Instruments, Escalation & Design System
1. Implement all six instruments: PHQ-2, Daily Symptom, KCCQ-12, SAQ-7, AFEQT, PROMIS
2. Wire escalation checking into completion flow
3. End-to-end test: assign → complete → score → escalate
4. Admin registration
5. Add "Data Visualization" section to DESIGN.md (sparklines, score bars, delta badges, trend indicators)
6. Ensure 90%+ test coverage

---

## Verification

1. `python manage.py seed_instruments` — seeds all instruments
2. Assign PHQ-2 to test patient via clinician Tools tab
3. Patient dashboard shows survey card
4. Complete survey via modal wizard
5. Chat shows green system message with score
6. Clinician can click "View Details" to see results
7. Set PHQ-2 threshold to 1, complete with score >= 1 → escalation triggers
8. Let a daily survey expire → chat shows amber missed message
9. Verify only one active instance exists per type (try to create duplicate)
10. `POSTGRES_PORT=5434 pytest apps/surveys/` — all tests pass, 90%+ coverage

---

## Performance Notes

- Use `select_related('instrument', 'assignment')` and `prefetch_related('answers__question')` on SurveyInstance querysets
- `create_survey_instances` task should use `bulk_create` for batch instance creation
- Add DB index: `Index(fields=["patient", "instrument", "status", "-completed_at"])` for score history queries

## Design System Notes

All new components use DESIGN.md tokens:
- **Padding:** Patient cards 24px (space-6), clinician cards 16px (space-4)
- **Border radius:** 8px on cards, 6px on buttons/inputs
- **Typography:** Satoshi throughout, 16px minimum for patients, 14px for clinician data
- **Colors:** Primary Blue actions, Teal accents/progress, Success Green completed, Warning Amber missed
- **Dark mode:** All new surfaces use CSS custom properties (`var(--color-surface)`, etc.)
- **Icons:** Lucide library, 20px default size
- **Animations:** `animate-in` on cards, `transition 200ms ease-out` on interactive elements

## Additional Test Coverage (from Eng Review)

Beyond the 6 test files in the plan, ensure explicit tests for:
- Score change alert logic (first completion = no alert, subsequent with delta = alert)
- Pathway auto-assign signal (PatientPathway post_save creates SurveyAssignments)
- Agent context integration (ContextService includes survey scores)
- Error paths: scoring failure → scoring_error=True, no conversation → skip chat injection, instrument not in registry → graceful skip

## Observability

- Log on completion: `instrument_code`, `patient_id`, `total_score`, `duration_seconds` (started_at → completed_at), `escalation_triggered`
- Log on miss: `instrument_code`, `patient_id`, `consecutive_miss_count`
- Structured logging via existing `AgentAuditLog` pattern

---

## Key Files Modified (Existing)

- `apps/agents/models.py:95` — add `("system", "System")` to role choices
- `templates/components/_message_bubble.html` — add system message rendering
- `templates/patients/dashboard.html` — add survey card HTMX section
- `templates/clinicians/components/_tab_care_plan.html` — add surveys section
- `templates/clinicians/components/_tab_tools.html` — add survey assignment UI
- `config/settings/base.py` — add `apps.surveys` to LOCAL_APPS, Celery Beat entries
- `apps/clinicians/urls.py` — add survey-related clinician routes
- `apps/clinicians/views.py` — add survey results/assign/deactivate views
- `static/js/clinician-dashboard.js` — add 5th tab (surveys), update keyboard shortcut 5 for surveys tab
- `apps/agents/services.py` — add survey scores to ContextService.assemble_full_context()
- `templates/components/_chat_sidebar.html` — add survey suggestion chips
- `templates/components/_button_group.html` — NEW reusable button-group component
- `DESIGN.md` — add Data Visualization section
- `apps/pathways/models.py` or new through-model — pathway survey defaults for auto-assignment
