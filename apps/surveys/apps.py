from django.apps import AppConfig


class SurveysConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.surveys"
    verbose_name = "Surveys & ePROs"

    def ready(self):
        # Import instruments to trigger @register decorators
        # Connect pathway auto-assignment signal
        from django.db.models.signals import post_save

        import apps.surveys.instruments.afeqt  # noqa: F401
        import apps.surveys.instruments.daily_symptom  # noqa: F401
        import apps.surveys.instruments.kccq_12  # noqa: F401
        import apps.surveys.instruments.phq_2  # noqa: F401
        import apps.surveys.instruments.promis  # noqa: F401
        import apps.surveys.instruments.saq_7  # noqa: F401
        from apps.surveys.signals import on_patient_pathway_created

        post_save.connect(
            on_patient_pathway_created,
            sender="pathways.PatientPathway",
            dispatch_uid="surveys_pathway_auto_assign",
        )
