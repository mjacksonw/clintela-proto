"""Template context processor for clinical feature flag."""

from django.conf import settings


def clinical_data_flags(request):
    return {
        "ENABLE_CLINICAL_DATA": getattr(settings, "ENABLE_CLINICAL_DATA", False),
    }
