"""Patient authentication views."""

from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.utils import timezone
from ratelimit.decorators import ratelimit
from ratelimit.core import get_usage
from .tokens import short_code_token_generator
from .utils import parse_flexible_date
from .models import AuthAttempt


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
    
    from apps.patients.models import Patient
    
    # Validate token
    try:
        # Extract patient ID from token (format: patient_id-timestamp-hash)
        patient_id = token_string.split('-')[0]
        patient = Patient.objects.get(id=patient_id)
    except (IndexError, Patient.DoesNotExist):
        return redirect('accounts:token_expired')
    
    # Verify token is valid
    if not short_code_token_generator.check_token(patient, token_string):
        return redirect('accounts:token_expired')
    
    # Verify code matches
    expected_code = short_code_token_generator.get_short_code(token_string)
    if expected_code != code:
        messages.error(request, "Code mismatch. Please check your leaflet.")
        return redirect('accounts:token_expired')
    
    # Store token in session for DOB verification
    PatientAuthSession.set_pending_auth(request, token_string, code, str(patient.id))
    
    return render(request, 'accounts/dob_entry.html', {
        'code': code,
        'patient': patient,
    })


def token_expired_view(request):
    """Show token expired page with options to resend."""
    return render(request, 'accounts/token_expired.html')


@require_http_methods(["POST"])
@ratelimit(key='ip', rate='5/h', method=['POST'])
def verify_dob_view(request):
    """Handle DOB verification.
    
    Validates DOB and creates patient session.
    """
    # Check rate limit
    usage = get_usage(request, key='ip', rate='5/h', method=['POST'])
    if usage and usage['should_limit']:
        return render(request, 'accounts/rate_limited.html', status=429)
    
    # Get pending auth info from session
    pending_auth = PatientAuthSession.get_pending_auth(request)
    token_string = pending_auth['token']
    patient_id = pending_auth['patient_id']
    
    if not token_string or not patient_id:
        messages.error(request, "Session expired. Please start again.")
        return redirect('accounts:start')
    
    # Get patient
    from apps.patients.models import Patient
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
    
    # Success! Log successful attempt
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
    
    # Redirect to patient dashboard
    return redirect('patients:dashboard')


@require_http_methods(["POST"])
@ratelimit(key='post:phone_number', rate='3/h', method=['POST'])
def resend_link_view(request):
    """Handle resending auth link via SMS."""
    # Check rate limit
    usage = get_usage(request, key='post:phone_number', rate='3/h', method=['POST'])
    if usage and usage['should_limit']:
        return render(request, 'accounts/rate_limited.html', status=429)
    
    phone_number = request.POST.get('phone_number', '').strip()
    
    if not phone_number:
        messages.error(request, "Please enter a phone number.")
        return redirect('accounts:token_expired')
    
    # TODO: Look up patient by phone, generate new token, send SMS
    # For now, show success message
    messages.success(request, "A new link has been sent to your phone.")
    return redirect('accounts:token_expired')


@require_http_methods(["POST"])
@ratelimit(key='ip', rate='10/h', method=['POST'])
def manual_entry_view(request):
    """Handle manual code + DOB entry for expired tokens."""
    # Check rate limit
    usage = get_usage(request, key='ip', rate='10/h', method=['POST'])
    if usage and usage['should_limit']:
        return render(request, 'accounts/rate_limited.html', status=429)
    
    code = request.POST.get('code', '').strip().upper()
    dob_input = request.POST.get('dob', '').strip()
    
    # TODO: Validate code + DOB combination
    # For now, show error
    messages.error(request, "Manual entry not yet implemented. Please request a new link.")
    return redirect('accounts:token_expired')


@require_http_methods(["POST"])
def logout_view(request):
    """Log out patient."""
    # Clear session
    request.session.flush()
    messages.success(request, "You have been logged out.")
    return redirect('accounts:start')
