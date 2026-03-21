"""Views for administrator KPI dashboard."""

import csv
import logging

from django.contrib.auth import authenticate, login, logout
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from apps.administrators.auth import admin_required
from apps.administrators.services import (
    CensusService,
    EngagementService,
    EscalationAnalyticsService,
    OperationalAlertService,
    OutcomesService,
    PathwayAnalyticsService,
    ReadmissionService,
)
from apps.patients.models import Hospital

logger = logging.getLogger(__name__)


def _get_filters(request):
    """Extract hospital_id and days from query params."""
    hospital_id = request.GET.get("hospital")
    if hospital_id:
        try:
            hospital_id = int(hospital_id)
        except (ValueError, TypeError):
            hospital_id = None

    days = request.GET.get("days", "30")
    try:
        days = int(days)
        if days not in (7, 14, 30, 60, 90, 120):
            days = 30
    except (ValueError, TypeError):
        days = 30

    return hospital_id, days


def _sanitize_csv_value(value):
    """Prevent CSV formula injection by prefixing dangerous characters."""
    s = str(value)
    if s and s[0] in ("=", "-", "+", "@"):
        return f"\t{s}"
    return s


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def admin_login_view(request):
    """Login view for administrators."""
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        user = authenticate(request, username=username, password=password)

        if user is not None and user.role == "admin":
            login(request, user)
            logger.info("Admin login: user=%s", user.id)
            return redirect("administrators:dashboard")

        return render(
            request,
            "administrators/login.html",
            {"error": "Invalid credentials or not an administrator account."},
        )

    return render(request, "administrators/login.html")


def admin_logout_view(request):
    """Logout and redirect to login."""
    logger.info("Admin logout: user=%s", request.user.id if request.user.is_authenticated else "anon")
    logout(request)
    return redirect("administrators:login")


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


@admin_required
def dashboard_view(request):
    """Main KPI scorecard dashboard."""
    hospitals = Hospital.objects.filter(is_active=True).order_by("name")
    hospital_id, days = _get_filters(request)

    context = {
        "hospitals": hospitals,
        "selected_hospital": hospital_id,
        "selected_days": days,
        "days_options": [30, 60, 90, 120],
        "period_options": [7, 30, 60, 90, 120],
    }
    return render(request, "administrators/dashboard.html", context)


# ---------------------------------------------------------------------------
# HTMX KPI Fragments
# ---------------------------------------------------------------------------


@admin_required
@require_GET
def hero_readmission_fragment(request):
    """Hero readmission rate card."""
    hospital_id, days = _get_filters(request)
    hero_days = request.GET.get("period")
    if hero_days:
        try:
            hero_days = int(hero_days)
        except (ValueError, TypeError):
            hero_days = days
    else:
        hero_days = days

    data = ReadmissionService.get_cohort_rate(days=hero_days, hospital_id=hospital_id)
    trend = ReadmissionService.get_trend(days=90, hospital_id=hospital_id)

    return render(
        request,
        "administrators/components/_hero_readmission.html",
        {"data": data, "trend": trend, "selected_period": hero_days, "period_options": [7, 30, 60, 90, 120]},
    )


@admin_required
@require_GET
def census_fragment(request):
    """Census card."""
    hospital_id, _ = _get_filters(request)
    triage = CensusService.get_triage_distribution(hospital_id)
    summary = CensusService.get_population_summary(hospital_id)
    return render(
        request,
        "administrators/components/_census_card.html",
        {"triage": triage, "summary": summary},
    )


@admin_required
@require_GET
def alerts_fragment(request):
    """Operational alerts bar (auto-refreshes every 5 min)."""
    alerts = OperationalAlertService.get_all_alerts()
    return render(request, "administrators/components/_alerts_bar.html", {"alerts": alerts})


@admin_required
@require_GET
def discharge_to_community_fragment(request):
    """Discharge to community card."""
    hospital_id, days = _get_filters(request)
    data = OutcomesService.get_discharge_to_community(days=days, hospital_id=hospital_id)
    return render(request, "administrators/components/_discharge_to_community_card.html", {"data": data})


@admin_required
@require_GET
def functional_improvement_fragment(request):
    """Functional improvement card (no data yet state)."""
    return render(request, "administrators/components/_functional_improvement_card.html", {})


@admin_required
@require_GET
def followup_completion_fragment(request):
    """Follow-up completion card."""
    hospital_id, days = _get_filters(request)
    data = OutcomesService.get_followup_completion(days=days, hospital_id=hospital_id)
    return render(request, "administrators/components/_followup_completion_card.html", {"data": data})


@admin_required
@require_GET
def engagement_fragment(request):
    """Program engagement card with multi-horizon display."""
    hospital_id, _ = _get_filters(request)
    horizons = EngagementService.get_program_engagement_multi_horizon(hospital_id=hospital_id)
    return render(request, "administrators/components/_engagement_card.html", {"horizons": horizons})


@admin_required
@require_GET
def message_volume_fragment(request):
    """Message volume card."""
    hospital_id, days = _get_filters(request)
    data = EngagementService.get_messaging_stats(days=days, hospital_id=hospital_id)
    return render(request, "administrators/components/_message_volume_card.html", {"data": data})


@admin_required
@require_GET
def checkin_completion_fragment(request):
    """Check-in completion card."""
    hospital_id, days = _get_filters(request)
    data = EngagementService.get_checkin_stats(days=days, hospital_id=hospital_id)
    return render(request, "administrators/components/_checkin_completion_card.html", {"data": data})


@admin_required
@require_GET
def escalation_response_fragment(request):
    """Escalation response card."""
    hospital_id, days = _get_filters(request)
    stats = EscalationAnalyticsService.get_response_stats(days=days, hospital_id=hospital_id)
    breakdown = EscalationAnalyticsService.get_status_breakdown(hospital_id=hospital_id)
    return render(
        request,
        "administrators/components/_escalation_response_card.html",
        {"stats": stats, "breakdown": breakdown},
    )


@admin_required
@require_GET
def pathway_performance_fragment(request):
    """Pathway performance card."""
    pathways = PathwayAnalyticsService.get_pathway_list_with_stats()
    return render(request, "administrators/components/_pathway_performance_card.html", {"pathways": pathways})


# ---------------------------------------------------------------------------
# CSV Export
# ---------------------------------------------------------------------------


class _Echo:
    """Pseudo-buffer for StreamingHttpResponse."""

    def write(self, value):
        return value


@admin_required
@require_GET
def export_csv_view(request):
    """Export current KPI snapshot as CSV."""
    hospital_id, days = _get_filters(request)

    def generate_rows():
        writer = csv.writer(_Echo())
        yield writer.writerow(["Clintela KPI Report", f"Period: {days} days"])
        yield writer.writerow([])

        # Readmission
        readmit = ReadmissionService.get_cohort_rate(days=days, hospital_id=hospital_id)
        yield writer.writerow(["Readmission Rate"])
        yield writer.writerow(["Metric", "Value"])
        yield writer.writerow(
            [
                _sanitize_csv_value("Rate"),
                _sanitize_csv_value(readmit.get("display", "N/A")),
            ]
        )
        yield writer.writerow(
            [
                _sanitize_csv_value("Readmissions"),
                _sanitize_csv_value(readmit.get("readmissions", 0)),
            ]
        )
        yield writer.writerow(
            [
                _sanitize_csv_value("Discharges"),
                _sanitize_csv_value(readmit.get("discharges", 0)),
            ]
        )
        yield writer.writerow([])

        # Census
        triage = CensusService.get_triage_distribution(hospital_id)
        yield writer.writerow(["Census"])
        yield writer.writerow(["Status", "Count"])
        for color in ["green", "yellow", "orange", "red"]:
            yield writer.writerow([_sanitize_csv_value(color.title()), _sanitize_csv_value(triage.get(color, 0))])
        yield writer.writerow([])

        # Engagement
        engagement = EngagementService.get_program_engagement(days=days, hospital_id=hospital_id)
        yield writer.writerow(["Engagement"])
        yield writer.writerow(["Metric", "Value"])
        yield writer.writerow(
            [
                _sanitize_csv_value("Program Engagement"),
                _sanitize_csv_value(engagement.get("display", "N/A")),
            ]
        )

        messaging = EngagementService.get_messaging_stats(days=days, hospital_id=hospital_id)
        yield writer.writerow(
            [
                _sanitize_csv_value("Total Messages"),
                _sanitize_csv_value(messaging.get("total", 0)),
            ]
        )
        yield writer.writerow(
            [
                _sanitize_csv_value("Avg per Patient"),
                _sanitize_csv_value(messaging.get("avg_per_patient", 0)),
            ]
        )
        yield writer.writerow([])

        # Escalations
        esc_stats = EscalationAnalyticsService.get_response_stats(days=days, hospital_id=hospital_id)
        yield writer.writerow(["Escalation Response"])
        yield writer.writerow(["Metric", "Value"])
        yield writer.writerow(
            [
                _sanitize_csv_value("Avg Response Time (min)"),
                _sanitize_csv_value(esc_stats.get("avg_minutes", "N/A")),
            ]
        )
        yield writer.writerow(
            [
                _sanitize_csv_value("SLA Compliance"),
                _sanitize_csv_value(
                    f"{esc_stats.get('sla_compliance', 'N/A')}%"
                    if esc_stats.get("sla_compliance") is not None
                    else "N/A"
                ),
            ]
        )

    response = StreamingHttpResponse(generate_rows(), content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="clintela-kpi-report-{days}d.csv"'
    return response


# ---------------------------------------------------------------------------
# Pathway Administration
# ---------------------------------------------------------------------------


@admin_required
def pathway_list_view(request):
    """Pathway list page with effectiveness stats."""
    pathways = PathwayAnalyticsService.get_pathway_list_with_stats()
    return render(request, "administrators/pathways.html", {"pathways": pathways})


@admin_required
def pathway_detail_view(request, pathway_id):
    """Pathway detail with milestones and per-milestone check-in rates."""
    data = PathwayAnalyticsService.get_pathway_effectiveness(pathway_id)
    if "error" in data and data["error"] == "Pathway not found.":
        from django.http import Http404

        raise Http404("Pathway not found")
    return render(request, "administrators/pathway_detail.html", {"data": data})


@admin_required
@require_POST
def pathway_toggle_active_view(request, pathway_id):
    """Toggle pathway is_active status."""
    from apps.pathways.models import ClinicalPathway

    pathway = get_object_or_404(ClinicalPathway, id=pathway_id)
    pathway.is_active = not pathway.is_active
    pathway.save(update_fields=["is_active"])
    logger.info("Admin toggled pathway %s active=%s (user=%s)", pathway_id, pathway.is_active, request.user.id)

    # Return updated pathway list
    pathways = PathwayAnalyticsService.get_pathway_list_with_stats()
    return render(request, "administrators/components/_pathway_list_table.html", {"pathways": pathways})


@admin_required
@require_POST
def pathway_edit_view(request, pathway_id):
    """Edit pathway metadata."""
    from apps.pathways.models import ClinicalPathway

    pathway = get_object_or_404(ClinicalPathway, id=pathway_id)

    name = request.POST.get("name", "").strip()
    description = request.POST.get("description", "").strip()
    duration_days = request.POST.get("duration_days")

    errors = {}
    if not name:
        errors["name"] = "Name is required."
    if duration_days:
        try:
            duration_days = int(duration_days)
            if duration_days < 1:
                errors["duration_days"] = "Duration must be at least 1 day."
        except ValueError:
            errors["duration_days"] = "Duration must be a number."

    if errors:
        data = PathwayAnalyticsService.get_pathway_effectiveness(pathway_id)
        data["errors"] = errors
        return render(request, "administrators/pathway_detail.html", {"data": data})

    pathway.name = name
    pathway.description = description
    if duration_days:
        pathway.duration_days = duration_days
    pathway.save(update_fields=["name", "description", "duration_days"])
    logger.info("Admin edited pathway %s (user=%s)", pathway_id, request.user.id)

    data = PathwayAnalyticsService.get_pathway_effectiveness(pathway_id)
    data["success"] = "Pathway updated successfully."
    return render(request, "administrators/pathway_detail.html", {"data": data})


@admin_required
@require_POST
def milestone_edit_view(request, milestone_id):
    """Edit milestone details."""
    from apps.pathways.models import PathwayMilestone

    milestone = get_object_or_404(PathwayMilestone, id=milestone_id)

    title = request.POST.get("title", "").strip()
    description = request.POST.get("description", "").strip()

    if not title:
        data = PathwayAnalyticsService.get_pathway_effectiveness(milestone.pathway_id)
        data["milestone_errors"] = {milestone_id: "Title is required."}
        return render(request, "administrators/pathway_detail.html", {"data": data})

    milestone.title = title
    milestone.description = description
    milestone.save(update_fields=["title", "description"])
    logger.info("Admin edited milestone %s (user=%s)", milestone_id, request.user.id)

    data = PathwayAnalyticsService.get_pathway_effectiveness(milestone.pathway_id)
    data["success"] = "Milestone updated successfully."
    return render(request, "administrators/pathway_detail.html", {"data": data})
