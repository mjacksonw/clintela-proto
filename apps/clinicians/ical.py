"""iCal generation for appointment calendar events (RFC 5545)."""

from icalendar import Calendar, Event, vText


def generate_ical_event(appointment) -> bytes:
    """Generate an iCal .ics file for an appointment.

    Args:
        appointment: Appointment instance with scheduled_start, scheduled_end,
                     clinician, patient, appointment_type, virtual_visit_url.

    Returns:
        Bytes of the .ics file content.
    """
    cal = Calendar()
    cal.add("prodid", "-//Clintela//Appointment//EN")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("method", "PUBLISH")

    event = Event()
    event.add("uid", f"{appointment.id}@clintela.com")
    event.add("dtstart", appointment.scheduled_start)
    event.add("dtend", appointment.scheduled_end)
    event.add("dtstamp", appointment.scheduled_start)

    clinician_name = appointment.clinician.user.get_full_name()
    type_display = appointment.get_appointment_type_display()
    event.add("summary", f"{type_display} with {clinician_name}")

    description_parts = [
        f"Appointment: {type_display}",
        f"Clinician: {clinician_name}",
    ]
    if appointment.virtual_visit_url:
        description_parts.append(f"Join: {appointment.virtual_visit_url}")
    if appointment.notes:
        description_parts.append(f"Notes: {appointment.notes}")

    event.add("description", "\n".join(description_parts))

    if appointment.virtual_visit_url:
        event["location"] = vText(appointment.virtual_visit_url)
    else:
        event["location"] = vText("Clintela Virtual Care")

    event.add("status", "CONFIRMED")

    cal.add_component(event)
    return cal.to_ical()
