# Phase 3 Acceptance Testing Guide

Manual acceptance testing for Communication & Multi-modality features.

---

## Prerequisites

```bash
# 1. Start the dev server
make dev
# or:
python manage.py runserver 0.0.0.0:8000

# 2. Start Celery worker + beat (optional — needed for scheduled tasks)
celery -A config worker -l info
celery -A config beat -l info

# 3. Start Daphne for WebSocket support (optional — needed for real-time notifications)
daphne -p 8001 config.asgi:application
```

> **Without Celery/Daphne:** Everything still works except scheduled reminders, voice file
> cleanup, and real-time WebSocket push. The notification bell will show "All caught up!"
> and WebSocket errors in console are expected.

---

## 1. Dev Toolbar

**What:** DEBUG-only toolbar at the bottom of patient pages with patient info, switcher, SMS simulator, and conversation reset.

### Steps

1. Open `http://localhost:8000/patient/dashboard/`
2. Look for the red **DEV** bar fixed at the bottom of the page
3. Click it to expand

### Verify

- [ ] Shows patient name, ID, and status
- [ ] Shows surgery type, days post-op, hospital
- [ ] **Patient switcher:** dropdown lists all patients, "Switch" changes the active patient and reloads
- [ ] **Clear Chat:** resets conversation history, chat shows empty state after reload
- [ ] **SMS simulator:** type a message, click "Send SMS" — look in the terminal for console SMS output:
  ```
  ═══════════════ SMS ═══════════════
    To:   +15550000000
    From: +15555555555
    Body: ...
  ═══════════════════════════════════
  ```
- [ ] Toolbar is **not visible** when `DEBUG=False`

---

## 2. Notification Bell

**What:** Real-time notification dropdown in the header with unread badge, empty state, and mark-read.

### Steps

1. Click the bell icon in the header (right side, next to sound toggle)
2. With no notifications, verify empty state
3. Create a notification via Django shell or by triggering an escalation:
   ```python
   from apps.notifications.services import NotificationService
   from apps.patients.models import Patient
   p = Patient.objects.first()
   NotificationService().create_notification(
       patient=p, type="update", severity="info",
       title="Test notification", message="This is a test."
   )
   ```
4. Reload the page and click the bell again

### Verify

- [ ] Bell icon is 44x44px touch target
- [ ] Empty state: muted bell-off icon + "All caught up!"
- [ ] **Desktop (≥768px):** dropdown appears below bell, `max-h-96`, rounded corners, shadow
- [ ] **Mobile (<768px):** bottom sheet slides up with backdrop overlay, swipe/tap to dismiss
- [ ] Unread badge: red circle with count (1-9, then "9+"), hidden at 0
- [ ] `aria-label` updates dynamically: "Notifications" → "3 unread notifications"
- [ ] `aria-expanded` toggles on click
- [ ] Escape key closes dropdown
- [ ] Clicking outside closes dropdown
- [ ] Unread items have tinted background + colored left border by severity
- [ ] Clicking a notification marks it as read (with WebSocket/Daphne running)

---

## 3. Voice Input

**What:** Record voice messages via the microphone button. Audio is transcribed and processed through the same AI workflow as text chat.

### Steps

1. Look for the microphone button next to the chat textarea (between textarea and send button)
2. Click it — browser will ask for microphone permission
3. Record a short message (watch the timer count up)
4. Click the stop button to send, or the X to cancel

### Verify

- [ ] Mic button: 44x44px, rounded-full, `aria-label="Record voice message"`
- [ ] Mic button **hidden** if browser doesn't support `navigator.mediaDevices.getUserMedia`
- [ ] **Recording state:** pulsing red dot, elapsed timer, cancel (X) button, stop button
- [ ] Timer turns warning color (amber) at 45 seconds
- [ ] Auto-stops at 60 seconds with `aria-live` announcement
- [ ] Cancel discards the recording, returns to idle
- [ ] On send: spinner appears, typing indicator shows in chat
- [ ] Transcribed text appears in chat as a voice message with 🎤 channel icon
- [ ] Audio playback widget appears below transcription (play/pause, duration)
- [ ] `beforeunload` warning fires during active recording
- [ ] **Error state:** toast "Microphone unavailable" or "Couldn't process audio"

### Voice File Serving

- [ ] Audio served via authenticated endpoint (`/patient/voice/file/<uuid>/`)
- [ ] Requesting another patient's voice file returns 404
- [ ] Files older than 24h show "Recording expired" placeholder

### Console Output (with MockTranscriptionClient)

The mock transcription client returns a canned response. With `LocalWhisperClient`, you'll see actual transcription (requires `faster-whisper` installed: `pip install faster-whisper`).

---

## 4. Chat Input

**What:** HTMX-powered chat with suggestion chips, progressive timeout, and error recovery.

### Steps

1. Type a message in the textarea and click Send (or press Enter)
2. Click a suggestion chip ("Is this normal?", "My medications", "Talk to my care team")
3. Wait for AI response (or timeout if LLM backend is unavailable)

### Verify

- [ ] Send button disabled when textarea is empty
- [ ] Send button enabled (teal) when text is entered
- [ ] Typing indicator appears while waiting for AI response
- [ ] Suggestion chips disappear during inflight request
- [ ] On success: AI response appears with agent type label, markdown rendered
- [ ] On error: red error bubble with "Try again" link
- [ ] **After timeout (45s):** error bubble appears AND textarea re-enables (not stuck disabled)
- [ ] "Try again" link re-sends the last message
- [ ] `focus-visible:ring` visible on mic, send, and stop buttons when tabbing with keyboard
- [ ] Enter sends, Shift+Enter adds newline

---

## 5. SMS Integration

**What:** Inbound/outbound SMS via Twilio (console backend in dev). STOP/START keyword handling for opt-out.

### Testing via Dev Toolbar

1. Expand the dev toolbar at the bottom
2. Type a message in the "Simulate inbound SMS..." field
3. Click "Send SMS"
4. Check the terminal for console output of the AI response SMS

### Testing via curl

```bash
# Simulate inbound SMS
curl -X POST http://localhost:8000/sms/webhook/ \
  -d "From=+15550000000&Body=Is my swelling normal?&MessageSid=TEST001"

# Simulate STOP opt-out
curl -X POST http://localhost:8000/sms/webhook/ \
  -d "From=+15550000000&Body=STOP&MessageSid=TEST002"

# Simulate START opt-in
curl -X POST http://localhost:8000/sms/webhook/ \
  -d "From=+15550000000&Body=START&MessageSid=TEST003"

# Simulate delivery status callback
curl -X POST http://localhost:8000/sms/status/ \
  -d "MessageSid=CONSOLE_000001&MessageStatus=delivered"
```

### Verify

- [ ] Inbound SMS returns 200 with empty TwiML `<Response></Response>`
- [ ] Console shows formatted SMS box for outbound response
- [ ] STOP keyword disables SMS preferences (check in Django admin)
- [ ] START keyword re-enables SMS preferences
- [ ] Duplicate SID is ignored (send same MessageSid twice)
- [ ] Unknown phone number returns 200 (no error, logged as "unknown number")
- [ ] Rate limit kicks in after 10 outbound SMS/hour (configurable via `SMS_RATE_LIMIT_PER_HOUR`)
- [ ] Twilio signature validation is skipped in `DEBUG` mode, enforced in production

---

## 6. Notification Delivery

**What:** Multi-channel notification delivery with preferences, quiet hours, and delivery tracking.

### Testing via Django Shell

```python
from apps.notifications.services import NotificationService
from apps.patients.models import Patient

ns = NotificationService()
p = Patient.objects.first()

# Create and deliver a notification (in_app + sms)
notif = ns.create_notification(
    patient=p,
    type="reminder",
    severity="info",
    title="Follow-up reminder",
    message="Your follow-up appointment is tomorrow at 2pm.",
    channels=["in_app", "sms"],
)

# Deliver it
ns.deliver_notification(notif.id)
```

### Verify

- [ ] Console shows formatted notification for SMS/email channels
- [ ] In-app delivery marked as delivered in DB
- [ ] `NotificationDelivery` records created per channel
- [ ] Preferences respected: if patient opted out of SMS, SMS delivery skipped
- [ ] Quiet hours respected (if configured on `NotificationPreference`)

---

## 7. Message Bubbles — Channel Icons & Delivery Status

**What:** Channel indicator icons on messages and delivery status checkmarks on outbound messages.

### Verify (inspect existing messages in chat)

- [ ] Voice messages show 🎤 mic icon before agent type
- [ ] SMS messages show 💬 message-square icon
- [ ] Web chat messages have no icon (default)
- [ ] Outbound messages show delivery status: ✓ (sent, gray), ✓✓ (delivered, teal), ✗ (failed, red)
- [ ] Status indicators have `aria-label` for screen readers

---

## 8. Dark Mode

**What:** All Phase 3 elements render correctly in dark mode.

### Steps

1. Click the moon/sun toggle in the header
2. Inspect all Phase 3 elements

### Verify

- [ ] Notification bell and dropdown adapt to dark theme
- [ ] Voice recorder button uses `bg-warm-700` in dark mode
- [ ] Chat input textarea has proper dark borders and text color
- [ ] Dev toolbar is always dark (intentional — terminal aesthetic)
- [ ] Error bubbles remain readable in dark mode

---

## 9. Responsive Layout

**What:** All features work at mobile (375px), tablet (768px), and desktop (1280px).

### Mobile (< 768px)

- [ ] Chat is behind a floating action button (blue circle, bottom-right)
- [ ] Clicking FAB opens full-screen chat overlay
- [ ] Notification dropdown becomes a bottom sheet
- [ ] Header icons are 44x44px touch targets
- [ ] Voice recorder and chat input are accessible in the overlay

### Tablet (768-1023px)

- [ ] Chat sidebar collapses to icon-only strip
- [ ] Click icon to expand sidebar
- [ ] Notification dropdown works normally

### Desktop (≥ 1024px)

- [ ] Chat sidebar always visible (360px width)
- [ ] Notification dropdown positioned below bell

---

## 10. WebSocket Real-Time (requires Daphne)

**What:** Live notification push, delivery status updates, unread count sync.

### Setup

```bash
# Start Daphne ASGI server (supports WebSocket)
daphne -p 8001 config.asgi:application
```

### Steps

1. Open dashboard in browser pointing to Daphne (port 8001)
2. Open Django shell in another terminal
3. Create a notification (see Section 6)
4. Watch the browser — notification should appear as a toast

### Verify

- [ ] WebSocket connects without 404 errors in console
- [ ] On connect: receives `unread_count` message
- [ ] New notification: toast appears, badge updates
- [ ] Mark read via dropdown: badge count decreases
- [ ] Reconnect: exponential backoff, caps at 30s, stops after 10 failures
- [ ] Unauthenticated WebSocket connection is rejected (not accepted)

---

## Configuration Quick Reference

| Setting | Dev Default | Purpose |
|---------|------------|---------|
| `SMS_BACKEND` | `ConsoleSMSBackend` | Print SMS to terminal |
| `NOTIFICATION_BACKENDS` | Console for sms/email, InApp for in_app | Print notifications to terminal |
| `TRANSCRIPTION_BACKEND` | `LocalWhisperClient` | CPU transcription (falls back to mock) |
| `SMS_RATE_LIMIT_PER_HOUR` | 10 | Max outbound SMS per patient per hour |
| `VOICE_MEMO_RETENTION_HOURS` | 24 | Auto-delete voice files after 24h |
| `VOICE_MEMO_MAX_SIZE_MB` | 10 | Max upload size |
| `VOICE_MEMO_MAX_DURATION_SECONDS` | 60 | Max recording length |
| `ENABLE_WEBSOCKETS` | True (dev) | Enable WebSocket consumers |
| `ENABLE_SMS` | False | Gate for production SMS sending |

---

## Running the Test Suite

```bash
# All Phase 3 tests
POSTGRES_PORT=5434 pytest apps/notifications/ apps/messages_app/ apps/patients/tests/ -v

# Just notification tests
POSTGRES_PORT=5434 pytest apps/notifications/tests/ -v

# Just SMS tests
POSTGRES_PORT=5434 pytest apps/messages_app/tests/ -v

# Just voice tests
POSTGRES_PORT=5434 pytest apps/patients/tests/test_voice_views.py -v

# Full suite
POSTGRES_PORT=5434 pytest
```
