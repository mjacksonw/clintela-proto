# Phase 3: Communication & Multi-modality

*Date: 2026-03-19 | Branch: claude/inspiring-clarke*
*Reviews: CEO (SELECTIVE EXPANSION), Eng (FULL_REVIEW), Design (FULL) — all CLEAR*

## Context

Phase 2.5 delivered a working patient chat UI (HTMX-powered), multi-agent AI workflow, and escalation system. The `notifications` and `messages_app` Django apps have models but no services, views, or tests. WebSocket infrastructure exists but is disabled. Phase 3 brings these dormant systems to life: notification delivery, SMS integration, voice input, and real-time WebSocket notifications — all with developer-friendly console backends so no external services are needed for local dev.

Key requirements:
- **Tests first** — every feature ships with unit + integration tests from the start
- **Developer mode** — SMS prints to runserver logs (console backend pattern)
- **Voice input** — MediaRecorder record button in chat UI (voice as input method, not "memo")
- **No external dependencies** for local development
- **Celery + Redis** for async task queue (scheduled reminders, cleanup, notification delivery)
- **Three-tier transcription** — remote API, local Whisper, and mock

### Accepted Scope Expansions (CEO Review)
- Channel indicator icons (SMS/voice/web) on message bubbles
- SMS simulator panel in DEBUG-only dev toolbar
- Audio playback widget in voice message bubbles (authenticated serving)
- Delivery status indicators (✓ sent, ✓✓ delivered) on outbound messages
- Cross-channel conversation threading (SMS/voice messages visible in web chat)

---

## Cross-Cutting Concerns

### Shared message processing helper
Extract `process_patient_message(patient, content, channel, audio_url=None)` from `patient_chat_send_view` pattern. Used by web chat, SMS inbound, and voice input views. Eliminates triplication of: get conversation → add message → call workflow → add response → handle escalation.

File: `apps/agents/services.py` (add to existing file)

### Database migration: User.phone_number index
`apps/accounts/models.py` has `phone_number` CharField without `db_index`. Add `db_index=True` for SMS inbound lookup. Migration in `apps/accounts/migrations/`.

### Structured logging
Every new service method logs at INFO with: operation, patient_id, channel, and outcome. SMS body content is NOT logged in production (PHI).

---

## Implementation Order

### 3.1 — Notification Engine + Celery

The foundation everything else builds on.

#### Model changes (`apps/notifications/models.py`)

**Modify existing `Notification` model** — remove `delivery_channel`, `delivery_status`, `delivered_at`, `retry_count`, `external_id` from this model (those belong on `NotificationDelivery`). The Notification model represents the *intent* to notify.

**New model `NotificationDelivery`:**
- `notification` FK → Notification
- `channel` — choices: `in_app`, `sms`, `email`
- `status` — choices: `pending`, `sent`, `delivered`, `failed`
- `delivered_at` — DateTimeField, nullable
- `retry_count` — IntegerField, default 0
- `external_id` — CharField (Twilio SID correlation)
- `error_message` — TextField, blank
- Index on `(notification_id, channel)`, index on `(status, created_at)`

**New model `NotificationPreference`:**
- `patient` FK, `channel` (in_app/sms/email), `notification_type` (escalation/reminder/alert/update)
- `enabled` bool, `quiet_hours_start`/`quiet_hours_end` TimeFields (nullable)
- Unique constraint on (patient, channel, notification_type)

#### Backend abstraction (`apps/notifications/backends.py`)

```
BaseNotificationBackend.send(notification, delivery) -> bool
├── InAppBackend         — marks delivered (DB-only)
├── ConsoleBackend       — prints formatted notification to stdout
├── SMSBackend           — delegates to messages_app SMS backend
├── EmailBackend         — delegates to Django's email system (console email backend in dev)
└── LocMemBackend        — stores in .outbox list (for tests)
```

Setting: `NOTIFICATION_BACKENDS` — a channel-to-backend registry dict:
```python
# base.py
NOTIFICATION_BACKENDS = {
    "in_app": "apps.notifications.backends.InAppBackend",
    "sms": "apps.notifications.backends.SMSBackend",
    "email": "apps.notifications.backends.EmailBackend",
}
# development.py — override all to console
NOTIFICATION_BACKENDS = {
    "in_app": "apps.notifications.backends.InAppBackend",
    "sms": "apps.notifications.backends.ConsoleBackend",
    "email": "apps.notifications.backends.ConsoleBackend",
}
# test.py — override all to locmem
NOTIFICATION_BACKENDS = {
    "in_app": "apps.notifications.backends.LocMemBackend",
    "sms": "apps.notifications.backends.LocMemBackend",
    "email": "apps.notifications.backends.LocMemBackend",
}
```
`deliver_notification()` looks up the backend per `NotificationDelivery.channel`.

#### Service (`apps/notifications/services.py`)

`NotificationService`:
- `create_notification(patient, type, severity, title, message, clinician=None, channels=None)` — creates Notification + one NotificationDelivery per channel. Defaults channels from patient preferences.
- `deliver_notification(notification_id)` — iterates NotificationDelivery records, dispatches to backend per channel, respects preferences + quiet hours
- `mark_read(notification_id)` — marks notification and all deliveries as read
- `get_unread_for_patient(patient_id)` / `get_unread_for_clinician(clinician_id)` — with `select_related('deliveries')`
- `create_escalation_notification(escalation)` — bridge from `EscalationService`

#### Celery configuration

- `config/celery.py` — Celery app config, autodiscover tasks
- `config/__init__.py` — import celery app
- Beat schedule for scheduled reminders (5 min) and voice file cleanup (1 hour)
- `CELERY_ALWAYS_EAGER = True` in test settings

#### Celery tasks (`apps/notifications/tasks.py`)

- `deliver_notification_task(notification_id)` — called via `.delay()`
- `send_scheduled_reminders()` — periodic, paginated (100 patients per batch). Coalesces same-time notifications per patient into a single SMS (notification batching). Ad-hoc notifications (escalations, nurse messages) always send immediately via `deliver_notification_task`.

#### Integration

Modify `EscalationService.create_escalation()` in `apps/agents/services.py` to call `NotificationService.create_escalation_notification()`.

#### Tests

- `apps/notifications/tests/factories.py` — `NotificationFactory`, `NotificationDeliveryFactory`, `NotificationPreferenceFactory`
- `apps/notifications/tests/test_models.py` — model validation, defaults, constraints, idempotent delivery
- `apps/notifications/tests/test_backends.py` — each backend in isolation, console output format
- `apps/notifications/tests/test_services.py` — service methods, preference/quiet-hours, multi-channel delivery
- `apps/notifications/tests/test_tasks.py` — Celery tasks with ALWAYS_EAGER
- `apps/notifications/tests/test_integration.py` — escalation → notification chain

#### Files

| File | Action |
|------|--------|
| `apps/notifications/models.py` | Edit (NotificationDelivery, NotificationPreference) |
| `apps/notifications/backends.py` | Create |
| `apps/notifications/services.py` | Create |
| `apps/notifications/admin.py` | Edit (register new models) |
| `apps/notifications/tasks.py` | Create |
| `apps/notifications/migrations/0002_*.py` | Generate |
| `apps/notifications/tests/__init__.py` | Create |
| `apps/notifications/tests/factories.py` | Create |
| `apps/notifications/tests/test_models.py` | Create |
| `apps/notifications/tests/test_backends.py` | Create |
| `apps/notifications/tests/test_services.py` | Create |
| `apps/notifications/tests/test_tasks.py` | Create |
| `apps/notifications/tests/test_integration.py` | Create |
| `apps/agents/services.py` | Edit (bridge escalation → notification, add process_patient_message helper) |
| `apps/agents/tests/test_process_message.py` | Create (direct unit tests for shared helper) |
| `config/celery.py` | Create |
| `config/__init__.py` | Edit (import celery app) |
| `config/settings/base.py` | Edit (NOTIFICATION_BACKEND, CELERY_*) |
| `config/settings/development.py` | Edit (ConsoleBackend) |
| `config/settings/test.py` | Edit (LocMemBackend, CELERY_ALWAYS_EAGER) |
| `docker-compose.yml` | Edit (add celery worker + beat) |
| `apps/accounts/migrations/0003_*.py` | Generate (phone_number db_index) |

---

### 3.2 — SMS Integration

Twilio SMS with a console backend for development. Inbound SMS routes through the same AI workflow as web chat.

#### SMS backend abstraction (`apps/messages_app/backends.py`)

```
BaseSMSBackend
├── TwilioSMSBackend     — real Twilio (production)
├── ConsoleSMSBackend    — prints to runserver stdout with clear formatting
└── LocMemSMSBackend     — stores in .outbox list (tests)
```

Console output:
```
═══════════════ SMS ═══════════════
  To:   +15551234567
  From: +15555555555
  Body: Your care team reminder: ...
═══════════════════════════════════
```

TwilioSMSBackend: singleton pattern (like LLMClient). `send_sms()` returns `{sid, status}`.

#### SMS service (`apps/messages_app/services.py`)

`SMSService`:
- `send_sms(patient, body, notification=None)` — checks ENABLE_SMS, opt-out, rate limit → calls backend → creates `Message` record
- `handle_inbound_sms(from_number, body, twilio_sid)` — looks up patient by `User.phone_number` → creates `Message` → calls `process_patient_message()` → sends response SMS
- Opt-out: STOP/UNSUBSCRIBE → disable SMS preference; START → re-enable
- Rate limit: `SMS_RATE_LIMIT_PER_HOUR` setting (default 10)

#### Webhooks (`apps/messages_app/views.py`)

`twilio_inbound_webhook` — receives inbound SMS:
- Validates Twilio signature (skipped in DEBUG)
- Idempotency check via `external_id` (Twilio SID)
- Wraps `handle_inbound_sms()` in try/except → always returns 200 + empty TwiML (prevents Twilio retries causing duplicates)

`twilio_status_webhook` — receives delivery status callbacks:
- Validates signature
- Updates `NotificationDelivery.status` and `delivered_at`
- Returns 200

#### SMS simulator (dev toolbar)

Add "Simulate Inbound SMS" panel to existing dev toolbar (`patient_dev_actions_view`). Input: message text. On submit: calls `SMSService.handle_inbound_sms()` with the current patient's phone number. Shows the AI response in chat + console SMS output.

#### Tests

- `apps/messages_app/tests/factories.py` — `MessageFactory`
- `apps/messages_app/tests/test_backends.py` — console prints (capture stdout), locmem stores, twilio mocked
- `apps/messages_app/tests/test_services.py` — send, inbound, opt-out, rate limit, idempotency
- `apps/messages_app/tests/test_webhook.py` — valid/invalid sig, STOP keyword, error handling returns 200, status callback updates delivery

#### Files

| File | Action |
|------|--------|
| `apps/messages_app/backends.py` | Create |
| `apps/messages_app/services.py` | Create |
| `apps/messages_app/views.py` | Create |
| `apps/messages_app/urls.py` | Create |
| `apps/messages_app/admin.py` | Edit (register Message) |
| `apps/messages_app/tests/__init__.py` | Create |
| `apps/messages_app/tests/factories.py` | Create |
| `apps/messages_app/tests/test_backends.py` | Create |
| `apps/messages_app/tests/test_services.py` | Create |
| `apps/messages_app/tests/test_webhook.py` | Create |
| `config/urls.py` | Edit (include messages_app urls) |
| `config/settings/base.py` | Edit (SMS_BACKEND, SMS_RATE_LIMIT_PER_HOUR) |
| `config/settings/development.py` | Edit (ConsoleSMSBackend) |
| `config/settings/test.py` | Edit (LocMemSMSBackend) |
| `apps/patients/views.py` | Edit (SMS simulator in dev toolbar) |
| `templates/patients/dashboard.html` | Edit (SMS simulator panel in dev toolbar) |

---

### 3.3 — Voice Input

Voice as an input method — just like using the keyboard, but with your voice. MediaRecorder captures audio, transcription converts to text, text feeds through the same AI workflow. Audio files are temporary (24h HIPAA retention); transcription is the durable record.

#### Transcription backend (`apps/messages_app/transcription.py`)

Three-tier following `LLMClient`/`MockLLMClient` pattern:
```
BaseTranscriptionClient.transcribe(audio_data, format) -> str
├── MockTranscriptionClient       — returns canned text (tests)
├── LocalWhisperClient            — faster-whisper, tiny/base model, CPU (dev default)
└── RemoteTranscriptionClient     — OpenAI-compatible /v1/audio/transcriptions (production)
```

`get_transcription_client()` factory function, reads `TRANSCRIPTION_BACKEND` setting.

#### Voice views (`apps/patients/views.py`)

`patient_voice_send_view` (POST):
1. Validate audio file (max 10MB, audio/* content type, patient authenticated)
2. Save to `MEDIA_ROOT/voice_memos/<patient_id>/<uuid>.webm`
3. Transcribe via transcription client
4. Call `process_patient_message(patient, transcription, channel="voice", audio_url=file_url)`
5. Return HTML fragment (message bubble with 🎤 channel icon + transcription text + playback widget)

`patient_voice_file_view` (GET):
- Authenticated file serving — verifies requesting user owns the patient record
- Serves audio file with appropriate Content-Type
- Returns 404 if file expired/deleted

URL: `path("voice/send/", ...)` and `path("voice/file/<uuid>/", ...)` in `apps/patients/urls.py`

#### Cleanup

Management command `cleanup_voice_memos` + Celery periodic task (hourly). Deletes files older than `VOICE_MEMO_RETENTION_HOURS` (24h).

#### Frontend (`static/js/voice-recorder.js`)

Alpine.js component `voiceRecorder()`:
- **Idle**: Microphone icon button (44px, warm gray). Hidden if `!navigator.mediaDevices?.getUserMedia`
- **Recording**: Red button with pulsing glow + elapsed timer counting UP + stop/send button + cancel button. Max 60 seconds, visual warning at 45s (timer turns amber), auto-stop at 60s
- **Processing**: Spinner (same style as text send inflight)
- **Error**: "Microphone unavailable" or "Couldn't process audio"

On stop/send: POST audio blob as FormData → voice_send_view → HTMX swap into #messages.
On cancel: discard recording, return to idle.

Edge cases handled:
- `beforeunload` warning during active recording
- Debounce on record button (prevent double-tap)
- Browser tab sleep → MediaRecorder onerror → show error state

#### Playback widget (accepted expansion)

In `_message_bubble.html`, voice messages include a small audio player:
- Play/pause button + duration display
- Served via authenticated `patient_voice_file_view`
- Shows "Recording expired" placeholder if file is deleted (>24h)

#### Tests

- `apps/messages_app/tests/test_transcription.py` — mock returns text, get_client logic, empty audio handling
- `apps/patients/tests/test_voice_views.py` — success, oversized, no auth, bad format, expired file
- `apps/messages_app/tests/test_cleanup_command.py` — deletes old files, keeps new ones
- `tests/e2e/test_voice_input.py` — record button in DOM, ARIA labels (`aria-label="Record voice message"`), hidden when no MediaRecorder, timer display

#### Files

| File | Action |
|------|--------|
| `apps/messages_app/transcription.py` | Create |
| `apps/patients/views.py` | Edit (voice_send_view, voice_file_view) |
| `apps/patients/urls.py` | Edit (add voice/send/, voice/file/) |
| `apps/messages_app/management/__init__.py` | Create |
| `apps/messages_app/management/commands/__init__.py` | Create |
| `apps/messages_app/management/commands/cleanup_voice_memos.py` | Create |
| `apps/messages_app/tasks.py` | Create (cleanup periodic task) |
| `static/js/voice-recorder.js` | Create |
| `templates/components/_chat_input.html` | Edit (add record button) |
| `templates/components/_message_bubble.html` | Edit (channel icon, voice playback widget) |
| `apps/messages_app/tests/test_transcription.py` | Create |
| `apps/patients/tests/test_voice_views.py` | Create |
| `apps/messages_app/tests/test_cleanup_command.py` | Create |
| `tests/e2e/test_voice_input.py` | Create |
| `config/settings/base.py` | Edit (TRANSCRIPTION_BACKEND, VOICE_*) |
| `pyproject.toml` | Edit (add faster-whisper optional dependency) |

---

### 3.4 — WebSocket Activation & Real-Time Notifications

Enable WebSockets for real-time notification push. Chat stays HTMX (it works well); WebSockets add live notifications and delivery status updates.

#### Notification consumer (`apps/notifications/consumers.py`)

`NotificationConsumer`:
- Groups: `patient_{id}_notifications`, `clinician_{id}_notifications`
- Events: `notification.new`, `notification.read`, `delivery.status_update`

Add to `apps/agents/routing.py`.

#### Real-time delivery bridge

`NotificationService.deliver_notification()` sends channel-layer message after delivery. WebSocket clients receive notifications instantly.

#### Delivery status push

When `twilio_status_webhook` updates a `NotificationDelivery` status, push the update via channel layer so the UI can show ✓✓ in real-time.

#### Frontend (`static/js/notifications.js`)

- Connect to notification WebSocket with auto-reconnect
- Toast notification on new notification
- Update unread badge count in header
- Update delivery status indicators (✓ → ✓✓) in real-time
- Reuse notification sound from `chat.js`
- On reconnect: fetch missed notifications via REST endpoint

Template: Notification bell icon with unread badge in `base_patient.html` header.

#### Tests

- `apps/notifications/tests/test_consumers.py` — connect, receive notification, receive read event (`InMemoryChannelLayer`)
- `apps/notifications/tests/test_realtime.py` — deliver notification → channel layer message sent
- `tests/e2e/test_notifications.py` — bell icon in DOM, badge display

#### Files

| File | Action |
|------|--------|
| `apps/notifications/consumers.py` | Create |
| `apps/agents/routing.py` | Edit (add notification routes) |
| `apps/notifications/services.py` | Edit (add channel layer push) |
| `static/js/notifications.js` | Create |
| `templates/base_patient.html` | Edit (notification bell) |
| `apps/notifications/tests/test_consumers.py` | Create |
| `apps/notifications/tests/test_realtime.py` | Create |
| `tests/e2e/test_notifications.py` | Create |
| `config/settings/development.py` | Edit (ENABLE_WEBSOCKETS = True) |
| `config/settings/test.py` | Edit (InMemoryChannelLayer) |
| `docker-compose.yml` | Edit (uncomment channels worker) |

---

## Settings Summary

```python
# base.py additions
NOTIFICATION_BACKENDS = {
    "in_app": "apps.notifications.backends.InAppBackend",
    "sms": "apps.notifications.backends.SMSBackend",
    "email": "apps.notifications.backends.EmailBackend",
}
SMS_BACKEND = "apps.messages_app.backends.ConsoleSMSBackend"
SMS_RATE_LIMIT_PER_HOUR = 10
TRANSCRIPTION_BACKEND = "apps.messages_app.transcription.MockTranscriptionClient"
VOICE_MEMO_RETENTION_HOURS = 24
VOICE_MEMO_MAX_SIZE_MB = 10
VOICE_MEMO_MAX_DURATION_SECONDS = 60

# Celery
CELERY_BROKER_URL = env("REDIS_URL", default="redis://localhost:6380/0")
CELERY_RESULT_BACKEND = CELERY_BROKER_URL
CELERY_BEAT_SCHEDULE = {
    "send-scheduled-reminders": {..., "schedule": 300},
    "cleanup-voice-files": {..., "schedule": 3600},
}

# development.py
NOTIFICATION_BACKENDS = {
    "in_app": "apps.notifications.backends.InAppBackend",
    "sms": "apps.notifications.backends.ConsoleBackend",
    "email": "apps.notifications.backends.ConsoleBackend",
}
SMS_BACKEND = "apps.messages_app.backends.ConsoleSMSBackend"
TRANSCRIPTION_BACKEND = "apps.messages_app.transcription.LocalWhisperClient"
ENABLE_WEBSOCKETS = True

# test.py
NOTIFICATION_BACKENDS = {
    "in_app": "apps.notifications.backends.LocMemBackend",
    "sms": "apps.notifications.backends.LocMemBackend",
    "email": "apps.notifications.backends.LocMemBackend",
}
SMS_BACKEND = "apps.messages_app.backends.LocMemSMSBackend"
TRANSCRIPTION_BACKEND = "apps.messages_app.transcription.MockTranscriptionClient"
CELERY_ALWAYS_EAGER = True
CELERY_EAGER_PROPAGATES = True
CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
```

---

## Critical Files to Reference During Implementation

| File | Why |
|------|-----|
| `apps/agents/llm_client.py` | Backend abstraction pattern to mirror |
| `apps/agents/services.py` | Service layer pattern + `process_patient_message` extraction source |
| `apps/patients/views.py` | HTMX view pattern for voice_send_view |
| `apps/agents/tests/factories.py` | Factory Boy pattern for new factories |
| `apps/notifications/models.py` | Existing Notification model to extend |
| `apps/messages_app/models.py` | Existing Message model (channel/direction/external_id) |
| `apps/accounts/models.py` | User.phone_number for SMS lookup |
| `config/asgi.py` | WebSocket routing configuration |
| `apps/agents/routing.py` | Existing WebSocket routes to extend |
| `static/js/chat.js` | Alpine.js patterns for voice-recorder.js |
| `templates/components/_chat_input.html` | Voice record button placement |

---

## Design Specifications (Design Review)

All new UI elements use CSS custom properties for dark mode, Lucide icons, Satoshi font, and the 4px spacing grid from DESIGN.md.

### Layout Map

```
HEADER (64px, sticky, z-40)
┌─────────────────────────────────────────────────────┐
│  [Logo]              [Name] [🔔 Bell] [🔊] [🌙]   │
└─────────────────────────────────────────────────────┘

CHAT INPUT AREA
┌─────────────────────────────────────────────────────┐
│  [  textarea (flex-1)  ] [🎤 Voice] [➤ Send]       │
└─────────────────────────────────────────────────────┘

MESSAGE BUBBLE (agent, voice channel)
┌─────────────────────────────────────────────────────┐
│  🎤 voice · care_coordinator                        │
│  ┌──────────────────────────────┐                   │
│  │  Transcribed text content... │                   │
│  └──────────────────────────────┘                   │
│  ▶ 0:15 ─────────── 0:45          ← playback       │
│  2 min ago · ✓✓                    ← status         │
└─────────────────────────────────────────────────────┘
```

### Voice Record Button

**Idle:**
- Size: `w-11 h-11` (44x44px touch target)
- Shape: `rounded-full`
- Background: `bg-warm-200` / dark: `bg-warm-700`
- Hover: `bg-warm-300` / `bg-warm-600`
- Icon: Lucide `microphone`, `w-5 h-5`, inherits text color
- `aria-label="Record voice message"`
- Hidden if `!navigator.mediaDevices?.getUserMedia`
- Transition: `transition-all duration-150`
- Tab order: textarea → mic → send

**Recording:**
- Background: `bg-danger` (#DC2626) — universal "recording active" convention
- Icon: Lucide `circle-stop`, `w-5 h-5`, white
- Pulse: `animate-pulse` glow ring (2px coral)
- `aria-label="Stop recording and send"`
- Timer: `text-xs font-medium tabular-nums` counting UP — `text-warm-600` normally, `text-warning` (#D97706) at 45s+
- At 45s: `aria-live="polite"` announcement: "Recording will stop in 15 seconds"
- At 60s auto-stop: `aria-live="assertive"`: "Recording stopped, sending"
- Cancel button: `w-8 h-8` transparent, Lucide `x` icon, `aria-label="Cancel recording"`

**Recording layout — mobile (<768px):**
```
┌─────────────────────────────────────────────────────┐
│  [✕ cancel]  ● 0:15          [⏹ Stop & Send]       │
│              pulsing          44x44px               │
└─────────────────────────────────────────────────────┘
  (textarea hidden, full-width recording bar)
```

**Recording layout — desktop:**
```
┌─────────────────────────────────────────────────────┐
│  [textarea (disabled, dimmed)] [✕] ● 0:15 [⏹] [➤]  │
└─────────────────────────────────────────────────────┘
```

**Processing:** Spinner in send button area (same as text send inflight), typing indicator in chat.

**Error:** Toast: "Microphone unavailable" or "Couldn't process audio". Return to idle.

### Notification Bell

**Button:** Matches existing header button pattern (`p-3 rounded-lg transition-colors`)
- Icon: Lucide `bell`, `w-5 h-5`
- Hover: `hover:bg-warm-100` / `[data-theme='dark']:hover:bg-warm-800`
- `aria-label="Notifications"` (no badge) / `aria-label="3 unread notifications"` (with badge)
- `aria-expanded`, `aria-haspopup="true"`

**Badge:** `absolute -top-1 -right-1 w-5 h-5 rounded-full bg-danger text-white text-[10px] font-bold`
- Shows count: 1, 2, ... 9+
- Hidden at 0

**Dropdown — desktop (≥768px):**
- Position: `absolute right-0 top-full mt-2 w-80`
- Background: `var(--color-surface)`, border, `rounded-lg shadow-lg`
- Max height: `max-h-96` with `overflow-y-auto`
- Header: "Notifications" (`text-sm font-semibold`) + "Mark all read" (`text-xs text-primary`)
- Items: `px-4 py-3 border-b hover:bg-warm-50`
- Unread items: `bg-primary-50/50` tint + `border-l-3 border-l-{severity-color}`
- Read items: no tint, no left border
- `role="menu"`, items `role="menuitem"`, Escape closes, focus trap

**Dropdown — mobile (<768px):** Bottom sheet
- `fixed bottom-0 left-0 right-0 rounded-t-xl`
- Swipe-down to dismiss
- Same content as desktop dropdown
- Backdrop overlay `bg-black/30`

**Empty state:** Muted bell icon + "All caught up!" in `text-sm text-secondary`

### Channel Icons

- Position: In agent label area above bubble (before agent type, separated by ` · `)
- Icon: `w-3.5 h-3.5`, color `var(--color-text-secondary)`
- Mapping: `mic` (voice), `message-square` (SMS), no icon for web chat (default = subtraction)
- Same at all breakpoints

### Delivery Status Indicators

- Position: After timestamp, `ml-1.5`
- Font: `text-xs`
- Only on outbound messages
- Pending: no indicator
- Sent: `✓` in `text-warm-400`
- Delivered: `✓✓` in `text-primary`
- Failed: `✗` in `text-danger`
- Screen reader: `aria-label="Sent"` / `aria-label="Delivered"` / `aria-label="Failed to send"`

### Voice Playback Widget

- Container: `flex items-center gap-2 px-3 py-1.5 rounded-lg mt-1 bg-warm-50` / dark: `bg-warm-800`
- Play button: `w-7 h-7 rounded-full bg-primary text-white`, Lucide `play`/`pause` `w-3.5 h-3.5`
- `aria-label="Play voice message"` / `aria-label="Pause voice message"`
- Progress: `h-1 rounded-full bg-warm-200` with `bg-primary` fill, `role="slider"` with aria-value attrs
- Duration: `text-xs tabular-nums text-warm-500`, format `0:15 / 0:45`
- **Recording expired:** Same container, Lucide `clock` `w-3.5 h-3.5 text-warm-400` + "Recording expired" in `text-xs text-warm-400 italic`, `aria-label="Voice recording has expired"`

### Toast Notifications

- Per DESIGN.md: auto-dismiss 5s, max 3 stacked, newest on top
- Desktop: `fixed top-4 right-4 w-80`
- Mobile: `fixed top-4 left-4 right-4`
- Background: `var(--color-surface)`, `shadow-lg`, `rounded-lg`
- Left border: `border-l-4` color-coded by severity
- Content: severity icon + title (`text-sm font-medium`) + body (`text-sm text-secondary`)
- Dismiss: Lucide `x`, `aria-label="Dismiss notification"`
- Animation: slide in from right (desktop) / top (mobile), 250ms ease-out
- `role="status"`, `aria-live="polite"`
- Focus does NOT move to toast

### SMS Simulator (dev toolbar, DEBUG only)

- Input: text field matching existing dev toolbar styling
- Submit: "Simulate SMS" button
- Loading: spinner on button
- Response: appears in chat + console output

### Interaction State Coverage

```
FEATURE               | LOADING          | EMPTY              | ERROR              | SUCCESS
──────────────────────|──────────────────|────────────────────|────────────────────|──────────────
Voice Record Button   | n/a              | n/a                | Toast: "Mic        | Returns to
                      |                  |                    | unavailable"       | idle
Voice Recording       | n/a              | n/a                | Toast: "Recording  | Sends, shows
                      |                  |                    | failed"            | processing
Voice Processing      | Spinner + typing | n/a                | Error bubble in    | AI response
                      | indicator        |                    | chat               | in chat
Notification Bell     | n/a              | "All caught up!"   | n/a                | Badge count
Notification Dropdown | Skeleton lines   | Bell + "All caught | "Couldn't load"   | List with
                      |                  | up!"               | + retry link       | read/unread
Toast Notification    | n/a              | n/a                | n/a                | Slide in, 5s
Delivery Status       | ✓ (sent, gray)   | n/a                | ✗ (failed, red)    | ✓✓ (delivered)
Voice Playback        | Spinner on play  | n/a                | "Audio unavail."   | Play/pause
Recording Expired     | n/a              | "Recording expired"| n/a                | n/a
```

---

## Verification

After each sub-phase:
1. `POSTGRES_PORT=5434 pytest` — all unit/integration tests pass
2. `pytest tests/e2e/ -p no:xdist` — E2E tests pass
3. `make coverage` — stays above 90%
4. `make dev` → trigger escalation → see notification in runserver logs (console backend)
5. `make dev` → use SMS simulator in dev toolbar → see SMS in console + AI response in chat
6. `make dev` → record voice in chat → see transcription + AI response
7. `make dev` → verify notification bell shows unread count
8. Pre-commit hooks pass (`ruff`, security checks)

---

## Review History

| Review | Date | Status | Score | Mode |
|--------|------|--------|-------|------|
| CEO Review | 2026-03-19 | CLEAR | — | SELECTIVE EXPANSION |
| Eng Review | 2026-03-19 | CLEAR | — | FULL_REVIEW |
| Design Review | 2026-03-19 | CLEAR | 4→8/10 | FULL |

### Design Decisions Made
1. Notification empty state: warm minimal ("All caught up!")
2. Voice record button: warm gray idle, red when recording
3. Mobile notifications: bottom sheet (not dropdown)
4. Notification badge: count with 9+ cap
