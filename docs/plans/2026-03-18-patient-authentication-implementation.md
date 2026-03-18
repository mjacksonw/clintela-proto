# Patient Authentication Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build patient authentication system with three modes: (1) initial onboarding with leaflet code + DOB, (2) ongoing magic links via phone/email, (3) SMS DOB verification for conversations.

**Architecture:** Django views/forms for patient-facing auth, Django's PasswordResetTokenGenerator for secure tokens (with short derived codes for display), django-ratelimit for brute force protection, Twilio for SMS delivery, standard Django sessions with custom expiry.

**Tech Stack:** Django 5.1, PostgreSQL, Twilio (SMS), django-ratelimit, pytest (testing)

**Key Design Decisions (from Architecture Review):**
- Use Django's `PasswordResetTokenGenerator` for cryptographic security, derive 6-char display codes from the full token
- Use `django-ratelimit` package instead of custom middleware
- PostgreSQL-backed token state (not Redis) with explicit expiry tracking

---

## Task 1: Install django-ratelimit and Configure Token Generator

**Files:**
- Modify: `pyproject.toml` (add django-ratelimit dependency)
- Create: `apps/accounts/tokens.py` (custom token generator with short display codes)
- Test: `apps/accounts/tests/test_tokens.py`

**Step 1: Add django-ratelimit to dependencies**

```toml
# pyproject.toml (add to dependencies)
dependencies = [
    # ... existing dependencies
    "django-ratelimit>=4.1.0",
]
```

**Step 2: Write the failing test**

```python
# apps/accounts/tests/test_tokens.py
import pytest
from datetime import timedelta
from django.utils import timezone
from apps.accounts.tokens import ShortCodeTokenGenerator
from apps.patients.models import Patient, Hospital
from apps.accounts.models import User


@pytest.mark.django_db
def test_token_generator_creates_valid_token():
    """Test that token generator creates valid tokens with short codes."""
    user = User.objects.create_user(username="testuser", password="testpass")
    hospital = Hospital.objects.create(name="Test Hospital", code="TEST001")
    patient = Patient.objects.create(
        user=user,
        hospital=hospital,
        date_of_birth="1990-01-15",
        leaflet_code="A3B9K2"
    )
    
    generator = ShortCodeTokenGenerator()
    full_token = generator.make_token(patient)
    short_code = generator.get_short_code(full_token)
    
    # Short code should be 6 characters
    assert len(short_code) == 6
    assert short_code.isalnum()
    
    # Token should be valid
    assert generator.check_token(patient, full_token) is True
```

**Step 3: Run test to verify it fails**

```bash
cd /Users/jackson/projects/clintela/proto
POSTGRES_PORT=5434 pytest apps/accounts/tests/test_tokens.py::test_token_generator_creates_valid_token -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'apps.accounts.tokens'"

**Step 4: Write minimal implementation**

```python
# apps/accounts/tokens.py
import hashlib
import secrets
import string
from django.contrib.auth.tokens import PasswordResetTokenGenerator


class ShortCodeTokenGenerator(PasswordResetTokenGenerator):
    """Token generator that creates secure tokens with short display codes.
    
    Uses Django's PasswordResetTokenGenerator for security, derives a 
    6-character alphanumeric code for patient-friendly display.
    """
    
    CODE_LENGTH = 6
    CODE_ALPHABET = string.ascii_uppercase + string.digits
    
    def get_short_code(self, token):
        """Derive a short 6-character code from the full token.
        
        Uses hash of token + secret key to create deterministic but 
        unguessable short code.
        """
        from django.conf import settings
        
        # Hash the token with secret key
        hash_input = f"{token}{settings.SECRET_KEY}".encode()
        hash_bytes = hashlib.sha256(hash_input).digest()
        
        # Convert to alphanumeric code
        code = ""
        for byte in hash_bytes:
            code += self.CODE_ALPHABET[byte % len(self.CODE_ALPHABET)]
            if len(code) >= self.CODE_LENGTH:
                break
        
        return code
    
    def generate_short_code(self):
        """Generate a random short code (for leaflet codes, not auth tokens)."""
        return "".join(
            secrets.choice(self.CODE_ALPHABET)
            for _ in range(self.CODE_LENGTH)
        )


# Singleton instance
short_code_token_generator = ShortCodeTokenGenerator()
```

**Step 5: Install dependencies and run migrations**

```bash
cd /Users/jackson/projects/clintela/proto
uv pip install django-ratelimit
python manage.py makemigrations accounts
```

**Step 6: Run test to verify it passes**

```bash
POSTGRES_PORT=5434 pytest apps/accounts/tests/test_tokens.py::test_token_generator_creates_valid_token -v
```

Expected: PASS

**Step 7: Add additional tests**

```python
# apps/accounts/tests/test_models.py

@pytest.mark.django_db
def test_auth_token_is_valid_expired():
    """Test that expired token is invalid."""
    user = User.objects.create_user(username="testuser2", password="testpass")
    hospital = Hospital.objects.create(name="Test Hospital 2", code="TEST002")
    patient = Patient.objects.create(
        user=user,
        hospital=hospital,
        date_of_birth="1990-01-15",
        leaflet_code="B4C0D1"
    )
    
    token = AuthToken.objects.create(
        token="expired_token_123",
        patient=patient,
        leaflet_code="B4C0D1",
        expires_at=timezone.now() - timedelta(minutes=1)  # Already expired
    )
    
    assert token.is_valid() is False


@pytest.mark.django_db
def test_auth_token_is_valid_used():
    """Test that used token is invalid."""
    user = User.objects.create_user(username="testuser3", password="testpass")
    hospital = Hospital.objects.create(name="Test Hospital 3", code="TEST003")
    patient = Patient.objects.create(
        user=user,
        hospital=hospital,
        date_of_birth="1990-01-15",
        leaflet_code="C5D1E2"
    )
    
    token = AuthToken.objects.create(
        token="used_token_456",
        patient=patient,
        leaflet_code="C5D1E2",
        expires_at=timezone.now() + timedelta(minutes=30),
        used=True
    )
    
    assert token.is_valid() is False
```

**Step 7: Run all new tests**

```bash
POSTGRES_PORT=5434 pytest apps/accounts/tests/test_models.py -v
```

Expected: All PASS

**Step 8: Commit**

```bash
git add apps/accounts/models.py apps/accounts/tests/test_models.py apps/accounts/migrations/
git commit -m "feat: add AuthToken model for patient authentication"
```

---

## Task 2: Create AuthAttempt Model

**Files:**
- Create: `apps/accounts/models.py` (add AuthAttempt model)
- Modify: `apps/accounts/migrations/` (run makemigrations)
- Test: `apps/accounts/tests/test_models.py`

**Step 1: Write the failing test**

```python
# apps/accounts/tests/test_models.py

@pytest.mark.django_db
def test_auth_attempt_creation():
    """Test that AuthAttempt can be created."""
    user = User.objects.create_user(username="attemptuser", password="testpass")
    hospital = Hospital.objects.create(name="Attempt Hospital", code="ATT001")
    patient = Patient.objects.create(
        user=user,
        hospital=hospital,
        date_of_birth="1985-05-20",
        leaflet_code="D6E2F3"
    )
    
    attempt = AuthAttempt.objects.create(
        patient=patient,
        ip_address="192.168.1.100",
        user_agent="Mozilla/5.0",
        success=True,
        method="sms_link",
        failure_reason=""
    )
    
    assert attempt.patient == patient
    assert attempt.ip_address == "192.168.1.100"
    assert attempt.success is True
    assert attempt.method == "sms_link"
    assert attempt.timestamp is not None
```

**Step 2: Run test to verify it fails**

```bash
POSTGRES_PORT=5434 pytest apps/accounts/tests/test_models.py::test_auth_attempt_creation -v
```

Expected: FAIL with "AttributeError: 'AuthAttempt' not defined"

**Step 3: Write minimal implementation**

```python
# apps/accounts/models.py (add after AuthToken class)

class AuthAttempt(models.Model):
    """Audit log for patient authentication attempts."""
    
    METHOD_CHOICES = [
        ("sms_link", "SMS Link"),
        ("manual", "Manual Entry"),
    ]
    
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="auth_attempts")
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    success = models.BooleanField()
    method = models.CharField(max_length=20, choices=METHOD_CHOICES)
    failure_reason = models.CharField(max_length=100, blank=True)
    
    class Meta:
        db_table = "accounts_auth_attempt"
        ordering = ["-timestamp"]
    
    def __str__(self):
        status = "success" if self.success else "failed"
        return f"Auth {status} for {self.patient} at {self.timestamp}"
```

**Step 4: Create migration**

```bash
cd /Users/jackson/projects/clintela/proto
python manage.py makemigrations accounts
```

**Step 5: Run test to verify it passes**

```bash
POSTGRES_PORT=5434 pytest apps/accounts/tests/test_models.py::test_auth_attempt_creation -v
```

Expected: PASS

**Step 6: Commit**

```bash
git add apps/accounts/models.py apps/accounts/tests/test_models.py apps/accounts/migrations/
git commit -m "feat: add AuthAttempt model for audit logging"
```

---

## Task 3: Create Token Generation Service

**Files:**
- Create: `apps/accounts/services.py`
- Create: `apps/accounts/tests/test_services.py`

**Step 1: Write the failing test**

```python
# apps/accounts/tests/test_services.py
import pytest
from datetime import timedelta
from django.utils import timezone
from apps.accounts.services import TokenService
from apps.accounts.models import AuthToken, User
from apps.patients.models import Patient, Hospital


@pytest.mark.django_db
def test_generate_token_creates_token():
    """Test that TokenService.generate creates a valid token."""
    user = User.objects.create_user(username="serviceuser", password="testpass")
    hospital = Hospital.objects.create(name="Service Hospital", code="SRV001")
    patient = Patient.objects.create(
        user=user,
        hospital=hospital,
        date_of_birth="1990-01-15",
        leaflet_code="A3B9K2"
    )
    
    token_string = TokenService.generate(patient)
    
    # Token should be a non-empty string
    assert isinstance(token_string, str)
    assert len(token_string) > 20  # Should be reasonably long
    
    # Token should exist in database
    token = AuthToken.objects.get(token=token_string)
    assert token.patient == patient
    assert token.leaflet_code == "A3B9K2"
    assert token.used is False
    assert token.is_valid() is True
    
    # Token should expire in ~30 minutes
    expected_expiry = timezone.now() + timedelta(minutes=30)
    time_diff = abs((token.expires_at - expected_expiry).total_seconds())
    assert time_diff < 5  # Within 5 seconds
```

**Step 2: Run test to verify it fails**

```bash
POSTGRES_PORT=5434 pytest apps/accounts/tests/test_services.py::test_generate_token_creates_token -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'apps.accounts.services'"

**Step 3: Write minimal implementation**

```python
# apps/accounts/services.py
import secrets
import string
from datetime import timedelta
from django.utils import timezone
from .models import AuthToken


class TokenService:
    """Service for generating and validating authentication tokens."""
    
    TOKEN_LENGTH = 32
    EXPIRY_MINUTES = 30
    
    @classmethod
    def generate(cls, patient):
        """Generate a new authentication token for a patient.
        
        Args:
            patient: Patient instance
            
        Returns:
            str: The generated token string
        """
        # Generate a secure random token
        token_string = ''.join(
            secrets.choice(string.ascii_letters + string.digits)
            for _ in range(cls.TOKEN_LENGTH)
        )
        
        # Calculate expiry time
        expires_at = timezone.now() + timedelta(minutes=cls.EXPIRY_MINUTES)
        
        # Create token record
        AuthToken.objects.create(
            token=token_string,
            patient=patient,
            leaflet_code=patient.leaflet_code,
            expires_at=expires_at
        )
        
        return token_string
    
    @classmethod
    def validate(cls, token_string):
        """Validate a token string.
        
        Args:
            token_string: The token to validate
            
        Returns:
            tuple: (is_valid: bool, token: AuthToken or None)
        """
        try:
            token = AuthToken.objects.get(token=token_string)
            if token.is_valid():
                return True, token
            return False, token
        except AuthToken.DoesNotExist:
            return False, None
    
    @classmethod
    def mark_used(cls, token_string):
        """Mark a token as used.
        
        Args:
            token_string: The token to mark
        """
        AuthToken.objects.filter(token=token_string).update(used=True)
```

**Step 4: Run test to verify it passes**

```bash
POSTGRES_PORT=5434 pytest apps/accounts/tests/test_services.py::test_generate_token_creates_token -v
```

Expected: PASS

**Step 5: Add additional tests**

```python
# apps/accounts/tests/test_services.py

@pytest.mark.django_db
def test_validate_token_valid():
    """Test validating a valid token."""
    user = User.objects.create_user(username="validuser", password="testpass")
    hospital = Hospital.objects.create(name="Valid Hospital", code="VAL001")
    patient = Patient.objects.create(
        user=user,
        hospital=hospital,
        date_of_birth="1990-01-15",
        leaflet_code="B4C0D1"
    )
    
    token_string = TokenService.generate(patient)
    is_valid, token = TokenService.validate(token_string)
    
    assert is_valid is True
    assert token is not None
    assert token.patient == patient


@pytest.mark.django_db
def test_validate_token_invalid():
    """Test validating a non-existent token."""
    is_valid, token = TokenService.validate("invalid_token_12345")
    
    assert is_valid is False
    assert token is None


@pytest.mark.django_db
def test_validate_token_expired():
    """Test validating an expired token."""
    user = User.objects.create_user(username="expireduser", password="testpass")
    hospital = Hospital.objects.create(name="Expired Hospital", code="EXP001")
    patient = Patient.objects.create(
        user=user,
        hospital=hospital,
        date_of_birth="1990-01-15",
        leaflet_code="C5D1E2"
    )
    
    # Create expired token manually
    from datetime import timedelta
    expired_token = AuthToken.objects.create(
        token="expired_abc_123",
        patient=patient,
        leaflet_code="C5D1E2",
        expires_at=timezone.now() - timedelta(minutes=1)
    )
    
    is_valid, token = TokenService.validate("expired_abc_123")
    
    assert is_valid is False
    assert token is not None  # Returns the token but marks as invalid


@pytest.mark.django_db
def test_mark_used():
    """Test marking a token as used."""
    user = User.objects.create_user(username="useduser", password="testpass")
    hospital = Hospital.objects.create(name="Used Hospital", code="USD001")
    patient = Patient.objects.create(
        user=user,
        hospital=hospital,
        date_of_birth="1990-01-15",
        leaflet_code="D6E2F3"
    )
    
    token_string = TokenService.generate(patient)
    
    # Mark as used
    TokenService.mark_used(token_string)
    
    # Verify token is now used
    token = AuthToken.objects.get(token=token_string)
    assert token.used is True
    assert token.is_valid() is False
```

**Step 6: Run all service tests**

```bash
POSTGRES_PORT=5434 pytest apps/accounts/tests/test_services.py -v
```

Expected: All PASS

**Step 7: Commit**

```bash
git add apps/accounts/services.py apps/accounts/tests/test_services.py
git commit -m "feat: add TokenService for generating and validating auth tokens"
```

---

## Task 4: Create DOB Parsing Utility

**Files:**
- Create: `apps/accounts/utils.py`
- Create: `apps/accounts/tests/test_utils.py`

**Step 1: Write the failing test**

```python
# apps/accounts/tests/test_utils.py
import pytest
from datetime import date
from apps.accounts.utils import parse_flexible_date


def test_parse_flexible_date_slash_format():
    """Test parsing MM/DD/YYYY format."""
    result = parse_flexible_date("01/15/1990")
    assert result == date(1990, 1, 15)


def test_parse_flexible_date_dash_format():
    """Test parsing MM-DD-YYYY format."""
    result = parse_flexible_date("01-15-1990")
    assert result == date(1990, 1, 15)


def test_parse_flexible_date_short_year():
    """Test parsing with 2-digit year."""
    result = parse_flexible_date("01/15/90")
    assert result == date(1990, 1, 15)


def test_parse_flexible_date_single_digits():
    """Test parsing with single digit month/day."""
    result = parse_flexible_date("1/5/1990")
    assert result == date(1990, 1, 5)


def test_parse_flexible_date_invalid():
    """Test parsing invalid date."""
    result = parse_flexible_date("not a date")
    assert result is None


def test_parse_flexible_date_empty():
    """Test parsing empty string."""
    result = parse_flexible_date("")
    assert result is None
```

**Step 2: Run test to verify it fails**

```bash
POSTGRES_PORT=5434 pytest apps/accounts/tests/test_utils.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'apps.accounts.utils'"

**Step 3: Write implementation**

```python
# apps/accounts/utils.py
import re
from datetime import datetime, date


def parse_flexible_date(date_string):
    """Parse a date string in various formats.
    
    Supported formats:
    - MM/DD/YYYY
    - MM-DD-YYYY
    - M/D/YY (single digit)
    - MM/DD/YY
    
    Args:
        date_string: String containing date
        
    Returns:
        date: Parsed date object, or None if parsing fails
    """
    if not date_string or not isinstance(date_string, str):
        return None
    
    date_string = date_string.strip()
    if not date_string:
        return None
    
    # Common date patterns
    patterns = [
        # MM/DD/YYYY or MM-DD-YYYY
        (r'^(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})$', lambda m: (int(m.group(1)), int(m.group(2)), int(m.group(3)))),
        # MM/DD/YY or MM-DD-YY (2-digit year)
        (r'^(\d{1,2})[/\-](\d{1,2})[/\-](\d{2})$', lambda m: (int(m.group(1)), int(m.group(2)), 2000 + int(m.group(3)))),
    ]
    
    for pattern, extractor in patterns:
        match = re.match(pattern, date_string)
        if match:
            try:
                month, day, year = extractor(match)
                return date(year, month, day)
            except ValueError:
                # Invalid date (e.g., 13/45/2020)
                continue
    
    # Try dateutil as fallback if available
    try:
        from dateutil import parser
        parsed = parser.parse(date_string)
        return parsed.date()
    except (ImportError, ValueError):
        pass
    
    return None
```

**Step 4: Run tests to verify**

```bash
POSTGRES_PORT=5434 pytest apps/accounts/tests/test_utils.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add apps/accounts/utils.py apps/accounts/tests/test_utils.py
git commit -m "feat: add flexible date parsing utility for DOB entry"
```

---

## Task 5: Create Auth Views - Token Validation Endpoint

**Files:**
- Create: `apps/accounts/views.py` (patient auth views)
- Create: `apps/accounts/urls.py` (URL patterns)
- Create: `apps/accounts/tests/test_views.py`

**Step 1: Write the failing test**

```python
# apps/accounts/tests/test_views.py
import pytest
from datetime import timedelta
from django.urls import reverse
from django.utils import timezone
from django.test import Client
from apps.accounts.models import AuthToken, User
from apps.accounts.services import TokenService
from apps.patients.models import Patient, Hospital


@pytest.mark.django_db
def test_start_view_with_valid_token():
    """Test start view with valid token shows DOB entry form."""
    client = Client()
    
    # Setup
    user = User.objects.create_user(username="viewuser", password="testpass")
    hospital = Hospital.objects.create(name="View Hospital", code="VIE001")
    patient = Patient.objects.create(
        user=user,
        hospital=hospital,
        date_of_birth="1990-01-15",
        leaflet_code="A3B9K2"
    )
    token_string = TokenService.generate(patient)
    
    # Request
    url = reverse('accounts:start')
    response = client.get(f"{url}?code=A3B9K2&token={token_string}")
    
    # Assertions
    assert response.status_code == 200
    assert b"A3B9K2" in response.content  # Code displayed on page
    assert b"Enter your date of birth" in response.content
```

**Step 2: Run test to verify it fails**

```bash
POSTGRES_PORT=5434 pytest apps/accounts/tests/test_views.py::test_start_view_with_valid_token -v
```

Expected: FAIL with URL resolution error or view not found

**Step 3: Write minimal implementation**

```python
# apps/accounts/views.py
from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.utils import timezone
from ratelimit.decorators import ratelimit
from ratelimit.core import get_usage
from .services import TokenService
from .utils import parse_flexible_date


class PatientAuthSession:
    """Helper class for managing patient authentication session data."""
    
    # Session keys
    PENDING_AUTH_TOKEN = 'pending_auth_token'
    PENDING_AUTH_CODE = 'pending_auth_code'
    PENDING_AUTH_PATIENT_ID = 'pending_auth_patient_id'
    PATIENT_ID = 'patient_id'
    AUTHENTICATED = 'authenticated'
    AUTH_METHOD = 'auth_method'
    AUTHENTICATED_AT = 'authenticated_at'
    
    # Auth method values
    AUTH_METHOD_SMS_LINK = 'sms_link'
    AUTH_METHOD_MANUAL = 'manual'
    AUTH_METHOD_MAGIC_LINK = 'magic_link'
    
    @classmethod
    def get_pending_auth(cls, request):
        """Get pending authentication data from session."""
        return {
            'token': request.session.get(cls.PENDING_AUTH_TOKEN),
            'code': request.session.get(cls.PENDING_AUTH_CODE),
            'patient_id': request.session.get(cls.PENDING_AUTH_PATIENT_ID),
        }
    
    @classmethod
    def set_pending_auth(cls, request, token, code, patient_id):
        """Store pending authentication data in session."""
        request.session[cls.PENDING_AUTH_TOKEN] = token
        request.session[cls.PENDING_AUTH_CODE] = code
        request.session[cls.PENDING_AUTH_PATIENT_ID] = patient_id
    
    @classmethod
    def clear_pending_auth(cls, request):
        """Clear pending authentication data from session."""
        for key in [cls.PENDING_AUTH_TOKEN, cls.PENDING_AUTH_CODE, cls.PENDING_AUTH_PATIENT_ID]:
            if key in request.session:
                del request.session[key]
    
    @classmethod
    def create_session(cls, request, patient_id, auth_method=AUTH_METHOD_SMS_LINK):
        """Create authenticated session."""
        request.session[cls.PATIENT_ID] = str(patient_id)
        request.session[cls.AUTHENTICATED] = True
        request.session[cls.AUTH_METHOD] = auth_method
        request.session[cls.AUTHENTICATED_AT] = timezone.now().isoformat()
    
    @classmethod
    def get_patient_id(cls, request):
        """Get authenticated patient ID from session."""
        return request.session.get(cls.PATIENT_ID) if request.session.get(cls.AUTHENTICATED) else None


@require_http_methods(["GET"])
@ratelimit(key='ip', rate='20/h', method=['GET'])
def start_view(request):
    """Handle start URL with token.
    
    Validates the token and shows DOB entry form.
    """
    # Check rate limit
    usage = get_usage(request, key='ip', rate='20/h', method=['GET'])
    if usage and usage['should_limit']:
        return render(request, 'accounts/rate_limited.html', status=429)
    
    code = request.GET.get('code')
    token_string = request.GET.get('token')
    
    if not code or not token_string:
        messages.error(request, "Invalid link. Please check your SMS or contact your care team.")
        return redirect('accounts:token_expired')
    
    # Validate token
    is_valid, token = TokenService.validate(token_string)
    
    if not is_valid or not token:
        return redirect('accounts:token_expired')
    
    # Verify code matches
    if token.leaflet_code != code:
        messages.error(request, "Code mismatch. Please check your leaflet.")
        return redirect('accounts:token_expired')
    
    # Store token in session for DOB verification
    PatientAuthSession.set_pending_auth(request, token_string, code, str(token.patient.id))
    
    return render(request, 'accounts/dob_entry.html', {
        'code': code,
        'patient': token.patient,
    })


def token_expired_view(request):
    """Show token expired page with options to resend."""
    return render(request, 'accounts/token_expired.html')
```

```python
# apps/accounts/urls.py
from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('start/', views.start_view, name='start'),
    path('token-expired/', views.token_expired_view, name='token_expired'),
]
```

**Step 4: Create templates**

```html
<!-- templates/accounts/dob_entry.html -->
<!DOCTYPE html>
<html>
<head>
    <title>Welcome to Clintela</title>
</head>
<body>
    <h1>Welcome to Clintela</h1>
    
    <p>Your code: <strong>{{ code }}</strong> ✓</p>
    <p>(Make sure this matches your discharge leaflet)</p>
    
    <form method="post" action="{% url 'accounts:verify_dob' %}">
        {% csrf_token %}
        <label for="dob">Please enter your date of birth:</label>
        <input type="text" id="dob" name="dob" placeholder="MM/DD/YYYY" required>
        <button type="submit">Continue</button>
    </form>
    
    <p><small>Code doesn't match? <a href="#">Contact your care team</a>.</small></p>
</body>
</html>
```

```html
<!-- templates/accounts/token_expired.html -->
<!DOCTYPE html>
<html>
<head>
    <title>Link Expired</title>
</head>
<body>
    <h1>Link Expired</h1>
    <p>This link has expired for security reasons.</p>
    
    <h2>Options:</h2>
    <form method="post" action="{% url 'accounts:resend_link' %}">
        {% csrf_token %}
        <label>Enter your mobile number:</label>
        <input type="tel" name="phone_number" placeholder="(555) 123-4567" required>
        <button type="submit">Send New Link</button>
    </form>
    
    <p>Or enter your leaflet code manually:</p>
    <form method="post" action="{% url 'accounts:manual_entry' %}">
        {% csrf_token %}
        <input type="text" name="code" placeholder="A3B9K2" required>
        <input type="text" name="dob" placeholder="MM/DD/YYYY" required>
        <button type="submit">Sign In</button>
    </form>
</body>
</html>
```

**Step 5: Update main urls.py**

```python
# config/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apps.accounts.urls', namespace='accounts')),
    # ... other apps
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

**Step 6: Run test to verify it passes**

```bash
POSTGRES_PORT=5434 pytest apps/accounts/tests/test_views.py::test_start_view_with_valid_token -v
```

Expected: PASS

**Step 7: Commit**

```bash
git add apps/accounts/views.py apps/accounts/urls.py apps/accounts/tests/test_views.py templates/
git commit -m "feat: add patient auth start view and token validation"
```

---

## Task 6: Create DOB Verification View

**Files:**
- Modify: `apps/accounts/views.py`
- Test: `apps/accounts/tests/test_views.py`

**Step 1: Write the failing test**

```python
# apps/accounts/tests/test_views.py

@pytest.mark.django_db
def test_verify_dob_success():
    """Test successful DOB verification creates session."""
    client = Client()
    
    # Setup
    user = User.objects.create_user(username="dobuser", password="testpass")
    hospital = Hospital.objects.create(name="DOB Hospital", code="DOB001")
    patient = Patient.objects.create(
        user=user,
        hospital=hospital,
        date_of_birth="1990-01-15",
        leaflet_code="A3B9K2"
    )
    token_string = TokenService.generate(patient)
    
    # First, visit start page to set session
    start_url = reverse('accounts:start')
    client.get(f"{start_url}?code=A3B9K2&token={token_string}")
    
    # Now submit DOB
    verify_url = reverse('accounts:verify_dob')
    response = client.post(verify_url, {'dob': '01/15/1990'})
    
    # Should redirect to patient dashboard
    assert response.status_code == 302
    
    # Verify session was created
    session = client.session
    assert session.get('patient_id') == str(patient.id)
    assert session.get('authenticated') is True


@pytest.mark.django_db
def test_verify_dob_failure():
    """Test DOB verification with wrong date."""
    client = Client()
    
    # Setup
    user = User.objects.create_user(username="wronguser", password="testpass")
    hospital = Hospital.objects.create(name="Wrong Hospital", code="WRG001")
    patient = Patient.objects.create(
        user=user,
        hospital=hospital,
        date_of_birth="1990-01-15",
        leaflet_code="A3B9K2"
    )
    token_string = TokenService.generate(patient)
    
    # Set session
    start_url = reverse('accounts:start')
    client.get(f"{start_url}?code=A3B9K2&token={token_string}")
    
    # Submit wrong DOB
    verify_url = reverse('accounts:verify_dob')
    response = client.post(verify_url, {'dob': '12/25/1985'})
    
    # Should show error, not redirect
    assert response.status_code == 200
    assert b"Date of birth doesn&#39;t match" in response.content or b"doesn't match" in response.content
```

**Step 2: Run test to verify it fails**

```bash
POSTGRES_PORT=5434 pytest apps/accounts/tests/test_views.py::test_verify_dob_success -v
```

Expected: FAIL with URL resolution error

**Step 3: Write implementation**

```python
# apps/accounts/views.py (add to existing file)

@require_http_methods(["POST"])
def verify_dob_view(request):
    """Handle DOB verification.
    
    Validates DOB and creates patient session.
    """
    from .models import AuthAttempt
    
    # Get pending auth info from session
    pending_auth = PatientAuthSession.get_pending_auth(request)
    token_string = pending_auth['token']
    patient_id = pending_auth['patient_id']
    
    if not token_string or not patient_id:
        messages.error(request, "Session expired. Please start again.")
        return redirect('accounts:start')
    
    # Get patient
    try:
        patient = Patient.objects.get(id=patient_id)
    except Patient.DoesNotExist:
        messages.error(request, "Patient not found.")
        return redirect('accounts:token_expired')
    
    # Parse DOB
    dob_input = request.POST.get('dob', '')
    parsed_dob = parse_flexible_date(dob_input)
    
    # Get IP and user agent
    ip_address = request.META.get('REMOTE_ADDR', '')
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    
    if not parsed_dob:
        # Log failed attempt
        AuthAttempt.objects.create(
            patient=patient,
            ip_address=ip_address,
            user_agent=user_agent,
            success=False,
            method=PatientAuthSession.AUTH_METHOD_SMS_LINK,
            failure_reason="invalid_date_format"
        )
        return render(request, 'accounts/dob_entry.html', {
            'code': pending_auth['code'],
            'patient': patient,
            'error': 'Please enter a valid date',
        })
    
    # Compare DOB
    if parsed_dob != patient.date_of_birth:
        # Log failed attempt
        AuthAttempt.objects.create(
            patient=patient,
            ip_address=ip_address,
            user_agent=user_agent,
            success=False,
            method=PatientAuthSession.AUTH_METHOD_SMS_LINK,
            failure_reason="invalid_dob"
        )
        return render(request, 'accounts/dob_entry.html', {
            'code': pending_auth['code'],
            'patient': patient,
            'error': "Date of birth doesn't match our records. Please try again.",
        })
    
    # Success! Mark token as used
    TokenService.mark_used(token_string)
    
    # Log successful attempt
    AuthAttempt.objects.create(
        patient=patient,
        ip_address=ip_address,
        user_agent=user_agent,
        success=True,
        method=PatientAuthSession.AUTH_METHOD_SMS_LINK
    )
    
    # Create session
    PatientAuthSession.create_session(request, patient.id, PatientAuthSession.AUTH_METHOD_SMS_LINK)
    
    # Clear pending auth
    PatientAuthSession.clear_pending_auth(request)
    
    # Redirect to patient dashboard (placeholder for now)
    return redirect('patients:dashboard')


@require_http_methods(["POST"])
def resend_link_view(request):
    """Handle resending auth link via SMS."""
    phone_number = request.POST.get('phone_number', '').strip()
    
    if not phone_number:
        messages.error(request, "Please enter a phone number.")
        return redirect('accounts:token_expired')
    
    # TODO: Look up patient by phone, generate new token, send SMS
    # For now, show success message
    messages.success(request, "A new link has been sent to your phone.")
    return redirect('accounts:token_expired')


@require_http_methods(["POST"])
def manual_entry_view(request):
    """Handle manual code + DOB entry for expired tokens."""
    code = request.POST.get('code', '').strip().upper()
    dob_input = request.POST.get('dob', '').strip()
    
    # TODO: Validate code + DOB combination
    # For now, show error
    messages.error(request, "Manual entry not yet implemented. Please request a new link.")
    return redirect('accounts:token_expired')
```

**Step 4: Update URLs**

```python
# apps/accounts/urls.py

urlpatterns = [
    path('start/', views.start_view, name='start'),
    path('token-expired/', views.token_expired_view, name='token_expired'),
    path('verify-dob/', views.verify_dob_view, name='verify_dob'),
    path('resend-link/', views.resend_link_view, name='resend_link'),
    path('manual-entry/', views.manual_entry_view, name='manual_entry'),
]
```

**Step 5: Update template to show errors**

```html
<!-- templates/accounts/dob_entry.html -->
<!DOCTYPE html>
<html>
<head>
    <title>Welcome to Clintela</title>
</head>
<body>
    <h1>Welcome to Clintela</h1>
    
    <p>Your code: <strong>{{ code }}</strong> ✓</p>
    <p>(Make sure this matches your discharge leaflet)</p>
    
    {% if error %}
        <div style="color: red;">{{ error }}</div>
    {% endif %}
    
    <form method="post" action="{% url 'accounts:verify_dob' %}">
        {% csrf_token %}
        <label for="dob">Please enter your date of birth:</label>
        <input type="text" id="dob" name="dob" placeholder="MM/DD/YYYY" required>
        <button type="submit">Continue</button>
    </form>
    
    <p><small>Code doesn't match? <a href="#">Contact your care team</a>.</small></p>
</body>
</html>
```

**Step 6: Run tests**

```bash
POSTGRES_PORT=5434 pytest apps/accounts/tests/test_views.py -v
```

Expected: PASS

**Step 7: Commit**

```bash
git add apps/accounts/views.py apps/accounts/urls.py apps/accounts/tests/test_views.py templates/
git commit -m "feat: add DOB verification view with session creation"
```

---

## Task 7: Configure 7-Day Rolling Sessions

**Files:**
- Modify: `config/settings/base.py`

**Step 1: Update settings**

```python
# config/settings/base.py

# Session configuration - 7-day rolling sessions
SESSION_COOKIE_AGE = 7 * 24 * 60 * 60  # 7 days in seconds
SESSION_SAVE_EVERY_REQUEST = True  # Rolling window - extends on every request
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = False  # Set to True in production with HTTPS
SESSION_COOKIE_SAMESITE = 'Lax'
```

**Step 2: Verify settings**

```bash
cd /Users/jackson/projects/clintela/proto
python -c "from django.conf import settings; settings.configure(); print('SESSION_COOKIE_AGE:', 7*24*60*60)"
```

**Step 3: Commit**

```bash
git add config/settings/base.py
git commit -m "config: set 7-day rolling session expiry"
```

---

## Task 8: Create Token Cleanup Command

**Files:**
- Create: `apps/accounts/management/commands/cleanup_tokens.py`
- Create: `apps/accounts/tests/test_commands.py`

**Step 1: Write the failing test**

```python
# apps/accounts/tests/test_commands.py
import pytest
from datetime import timedelta
from django.utils import timezone
from django.core.management import call_command
from apps.accounts.models import AuthToken, User
from apps.patients.models import Patient, Hospital


@pytest.mark.django_db
def test_cleanup_tokens_removes_expired():
    """Test that cleanup command removes expired tokens."""
    user = User.objects.create_user(username="cleanupuser", password="testpass")
    hospital = Hospital.objects.create(name="Cleanup Hospital", code="CLN001")
    patient = Patient.objects.create(
        user=user,
        hospital=hospital,
        date_of_birth="1990-01-15",
        leaflet_code="A3B9K2"
    )
    
    # Create expired token
    expired_token = AuthToken.objects.create(
        token="expired_abc_123",
        patient=patient,
        leaflet_code="A3B9K2",
        expires_at=timezone.now() - timedelta(hours=1)
    )
    
    # Create valid token
    valid_token = AuthToken.objects.create(
        token="valid_def_456",
        patient=patient,
        leaflet_code="B4C0D1",
        expires_at=timezone.now() + timedelta(hours=1)
    )
    
    # Run cleanup
    call_command('cleanup_tokens')
    
    # Verify expired token removed, valid token remains
    assert AuthToken.objects.filter(token="expired_abc_123").exists() is False
    assert AuthToken.objects.filter(token="valid_def_456").exists() is True
```

**Step 2: Run test to verify it fails**

```bash
POSTGRES_PORT=5434 pytest apps/accounts/tests/test_commands.py::test_cleanup_tokens_removes_expired -v
```

Expected: FAIL with "Unknown command: 'cleanup_tokens'"

**Step 3: Write implementation**

```python
# apps/accounts/management/__init__.py (empty file)
```

```python
# apps/accounts/management/commands/__init__.py (empty file)
```

```python
# apps/accounts/management/commands/cleanup_tokens.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.accounts.models import AuthToken


class Command(BaseCommand):
    help = 'Clean up expired authentication tokens'
    
    def handle(self, *args, **options):
        expired_count = AuthToken.objects.filter(
            expires_at__lt=timezone.now()
        ).count()
        
        AuthToken.objects.filter(
            expires_at__lt=timezone.now()
        ).delete()
        
        self.stdout.write(
            self.style.SUCCESS(f'Deleted {expired_count} expired tokens')
        )
```

**Step 4: Run test to verify it passes**

```bash
POSTGRES_PORT=5434 pytest apps/accounts/tests/test_commands.py::test_cleanup_tokens_removes_expired -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add apps/accounts/management/ apps/accounts/tests/test_commands.py
git commit -m "feat: add cleanup_tokens management command for expired tokens"
```

---

## Task 9: Create Patient Dashboard Placeholder

**Files:**
- Create: `apps/patients/views.py`
- Create: `apps/patients/urls.py`
- Create: `templates/patients/dashboard.html`

**Step 1: Create minimal dashboard view**

```python
# apps/patients/views.py
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.conf import settings


def patient_dashboard_view(request):
    """Patient dashboard - placeholder for Phase 2."""
    # Check if patient is authenticated via session
    patient_id = request.session.get('patient_id')
    authenticated = request.session.get('authenticated')
    
    if not patient_id or not authenticated:
        return redirect('accounts:start')
    
    from .models import Patient
    try:
        patient = Patient.objects.get(id=patient_id)
    except Patient.DoesNotExist:
        return redirect('accounts:start')
    
    return render(request, 'patients/dashboard.html', {
        'patient': patient,
    })
```

```python
# apps/patients/urls.py
from django.urls import path
from . import views

app_name = 'patients'

urlpatterns = [
    path('dashboard/', views.patient_dashboard_view, name='dashboard'),
]
```

```html
<!-- templates/patients/dashboard.html -->
<!DOCTYPE html>
<html>
<head>
    <title>Clintela - Your Recovery</title>
</head>
<body>
    <h1>Welcome, {{ patient.user.get_full_name }}</h1>
    <p>This is your patient dashboard.</p>
    <p>Recovery plan and AI agent features coming in Phase 3.</p>
    
    <p><a href="{% url 'accounts:logout' %}">Log out</a></p>
</body>
</html>
```

**Step 2: Add logout view**

```python
# apps/accounts/views.py (add to existing file)

@require_http_methods(["POST"])
def logout_view(request):
    """Log out patient."""
    # Clear session
    request.session.flush()
    messages.success(request, "You have been logged out.")
    return redirect('accounts:start')
```

**Step 3: Update URLs**

```python
# apps/accounts/urls.py

urlpatterns = [
    # ... existing patterns
    path('logout/', views.logout_view, name='logout'),
]
```

**Step 4: Update main urls.py**

```python
# config/urls.py

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apps.accounts.urls', namespace='accounts')),
    path('patient/', include('apps.patients.urls', namespace='patients')),
]
```

**Step 5: Commit**

```bash
git add apps/patients/views.py apps/patients/urls.py apps/accounts/views.py config/urls.py templates/
git commit -m "feat: add patient dashboard placeholder and logout view"
```

---

## Task 10: Add Rate Limiting with django-ratelimit

**Files:**
- Modify: `apps/accounts/views.py` (add @ratelimit decorators)
- Modify: `config/settings/base.py` (configure cache for rate limiting)
- Create: `templates/accounts/rate_limited.html`

**Step 1: Add @ratelimit decorators to auth views**

```python
# apps/accounts/views.py
from ratelimit.decorators import ratelimit
from ratelimit.core import get_usage
from django.http import JsonResponse

# Rate limit: 5 attempts per hour per IP for DOB verification
@ratelimit(key='ip', rate='5/h', method=['POST'])
def verify_dob_view(request):
    """Handle DOB verification with rate limiting."""
    # Check if rate limited
    usage = get_usage(request, key='ip', rate='5/h', method=['POST'])
    if usage and usage['should_limit']:
        return render(request, 'accounts/rate_limited.html', status=429)
    
    # ... rest of implementation

# Rate limit: 3 SMS resends per hour per phone number
@ratelimit(key='post:phone_number', rate='3/h', method=['POST'])
def resend_link_view(request):
    """Handle resending auth link via SMS with rate limiting."""
    # ... implementation

# Rate limit: 10 manual entry attempts per hour per IP
@ratelimit(key='ip', rate='10/h', method=['POST'])
def manual_entry_view(request):
    """Handle manual code + DOB entry with rate limiting."""
    # ... implementation
```

**Step 2: Create rate limited template**

```html
<!-- templates/accounts/rate_limited.html -->
<!DOCTYPE html>
<html>
<head>
    <title>Rate Limited</title>
</head>
<body>
    <h1>Too Many Attempts</h1>
    <p>You've made too many attempts. Please try again in an hour.</p>
    <p>If you need immediate assistance, contact your care team.</p>
</body>
</html>
```

**Step 3: Update settings for django-ratelimit**

```python
# config/settings/base.py

# django-ratelimit configuration
RATELIMIT_ENABLE = True
RATELIMIT_USE_CACHE = 'default'

# Use Redis for rate limiting if available, fallback to database
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': env('REDIS_URL', default='redis://localhost:6380/1'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}
```

**Step 4: Add rate limiting tests**

```python
# apps/accounts/tests/test_rate_limiting.py
import pytest
from django.test import Client
from django.urls import reverse
from datetime import timedelta
from django.utils import timezone
from apps.accounts.models import User, AuthAttempt
from apps.patients.models import Patient, Hospital
from apps.accounts.tokens import short_code_token_generator


@pytest.mark.django_db
class TestRateLimiting:
    """Test rate limiting on authentication endpoints."""
    
    def setup_method(self):
        """Set up test patient and token."""
        self.client = Client()
        self.user = User.objects.create_user(username="rateuser", password="testpass")
        self.hospital = Hospital.objects.create(name="Rate Hospital", code="RAT001")
        self.patient = Patient.objects.create(
            user=self.user,
            hospital=self.hospital,
            date_of_birth="1990-01-15",
            leaflet_code="A3B9K2"
        )
        self.token = short_code_token_generator.make_token(self.patient)
        self.short_code = short_code_token_generator.get_short_code(self.token)
    
    def test_start_view_rate_limit_allows_normal_use(self):
        """Test that start_view allows 20 requests per hour normally."""
        # Make 20 requests (should all succeed)
        for _ in range(20):
            response = self.client.get(
                reverse('accounts:start'),
                {'code': self.short_code, 'token': self.token}
            )
            assert response.status_code in [200, 302]  # Success or redirect
    
    def test_start_view_rate_limit_blocks_after_20(self):
        """Test that start_view returns 429 after 20 requests per hour."""
        # Make 20 requests
        for _ in range(20):
            self.client.get(
                reverse('accounts:start'),
                {'code': self.short_code, 'token': self.token}
            )
        
        # 21st request should be rate limited
        response = self.client.get(
            reverse('accounts:start'),
            {'code': self.short_code, 'token': self.token}
        )
        assert response.status_code == 429
        assert b"Too Many Attempts" in response.content
    
    def test_verify_dob_rate_limit_allows_5_attempts(self):
        """Test that verify_dob allows 5 POST requests per hour."""
        # Set up session
        session = self.client.session
        session['pending_auth_token'] = self.token
        session['pending_auth_code'] = self.short_code
        session['pending_auth_patient_id'] = str(self.patient.id)
        session.save()
        
        # Make 5 DOB verification attempts (should all be processed)
        for _ in range(5):
            response = self.client.post(
                reverse('accounts:verify_dob'),
                {'dob': '12/25/1985'}  # Wrong DOB
            )
            assert response.status_code == 200  # Shows error, not rate limited
    
    def test_verify_dob_rate_limit_blocks_after_5(self):
        """Test that verify_dob returns 429 after 5 attempts per hour."""
        # Set up session
        session = self.client.session
        session['pending_auth_token'] = self.token
        session['pending_auth_code'] = self.short_code
        session['pending_auth_patient_id'] = str(self.patient.id)
        session.save()
        
        # Make 5 DOB verification attempts
        for _ in range(5):
            self.client.post(
                reverse('accounts:verify_dob'),
                {'dob': '12/25/1985'}  # Wrong DOB
            )
        
        # 6th attempt should be rate limited
        response = self.client.post(
            reverse('accounts:verify_dob'),
            {'dob': '01/15/1990'}  # Correct DOB
        )
        assert response.status_code == 429
    
    def test_resend_link_rate_limit_by_phone(self):
        """Test that resend_link rate limits by phone number."""
        # Make 3 resend attempts for same phone
        for _ in range(3):
            response = self.client.post(
                reverse('accounts:resend_link'),
                {'phone_number': '(555) 123-4567'}
            )
            assert response.status_code == 302  # Redirect (success)
        
        # 4th attempt should be rate limited
        response = self.client.post(
            reverse('accounts:resend_link'),
            {'phone_number': '(555) 123-4567'}
        )
        assert response.status_code == 429
    
    def test_resend_link_rate_limit_different_phones_independent(self):
        """Test that rate limits are per-phone, not global."""
        # Make 3 attempts for phone 1
        for _ in range(3):
            self.client.post(
                reverse('accounts:resend_link'),
                {'phone_number': '(555) 123-4567'}
            )
        
        # Different phone should still have full quota
        response = self.client.post(
            reverse('accounts:resend_link'),
            {'phone_number': '(555) 999-8888'}
        )
        assert response.status_code == 302  # Not rate limited
    
    def test_manual_entry_rate_limit_blocks_after_10(self):
        """Test that manual_entry returns 429 after 10 attempts per hour."""
        # Make 10 manual entry attempts
        for _ in range(10):
            self.client.post(
                reverse('accounts:manual_entry'),
                {'code': self.short_code, 'dob': '12/25/1985'}
            )
        
        # 11th attempt should be rate limited
        response = self.client.post(
            reverse('accounts:manual_entry'),
            {'code': self.short_code, 'dob': '01/15/1990'}
        )
        assert response.status_code == 429


@pytest.mark.django_db
class TestRateLimitEdgeCases:
    """Test edge cases for rate limiting."""
    
    def test_rate_limit_shows_custom_template(self):
        """Test that rate limited requests show custom rate_limited template."""
        client = Client()
        user = User.objects.create_user(username="templateuser", password="testpass")
        hospital = Hospital.objects.create(name="Template Hospital", code="TMP001")
        patient = Patient.objects.create(
            user=user,
            hospital=hospital,
            date_of_birth="1990-01-15",
            leaflet_code="A3B9K2"
        )
        token = short_code_token_generator.make_token(patient)
        short_code = short_code_token_generator.get_short_code(token)
        
        # Exhaust rate limit
        for _ in range(20):
            client.get(reverse('accounts:start'), {'code': short_code, 'token': token})
        
        # Next request should show custom template
        response = client.get(reverse('accounts:start'), {'code': short_code, 'token': token})
        assert response.status_code == 429
        assert b"contact your care team" in response.content.lower()
```

**Step 5: Run rate limiting tests**

```bash
POSTGRES_PORT=5434 pytest apps/accounts/tests/test_rate_limiting.py -v
```

Expected: All PASS

**Step 6: Commit**

```bash
git add apps/accounts/tests/test_rate_limiting.py
git commit -m "test: add comprehensive rate limiting tests"
```

---

## Task 11: Run Full Test Suite

**Step 1: Run all accounts tests**

```bash
POSTGRES_PORT=5434 pytest apps/accounts/tests/ -v
```

Expected: All PASS

**Step 2: Check code coverage**

```bash
POSTGRES_PORT=5434 pytest apps/accounts/tests/ --cov=apps.accounts --cov-report=term-missing
```

**Step 3: Run linting**

```bash
ruff check apps/accounts/
```

Expected: No errors

**Step 4: Final commit**

```bash
git add .
git commit -m "feat: complete patient authentication system (Phase 2)"
```

---

## Summary

This implementation plan creates a complete patient authentication system with:

1. **AuthToken model** - PostgreSQL-backed, 30-minute expiry
2. **AuthAttempt model** - Comprehensive audit logging
3. **TokenService** - Generate, validate, and mark tokens as used
4. **DOB parsing** - Flexible date formats
5. **Views** - Start page, DOB verification, session creation
6. **7-day sessions** - Rolling window configuration
7. **Token cleanup** - Daily management command
8. **Rate limiting** - Protection against brute force
9. **Templates** - Basic HTML for all flows

**Next Phase:** SMS integration with Twilio, SMS sending on patient onboarding.

---

*Plan complete and saved to `docs/plans/2026-03-18-patient-authentication-implementation.md`*

**Execution Options:**

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

Which approach would you prefer?
