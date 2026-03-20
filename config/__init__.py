"""
Clintela - AI-powered post-surgical patient recovery support
"""

__version__ = "0.1.0"

# Import Celery app so it's available when Django starts
from .celery import app as celery_app

__all__ = ("celery_app",)
