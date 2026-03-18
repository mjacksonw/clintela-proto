"""
Settings module selector for Django.

Usage:
    DJANGO_SETTINGS_MODULE=config.settings.development
    DJANGO_SETTINGS_MODULE=config.settings.production
    DJANGO_SETTINGS_MODULE=config.settings.test
"""

import os

# Default to development settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
