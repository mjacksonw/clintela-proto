# Phase 5: Clinician Dashboard UI

## Context

Phases 1-4 are complete: Django backend, multi-agent AI, patient UI with chat/voice/SMS, clinical knowledge RAG with specialist agents, patient lifecycle state machine, caregiver/consent management. The backend already has rich escalation tracking (with SLA/priority scoring), real-time WebSocket consumers for clinicians, and notification infrastructure — but zero clinician-facing UI. Phase 5 builds the clinician interface.

The user wants two main surfaces:
1. **Three-panel dashboard** — patient list, patient detail (4 tabs), patient chat
2. **Scheduling UI** — availability management, appointment oversight

### Accepted Scope Expansions (CEO Review)
- Shift handoff summary card on dashboard load
- Keyboard shortcuts (j/k navigate, 1-4 tabs, e acknowledge, / search, ? help)
- Patient timeline in Details tab (collapsed by day/week, expandable summaries)
- Desktop notifications + audio for critical escalations (Web Notification API)
- Export handoff notes button (clipboard copy via existing `generate_structured_handoff`)
- Bulk escalation acknowledge (checkboxes + batch POST)
- Take Control mode (clinician takes over patient chat thread)

### Security Fixes (from review)
- Fix `apps/agents/consumers.py:255` — add auth to `ClinicianDashboardConsumer`
- Fix `apps/agents/api.py:200` — replace hacky clinician_id-from-body with proper session auth
- All views with `patient_id` must verify patient belongs to clinician's hospitals (IDOR prevention)

---

## Sub-Phase 5A: Foundation (Models, Auth, Shell)

### New Models in `apps/clinicians/models.py`

```
ClinicianNote
  - patient FK, clinician FK
  - content (text), note_type (quick_note | clinical_observation | follow_up | care_plan_note)
  - is_pinned (bool), created_at, updated_at

ClinicianAvailability
  - clinician FK
  - day_of_week (int 0-6), start_time, end_time
  - is_recurring (bool), effective_date (nullable, for one-offs)
  - unique_together: [clinician, day_of_week, start_time] for recurring

Appointment
  - id (UUID), patient FK, clinician FK, created_by FK (User)
  - appointment_type (follow_up | virtual_visit | check_in | consultation)
  - status (scheduled | confirmed | in_progress | completed | cancelled | no_show)
  - scheduled_start, scheduled_end (DateTimeField)
  - notes (text), virtual_visit_url (char, blank)
  - indexes on [clinician, scheduled_start], [patient, scheduled_start]
```

### Model change: `apps/agents/models.py`
- Add `("clinician_research", "Clinician Research")` to `AgentConversation.AGENT_TYPES`
- Add `("clinician", "Clinician")` to `AgentConversation.AGENT_TYPES` (for injected messages)
- Add nullable `clinician` FK to `AgentConversation` for research conversations
- Add `paused_by` FK (nullable) to User + `paused_at` DateTimeField for take-control mode

### Auth: `apps/clinicians/auth.py`
- `get_authenticated_clinician(request)` — returns Clinician if `request.user.is_authenticated` and `role == "clinician"`
- `@clinician_required` decorator — redirects to `clinicians:login` if not a clinician
- **Design for graduation**: Auth module isolated so we can later add passkeys, TOTP MFA, magic links, and SAML/SSO without touching views. The decorator is the single enforcement point.

### Views: `apps/clinicians/views.py`
- `clinician_login_view` / `clinician_logout_view` — Django's built-in username/password auth for now
- Auth views structured to be replaceable (login view delegates to an auth backend, not hardcoded to password check)

### URLs: `apps/clinicians/urls.py` (new file)
- Uncomment `config/urls.py` line 38: `path("clinician/", include("apps.clinicians.urls", namespace="clinicians"))`

### Admin: `apps/clinicians/admin.py` (new file)
- Register Clinician, ClinicianNote, Appointment, ClinicianAvailability

### Templates
- `templates/base_clinician.html` — extends `base.html`, three-panel layout shell
- `templates/clinicians/login.html`
- `templates/clinicians/dashboard.html` — extends `base_clinician.html`, includes handoff summary
- `templates/clinicians/components/_header.html` — logo, nav (dashboard/schedule), notification bell, user menu
- `templates/clinicians/components/_handoff_summary.html` — shift handoff briefing card
- `templates/clinicians/components/_keyboard_help.html` — shortcuts modal (triggered by `?`)

### JavaScript
- `static/js/clinician-dashboard.js` — Alpine `clinicianDashboard()` component:
  - Selected patient, panel loading, WebSocket connections
  - Keyboard shortcuts: `j/k` navigate list, `1-4` switch tabs, `e` acknowledge escalation, `/` focus search, `Escape` deselect, `?` show help
  - Desktop notification permission request + critical escalation alerts (Web Notification API + Web Audio)
  - Notification state management

### Shift Handoff Summary
- On dashboard load, query changes since `request.user.last_login`:
  - New/resolved escalations, patient status changes, missed check-ins
- Render `_handoff_summary.html` — dismissible card above the patient list
- First login: show "Welcome" card instead
- Updates `last_login` on dashboard view (Django's `update_last_login` signal)

### Management Command
- `apps/clinicians/management/commands/create_test_clinician.py` — creates hospital, clinician user, 5 patients at varying triage levels with escalations/conversations, prints login URL

---

## Sub-Phase 5B: Patient List (Left Panel)

### View: `patient_list_fragment` (HTMX GET)
- Queries patients from clinician's hospitals
- Annotates: pending escalation count, last message timestamp, unread count
- Sortable: severity (default), alphabetical, last contacted
- Searchable: name, MRN
- Builds "status line" per patient — escalation reason excerpt, last AI message summary, or lifecycle/days-post-op fallback

### Templates
- `templates/clinicians/components/_patient_list.html` — search bar, sort buttons, scrollable list
- `templates/clinicians/components/_patient_list_item.html` — triage color dot, name, surgery type, status line, unread badge, days post-op

### Interaction
- Click patient → fires two parallel HTMX GETs: detail panel + chat panel
- Selected state tracked in Alpine, highlighted in list

---

## Sub-Phase 5C: Patient Detail (Center Panel — 4 Tabs)

### Tab 1: Details (`patient_detail_fragment`)
- Current triage status + lifecycle badge
- Days post-op, surgery info, hospital
- **Patient timeline** — unified chronological view collapsed by day/week:
  - Each day shows summary counts ("3 check-ins, 2 notes, 4 conversations")
  - Click to expand and see individual events (lifecycle transitions, escalations, agent conversations, milestone check-ins, clinician notes)
  - Query interleaves `PatientStatusTransition`, `Escalation`, `AgentConversation`, `PatientMilestoneCheckin`, `ClinicianNote` by timestamp
- Recent symptoms (from `ConversationState.recent_symptoms`)
- Pending/acknowledged escalations (with acknowledge/resolve actions + **bulk acknowledge** via checkboxes)
- Quick notes list + add form (POST to `add_note_view`)
- **Export handoff notes** button — generates clipboard-ready summary via `EscalationService.generate_structured_handoff()`
- Upcoming appointments for this patient (from `SchedulingService.get_patient_appointments`)
- Templates: `_tab_details.html`, `_note_form.html`, `_note_item.html`, `_escalation_badge.html`, `_patient_timeline.html`, `_timeline_day.html`, `_export_handoff.html`, `_bulk_escalation_form.html`

### Tab 2: Care Plan (`patient_care_plan_fragment`)
- Active pathway with milestone timeline
- Milestone check-in status (sent, completed, skipped)
- Clinician can add notes per milestone
- Template: `_tab_care_plan.html`

### Tab 3: Research (`patient_research_fragment`)
- Private clinician LLM chat with patient context pre-loaded
- Stored as `AgentConversation(agent_type="clinician_research", clinician=clinician)`
- **Routing**: Default to supervisor auto-routing, with an optional dropdown to force a specific specialist (cardiology, pharmacy, nutrition, etc.)
- POST to `research_chat_send_view` → processes through agent workflow with clinician research system prompt, patient context injected, escalation triggers disabled
- If specialist override selected, routes directly to that agent instead of supervisor
- New service: `ClinicianResearchService` in `apps/clinicians/services.py`
- Templates: `_tab_research.html`, `_research_message.html`
- JS: `static/js/clinician-research-chat.js`

### Tab 4: Tools (`patient_tools_fragment`)
- **Send Auth Text** — POST triggers SMS with new auth link
- **Manage Caregivers** — list relationships/invitations, revoke access
- **Consent Status** — read-only view of patient's consent records
- **Lifecycle Transition** — form with valid transitions, POST to `lifecycle_transition_view`
- **Patient Info** — MRN, DOB, phone, hospital (read-only)
- Templates: `_tab_tools.html`, `_lifecycle_transition_form.html`

### Center Panel Container
- `_patient_detail.html` — tab bar + content area, tabs load via HTMX with `hx-get` on tab click

---

## Sub-Phase 5D: Patient Chat (Right Panel)

### View: `patient_chat_fragment` (HTMX GET)
- Shows the patient's actual AI conversation (not the research chat)
- Filters `AgentConversation` where `clinician__isnull=True` (excludes research)
- Messages with agent type indicators, confidence scores, citations

### Take Control Mode
- Sending a message implicitly enters "take control" — sets `conversation.paused_by` to clinician user (atomic `UPDATE WHERE paused_by IS NULL`)
- Patient sees messages from named clinician (e.g. "Dr. Smith")
- AI stops auto-responding — simple if-check at top of `process_patient_message` in `apps/agents/services.py`
- Incoming patient messages routed to clinician's WebSocket group instead of AI
- Other clinicians see lock indicator + "Dr. Smith is responding" — input area replaced with notice
- Release (3 mechanisms, belt-and-suspenders):
  1. Explicit "Release Control" button (POST to `release_take_control_view`)
  2. WebSocket disconnect handler (clinician closes tab/navigates away)
  3. 30-min inactivity: JS timer fires release POST (happy path) + Celery task scans every 5min for `paused_at > 30min` (fallback for browser crashes)
- On release: clear `paused_by`/`paused_at`, AI resumes, patient flow returns to normal

### Clinician Message Injection
- `inject_chat_message_view` (POST) — creates `AgentMessage(role="assistant", agent_type="clinician")` with metadata tracking who injected it
- Implicitly takes control if not already in control (atomic DB update)
- Pushes to patient's WebSocket group so they see it in real-time
- Template: `_inject_message_form.html`

### Templates
- `_patient_chat.html` — message thread (scrollable) + injection form at bottom
- `_chat_message_clinician.html` — message bubble with clinician name display
- `_take_control_bar.html` — control status indicator + release button
- `_locked_by_other.html` — notice replacing input when another clinician has control

---

## Sub-Phase 5E: Scheduling UI

Scheduling is protocol-critical — virtual visits at specific post-op days (e.g. day 3, 10, 14, 21) are part of the care pathway. This needs to work at pilot quality: set availability, create/view appointments, and see what's coming up.

### Separate page: `templates/clinicians/schedule.html`
- Split layout: weekly calendar view + form panel

### Views
- `schedule_view` — full page, weekly calendar grid with availability blocks + appointment cards
- `availability_fragment` — HTMX fragment for availability editor (set recurring weekly hours)
- `save_availability_view` — POST: save `ClinicianAvailability` records
- `create_appointment_view` — POST: create `Appointment` with conflict validation against availability
- `appointment_detail_view` / `cancel_appointment_view`

### Service: `SchedulingService` in `apps/clinicians/services.py`
- `get_weekly_schedule(clinician, week_start)` — appointments + availability for a week
- `get_available_slots(clinician, date, duration_minutes)` — open slots within availability windows
- `create_appointment(clinician, patient, start, end, type)` — with conflict check
- `get_next_appointment(clinician)` — for dashboard footer toast
- `get_patient_appointments(patient)` — for patient detail tab and patient-facing schedule

### Pathway Integration
- When a patient enters a pathway, protocol-defined virtual visits (from `PathwayMilestone`) can be surfaced as "suggested appointments" that the clinician confirms/schedules
- This is a display-layer concern — milestones already exist, we just surface them in the scheduling context

### Templates
- `_schedule_calendar.html`, `_availability_form.html`, `_appointment_form.html`, `_appointment_card.html`

### Dashboard Integration
- `_next_appointment_toast.html` — footer bar showing next upcoming appointment
- Details tab shows upcoming appointments for the selected patient

---

## Sub-Phase 5F: Real-Time WebSocket

### Connect to existing consumers
- `ClinicianDashboardConsumer` at `ws/dashboard/{hospital_id}/` — receives `escalation_alert`, `patient_status_update`
- `ClinicianNotificationConsumer` at `ws/notifications/clinician/{clinician_id}/` — receives `notification.new`

### Fix auth in `apps/agents/consumers.py`
- `ClinicianDashboardConsumer.connect()` — verify user is authenticated clinician with access to hospital

### Dashboard JS handles
- Escalation alert → flash patient row in list, play sound, show toast
- Status update → update patient row triage color, re-sort if sorted by severity
- New notification → increment bell badge, add to dropdown

---

## Sub-Phase 5G: Tests

**Target: 90% coverage**

```
apps/clinicians/tests/
    test_models.py         — model creation, constraints, availability uniqueness
    test_auth.py           — login/logout, @clinician_required, role enforcement
    test_views.py          — all GET/POST views, HTMX fragment responses
    test_services.py       — SchedulingService, ClinicianResearchService
    test_management_cmd.py — create_test_clinician
```

Key scenarios:
- Hospital-scoped patient visibility (clinician only sees their patients)
- IDOR prevention (patient_id URL param must belong to clinician's hospitals)
- Sort ordering correctness (severity, alpha, last contact)
- Escalation acknowledge/resolve state transitions
- Bulk escalation acknowledge (partial success when some already acknowledged)
- Research chat isolation from patient chat (separate agent_type + clinician FK)
- Take control: race condition (two clinicians, atomic DB check)
- Take control: timeout release, WebSocket disconnect release
- Take control: other clinician sees lock indicator
- **Take control: `process_patient_message()` skips AI when `paused_by` is set** (from eng review)
- **Take control: Celery task releases stale locks (`paused_at` > 30min)** (from eng review)
- **Research chat: LLM failure (timeout/malformed response) returns graceful error** (from eng review)
- Lifecycle transition validation (invalid transitions rejected)
- Appointment conflict detection
- WebSocket auth rejection for non-clinicians
- Shift handoff summary (first login vs returning user)
- Keyboard shortcuts don't fire when typing in input fields

---

## Design Specification (from design review)

### Information Architecture — Dashboard Layout

```
┌──────────────────────────────────────────────────────────────────┐
│ HEADER: Logo · Dashboard | Schedule · 🔔 Notifications · User ▼ │
├──────────────┬────────────────────────┬──────────────────────────┤
│ LEFT 280px   │ CENTER flex-1          │ RIGHT 360px              │
│              │                        │                          │
│ [Handoff     │ ┌─Details─┬Care─┬Res─┬Tools─┐ │ Patient Chat     │
│  Summary]    │ │ Tab content area     │ │                          │
│              │ │                      │ │ Message thread           │
│ ┌──Search──┐ │ │ (HTMX lazy-loaded)   │ │ (read-only until       │
│ │ 🔍 ░░░░░ │ │ │                      │ │  clinician sends)      │
│ └──────────┘ │ │                      │ │                          │
│ Sort: ▼      │ │                      │ │ ┌─────────────────────┐ │
│              │ │                      │ │ │ Take Control Bar    │ │
│ ● Patient A  │ │                      │ │ │ [teal=yours/amber]  │ │
│   Cardiac..  │ │                      │ │ ├─────────────────────┤ │
│ ● Patient B  │ │                      │ │ │ Message input       │ │
│   Post-op..  │ └──────────────────────┘ │ └─────────────────────┘ │
│ (scrollable) │                        │                          │
├──────────────┴────────────────────────┴──────────────────────────┤
│ FOOTER: Next appointment toast (if any)                          │
└──────────────────────────────────────────────────────────────────┘
```

**Visual weight ordering** (what the eye hits first):
1. Triage color dots in patient list (immediate severity scan)
2. Active escalation badges (red, pulsing)
3. Patient name + status line in selected row
4. Tab content in center panel
5. Chat messages in right panel

### Patient List Item Anatomy

```
┌─────────────────────────────────┐
│ ● Name                  3d post │  ● = triage color dot (12px)
│   Surgery type · Status line    │  Status line = escalation excerpt
│                          [2] 💬 │  [2] = unread badge
└─────────────────────────────────┘
```

- Triage dot: 12px circle, DESIGN.md triage colors (green/yellow/orange/red)
- Name: `font-semibold text-sm` (14px per clinician tokens)
- Surgery type: `text-xs text-gray-500 dark:text-gray-400`
- Status line: truncated to 1 line, `text-xs`, shows most actionable info first
- Days post-op: right-aligned, `text-xs font-mono`
- Unread badge: `bg-teal-500 text-white rounded-full text-xs px-1.5`
- Selected row: `bg-gray-100 dark:bg-gray-800 border-l-2 border-teal-500`

### Interaction State Table

```
FEATURE                  | LOADING              | EMPTY                           | ERROR                    | SUCCESS              | PARTIAL
-------------------------|----------------------|---------------------------------|--------------------------|----------------------|------------------
Patient list             | Skeleton rows (5)    | "No patients assigned to your   | "Couldn't load patients. | Rendered list        | —
                         | with pulse animation | hospitals yet. Contact admin."   |  Try refreshing."        |                      |
Handoff summary          | Skeleton card        | "Welcome! This is your first    | Silent fail, hide card   | Rendered card        | —
                         |                      | shift. Your patients are below."|                          |                      |
Detail tab: Details      | Skeleton sections    | "Select a patient from the list | "Failed to load patient  | Rendered content     | Timeline empty:
                         |                      | to see their details."          |  details. Retrying..."   |                      | "No activity yet."
Detail tab: Care Plan    | Skeleton timeline    | "No care pathway assigned yet.  | "Couldn't load care      | Rendered pathway     | Partial milestones
                         |                      | Assign one in Tools tab."       |  plan."                  |                      | shown, rest loading
Detail tab: Research     | —                    | "Ask a question about this      | "Research unavailable.   | Chat messages        | —
                         |                      | patient. Their records are       |  Try again later."       |                      |
                         |                      | pre-loaded as context."         |                          |                      |
Detail tab: Tools        | Skeleton cards       | —  (always has content)         | Per-tool inline error    | Rendered tools       | —
Patient chat             | Skeleton bubbles     | "No conversation yet. The       | "Chat connection lost.   | Message thread       | Messages load,
                         |                      | patient hasn't messaged."       |  Reconnecting..."        |                      | new ones stream in
Escalation list          | Skeleton rows        | "No pending escalations. All    | "Couldn't load           | Rendered list        | —
                         |                      | patients are stable. ✓"         |  escalations."           |                      |
Timeline (per day)       | Inline spinner       | "No events this day."           | "Failed to load events." | Expanded events      | —
Schedule calendar        | Skeleton grid        | "No availability set. Add your  | "Couldn't load schedule."| Rendered calendar    | Availability shows,
                         |                      | hours to start scheduling."     |                          |                      | appointments loading
Take control             | "Taking control..."  | — (always has state)            | "Couldn't take control.  | Teal bar appears     | —
                         | (button disabled)    |                                 |  Another clinician may   |                      |
                         |                      |                                 |  have it."               |                      |
Bulk escalation ack      | "Acknowledging..."   | — (checkboxes are present)      | "X of Y acknowledged.    | "All acknowledged."  | Partial: "3 of 5
                         | (button disabled)    |                                 |  Retry failed ones."     |  toast               |  acknowledged."
```

### User Journey — Emotional Arc

```
STEP | USER DOES                    | USER FEELS           | DESIGN SUPPORTS WITH
-----|------------------------------|----------------------|----------------------------------
1    | Opens dashboard (shift start)| "What did I miss?"   | Handoff summary: changes since
     |                              |                      | last login, warm greeting on first
2    | Scans patient list           | "Who needs me most?" | Severity sort default, red dots
     |                              |                      | and pulsing escalation badges
3    | Clicks critical patient      | "Show me everything" | Parallel load: detail + chat snap
     |                              |                      | in <200ms (HTMX), skeleton states
4    | Reads timeline + escalations | "I understand now"   | Collapsed days, summary counts,
     |                              |                      | expand for detail — not overwhelming
5    | Acknowledges escalation      | "I'm on it"          | Inline ack with toast confirmation,
     |                              |                      | badge count decrements live
6    | Takes control of chat        | "Direct connection"  | Teal bar: "You're responding",
     |                              |                      | patient sees "Dr. Smith", AI pauses
7    | Moves to next patient (j/k)  | "In the flow"        | Keyboard shortcuts, smooth panel
     |                              |                      | transitions, no full-page reloads
8    | Ends shift                   | "Handed off cleanly" | Export handoff notes → clipboard,
     |                              |                      | next clinician sees handoff summary
```

### Take Control — Visual Language

```
YOUR CONTROL (teal):
┌─ bg-teal-50 dark:bg-teal-900/20 border-teal-500 ──────────────┐
│ ● You're responding to this patient    [Release Control]       │
├────────────────────────────────────────────────────────────────┤
│ [Message input active, full width]                [Send ▶]     │
└────────────────────────────────────────────────────────────────┘

LOCKED BY OTHER (amber):
┌─ bg-amber-50 dark:bg-amber-900/20 border-amber-500 ───────────┐
│ ⚠ Dr. Smith is responding to this patient                      │
│   You can still read the conversation.                         │
└────────────────────────────────────────────────────────────────┘
(Input area hidden — replaced by this notice)

NO CONTROL (default):
┌─ bg-gray-50 dark:bg-gray-800 border-gray-300 ─────────────────┐
│ [Message input]                                    [Send ▶]    │
│ Sending a message will pause the AI and put you in control.    │
└────────────────────────────────────────────────────────────────┘
```

### Scheduling — Clinical Calendar (not Google Calendar)

The schedule page must feel clinical, not consumer:
- **Time axis**: 7am–7pm default (clinical shift hours), not midnight-to-midnight
- **Density**: 30-min row height, compact — clinicians manage 15+ patients
- **Color coding**: Appointment type colors (follow-up=teal, virtual=purple, check-in=gray, consultation=coral)
- **Protocol hints**: When a patient's pathway has a suggested visit day, show as dashed-outline ghost block in the calendar ("Suggested: Day 14 follow-up for Patient X")
- **No drag-and-drop**: Click to create — simpler, more reliable, accessible

### Design System Alignment

Reuse existing patient UI patterns from `templates/base_patient.html` and `DESIGN.md`:
- `.card` class for panels (same border-radius, shadow, dark mode treatment)
- `.animate-in` for HTMX fragment appearance (Tailwind `animate-fadeIn`)
- Skeleton loading: `bg-gray-200 dark:bg-gray-700 animate-pulse rounded`
- Toast notifications: existing pattern from `static/js/notifications.js`
- Alpine.js state management patterns from patient chat (`static/js/chat.js`)

**Clinician-specific tokens** (from DESIGN.md):
- Base text: 14px / 1.5 line height
- Card padding: 16px
- Table row height: 48px
- Max-width: 1440px
- Panel gaps: 1px border (not gap — seamless feel)

### Responsive Behavior

**Desktop (1024px+) — Primary target:**
- Full three-panel layout, max-width 1440px, centered
- Left: 280px fixed, Center: flex-1 (min 400px), Right: 360px fixed
- All panels visible simultaneously
- Keyboard shortcuts fully active

**Tablet (640–1023px):**
- Two panels: patient list (240px) + detail (flex-1)
- Chat opens as slide-in drawer from right (320px, overlays detail)
- Trigger: click chat icon in patient list item or "View Chat" button in detail
- Close: X button, swipe right, or Escape
- Patient list collapses surgery type line (name + triage dot only)

**Mobile (<640px):**
- Single panel with bottom navigation bar (3 icons: list/detail/chat)
- Bottom nav: 56px height, `fixed bottom-0`, icons + labels
- Patient list: full width, tap to navigate to detail
- Back button (top-left) returns to list
- Chat: full-screen view
- Keyboard shortcuts disabled (no physical keyboard)
- Touch targets: 44px minimum (WCAG 2.5.5)

### Accessibility Specification

**ARIA landmarks:**
- `role="navigation"` on header nav
- `role="region" aria-label="Patient list"` on left panel
- `role="main"` on center panel
- `role="complementary" aria-label="Patient chat"` on right panel
- `role="tablist"` on center panel tab bar, `role="tab"` / `role="tabpanel"` on tabs

**Keyboard navigation:**
- `Tab` moves between panels (left → center → right)
- `j/k` navigate patient list (only when list panel focused, not in input fields)
- `1-4` switch tabs (only when not in input fields)
- `e` acknowledge selected escalation
- `/` focuses search input
- `Escape` deselects patient / closes drawer (tablet) / closes modal
- `?` opens keyboard help modal
- All shortcuts suppressed when `event.target` is `input`, `textarea`, or `[contenteditable]`

**Focus management:**
- Selecting a patient moves focus to center panel heading
- Tab switch moves focus to first focusable element in tab content
- Take control moves focus to message input
- Modal open traps focus within modal, Escape restores previous focus
- Drawer (tablet) traps focus, Escape closes and restores

**Color and contrast:**
- Triage colors always paired with icon shape + text label (never color-alone)
- All text meets WCAG AA contrast (4.5:1 normal, 3:1 large text)
- Focus indicators: `ring-2 ring-teal-500 ring-offset-2` (visible in both light/dark)
- Dark mode tested independently for contrast compliance

**Screen reader support:**
- Patient list items: `aria-label="Patient Name, triage level, N unread messages"`
- Escalation badges: `aria-live="polite"` for count changes
- Take control bar: `aria-live="assertive"` for state changes
- Toast notifications: `role="status" aria-live="polite"`

## Implementation Notes (from CEO + eng review)

- **IDOR prevention via decorator**: `@clinician_required` auto-verifies `patient_id` URL kwarg belongs to clinician's hospitals. Single enforcement point — no manual `_verify_patient_access` calls needed in individual views.
- Patient list: scrollable with client-side search filter (no pagination needed for prototype, works up to ~300 patients)
- Patient list annotations: use Django ORM `Subquery`/`Count`/`Max` annotations in a single queryset — NOT per-patient queries
- Take control: use `select_for_update()` or atomic `UPDATE WHERE paused_by IS NULL` for race safety
- **Take control patient message routing**: When `paused_by` is set, `process_patient_message()` saves the message to DB AND pushes to clinician's WebSocket group via `channel_layer.group_send` (real-time, not polling)
- **Take control timeout**: Belt-and-suspenders — JS timer fires release POST after 30min inactivity + Celery periodic task (every 5min) scans for `paused_at > 30min` and releases stale locks
- **Research mode**: Pass `research_mode=True` in workflow context dict. Agents check the flag and skip escalation triggers. Can note "would escalate in production" in response.
- **Channel layer graceful degradation**: Wrap all `channel_layer.group_send` calls in try/except. If Redis is down, messages are still in DB — clinician sees them on next HTMX refresh. Log warning, don't crash.
- **Inject message error handling**: Catch DB failures on `AgentMessage.create` and return user-friendly error, not 500.
- Structured logging (`logger.info()`) for: clinician login, take-control events, escalation actions, research queries (HIPAA audit trail)
- Timeline: 5 bulk queries (one per model) + Python merge/sort by timestamp + group by date. NOT N queries per day.

---

## Implementation Order

| Step | What | Ships Independently? |
|------|------|---------------------|
| 5A | Foundation: models, migrations, auth, shell layout, test data command | Yes |
| 5B | Patient list panel (left) | Yes |
| 5D | Patient chat panel (right) + message injection | Yes |
| 5C | Detail panel tabs: Details first, then Care Plan, Research, Tools | Yes (per tab) |
| 5E | Scheduling page | Yes |
| 5F | WebSocket real-time integration | Yes (progressive enhancement) |
| 5G | Test coverage to 90% | Alongside each step |

---

## Files Summary

### New Files
- `apps/clinicians/auth.py`
- `apps/clinicians/urls.py`
- `apps/clinicians/views.py`
- `apps/clinicians/services.py`
- `apps/clinicians/admin.py`
- `apps/clinicians/management/commands/create_test_clinician.py`
- `apps/clinicians/tests/test_*.py` (5 files)
- `templates/base_clinician.html`
- `templates/clinicians/login.html`
- `templates/clinicians/dashboard.html`
- `templates/clinicians/schedule.html`
- `templates/clinicians/components/*.html` (~20 component templates)
- `static/js/clinician-dashboard.js`
- `static/js/clinician-research-chat.js`

### Modified Files
- `apps/clinicians/models.py` — add ClinicianNote, ClinicianAvailability, Appointment
- `apps/agents/models.py` — add clinician_research + clinician agent types, clinician FK, paused_by/paused_at on AgentConversation
- `apps/agents/services.py` — add paused_by check at top of `process_patient_message`
- `apps/agents/consumers.py` — auth hardening on ClinicianDashboardConsumer
- `apps/agents/api.py` — fix FIXME at line 200 (proper session auth for escalation acknowledge)
- `config/urls.py` — uncomment clinician URL include

---

## Verification

1. `python manage.py create_test_clinician` → get login credentials
2. Log in → see shift handoff summary + three-panel dashboard with 5 test patients
3. Click patient → center + right panels load
4. Cycle through all 4 tabs, verify data renders
5. Details tab: patient timeline (collapsed by day), escalation list, notes, export handoff
6. Inject a clinician message → takes control, patient sees "Dr. Smith", other clinicians see lock
7. Release control → AI resumes
8. Send a research question → get contextual LLM response
9. Acknowledge/resolve escalations (single + bulk)
10. Create an appointment on the schedule page
11. Keyboard shortcuts: j/k navigate, 1-4 tabs, e acknowledge, / search, ? help
12. Verify dark mode works across all views
13. Verify responsive: resize to tablet (two panels), mobile (single panel)
14. `POSTGRES_PORT=5434 pytest` → all tests pass, coverage >= 90%

## What Already Exists (reused, not rebuilt)

- `EscalationService` (acknowledge, resolve, get_pending, structured_handoff) → `apps/agents/services.py`
- `ConversationService` (get_or_create, add_message) → `apps/agents/services.py`
- `ContextService` (assemble_full_context) → `apps/agents/services.py`
- `NotificationService` (create, deliver, get_unread_for_clinician) → `apps/notifications/services.py`
- `ClinicianDashboardConsumer` (escalation_alert, patient_status_update) → `apps/agents/consumers.py`
- `ClinicianNotificationConsumer` (notification.new) → `apps/notifications/consumers.py`
- `Patient.transition_lifecycle()` → `apps/patients/models.py`
- `workflow.process_message()` → `apps/agents/workflow.py`
- Web Audio notification sound pattern → `static/js/chat.js`
- Alpine.js notification bell pattern → `static/js/notifications.js`
- Template/CSS patterns → `templates/base_patient.html`, `DESIGN.md`

## NOT in Scope

- EHR integration (TODO-001) — separate phase
- Caregiver read-only dashboard (TODO-013) — separate feature
- Predictive risk scoring (TODO-003) — needs data science work
- Video/telehealth in virtual visits — just scheduling + link for now
- Clinician-to-clinician messaging — out of scope
- Mobile native app — web responsive is sufficient

## TODOs to Add During Implementation

- **TODO-015**: Server-side pagination for patient list (P2, blocked by Phase 5)
- **TODO-016**: Migrate `apps/agents/api.py` async wrappers to Django 5.1 native async ORM (`aget`, `acreate`, `aiterator`) — 8 boilerplate `sync_to_async` functions can be eliminated (P3, Small, CC: ~15 min)

## Post-Implementation

- Run `/design-review` on the live clinician dashboard for visual QA
- Run `/plan-eng-review` before shipping PR
