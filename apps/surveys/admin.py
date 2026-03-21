from django.contrib import admin

from apps.surveys.models import (
    SurveyAnswer,
    SurveyAssignment,
    SurveyInstance,
    SurveyInstrument,
    SurveyQuestion,
)


class SurveyQuestionInline(admin.TabularInline):
    model = SurveyQuestion
    extra = 0
    ordering = ["order"]


@admin.register(SurveyInstrument)
class SurveyInstrumentAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "category", "version", "is_active", "estimated_minutes"]
    list_filter = ["category", "is_active", "is_standard"]
    search_fields = ["code", "name"]
    inlines = [SurveyQuestionInline]


@admin.register(SurveyAssignment)
class SurveyAssignmentAdmin(admin.ModelAdmin):
    list_display = ["patient", "instrument", "schedule_type", "is_active", "start_date"]
    list_filter = ["schedule_type", "is_active"]
    raw_id_fields = ["patient", "assigned_by"]


class SurveyAnswerInline(admin.TabularInline):
    model = SurveyAnswer
    extra = 0
    readonly_fields = ["question", "value", "raw_value"]


@admin.register(SurveyInstance)
class SurveyInstanceAdmin(admin.ModelAdmin):
    list_display = [
        "instrument",
        "patient",
        "status",
        "due_date",
        "total_score",
        "completed_at",
    ]
    list_filter = ["status", "instrument"]
    raw_id_fields = ["patient"]
    inlines = [SurveyAnswerInline]
    readonly_fields = ["id"]
