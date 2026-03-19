"""Template tags and filters for patient views."""

from django import template

register = template.Library()

AGENT_DISPLAY_NAMES = {
    "supervisor": "Clintela",
    "care_coordinator": "Care Coordinator",
    "nurse_triage": "Nurse",
    "documentation": "Documentation",
    "escalation": "Clintela",
    "specialist_cardiology": "Cardiology Specialist",
    "specialist_social_work": "Social Worker",
    "specialist_nutrition": "Nutrition Specialist",
    "specialist_pt_rehab": "Rehab Specialist",
    "specialist_palliative": "Palliative Care",
    "specialist_pharmacy": "Pharmacist",
}

AGENT_ICONS = {
    "supervisor": "bot",
    "care_coordinator": "heart-handshake",
    "nurse_triage": "stethoscope",
    "documentation": "file-text",
    "escalation": "alert-triangle",
    "specialist_cardiology": "heart-pulse",
    "specialist_social_work": "hand-helping",
    "specialist_nutrition": "apple",
    "specialist_pt_rehab": "activity",
    "specialist_palliative": "hand-heart",
    "specialist_pharmacy": "pill",
}


@register.filter
def agent_display_name(agent_type):
    """Convert agent_type slug to human-readable name."""
    return AGENT_DISPLAY_NAMES.get(agent_type, "Assistant")


@register.filter
def agent_icon(agent_type):
    """Return Lucide icon name for agent type."""
    return AGENT_ICONS.get(agent_type, "bot")
