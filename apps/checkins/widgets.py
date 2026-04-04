"""
Widget schema for check-in questions.

Produces JSON metadata dicts that get stored on AgentMessage.metadata.
The template layer reads these to render interactive widget components.
Mobile clients consume the same JSON to render native widgets.
"""


def build_widget_metadata(question, session, *, answered=False, selected_value=None, expired=False):
    """Build widget metadata dict for an AgentMessage.

    Args:
        question: CheckinQuestion instance
        session: CheckinSession instance
        answered: Whether the question has been answered
        selected_value: The selected value if answered
        expired: Whether the session has expired

    Returns:
        dict suitable for AgentMessage.metadata
    """
    widget = {
        "type": "checkin_widget",
        "category": "checkin",
        "widget_type": question.response_type,
        "question_code": question.code,
        "question_text": question.text,
        "session_id": str(session.id),
        "options": _build_options(question),
        "answered": answered,
        "selected_value": selected_value,
        "expired": expired,
    }
    return widget


def _build_options(question):
    """Build the options list for a question based on its response type."""
    if question.response_type == "yes_no":
        return [
            {"value": "yes", "label": "Yes"},
            {"value": "no", "label": "No"},
        ]
    elif question.response_type == "scale_1_5":
        return [{"value": i, "label": str(i)} for i in range(1, 6)]
    elif question.response_type == "scale_1_10":
        return [{"value": i, "label": str(i)} for i in range(1, 11)]
    elif question.response_type == "multiple_choice":
        return question.options or []
    elif question.response_type == "free_text":
        return []
    return []


def update_widget_answered(metadata, value):
    """Return a copy of widget metadata with answered state updated.

    Used when recording a response to mark the widget as answered
    without mutating the original dict.
    """
    updated = dict(metadata)
    updated["answered"] = True
    updated["selected_value"] = value
    return updated


def update_widget_expired(metadata):
    """Return a copy of widget metadata with expired state."""
    updated = dict(metadata)
    updated["expired"] = True
    return updated
