# Patient Authentication Design

**Date:** 2026-03-18
**Status:** Approved for Implementation
**Scope:** Phase 2 - Patient onboarding and authentication system

---

## Overview

This document defines the patient authentication system for Clintela, designed around the principle of **mutual verification**: the patient verifies the system is legitimate (via matching codes), and the system verifies the patient is who they claim to be (via date of birth).

### Key Principles

1. **Trust through transparency** - Patients see their leaflet code on screen, confirming legitimacy
2. **Low friction** - No passwords to remember, no apps to download
3. **Phone-centric** - Works entirely via SMS and web browser
4. **Secure by default** - Time-limited tokens prevent replay attacks

---

## Design Philosophy: Mutual Verification

Traditional authentication: user proves identity to system.
Clintela authentication: **both parties verify each other**.

```
┌─────────────────┐         ┌─────────────────┐
│   PATIENT       │         │    CLINTELA     │
│                 │         │                 │
│ Physical leaflet│◄───────►│ Database record │
│  (code: A3B9K2) │  match  │  (code: A3B9K2) │
└────────┬────────┘         └────────┬────────┘
         │                           │
         │  Sees code in SMS         │
         │  Confirms match           │
         │                           │
         │  Clicks link              │
         │  (with TOTP token)        │
         └──────────►┌───────────────┘
                     │
         ┌───────────▼───────────┐
         │  "Your code: A3B9K2"  │
         │  "Enter your DOB:"    │
         └───────────┬───────────┘
                     │
         Patient enters DOB
         (proves identity)
                     │
         ┌───────────▼───────────┐
         │   SESSION CREATED     │
         │   (7-day rolling)     │
         └───────────────────────┘
```

**Why this works:**
- Patient **knows** the code is legitimate because they see it on both their physical leaflet AND in the SMS
- System **knows** the patient is legitimate because they have the specific phone + know the DOB
- Attacker would need: physical leaflet + patient's phone + knowledge of DOB

---

## Patient Onboarding Flow (Backend)

When a patient is discharged, a clinician/administrator enters them into Clintela:

### Required Information

| Field | Required | Notes |
|-------|----------|-------|
| MRN | Yes | Medical Record Number (links to EHR) |
| Mobile number | Yes | Primary contact for SMS |
| Recovery plan | Yes | Selected from template library |
| Name | Optional | May auto-populate from EHR via MRN |
| Leaflet code | Auto-generated | 6-character alphanumeric |

### Onboarding Steps

1. **Clinician enters MRN**
   - System fetches patient demographics from EHR (if integrated)
   - Auto-populates name, DOB

2. **Clinician confirms/edits mobile number**
   - Must be the patient's personal mobile
   - Validates format (E.164)

3. **Clinician selects recovery plan**
   - Based on surgery type
   - Determines check-in schedule, pathways

4. **System generates leaflet code**
   - 6-character alphanumeric (e.g., `A3B9K2`)
   - Unique, unguessable
   - Stored in `Patient.leaflet_code`

5. **Print leaflet**
   - System generates printable PDF
   - Contains: code prominently displayed, QR code to website, brief instructions

6. **Send welcome SMS**
   - Triggered after discharge
   - Contains code + secure link with TOTP token

---

## Ongoing Authentication (After Onboarding)

Once a patient has completed initial onboarding, they have three ways to authenticate on subsequent visits:

### Method 1: Magic Link via Web

**When:** Patient visits website directly (session expired)

**Flow:**
```
Patient visits clintela.com
         │
         ▼
┌─────────────────────────────┐
│  "Enter your phone number   │
│   or email to sign in:"     │
│                             │
│  [(555) 123-4567    ]       │
│                             │
│  [Send Magic Link]          │
└────────┬────────────────────┘
         │
         ▼
SMS sent with magic link
         │
         ▼
Patient clicks link
         │
         ▼
┌─────────────────────────────┐
│  "Welcome back, Sarah!"     │
│  Session created            │
└─────────────────────────────┘
```

**Magic Link Details:**
- Same TOTP token system as onboarding (30-min expiry, single-use)
- No DOB required (we trust the phone/email ownership)
- Link format: `clintela.com/auth/magic?token=xyz789abc`
- Patient just clicks → instant session

### Method 2: Magic Link via Email

Same as phone, but:
- Patient enters email address
- Email sent with magic link
- Link works the same way

### Method 3: SMS Conversation (DOB Verification)

**When:** Patient texts us after long gap, session expired

**Flow:**
```
Patient: "Hi, I'm having some pain"
System:  "Hi! It's been a while. To confirm it's you,
         please reply with your date of birth (MM/DD/YYYY)"
Patient: "01/15/1990"
System:  "Thanks! Now let's talk about your pain..."
```

**DOB Verification in SMS:**
- System detects expired/missing session
- Asks for DOB before continuing conversation
- Validates against `Patient.date_of_birth`
- 3-attempt limit, then human escalation
- Creates new 7-day session on success

---

## Authentication Flow

### Step 1: SMS Delivery (Initial Onboarding)

**Timing:** Sent at discharge or scheduled for specific time

**Message format:**
```
Welcome to Clintela! We're here to support your recovery.

Your code: A3B9K2
Make sure this matches your discharge leaflet.

Get started: https://clintela.com/start?code=A3B9K2&token=xyz789abc

Reply STOP to opt out.
```

**Technical details:**
- Token is a time-limited (30-minute), single-use TOTP
- Generated server-side, stored in Redis with expiry
- URL includes both code (for display) and token (for validation)

### Step 2: Patient Clicks Link

**What happens:**
1. Patient receives SMS, sees code `A3B9K2`
2. Checks physical leaflet, confirms match (builds trust)
3. Clicks link on their phone

**System validates:**
```python
# Validate token exists and hasn't expired
token_valid = redis.get(f"auth_token:{token}")
if not token_valid:
    return redirect("/token-expired")  # Prompt to resend SMS

# Validate code matches token
if token_data["leaflet_code"] != code:
    return redirect("/invalid-link")

# Mark token as used (single-use)
redis.delete(f"auth_token:{token}")
```

### Step 3: DOB Entry Page

**What patient sees:**

```
┌─────────────────────────────┐
│  Welcome to Clintela        │
│                             │
│  Your code: A3B9K2 ✓        │
│  (matches your leaflet)     │
│                             │
│  Please enter your date     │
│  of birth to continue:      │
│                             │
│  [MM/DD/YYYY]               │
│                             │
│  [Continue]                 │
│                             │
│  Code doesn't match?        │
│  Contact your care team.    │
└─────────────────────────────┘
```

**DOB Input handling:**
- Accept flexible formats: `MM/DD/YYYY`, `M/D/YY`, `MM-DD-YYYY`, etc.
- Normalize to `YYYY-MM-DD` for storage
- Show example format below input field
- Clear error message if incorrect: "Date of birth doesn't match our records. Please try again."

**Validation:**
```python
# Normalize input
parsed_dob = parse_flexible_date(dob_input)  # Returns date or None
if not parsed_dob:
    return error("Please enter a valid date")

# Compare with patient record
if parsed_dob != patient.date_of_birth:
    log_failed_attempt(patient, request)
    return error("Date of birth doesn't match")
```

### Step 4: Session Creation

**On successful DOB match:**

1. Create Django session
2. Store in session:
   - `patient_id` (link to Patient record)
   - `authenticated_at` (timestamp)
   - `last_activity` (timestamp)
3. Set session cookie with 7-day expiry
4. Redirect to patient dashboard

**Session configuration:**
```python
# settings.py
SESSION_COOKIE_AGE = 7 * 24 * 60 * 60  # 7 days in seconds
SESSION_SAVE_EVERY_REQUEST = True  # Rolling window
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
```

---

## Session Management

### Rolling 7-Day Sessions

- **Expiry:** 7 days from last activity
- **Extension:** Every request extends the session
- **Cookie:** HttpOnly, Secure, SameSite=Strict
- **Storage:** Database-backed (PostgreSQL)

### Session Lifecycle

```
Day 0: Patient authenticates → Session created (expires Day 7)
Day 2: Patient checks in → Session extended (expires Day 9)
Day 5: Patient messages agent → Session extended (expires Day 12)
Day 9: Patient checks in → Session extended (expires Day 16)
Day 16: No activity → Session expires
```

### Re-Authentication

When session expires:

1. Patient visits site → "Session expired" page
2. Options:
   - **Resend SMS** - Enter mobile number → new SMS with fresh token
   - **Enter code manually** - Type leaflet code + DOB (if they have physical leaflet)

**Resend flow:**
```
┌─────────────────────────────┐
│  Session Expired            │
│                             │
│  Enter your mobile number   │
│  to receive a new link:     │
│                             │
│  [(555) 123-4567    ]       │
│                             │
│  [Send Link]                │
│                             │
│  ───── OR ─────             │
│                             │
│  Enter your leaflet code:   │
│  [A3B9K2          ]         │
│                             │
│  And your date of birth:    │
│  [MM/DD/YYYY      ]         │
│                             │
│  [Sign In]                  │
└─────────────────────────────┘
```

---

## Security Considerations

### Threat Model

| Threat | Mitigation |
|--------|-----------|
| Leaflet lost/stolen | TOTP token required; DOB still needed; no sensitive data in session |
| SMS intercepted | TOTP is single-use and time-limited; 30-min window minimizes exposure |
| DOB guessed | 3-attempt lockout; audit logging; rate limiting |
| Session hijacking | HttpOnly cookies; HTTPS only; 7-day max lifetime |
| Replay attack | Tokens are single-use; used tokens deleted immediately |

### Rate Limiting

**DOB attempts:**
- Max 3 attempts per patient per hour
- After 3 failures: lockout for 1 hour
- Alert care team on 3rd failure (possible fraud attempt)

**SMS resend:**
- Max 3 resends per patient per day
- Prevent SMS spam/abuse

**Token generation:**
- Max 5 tokens per patient per hour
- Prevent enumeration attacks

### Audit Logging

All authentication events logged:

```json
{
  "event": "patient_auth_success",
  "patient_id": "uuid",
  "timestamp": "2026-03-18T14:30:00Z",
  "ip_address": "192.168.1.1",
  "user_agent": "Mozilla/5.0...",
  "method": "sms_link",
  "session_id": "session_uuid"
}
```

```json
{
  "event": "patient_auth_failed",
  "patient_id": "uuid",
  "timestamp": "2026-03-18T14:30:00Z",
  "ip_address": "192.168.1.1",
  "reason": "invalid_dob",
  "attempt_count": 2
}
```

---

## Data Models

### Existing (No Changes Required)

The current models already support this design:

**Patient model:**
- `leaflet_code` - 6-char alphanumeric, unique, indexed
- `date_of_birth` - DateField
- `user` - OneToOne to User (for sessions)

### New Models

**AuthToken** (PostgreSQL-backed Django model)
```python
class AuthToken(models.Model):
    """Time-limited, single-use authentication token."""

    token = models.CharField(max_length=64, unique=True, db_index=True)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    leaflet_code = models.CharField(max_length=6)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "accounts_auth_token"
        indexes = [
            models.Index(fields=["expires_at"]),  # For cleanup queries
        ]

    def is_valid(self):
        return not self.used and timezone.now() < self.expires_at
```

**Token Cleanup:** Periodic task (daily) to delete expired tokens: `AuthToken.objects.filter(expires_at__lt=timezone.now()).delete()`

**AuthAttempt** (Django model - for audit)
```python
class AuthAttempt(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    success = models.BooleanField()
    method = models.CharField(choices=[("sms_link", "SMS Link"), ("manual", "Manual Entry")])
    failure_reason = models.CharField(max_length=100, blank=True)

    class Meta:
        db_table = "accounts_auth_attempt"
```

---

## API Endpoints

### Patient-Facing

```
GET  /start?code=<code>&token=<token>
     → Validates token, shows DOB entry form

POST /auth/verify-dob
     → Body: {code, dob}
     → Creates session, returns redirect URL

POST /auth/resend-link
     → Body: {phone_number}
     → Validates phone matches patient, sends new SMS

POST /auth/manual-entry
     → Body: {code, dob}
     → For expired tokens, validates code + DOB directly

POST /auth/logout
     → Destroys session
```

### Clinician/Admin-Facing

```
POST /admin/patients/onboard
     → Body: {mrn, mobile_number, recovery_plan_id}
     → Creates patient, generates code, schedules SMS

GET  /admin/patients/{id}/resend-welcome
     → Resends welcome SMS with new token
```

---

## Edge Cases & Error Handling

### Scenario: Patient enters wrong DOB

1. Show clear error: "Date of birth doesn't match our records"
2. Log attempt (but don't reveal if code is valid)
3. After 3 attempts: "Too many attempts. Please try again in 1 hour or contact your care team."
4. Alert nurse if patient is in "yellow" or "orange" status

### Scenario: Link expired (30+ minutes)

1. Show friendly message: "This link has expired for security."
2. Offer: "Send new link to (555) 123-4567?"
3. Or: "Enter your leaflet code manually"

### Scenario: Patient has new phone number

1. Patient contacts care team
2. Clinician updates mobile number in admin
3. System sends new welcome SMS
4. Old links invalidated (token tied to phone at creation time)

### Scenario: Patient loses leaflet but has SMS

1. Patient can still authenticate via SMS link
2. They just won't see the "code matches leaflet" confirmation
3. Optional: Show warning if code hasn't been visually confirmed

### Scenario: Multiple devices

1. Patient can be logged in on multiple devices
2. Each device has separate session
3. Logging out on one doesn't affect others

---

## Implementation Notes

### Phase 2 Scope

This design is for **Phase 2 implementation** and includes:
- [ ] Token generation and validation
- [ ] SMS sending (Twilio integration)
- [ ] DOB entry form
- [ ] Session management
- [ ] Audit logging

### Future Enhancements (Phase 3+)

- [ ] Push notifications (mobile app)
- [ ] Biometric authentication (app)
- [ ] Caregiver authentication (separate flow)
- [ ] Clinician SAML SSO (separate design)

### Dependencies

- Twilio (SMS)
- Redis (token storage)
- Django sessions (configured for 7-day rolling)

### Testing Strategy

1. **Unit tests:** Token generation/validation, DOB parsing
2. **Integration tests:** Full auth flow, SMS simulation
3. **Security tests:** Rate limiting, token expiration, session hijacking
4. **E2E tests:** Patient journey from SMS to dashboard

---

## Summary

This authentication system prioritizes **patient trust** and **ease of use** while maintaining security through:

1. **Mutual verification** - Code visible in both SMS and on leaflet
2. **Time-limited tokens** - 30-minute window prevents replay
3. **Flexible DOB entry** - Reduces friction, accepts common formats
4. **Long sessions** - 7-day rolling window for daily check-ins
5. **Clear recovery** - Easy re-auth when sessions expire

The result: Patients feel confident the system is legitimate, and they can access their care coordination without passwords or friction.

---

*Design approved for Phase 2 implementation*
