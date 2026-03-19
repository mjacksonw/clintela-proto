# Plan: Patient Chat UI

## Context

Phase 2 (multi-agent system) is complete but can only be tested via `manage.py shell`. We need a real patient-facing UI to acceptance-test the agent system and prove out the DESIGN.md design system. This pulls forward a focused slice of Phase 5 — patient chat + dashboard + auth page styling.

## Scope

- Base template with full design system (Satoshi, colors, dark mode, spacing)
- Patient chat as an **omnipresent sidebar** (always visible alongside dashboard content)
- Patient dashboard (recovery info, care plan, milestones — the main content area)
- Django admin registration (Patient, Hospital, User) so we can create test data and auth URLs
- Restyle auth flow pages (DOB entry, token expired, rate limited)
- Home page restyle

**Accepted expansions (from CEO review):**
- Markdown rendering in agent bubbles (marked.js + DOMPurify CDN)
- Skeleton loading screens for chat and dashboard (CSS shimmer per DESIGN.md)
- Offline detection banner (navigator.onLine API)
- Subtle notification sound on agent response (mute toggle, off by default)
- Dev toolbar for acceptance testing (DEBUG-only: patient switcher, clear conversation, raw metadata)
- Confidence indicator on low-confidence agent responses
- Progressive timeout messages ("Thinking..." → "Still working..." → "Taking longer than usual..." → error)

**Not in scope:** Clinician dashboard, admin analytics, WebSocket real-time (HTTP POST first, WS upgrade later).

Also: save plan to `docs/plans/` and update `IMPLEMENTATION_HANDOFF.md` to reflect new phase order.

---

## Approach

### Frontend Stack (CDN, zero build tools)

- **Tailwind CSS Play CDN** — design tokens configured inline via `tailwind.config`, maps directly to DESIGN.md
- **HTMX 2.0** — form submission, HTML fragment swapping for chat messages
- **Alpine.js 3.x** — reactive state: dark mode toggle, typing indicator, auto-scroll, textarea auto-resize, sidebar collapse
- **Satoshi font** from Fontshare CDN (with `<link rel="preconnect">` to avoid FOIT)
- **Lucide icons** from CDN
- **marked.js** from CDN — markdown rendering in agent messages
- **DOMPurify** from CDN — sanitize marked.js output (XSS prevention for LLM-generated content)

No `package.json`, no bundler. Prototype-appropriate; migrate to built Tailwind before production.

### Layout Architecture: Sidebar Chat

The patient experience is a **two-panel layout**: dashboard content on the right, chat sidebar on the left. The chat is always present — it's the primary way patients interact with Clintela. The dashboard provides context (recovery timeline, care plan, milestones) that the chat can reference.

```
┌─────────────────────────────────────────────────────┐
│  Header: Clintela wordmark  |  Patient name  |  ☾   │
├──────────────────┬──────────────────────────────────┤
│                  │                                  │
│   Chat Sidebar   │       Dashboard Content          │
│   (360px fixed)  │       (flex-grow, max 720px)     │
│                  │                                  │
│  ┌────────────┐  │   Welcome card                   │
│  │ Messages   │  │   Recovery status                │
│  │ ...        │  │   Care plan / milestones         │
│  │ ...        │  │   Recent activity                │
│  └────────────┘  │                                  │
│  ┌────────────┐  │                                  │
│  │ Input area │  │                                  │
│  └────────────┘  │                                  │
├──────────────────┴──────────────────────────────────┤
```

**Mobile (< 768px):** Chat becomes a full-screen overlay triggered by a floating action button (chat bubble icon, bottom-right, 56px). Dashboard is the default view. This matches the phone-first patient experience.

**Tablet (768-1023px):** Sidebar collapses to icon-width (64px) by default, expands on click. Dashboard takes full width.

**Desktop (1024px+):** Both panels visible side by side. Sidebar is 360px fixed width.

### Template Architecture

```
templates/
  base.html                         # NEW — design system, CDN deps, dark mode
  base_patient.html                 # NEW — extends base, adds sidebar+dashboard layout
  components/
    _header.html                    # Patient header + dark mode toggle
    _chat_sidebar.html              # Chat sidebar container (messages + input)
    _message_bubble.html            # Chat message (user or agent)
    _typing_indicator.html          # Animated dots
    _chat_input.html                # Textarea + send button (HTMX form)
    _empty_chat.html                # Welcome state with suggestion chips
    _error_toast.html               # Error notification
    _escalation_banner.html         # "Your care team has been notified" banner
  patients/
    dashboard.html                  # REWRITE — recovery info (fills main content area)
  accounts/
    dob_entry.html                  # RESTYLE — extend base.html
    token_expired.html              # RESTYLE — extend base.html
    rate_limited.html               # RESTYLE — extend base.html
  home.html                         # RESTYLE — extend base.html
```

Note: no separate `chat.html` — the chat sidebar is part of `base_patient.html` and is always present on every patient page.

---

## Implementation Steps

### Step 0: Django Admin + Test Data Setup

**Create `apps/patients/admin.py`**

Register Patient, Hospital models with useful admin configuration:
- `PatientAdmin`: list display (name, hospital, leaflet_code, status, surgery_type, days_post_op), search fields, filters. Include a **read-only field** that generates and displays the full auth URL for the patient (using `ShortCodeTokenGenerator` from `apps/accounts/tokens.py` to generate token + code, then building the URL: `/accounts/start/?code={code}&token={token}&patient_id={id}`). This lets the admin click a link to test the auth flow.
- `HospitalAdmin`: list display (name, code, is_active)

**Create `apps/accounts/admin.py`**

Register User, AuthAttempt models:
- `UserAdmin`: extend Django's UserAdmin, add `role`, `phone_number` fields
- `AuthAttemptAdmin`: list display (patient, success, method, created_at), read-only

**Create `apps/agents/admin.py`**

Register conversation/escalation models (read-only, for inspection):
- `AgentConversationAdmin`: list display (patient, status, agent_type, created_at)
- `AgentMessageAdmin`: list display (conversation, role, agent_type, created_at)
- `EscalationAdmin`: list display (patient, severity, status, created_at)

**Management command: `create_test_patient`**

Create `apps/patients/management/commands/create_test_patient.py`:
- Creates a Hospital ("Test Hospital", code "TEST")
- Creates a User (first_name="Sarah", last_name="Chen", role="patient")
- Creates a Patient (hospital, DOB=1985-06-15, leaflet_code auto-generated, surgery_type="Knee Replacement", surgery_date=14 days ago)
- Generates auth token + code
- Prints the full auth URL to console
- Idempotent (skips if user already exists)

### Step 1: Base Template + Design System

**Create `templates/base.html`**

- Tailwind CDN with inline config mapping DESIGN.md tokens:
  - `fontFamily.sans`: `['Satoshi', ...system]`
  - Colors: primary #2563EB, secondary #0D9488, warm gray scale (stone-toned), semantic colors
  - Spacing: 4px base scale
  - Type scale from DESIGN.md (Major Third 1.25 modular scale)
  - `darkMode: ['selector', '[data-theme="dark"]']`
  - `maxWidth.patient: '720px'`
- CSS custom properties for dark mode (`:root` + `[data-theme="dark"]`) — exact values from DESIGN.md
- Inline `<script>` in `<head>` to set theme before paint (prevents flash)
- `prefers-reduced-motion` reset in CSS
- Skip-to-content link
- CSRF meta tag for HTMX
- `{% block content %}`, `{% block extra_js %}`, `{% block title %}`
- HTMX config: include CSRF token on all requests via `htmx:configRequest` listener

**Create `templates/base_patient.html`**

- Extends `base.html`
- Implements the two-panel layout:
  - Left: `{% include "components/_chat_sidebar.html" %}` (360px, always present)
  - Right: `{% block dashboard_content %}` (flex-grow, max-width 720px, centered)
- Alpine.js `x-data` on body for sidebar state (`sidebarOpen`, `mobileOverlay`)
- Mobile FAB button to open chat overlay
- Responsive breakpoints per DESIGN.md (mobile/tablet/desktop)

**Create `static/js/theme.js`**

- Read/write `localStorage('clintela-theme')` — `light`, `dark`, or `system`
- Listen for `prefers-color-scheme` changes
- Toggle function for the dark mode button

**Create `templates/components/_header.html`**

- Sticky top, 64px height, border-bottom 1px solid Gray 200 (dark: `--color-border`)
- Layout hierarchy (left → right):
  - LEFT: Clintela wordmark (Satoshi 700, -0.02em tracking, teal color) — brand anchor
  - CENTER/RIGHT: Patient name if authenticated (Satoshi 500, Gray 700) — secondary
  - FAR RIGHT: Icon group — sound toggle (speaker Lucide icon, 20px) + dark mode toggle (sun/moon, 20px) — tertiary, 8px gap between icons, 44px touch targets via padding
- Mobile: wordmark left, icons right, patient name hidden (available in sidebar)
- Dark mode: bg `--color-surface`, border `--color-border`, wordmark stays teal (works on both)

### Step 2: Chat Sidebar UI

**Create `templates/components/_chat_sidebar.html`**

- Container: 360px fixed width, full height below header, flex column, border-right 1px solid Gray 200 (dark: `--color-border`) — panel separator, not shadow
- Top section: "Chat" label, minimize button (desktop/tablet)
- Middle: scrollable messages area (`role="log"`, `aria-live="polite"`, `id="messages"`)
  - Loads existing history from context on page load
  - Empty state: `{% include "components/_empty_chat.html" %}`
  - Messages: loop over `messages` context, each `{% include "components/_message_bubble.html" %}`
- Bottom: `{% include "components/_chat_input.html" %}` (sticky to bottom of sidebar)
- Mobile: full-screen overlay with close button, z-50

**Create `templates/components/_message_bubble.html`**

- **Patient messages**: right-aligned, Primary Blue bg (dark: #3B82F6 per DESIGN.md dark mode adjustment), white text, rounded (16px 16px 4px 16px — flat bottom-right)
- **Agent messages**: left-aligned, white bg (dark: `--color-surface` #1E293B), 1px border Gray 200 (dark: `--color-border`), rounded (16px 16px 16px 4px — flat bottom-left), text color Gray 700 (dark: `--color-text`)
- Agent label above bubble: human-readable name ("Care Coordinator", "Nurse") in gray-500, 14px
- Timestamp below in gray-400, 12px (using `django.contrib.humanize` `naturaltime`)
- 18px body text, line-height 1.6, max-width 100% (sidebar constrains width)
- **Agent messages**: render content through marked.js + DOMPurify for safe markdown
- **Confidence indicator**: if `confidence_score < 0.6`, show subtle disclaimer below bubble: "I may not have the best answer for this — consider reaching out to your care team."

**Create `templates/components/_typing_indicator.html`**

- Three animated dots in agent-bubble style
- Respects `prefers-reduced-motion` (shows static "..." text instead)
- `aria-label="Agent is typing"`, `role="status"`
- Hidden by default, shown via Alpine.js `x-show="typing"`
- **Placement: OUTSIDE `#messages`** — sits in a fixed position below the messages container, above the input. This avoids conflicts with HTMX's `beforeend` swap on `#messages`.
- **Progressive timeout messages** (warm, personal tone): text updates at 0s ("Your care team is thinking..."), 10s ("Still working on your question..."), 25s ("This is taking longer than usual..."), 45s → hide indicator + show error toast with retry. Note: specific agent name (e.g., "Care Coordinator") not available until response arrives — use "Your care team" as warm generic during typing.

**Create `templates/components/_chat_input.html`**

- Auto-growing textarea (max 4 lines, `maxlength="2000"`), 16px font (prevents iOS zoom)
- Send button: primary blue, 44x44px min, arrow-up Lucide icon
- HTMX attributes: `hx-post="{% url 'patients:chat_send' %}"`, `hx-target="#messages"`, `hx-swap="beforeend"`, `hx-indicator="#typing-indicator"`
- **Send button micro-states:**
  - **Empty textarea**: Gray 300 bg, Gray 500 icon — visually inert, not clickable
  - **Has text**: Primary Blue bg, white icon — visually active, inviting
  - **In flight**: Primary Blue bg at 50% opacity, spinning loader icon replaces arrow — clearly "working"
  - **After response**: Returns to "has text" or "empty" state based on textarea content
- Suggestion chips disabled during in-flight requests (opacity 50%, pointer-events none)

**Create `templates/components/_empty_chat.html`**

- Centered vertically in chat area
- Clintela icon (secondary teal, 48px)
- "Hi {{ patient.user.first_name }}!" heading (Satoshi 600, H3)
- "I'm here to help with your recovery. Ask me anything." — subtext in Gray 500, 16px
- **Trust signal**: Small line below: "Your conversations are private and shared only with your care team." — Gray 400, 14px. Builds trust before first interaction.
- 3 suggestion chips — **contextual, generated from pathway data**:
  - If pathway milestone exists: chips reflect recovery stage (e.g., "Is this swelling normal?", "When can I shower?", "My pain today"). Generated from `PathwayMilestone.expected_symptoms` and `activities` fields in the view, passed as template context.
  - Fallback (no pathway): "Is this normal?", "My medications", "Talk to my care team" — healthcare-specific, not generic chatbot copy.
- Clicking a chip populates textarea and auto-submits
- **Chips persist after first message** — moved to thin row above textarea in `_chat_input.html` once empty state is replaced by messages. Quick-action shortcuts for recurring patient questions. Disabled (opacity 50%) during in-flight requests.

**Create `templates/components/_escalation_banner.html`**

- Slim banner below header or at top of chat: "Your care team has been notified and will follow up shortly."
- Warning amber background, icon + text
- Dismissible

**Create `static/js/chat.js`**

- Optimistic UI: on `htmx:beforeRequest`, append user's message as a right-aligned bubble + show typing indicator
- Auto-scroll: on `htmx:afterSwap`, smooth-scroll messages container to bottom (only if user was near bottom — within 100px)
- Textarea: auto-resize on `input` event, Enter to send, Shift+Enter for newline
- Suggestion chips: on click, set textarea value + trigger HTMX submit
- Error handling: `htmx:responseError` → show **inline error bubble** in message flow (red-tinted agent bubble style: Danger bg #FEE2E2, Danger text #991B1B, with retry button). Appears where the response would have been — contextual, no positioning conflicts in narrow sidebar.
- Escalation: if response element has `data-escalation` attribute, show escalation banner
- Mobile FAB: toggle sidebar overlay open/closed
- Mobile back button: push history state when opening overlay, close on `popstate`
- **Offline detection**: listen for `navigator.onLine` changes, show/hide offline banner, disable send button when offline
- **Notification sound**: play subtle chime on `htmx:afterSwap` for agent messages; mute state stored in `localStorage('clintela-sound')`, toggle in header
- **Markdown rendering**: use marked.js + DOMPurify on agent message content after HTMX swap
- **Progressive timeout**: Alpine.js timer starts on send; updates typing indicator text at 10s, 25s; fires error at 45s

### Step 3: Backend Views

**Modify `apps/patients/views.py`**

- `patient_dashboard_view(request)` — **enhance existing view**:
  - Keep existing auth check pattern
  - Add message history to context (via `ConversationService.get_conversation_history`, limit=50)
  - Add patient context (hospital, surgery info, days_post_op, status)
  - Pass `messages` list to template for chat sidebar to render on load
  - Pass `debug` flag for dev toolbar conditional rendering

- Add `patient_chat_send_view(request)` — **new async HTMX endpoint**:
  1. Auth check (same session pattern)
  2. Validate message text from POST body
  3. Write own thin async wrappers calling `ConversationService`, `ContextService`, `EscalationService` (same pattern as `api.py` but local to this module — avoid cross-app import from `agents.api`)
  4. Call `get_workflow().process_message(message, context)`
  5. Guard against empty LLM response — if response is empty/whitespace, return fallback message: "I'm sorry, I wasn't able to process that. Could you try rephrasing?"
  6. Return rendered `_message_bubble.html` HTML fragment (includes `confidence_score` and `agent_type` in template context)
  7. If escalation: set `HX-Trigger: escalation` response header
  8. **Logging**: log message received, agent type routed to, response time (ms), and escalation events at INFO level

**Modify `apps/patients/urls.py`**

- Keep `path("dashboard/", ...)` as-is
- Add `path("chat/send/", views.patient_chat_send_view, name="chat_send")`

**Create `apps/patients/templatetags/__init__.py`** (empty)

**Create `apps/patients/templatetags/patient_tags.py`**

- `agent_display_name` filter: `care_coordinator` → "Care Coordinator", `nurse_triage` → "Nurse", `supervisor` → "Clintela"
- `agent_icon` filter: returns Lucide icon name (`heart-handshake`, `stethoscope`, `bot`)

### Step 4: Dashboard Content

**Visual Hierarchy (what the patient sees 1st → 3rd):**

```
┌─────────────────────────────────────────┐
│  ① RECOVERY STATUS (primary anchor)     │  ← First thing they see
│  "Day 14 of recovery · On Track ✓"      │     Large type, status badge
│  Surgery: Knee Replacement              │     Color-coded (green = calm)
│  Current phase: Mid Recovery            │
├─────────────────────────────────────────┤
│  ② WHAT TO EXPECT (contextual)          │  ← Answers "what's normal?"
│  "At this stage, mild swelling is       │     Reassuring, educational
│   normal. Your next milestone is..."    │
├─────────────────────────────────────────┤
│  ③ WELCOME + CARE TEAM (warm footer)    │  ← Grounding, not primary
│  "Hi Sarah — your team at Mass General  │     Hospital name, team info
│   is here for you."                     │
└─────────────────────────────────────────┘
```

**Rewrite `templates/patients/dashboard.html`**

- Extends `base_patient.html` (gets sidebar chat for free)
- `{% block dashboard_content %}` contains (in visual priority order):
  - **Recovery status hero** (PRIMARY): Days post-op as large number (48px/H1), surgery type, color-coded status badge (green/yellow/orange/red with text + icon per DESIGN.md triage colors). This is the patient's #1 question: "Am I on track?" — answer it immediately. Status badge uses DESIGN.md semantic colors + text + icon (colorblind-safe).
  - **What to expect card** (SECONDARY): If pathway assigned, show current phase (Early/Middle/Late) and phase-specific guidance. Next milestone with estimated day. Expected vs. concerning symptoms at this stage. Educational, reassuring tone.
  - **Welcome / care team card** (TERTIARY): "Hi {{ first_name }}" with hospital name. Warm but not primary — the patient already knows their name. This grounds them ("you're connected to Mass General") without consuming prime visual real estate.
- All within max-width 720px, generous spacing per DESIGN.md patient interface rules (24px card padding, 32px section gaps)
- Cards use DESIGN.md patient card spec: white bg, 1px solid Gray 200, 8px radius, 24px padding, subtle shadow

**Dashboard empty/missing data states:**
- **No surgery data**: Recovery status card shows "Your care team is setting up your recovery plan" with a heart-pulse Lucide icon. Warm, not broken-looking.
- **No pathway assigned**: "What to expect" card hidden entirely (not shown as empty). Dashboard is shorter — that's fine.
- **No milestones**: Care plan section hidden. The dashboard gracefully contracts to show only what's available.
- **All data present**: Full dashboard with all three cards visible.

### Step 5: Skeleton Loading + Dev Toolbar

**Create `templates/components/_skeleton.html`**

- Reusable skeleton placeholder component (CSS-only shimmer animation)
- Variants: `skeleton-message` (chat bubble shape), `skeleton-card` (dashboard card shape)
- Shimmer: linear-gradient animation, 1.5s infinite, per DESIGN.md motion spec
- Respects `prefers-reduced-motion` (static gray placeholder instead)
- Used in chat sidebar on initial load (3 skeleton message shapes) and dashboard (skeleton cards)

**Create `templates/components/_dev_toolbar.html`**

- Only rendered when `{% if debug %}` (Django `debug` context processor — server-side gate, NOT client-side)
- Fixed bottom bar, small, collapsible
- Shows: current patient name + ID, agent_type of last response, confidence score, escalation status
- "Switch Patient" dropdown (queries all patients, sets session)
- "Clear Conversation" button (deletes current conversation, reloads)
- "Bypass Auth" link (auto-authenticates as selected patient — skips DOB flow)
- Styled distinctly (dark bg, monospace font) so it's obviously not part of the app

**Add `patient_dev_actions_view` to `apps/patients/views.py`**

- POST endpoint for dev toolbar actions (switch patient, clear conversation)
- Gated on `settings.DEBUG` — returns 404 in production
- URL: `path("dev/", views.patient_dev_actions_view, name="dev_actions")` (DEBUG-only)

### Step 6: Restyle Existing Pages

**Retrofit existing templates to extend `base.html`** (not `base_patient.html` — these pages don't need the chat sidebar):

- `home.html` — clean landing page. Remove inline CSS. Centered content: Clintela wordmark (teal, Satoshi 700), tagline "Your recovery companion — available 24/7", brief reassurance line ("Secure, private, and connected to your care team at [hospital name]"), prominent "I have an access code" button → `/accounts/start/`. Warm, confident, not clinical. The patient just left the hospital — this page should feel like a calm handoff, not a login wall.
- `accounts/dob_entry.html` — styled form card (DESIGN.md card styling: white bg, 1px border, 8px radius, 24px padding). Input field 48px height, 16px font, focus ring. Patient code shown as verified badge.
- `accounts/token_expired.html` — styled with clear CTAs for resend/manual entry
- `accounts/rate_limited.html` — styled error page with "contact care team" guidance

### Step 7: Documentation + Handoff Update

**Create `docs/plans/2026-03-19-patient-chat-ui.md`**

Copy of this plan for project history.

**Update `IMPLEMENTATION_HANDOFF.md`**

- Add "Phase 2.5: Patient UI" between Phase 2 and Phase 3
- Mark it as "IN PROGRESS"
- Move auth page styling from Phase 3 into Phase 2.5
- Note that Phase 5 (Dashboard & UI) now only covers clinician dashboard + admin analytics
- Update "What to Do in Next Session" section

### Step 8: Accessibility + Polish

**WCAG 2.1 AA Compliance:**
- Verify contrast ratios on all text/bg combos (especially agent bubbles in dark mode — white text on `--color-surface` must pass 4.5:1)
- Agent bubble: Gray 700 text on white bg = 5.7:1 ✓. Dark mode: `--color-text` on `--color-surface` = verify
- Patient bubble: white text on Primary Blue = 4.6:1 ✓
- Confidence disclaimer: Gray 500 text on white bg = 4.6:1 ✓
- Status badges: verify DESIGN.md badge text/bg combos all pass

**Keyboard Navigation (tab order):**
1. Skip-to-content link → main dashboard content
2. Header: wordmark (link to /), sound toggle, dark mode toggle
3. Chat sidebar: messages area (scrollable via arrow keys), suggestion chips, textarea, send button
4. Dashboard content: cards (if interactive)
5. Focus trap when mobile chat overlay is open (tab cycles within overlay)
6. Escape key closes mobile overlay

**ARIA Landmarks:**
- `<header role="banner">` — site header
- `<aside role="complementary" aria-label="Chat with your care team">` — chat sidebar
- `<main role="main" aria-label="Recovery dashboard">` — dashboard content
- `<div role="log" aria-live="polite" aria-label="Chat messages">` — messages area
- `<div role="status" aria-live="assertive">` — typing indicator (assertive because it's brief and important)
- Error toast: `role="alert"` (auto-announced by screen readers)
- Escalation banner: `role="alert"`

**Focus Management:**
- After sending message: focus returns to textarea
- After mobile overlay opens: focus moves to close button
- After mobile overlay closes: focus returns to FAB button
- New agent message: `aria-live` announces it (no focus steal)

**Responsive Details:**
- Mobile (< 768px): Dashboard cards stack full-width, 16px side margins. FAB at bottom-right, 56px, 16px from edges. Bottom padding on dashboard (80px) to prevent FAB overlap with content.
- Tablet (768-1023px): Collapsed sidebar shows chat icon (teal, 24px) at 64px width. Click expands to 360px with slide animation (300ms ease-out). Dashboard reflows.
- Desktop (1024px+): Both panels visible. Sidebar doesn't scroll the page — independent scroll on messages area.
- All viewports: horizontal scroll never appears (overflow-x: hidden on body)

**Other Polish:**
- Test `prefers-reduced-motion` — skeleton shows static gray, typing dots become "..." text, no slide animations
- Verify 44px minimum touch targets on: send button, FAB, suggestion chips, dark mode toggle, sound toggle, overlay close button
- Verify 8px minimum spacing between adjacent touch targets

### Step 9: Tests

**Add to `apps/patients/tests/`:**

- `test_chat_send_view.py`:
  - Unauthenticated request → redirect
  - Empty message → 400 response
  - Valid message → returns HTML fragment containing `_message_bubble` markup
  - Response includes agent_type in rendered output
  - Escalation → `HX-Trigger: escalation` header present
  - (Use `MockLLMClient` from `apps/agents/llm_client.py` for workflow)

- `test_templatetags.py`:
  - `agent_display_name("care_coordinator")` → `"Care Coordinator"`
  - `agent_display_name("nurse_triage")` → `"Nurse"`
  - `agent_display_name("supervisor")` → `"Clintela"`
  - `agent_display_name("unknown")` → `"Assistant"` (fallback)
  - `agent_icon("care_coordinator")` → `"heart-handshake"`

- `test_management_command.py`:
  - Running `create_test_patient` creates Hospital, User, Patient
  - Running it twice is idempotent (no IntegrityError)
  - Output includes auth URL

---

## Security Notes

- **XSS in agent responses**: Agent messages are rendered through marked.js. Output MUST be sanitized with DOMPurify before DOM insertion. Never use `|safe` on raw LLM content.
- **XSS in patient messages**: Django's `{{ content }}` auto-escapes by default. Do NOT use `|safe` on user messages.
- **Dev toolbar**: Server-side gated via `settings.DEBUG` check in both view and template. The `patient_dev_actions_view` returns 404 when `DEBUG=False`.
- **CSRF**: HTMX includes CSRF token via `htmx:configRequest` listener reading from `<meta name="csrf-token">` tag.
- **Session auth**: All patient views check `request.session.get("authenticated")`. No URL-based patient ID manipulation.

---

## Key Files to Modify

| File | Action |
|------|--------|
| `apps/patients/views.py` | Enhance dashboard view, add `patient_chat_send_view` |
| `apps/patients/urls.py` | Add `chat/send/` route |
| `apps/agents/api.py` | Reference only — reuse its async helper functions |
| `apps/agents/services.py` | Reference only — `ConversationService`, `ContextService` |
| `apps/agents/workflow.py` | Reference only — `get_workflow().process_message()` |
| `apps/accounts/tokens.py` | Reference only — `short_code_token_generator` for admin URL generation |
| `templates/patients/dashboard.html` | Full rewrite |
| `templates/home.html` | Restyle to extend base.html |
| `templates/accounts/*.html` | Restyle to extend base.html |
| `IMPLEMENTATION_HANDOFF.md` | Update roadmap with Phase 2.5 |

## New Files

| File | Purpose |
|------|---------|
| `apps/patients/admin.py` | Patient + Hospital admin with auth URL generation |
| `apps/accounts/admin.py` | User + AuthAttempt admin |
| `apps/agents/admin.py` | Conversation + Escalation admin (read-only) |
| `apps/patients/management/commands/create_test_patient.py` | Seed test data + print auth URL |
| `templates/base.html` | Master template with design system |
| `templates/base_patient.html` | Two-panel layout: chat sidebar + dashboard content |
| `templates/components/_header.html` | Shared patient header |
| `templates/components/_chat_sidebar.html` | Chat sidebar container |
| `templates/components/_message_bubble.html` | Chat message component |
| `templates/components/_typing_indicator.html` | Animated typing dots |
| `templates/components/_chat_input.html` | Message input form |
| `templates/components/_empty_chat.html` | Welcome state |
| `templates/components/_error_toast.html` | Error notification |
| `templates/components/_escalation_banner.html` | Escalation notification |
| `templates/components/_skeleton.html` | Skeleton loading placeholders |
| `templates/components/_dev_toolbar.html` | DEBUG-only dev toolbar |
| `templates/components/_offline_banner.html` | Offline detection banner |
| `static/js/chat.js` | Chat interaction logic |
| `static/js/theme.js` | Dark mode management |
| `static/sounds/notify.mp3` | Subtle chime for agent responses (~2KB) |
| `apps/patients/templatetags/__init__.py` | Package init |
| `apps/patients/templatetags/patient_tags.py` | Template filters |
| `apps/patients/tests/test_chat_send_view.py` | Chat view tests |
| `apps/patients/tests/test_templatetags.py` | Template tag tests |
| `apps/patients/tests/test_management_command.py` | Management command tests |
| `docs/plans/2026-03-19-patient-chat-ui.md` | Plan documentation |

---

## Verification

1. **Create test data**: `python manage.py create_test_patient` → prints auth URL
2. **Django admin**: visit `/admin/`, verify Patient/Hospital/User models visible, auth URL displayed on patient detail page
3. **Auth flow**: click generated auth URL → styled DOB form → enter `06/15/1985` → redirected to dashboard
4. **Dashboard**: recovery info cards visible, chat sidebar open on left
5. **Chat**: type a message in sidebar → see optimistic user bubble → typing indicator → agent response in styled bubble
6. **Suggestion chips**: click "How am I doing?" → auto-sends → agent responds
7. **Escalation**: send "I'm having severe chest pain" → agent responds + escalation banner appears
8. **Dark mode**: toggle in header → all panels switch correctly, persists on refresh
9. **Mobile (375px)**: dashboard fills screen, FAB button bottom-right, tap FAB → chat overlay opens full-screen
10. **Tablet (768px)**: sidebar collapsed to icon, click → expands
11. **Accessibility**: tab through all interactive elements, focus rings visible, screen reader announces new messages
12. **Home page**: visit `/` → styled landing page with Satoshi font, design system colors
13. **Markdown**: agent response with bullet points renders as formatted HTML
14. **Skeleton**: on page load, skeleton placeholders visible briefly before content
15. **Offline**: disconnect network → offline banner appears, send button disabled → reconnect → banner hides
16. **Sound**: send a message → subtle chime plays when agent responds (toggle mute in header)
17. **Dev toolbar** (DEBUG=True): visible at bottom, shows patient info, switch patient works, clear conversation works
18. **Confidence**: send an ambiguous message → if agent confidence < 0.6, disclaimer appears below bubble
19. **Progressive timeout**: if LLM is slow, typing indicator text updates at 10s and 25s
20. **Tests**: `POSTGRES_PORT=5434 pytest apps/patients/tests/ -v` — all passing
