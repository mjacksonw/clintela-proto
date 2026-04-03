"""
URL configuration for Clintela project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from django.views.generic import TemplateView
from ninja import NinjaAPI

# Import API routers
from apps.accounts.views_dev import demo_login_view, protected_gate_view
from apps.agents.api import router as agents_router
from apps.clinical.api import router as health_router
from apps.notifications.api import router as devices_router

api = NinjaAPI(version="1.0.0")
api.add_router("/agents/", agents_router)
api.add_router("/v1/devices/", devices_router)
api.add_router("/v1/health/", health_router)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", TemplateView.as_view(template_name="home.html"), name="home"),
    path("api/", api.urls),  # Django Ninja API
    path("accounts/", include("apps.accounts.urls", namespace="accounts")),
    path("patient/", include("apps.patients.urls", namespace="patients")),
    path("", include("apps.messages_app.urls", namespace="messages")),
    path("clinician/", include("apps.clinicians.urls", namespace="clinicians")),
    path("patient/surveys/", include("apps.surveys.urls", namespace="surveys")),
    path("admin-dashboard/", include("apps.administrators.urls", namespace="administrators")),
    path("clinical/", include("apps.clinical.urls", namespace="clinical")),
    path("i18n/", include("django.conf.urls.i18n")),
    # path("caregivers/", include("apps.caregivers.urls")),
    # Universal Links (iOS) + App Links (Android) for deep linking
    path(
        ".well-known/apple-app-site-association",
        lambda r: JsonResponse(
            {
                "applinks": {
                    "apps": [],
                    "details": [
                        {
                            "appID": settings.APPLE_APP_ID,
                            "paths": ["/patient/*", "/api/v1/*"],
                        }
                    ],
                },
                "webcredentials": {"apps": [settings.APPLE_APP_ID]},
            },
            content_type="application/json",
        ),
        name="apple_app_site_association",
    ),
    path(
        ".well-known/assetlinks.json",
        lambda r: JsonResponse(
            [
                {
                    "relation": ["delegate_permission/common.handle_all_urls"],
                    "target": {
                        "namespace": "android_app",
                        "package_name": settings.ANDROID_PACKAGE_NAME,
                        "sha256_cert_fingerprints": settings.ANDROID_CERT_FINGERPRINTS,
                    },
                }
            ],
            safe=False,
            content_type="application/json",
        ),
        name="android_asset_links",
    ),
]

# Demo login — always registered; view-level guard returns 404 when not DEBUG
urlpatterns += [path("demo-login/", demo_login_view, name="demo_login")]

# Protected environment gate — only registered when PROTECTED=True
if settings.PROTECTED:
    urlpatterns += [
        path(
            f"auth/{settings.PROTECTED_GATE_PATH}/",
            protected_gate_view,
            name="protected_gate",
        )
    ]

# Serve static and media files in development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Debug toolbar
if settings.DEBUG and "debug_toolbar" in settings.INSTALLED_APPS:
    urlpatterns.insert(0, path("__debug__/", include("debug_toolbar.urls")))
